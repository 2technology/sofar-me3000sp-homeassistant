"""Clock-quarter peak tracking for the capacity tariff (Fluvius).

Standalone module without Home Assistant imports so the maths can be
unit-tested in isolation (see tests/test_quarter_tracker.py).
"""

from __future__ import annotations

import datetime as dt

from .const import QUARTER_SECONDS


def _set_hold(store: dict, name: str | None, start: float | None, duration: int) -> None:
    """Record which hold timer is active so sensors can show the countdown."""
    store["active_hold"] = name
    store["active_hold_start"] = start
    store["active_hold_duration"] = duration


def _fmt_mmss(seconds: float) -> str:
    """Format seconds as m:ss for human-readable reasons."""
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _update_quarter_tracker(store: dict, import_w: float, now_ts: float, peak_threshold: float) -> None:
    """Track the clock-aligned quarter-hour import average (capaciteitstarief).

    Fluvius bills on the highest average import power per clock quarter
    (:00/:15/:30/:45) of the month. This integrates import power
    time-weighted within the current quarter and, on each quarter
    boundary, closes the quarter and updates the monthly peak.

    Written to the store (single source of truth for sensors):
      q_start, q_energy_ws, q_observed_s   — internal accumulator state
      q_elapsed_s, q_remaining_s           — position within the quarter
      q_avg_w                              — time-weighted average so far
      q_projected_w                        — average if current power holds
      q_budget_w                           — max sustainable import for the
                                             rest of the quarter without
                                             breaching the threshold
      last_quarter_avg_w                   — average of last closed quarter
      monthly_peak_w / monthly_peak_ts / peak_month
    """
    q_start = int(now_ts // QUARTER_SECONDS) * QUARTER_SECONDS
    last_ts = store.get("q_last_ts")
    last_w = store.get("q_last_w", 0.0)
    cur_start = store.get("q_start")

    if cur_start is None or last_ts is None:
        # First run (or after restart): start mid-quarter with what we have.
        store["q_start"] = q_start
        store["q_energy_ws"] = 0.0
        store["q_observed_s"] = 0.0
    elif q_start != cur_start:
        # Quarter boundary crossed: integrate the tail of the old quarter.
        boundary = cur_start + QUARTER_SECONDS
        tail = max(0.0, min(boundary, now_ts) - last_ts)
        store["q_energy_ws"] += last_w * tail
        store["q_observed_s"] += tail

        # Close the old quarter. Unobserved time counts as 0 W, so a
        # partially observed quarter can only *under*estimate — it can
        # never inflate the monthly peak.
        q_avg = store["q_energy_ws"] / QUARTER_SECONDS
        store["last_quarter_avg_w"] = round(q_avg)

        month = dt.datetime.fromtimestamp(cur_start).strftime("%Y-%m")
        if store.get("peak_month") != month:
            store["peak_month"] = month
            store["monthly_peak_w"] = 0
            store["monthly_peak_ts"] = None
        if q_avg > store.get("monthly_peak_w", 0):
            store["monthly_peak_w"] = round(q_avg)
            store["monthly_peak_ts"] = dt.datetime.fromtimestamp(cur_start).isoformat()

        # Start the new quarter; integrate the head since the boundary.
        # (If HA was down for multiple quarters, the skipped quarters are
        # simply not recorded — we never fabricate data for them.)
        store["q_start"] = q_start
        head = max(0.0, now_ts - max(q_start, last_ts))
        store["q_energy_ws"] = last_w * head
        store["q_observed_s"] = head
    else:
        step = max(0.0, now_ts - last_ts)
        store["q_energy_ws"] += last_w * step
        store["q_observed_s"] += step

    store["q_last_ts"] = now_ts
    store["q_last_w"] = import_w

    elapsed = max(0.0, now_ts - store["q_start"])
    remaining = max(0.0, QUARTER_SECONDS - elapsed)
    energy = store["q_energy_ws"]

    store["q_elapsed_s"] = round(elapsed)
    store["q_remaining_s"] = round(remaining)
    store["q_avg_w"] = round(energy / elapsed) if elapsed >= 1 else round(import_w)
    store["q_projected_w"] = round((energy + import_w * remaining) / QUARTER_SECONDS)

    budget_energy = peak_threshold * QUARTER_SECONDS - energy
    if remaining >= 5:
        store["q_budget_w"] = round(min(budget_energy / remaining, 99999))
    else:
        # Quarter is effectively over; budget is meaningless this close
        # to the boundary. Report the threshold itself.
        store["q_budget_w"] = round(peak_threshold)


