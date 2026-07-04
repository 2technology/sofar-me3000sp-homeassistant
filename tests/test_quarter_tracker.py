"""Unit tests for the clock-quarter peak tracker.

The tracker must reproduce what a Fluvius-style meter registers:
time-weighted average import power per clock-aligned quarter
(:00 / :15 / :30 / :45), with a monthly peak over closed quarters.

All expected values below are derived analytically — never from the
implementation itself.
"""

from __future__ import annotations

import datetime as dt
import sys

# Import the tracker without pulling in Home Assistant: quarter.py only
# depends on const.QUARTER_SECONDS, so a stub const module suffices.
import types
from pathlib import Path

_COMPONENT = Path(__file__).parent.parent / "custom_components" / "sofar_me3000sp"

_pkg = types.ModuleType("sofar_me3000sp")
_pkg.__path__ = [str(_COMPONENT)]
sys.modules["sofar_me3000sp"] = _pkg
_const = types.ModuleType("sofar_me3000sp.const")
_const.QUARTER_SECONDS = 900
sys.modules["sofar_me3000sp.const"] = _const

_src = (_COMPONENT / "quarter.py").read_text()
_mod = types.ModuleType("sofar_me3000sp.quarter")
_mod.__dict__["dt"] = dt
_mod.__dict__["QUARTER_SECONDS"] = 900
exec(compile(_src.replace("from .const import QUARTER_SECONDS", ""), "quarter.py", "exec"), _mod.__dict__)

tracker = _mod._update_quarter_tracker
fmt_mmss = _mod._fmt_mmss

THRESHOLD = 2500
T0 = dt.datetime(2026, 7, 3, 10, 0, 0).timestamp()  # exactly on a quarter boundary


def test_constant_power_full_quarter() -> None:
    """Constant 2000 W with irregular sampling → avg and projection = 2000 W."""
    store: dict = {}
    for t in (0, 7, 20, 61, 200, 455, 850, 899.9):
        tracker(store, 2000.0, T0 + t, THRESHOLD)
    assert abs(store["q_avg_w"] - 2000) <= 1
    assert abs(store["q_projected_w"] - 2000) <= 1


def test_quarter_close_updates_monthly_peak() -> None:
    """Crossing the boundary closes the quarter and records the monthly peak."""
    store: dict = {}
    for t in (0, 7, 20, 61, 200, 455, 850, 899.9):
        tracker(store, 2000.0, T0 + t, THRESHOLD)
    tracker(store, 500.0, T0 + 905, THRESHOLD)
    assert store["last_quarter_avg_w"] == 2000
    assert store["monthly_peak_w"] == 2000
    assert store["peak_month"] == "2026-07"


def test_time_weighted_average() -> None:
    """450 s @ 3000 W + 450 s @ 1000 W → exactly 2000 W, regardless of sample count."""
    store: dict = {}
    tracker(store, 3000.0, T0, THRESHOLD)
    tracker(store, 3000.0, T0 + 450, THRESHOLD)
    tracker(store, 1000.0, T0 + 450, THRESHOLD)
    tracker(store, 1000.0, T0 + 900, THRESHOLD)
    assert store["last_quarter_avg_w"] == 2000


def test_spike_immunity() -> None:
    """A 60 s spike of 8000 W in an otherwise 1000 W quarter stays under threshold.

    Analytical projection: (400*1000 + 60*8000 + 439*1000 + 1*1000) / 900 ≈ 1467 W.
    Instantaneous control would have panicked; projection control must not.
    """
    store: dict = {}
    tq = T0 + 1800
    tracker(store, 1000.0, tq, THRESHOLD)
    tracker(store, 8000.0, tq + 400, THRESHOLD)
    tracker(store, 1000.0, tq + 460, THRESHOLD)
    tracker(store, 1000.0, tq + 899, THRESHOLD)
    assert store["q_projected_w"] < THRESHOLD


def test_creeping_overrun_budget() -> None:
    """Constant 2600 W: after 300 s the required discharge is 150 W, not 100 W.

    E(300 s @ 2600) = 780 kWs; budget = (2250 kWs − 780 kWs) / 600 s = 2450 W;
    needed = 2600 − 2450 = 150 W — the extra 50 W compensates the overshoot
    already accumulated. This is why projection control beats instantaneous.
    """
    store: dict = {}
    tq = T0 + 1800
    tracker(store, 2600.0, tq, THRESHOLD)
    tracker(store, 2600.0, tq + 300, THRESHOLD)
    assert store["q_projected_w"] > THRESHOLD
    needed = 2600 - store["q_budget_w"]
    assert abs(needed - 150) < 2


def test_month_rollover() -> None:
    """A quarter starting in July counts for July; August starts at zero.

    The August quarter's 403 W is analytically correct: 1 s of 3000 W head
    spill + 899 s of 400 W → (3000 + 359600) / 900 ≈ 402.9 W.
    """
    store: dict = {}
    t_end_july = dt.datetime(2026, 7, 31, 23, 45, 0).timestamp()
    tracker(store, 3000.0, t_end_july, THRESHOLD)
    tracker(store, 3000.0, t_end_july + 899, THRESHOLD)
    tracker(store, 400.0, t_end_july + 901, THRESHOLD)
    assert store["peak_month"] == "2026-07"
    assert store["monthly_peak_w"] == 3000

    t_aug = dt.datetime(2026, 8, 1, 0, 15, 0).timestamp()
    tracker(store, 400.0, t_aug - 1, THRESHOLD)
    tracker(store, 400.0, t_aug + 1, THRESHOLD)
    assert store["peak_month"] == "2026-08"
    assert store["monthly_peak_w"] == 403


def test_partial_quarter_never_inflates() -> None:
    """A quarter observed only partially (restart) can underestimate, never inflate."""
    store: dict = {}
    tmid = T0 + 3600 + 600  # tracker starts 10 min into a quarter
    tracker(store, 5000.0, tmid, THRESHOLD)
    tracker(store, 5000.0, tmid + 299, THRESHOLD)
    tracker(store, 5000.0, tmid + 301, THRESHOLD)
    # ~300 s observed @ 5000 W → 300*5000/900 ≈ 1667 W, well under the real 5000 W
    assert store["last_quarter_avg_w"] < 1700


def test_fmt_mmss() -> None:
    assert fmt_mmss(0) == "0:00"
    assert fmt_mmss(59) == "0:59"
    assert fmt_mmss(60) == "1:00"
    assert fmt_mmss(899) == "14:59"
    assert fmt_mmss(-5) == "0:00"
