"""SOFAR ME3000SP Controller — Home Assistant custom integration.

Provides template sensors, binary sensors, number helpers, and internal
automation logic for controlling a SOFAR ME3000SP inverter via ESPHome,
using external smart meter + PV data as the truth source.

The automation loop is the single source of truth for all decisions.
It writes its state (decision_reason, hold timers, quarter tracker,
monthly peak) into the per-entry store and broadcasts a dispatcher
signal; sensors only *report* that state, never re-derive it.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    STATE_OK,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval

from .const import (
    BALANCE_HOLD_SECONDS,
    CHARGE_HOLD_SECONDS,
    CONF_EXPORT_ENTITY,
    CONF_IMPORT_ENTITY,
    CONF_PV_ENTITY,
    CONF_SOFAR_CHARGE_RATE_ENTITY,
    CONF_SOFAR_DISCHARGE_RATE_ENTITY,
    CONF_SOFAR_FAULT_ENTITY,
    CONF_SOFAR_MODE_ENTITY,
    CONF_SOFAR_SOC_ENTITY,
    DEFAULT_BALANCE_W,
    DEFAULT_CHARGE_MARGIN_W,
    DEFAULT_DISCHARGE_MARGIN_W,
    DEFAULT_EXPORT_START_W,
    DEFAULT_FORCE_CHARGE_RATE,
    DEFAULT_IMPORT_START_W,
    DEFAULT_MAX_RATE,
    DEFAULT_NIGHT_END_HOUR,
    DEFAULT_NIGHT_START_HOUR,
    DEFAULT_PEAK_THRESHOLD_W,
    DEFAULT_PV_MIN_W,
    DEFAULT_SOC_FORCE_CHARGE,
    DEFAULT_SOC_FORCE_CHARGE_TARGET,
    DEFAULT_SOC_MAX_CHARGE,
    DEFAULT_SOC_MIN_DISCHARGE,
    DISCHARGE_HOLD_SECONDS,
    DOMAIN,
    FORCE_CHARGE_TIMEOUT,
    MODE_AUTO,
    MODE_CHARGE,
    MODE_DISCHARGE,
    MODE_STANDBY,
    NUMBER_BALANCE_W,
    NUMBER_CHARGE_MARGIN_W,
    NUMBER_DISCHARGE_MARGIN_W,
    NUMBER_EXPORT_START_W,
    NUMBER_FORCE_CHARGE_RATE,
    NUMBER_IMPORT_START_W,
    NUMBER_NIGHT_END_HOUR,
    NUMBER_NIGHT_START_HOUR,
    NUMBER_PEAK_THRESHOLD_W,
    NUMBER_PV_MIN_W,
    NUMBER_SOC_FORCE_CHARGE,
    NUMBER_SOC_FORCE_CHARGE_TARGET,
    NUMBER_SOC_MAX_CHARGE,
    NUMBER_SOC_MIN_DISCHARGE,
    RATE_CHANGE_THRESHOLD_W,
    RATE_UPDATE_MIN_INTERVAL,
    SIGNAL_UPDATE,
    SMOOTHING_WINDOW_SECONDS,
    STRATEGY_AUTO,
    STRATEGY_FORCE_CHARGE,
    STRATEGY_FORCE_DISCHARGE,
    STRATEGY_NIGHT_SAVE,
    STRATEGY_PEAK_SHAVING,
    STRATEGY_SELF_CONSUMPTION,
)
from .number import _get_number_helper
from .quarter import _fmt_mmss, _set_hold, _update_quarter_tracker

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SELECT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SOFAR ME3000SP Controller from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    entry_data = dict(entry.data)
    hass.data[DOMAIN][entry.entry_id] = {
        "entry_data": entry_data,
        "charge_hold_start": None,
        "discharge_hold_start": None,
        "balance_hold_start": None,
        "active_hold": None,
        "active_hold_start": None,
        "active_hold_duration": 0,
        "force_charge_active": False,
        "force_charge_start": None,
        "last_charge_rate_update": 0,
        "last_discharge_rate_update": 0,
        "last_charge_rate": 0,
        "last_discharge_rate": 0,
        "surplus_history": [],
        "deficit_history": [],
        "unsubs": [],
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services once, at domain level (multi-entry safe)
    await _async_register_services(hass)

    # Start automation logic after HA is fully started
    async def _start_automation(_event=None):
        _LOGGER.info("SOFAR ME3000SP automation started")
        await _setup_automation(hass, entry)

    if hass.is_running:
        await _start_automation()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _start_automation)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Stop automation listeners first so no runs happen mid-unload
    store = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    for unsub in store.get("unsubs", []):
        unsub()
    store["unsubs"] = []

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # Only remove services if no other entries remain
        remaining = hass.data.get(DOMAIN, {})
        if not remaining:
            for service in ("set_mode", "set_charge_rate", "set_discharge_rate"):
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)
    return unload_ok


def _get_strategy(hass: HomeAssistant, entry_id: str) -> str:
    """Get the current strategy from the store."""
    store = hass.data.get(DOMAIN, {}).get(entry_id, {})
    return store.get("strategy", STRATEGY_SELF_CONSUMPTION)


def _is_night_time(now: float, night_start: int, night_end: int) -> bool:
    """Check if current time is within night-save hours."""
    current = dt.datetime.fromtimestamp(now)
    hour = current.hour
    if night_start > night_end:
        # Spans midnight (e.g. 22:00 - 06:00)
        return hour >= night_start or hour < night_end
    return night_start <= hour < night_end


def _smooth_value(store: dict, key: str, value: float, now: float) -> float:
    """Return a moving average over the last SMOOTHING_WINDOW_SECONDS."""
    history = store.setdefault(key, [])
    history.append((now, value))
    cutoff = now - SMOOTHING_WINDOW_SECONDS
    store[key] = [(t, v) for t, v in history if t >= cutoff]
    if not store[key]:
        return value
    return sum(v for _, v in store[key]) / len(store[key])


def _should_update_rate(store: dict, rate_key: str, update_key: str, new_rate: int, now: float) -> bool:
    """Check if we should update the rate (throttle + minimum change).

    Charge and discharge each use their own update timestamp so one
    direction never blocks the other.
    """
    last_update = store.get(update_key, 0)
    last_rate = store.get(rate_key, 0)
    if now - last_update < RATE_UPDATE_MIN_INTERVAL:
        return False
    return abs(new_rate - last_rate) >= RATE_CHANGE_THRESHOLD_W


def _get_entity_state(hass: HomeAssistant, entity_id: str, default=0.0):
    """Get numeric state of an entity, returning default if unavailable."""
    state = hass.states.get(entity_id)
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return default
    try:
        return float(state.state)
    except (ValueError, TypeError):
        return default


def _get_entity_str(hass: HomeAssistant, entity_id: str, default=""):
    """Get string state of an entity."""
    state = hass.states.get(entity_id)
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return default
    return str(state.state)


async def _setup_automation(hass: HomeAssistant, entry: ConfigEntry):
    """Set up internal automation logic using state change listeners."""
    data = entry.data
    export_entity = data[CONF_EXPORT_ENTITY]
    import_entity = data[CONF_IMPORT_ENTITY]
    pv_entity = data[CONF_PV_ENTITY]
    soc_entity = data[CONF_SOFAR_SOC_ENTITY]
    fault_entity = data[CONF_SOFAR_FAULT_ENTITY]

    tracked = [export_entity, import_entity, pv_entity, soc_entity, fault_entity]
    store = hass.data[DOMAIN][entry.entry_id]

    async def _on_state_change(event):
        """Handle state changes and run automation logic."""
        await _run_automation(hass, entry, store)

    async def _periodic_check(_now):
        """Also run periodically as a safety net."""
        await _run_automation(hass, entry, store)

    # Keep the unsubscribe handles so async_unload_entry can stop us;
    # without this a reload leaves a second automation loop running.
    store["unsubs"].append(async_track_state_change_event(hass, tracked, _on_state_change))
    store["unsubs"].append(async_track_time_interval(hass, _periodic_check, timedelta(seconds=60)))

    _LOGGER.info("SOFAR ME3000SP automation listeners registered for: %s", tracked)


async def _run_automation(hass: HomeAssistant, entry: ConfigEntry, store: dict):
    """Run the automation logic based on the selected strategy."""
    data = entry.data
    now = time.monotonic()
    now_ts = time.time()

    export_w = _get_entity_state(hass, data[CONF_EXPORT_ENTITY]) * 1000  # kW → W
    import_w = _get_entity_state(hass, data[CONF_IMPORT_ENTITY]) * 1000
    pv_w = _get_entity_state(hass, data[CONF_PV_ENTITY])
    soc = _get_entity_state(hass, data[CONF_SOFAR_SOC_ENTITY])
    fault = _get_entity_str(hass, data[CONF_SOFAR_FAULT_ENTITY])
    current_mode = _get_entity_str(hass, data[CONF_SOFAR_MODE_ENTITY])

    net_w = export_w - import_w
    surplus_w = max(0, net_w)
    deficit_w = max(0, -net_w)

    # Keep the smoothing histories warm on every run so the moving
    # average is meaningful the moment a hold period expires.
    smooth_surplus = _smooth_value(store, "surplus_history", surplus_w, now)
    smooth_deficit = _smooth_value(store, "deficit_history", deficit_w, now)

    # Read tunable thresholds
    export_start = _get_number_helper(hass, entry.entry_id, NUMBER_EXPORT_START_W, DEFAULT_EXPORT_START_W)
    import_start = _get_number_helper(hass, entry.entry_id, NUMBER_IMPORT_START_W, DEFAULT_IMPORT_START_W)
    pv_min = _get_number_helper(hass, entry.entry_id, NUMBER_PV_MIN_W, DEFAULT_PV_MIN_W)
    balance_w = _get_number_helper(hass, entry.entry_id, NUMBER_BALANCE_W, DEFAULT_BALANCE_W)
    charge_margin = _get_number_helper(hass, entry.entry_id, NUMBER_CHARGE_MARGIN_W, DEFAULT_CHARGE_MARGIN_W)
    discharge_margin = _get_number_helper(hass, entry.entry_id, NUMBER_DISCHARGE_MARGIN_W, DEFAULT_DISCHARGE_MARGIN_W)
    soc_max_charge = _get_number_helper(hass, entry.entry_id, NUMBER_SOC_MAX_CHARGE, DEFAULT_SOC_MAX_CHARGE)
    soc_min_discharge = _get_number_helper(hass, entry.entry_id, NUMBER_SOC_MIN_DISCHARGE, DEFAULT_SOC_MIN_DISCHARGE)
    soc_force_charge = _get_number_helper(hass, entry.entry_id, NUMBER_SOC_FORCE_CHARGE, DEFAULT_SOC_FORCE_CHARGE)
    soc_force_charge_target = _get_number_helper(hass, entry.entry_id, NUMBER_SOC_FORCE_CHARGE_TARGET, DEFAULT_SOC_FORCE_CHARGE_TARGET)
    force_charge_rate = _get_number_helper(hass, entry.entry_id, NUMBER_FORCE_CHARGE_RATE, DEFAULT_FORCE_CHARGE_RATE)
    peak_threshold = _get_number_helper(hass, entry.entry_id, NUMBER_PEAK_THRESHOLD_W, DEFAULT_PEAK_THRESHOLD_W)
    night_start = int(_get_number_helper(hass, entry.entry_id, NUMBER_NIGHT_START_HOUR, DEFAULT_NIGHT_START_HOUR))
    night_end = int(_get_number_helper(hass, entry.entry_id, NUMBER_NIGHT_END_HOUR, DEFAULT_NIGHT_END_HOUR))

    # Update the quarter-hour tracker on EVERY run, independent of the
    # strategy — the sensors and monthly peak must always be correct.
    _update_quarter_tracker(store, import_w, now_ts, peak_threshold)

    try:
        await _decide(
            hass, data, store, now, now_ts,
            export_w=export_w, import_w=import_w, pv_w=pv_w, soc=soc,
            fault=fault, current_mode=current_mode,
            net_w=net_w, surplus_w=surplus_w, deficit_w=deficit_w,
            smooth_surplus=smooth_surplus, smooth_deficit=smooth_deficit,
            export_start=export_start, import_start=import_start, pv_min=pv_min,
            balance_w=balance_w, charge_margin=charge_margin, discharge_margin=discharge_margin,
            soc_max_charge=soc_max_charge, soc_min_discharge=soc_min_discharge,
            soc_force_charge=soc_force_charge, soc_force_charge_target=soc_force_charge_target,
            force_charge_rate=force_charge_rate, peak_threshold=peak_threshold,
            night_start=night_start, night_end=night_end,
        )
    finally:
        # Tell the reporting sensors that fresh state is available,
        # even if the decision path raised.
        async_dispatcher_send(hass, f"{SIGNAL_UPDATE}_{entry.entry_id}")


async def _decide(hass, data, store, now, now_ts, *, export_w, import_w, pv_w, soc,
                  fault, current_mode, net_w, surplus_w, deficit_w,
                  smooth_surplus, smooth_deficit, export_start, import_start,
                  pv_min, balance_w, charge_margin, discharge_margin,
                  soc_max_charge, soc_min_discharge, soc_force_charge,
                  soc_force_charge_target, force_charge_rate, peak_threshold,
                  night_start, night_end):
    """The actual decision tree. Every exit sets an honest decision_reason."""
    strategy = store.get("strategy", STRATEGY_SELF_CONSUMPTION)

    # --- ALARM: always force standby regardless of strategy ---
    if fault.lower() not in (STATE_OK, STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
        if current_mode != MODE_STANDBY:
            await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_STANDBY)
        _set_hold(store, None, None, 0)
        store["decision_reason"] = f"Alarm: {fault} → standby"
        return

    # --- FORCE CHARGE: critical low SOC (always, regardless of strategy) ---
    if soc < soc_force_charge:
        if not store.get("force_charge_active"):
            store["force_charge_active"] = True
            store["force_charge_start"] = now
            await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_CHARGE)
            await _set_number(hass, data[CONF_SOFAR_CHARGE_RATE_ENTITY], int(force_charge_rate))
            store["decision_reason"] = f"Force charge: SOC {soc:.0f}% < {soc_force_charge:.0f}% → charge @ {force_charge_rate:.0f}W"
        else:
            elapsed = now - store.get("force_charge_start", now)
            if soc >= soc_force_charge_target:
                store["force_charge_active"] = False
                await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_AUTO)
                store["decision_reason"] = f"Force charge done: SOC {soc:.0f}% >= {soc_force_charge_target:.0f}% → auto"
            elif elapsed > FORCE_CHARGE_TIMEOUT:
                store["force_charge_active"] = False
                await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_AUTO)
                store["decision_reason"] = "Force charge timeout → auto"
            else:
                store["decision_reason"] = (
                    f"Force charge in progress: SOC {soc:.0f}% → target {soc_force_charge_target:.0f}% "
                    f"({_fmt_mmss(FORCE_CHARGE_TIMEOUT - elapsed)} until timeout)"
                )
        return
    if store.get("force_charge_active"):
        store["force_charge_active"] = False

    # === STRATEGY DISPATCH ===

    if strategy == STRATEGY_AUTO:
        if current_mode != MODE_AUTO:
            await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_AUTO)
        _set_hold(store, None, None, 0)
        store["decision_reason"] = "Auto: SOFAR decides on its own"
        return

    if strategy == STRATEGY_FORCE_CHARGE:
        if current_mode != MODE_CHARGE:
            await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_CHARGE)
        rate = int(force_charge_rate)
        if _should_update_rate(store, "last_charge_rate", "last_charge_rate_update", rate, now):
            await _set_number(hass, data[CONF_SOFAR_CHARGE_RATE_ENTITY], rate)
            store["last_charge_rate_update"] = now
            store["last_charge_rate"] = rate
        _set_hold(store, None, None, 0)
        store["decision_reason"] = f"Force charge: charge @ {rate}W (manual override)"
        return

    if strategy == STRATEGY_FORCE_DISCHARGE:
        if soc > soc_min_discharge:
            if current_mode != MODE_DISCHARGE:
                await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_DISCHARGE)
            discharge_w = min(int(deficit_w + discharge_margin) if deficit_w > 0 else 1000, DEFAULT_MAX_RATE)
            if _should_update_rate(store, "last_discharge_rate", "last_discharge_rate_update", discharge_w, now):
                await _set_number(hass, data[CONF_SOFAR_DISCHARGE_RATE_ENTITY], discharge_w)
                store["last_discharge_rate_update"] = now
                store["last_discharge_rate"] = discharge_w
            store["decision_reason"] = f"Force discharge: discharge @ {store['last_discharge_rate']}W (manual override)"
        else:
            store["decision_reason"] = f"Force discharge: SOC {soc:.0f}% <= min {soc_min_discharge:.0f}% → not discharging"
        _set_hold(store, None, None, 0)
        return

    # === PEAK-SHAVING STRATEGY (optimized) ===
    # Controls the *projected clock-quarter average* — what Fluvius bills.
    # Three zones:
    #   1. RED: projection > threshold → active discharge to flatten the quarter
    #   2. YELLOW: projection > 90% of threshold → pre-emptive gentle discharge
    #   3. GREEN: no risk → charge on surplus, or recovery charge, or auto
    if strategy == STRATEGY_PEAK_SHAVING:
        projected = store.get("q_projected_w", 0)
        budget = store.get("q_budget_w", peak_threshold)
        remaining = store.get("q_remaining_s", 0)
        pre_emptive_threshold = int(peak_threshold * 0.9)

        # --- ZONE 1: RED — projection exceeds threshold ---
        if projected > peak_threshold:
            if soc > soc_min_discharge:
                # Calculate exactly how much discharge is needed to bring
                # the quarter average down to the threshold.
                # Target: (energy + (import_w - discharge_w) * remaining) / 900 <= threshold
                # → discharge_w >= import_w - (threshold * 900 - energy) / remaining
                # Quarter almost over: cover the overshoot directly instead of budget-based
                needed = max(0, int(import_w - budget)) if remaining >= 5 else max(0, int(import_w - peak_threshold))
                discharge_w = min(needed + int(discharge_margin), DEFAULT_MAX_RATE)
                if discharge_w > 0:
                    if current_mode != MODE_DISCHARGE:
                        await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_DISCHARGE)
                    if _should_update_rate(store, "last_discharge_rate", "last_discharge_rate_update", discharge_w, now):
                        await _set_number(hass, data[CONF_SOFAR_DISCHARGE_RATE_ENTITY], discharge_w)
                        store["last_discharge_rate_update"] = now
                        store["last_discharge_rate"] = discharge_w
                    store["decision_reason"] = (
                        f"Peak shaving RED: projection {projected}W > {peak_threshold:.0f}W "
                        f"(quarter: {_fmt_mmss(remaining)} left, budget {budget}W) → discharge @ {store['last_discharge_rate']}W"
                    )
                    _set_hold(store, None, None, 0)
                    store["charge_hold_start"] = None
                    store["balance_hold_start"] = None
                    return
            else:
                store["decision_reason"] = (
                    f"Peak shaving RED: projection {projected}W > {peak_threshold:.0f}W "
                    f"but SOC {soc:.0f}% ≤ min {soc_min_discharge:.0f}% → cannot discharge"
                )
                _set_hold(store, None, None, 0)
                if current_mode not in (MODE_AUTO, MODE_STANDBY):
                    await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_AUTO)
                return

        # --- ZONE 2: YELLOW — pre-emptive (90-100% of threshold) ---
        # Start a gentle discharge to prevent the projection from reaching RED.
        # Only if SOC is healthy and the quarter is early enough to matter.
        if projected > pre_emptive_threshold and remaining > 60 and soc > soc_min_discharge:
            # Gentle discharge: cover just the excess above 90% of threshold
            pre_emptive_needed = max(0, int(import_w - budget * 0.9))
            discharge_w = min(pre_emptive_needed, DEFAULT_MAX_RATE)
            if discharge_w > 0:
                if current_mode != MODE_DISCHARGE:
                    await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_DISCHARGE)
                if _should_update_rate(store, "last_discharge_rate", "last_discharge_rate_update", discharge_w, now):
                    await _set_number(hass, data[CONF_SOFAR_DISCHARGE_RATE_ENTITY], discharge_w)
                    store["last_discharge_rate_update"] = now
                    store["last_discharge_rate"] = discharge_w
                store["decision_reason"] = (
                    f"Peak shaving YELLOW: projection {projected}W approaching {peak_threshold:.0f}W "
                    f"(90% = {pre_emptive_threshold}W, quarter: {_fmt_mmss(remaining)} left) → pre-emptive discharge @ {store['last_discharge_rate']}W"
                )
                _set_hold(store, None, None, 0)
                store["charge_hold_start"] = None
                store["balance_hold_start"] = None
                return

        # --- ZONE 3: GREEN — no peak risk ---
        # Priority: (a) charge on PV surplus, (b) recovery charge if SOC low, (c) auto

        # (a) Charge on PV surplus (with hold)
        if surplus_w > export_start and pv_w > pv_min and soc < soc_max_charge:
            if store.get("charge_hold_start") is None:
                store["charge_hold_start"] = now
                _set_hold(store, "charge", now, CHARGE_HOLD_SECONDS)
                store["decision_reason"] = f"Peak shaving charge pending: surplus {surplus_w:.0f}W > {export_start:.0f}W (hold {_fmt_mmss(CHARGE_HOLD_SECONDS)})"
            elif now - store["charge_hold_start"] >= CHARGE_HOLD_SECONDS:
                charge_w = min(max(0, int(smooth_surplus - charge_margin)), DEFAULT_MAX_RATE)
                if charge_w > 0:
                    if current_mode != MODE_CHARGE:
                        await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_CHARGE)
                    if _should_update_rate(store, "last_charge_rate", "last_charge_rate_update", charge_w, now):
                        await _set_number(hass, data[CONF_SOFAR_CHARGE_RATE_ENTITY], charge_w)
                        store["last_charge_rate_update"] = now
                        store["last_charge_rate"] = charge_w
                    store["decision_reason"] = f"Peak shaving charge: surplus {surplus_w:.0f}W (avg {smooth_surplus:.0f}W) → charge @ {store['last_charge_rate']}W"
                    _set_hold(store, None, None, 0)
                    store["discharge_hold_start"] = None
                    store["balance_hold_start"] = None
            else:
                store["decision_reason"] = (
                    f"Peak shaving charge pending: {_fmt_mmss(CHARGE_HOLD_SECONDS - (now - store['charge_hold_start']))} left"
                )
            return

        # (b) Recovery charge: after a peak discharge, SOC is low and no surplus.
        # Charge from grid to be ready for the next peak. Only if SOC is below
        # a recovery threshold (e.g. 60%) and we're not in a peak-risk quarter.
        recovery_soc = min(soc_max_charge, 60)
        if soc < recovery_soc and projected < pre_emptive_threshold:
            if store.get("charge_hold_start") is None:
                store["charge_hold_start"] = now
                _set_hold(store, "charge", now, CHARGE_HOLD_SECONDS)
                store["decision_reason"] = f"Peak shaving recovery charge pending: SOC {soc:.0f}% < {recovery_soc:.0f}% (hold {_fmt_mmss(CHARGE_HOLD_SECONDS)})"
            elif now - store["charge_hold_start"] >= CHARGE_HOLD_SECONDS:
                # Charge at a moderate rate from the grid
                recovery_rate = min(1500, int(DEFAULT_MAX_RATE * 0.5))
                if current_mode != MODE_CHARGE:
                    await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_CHARGE)
                if _should_update_rate(store, "last_charge_rate", "last_charge_rate_update", recovery_rate, now):
                    await _set_number(hass, data[CONF_SOFAR_CHARGE_RATE_ENTITY], recovery_rate)
                    store["last_charge_rate_update"] = now
                    store["last_charge_rate"] = recovery_rate
                store["decision_reason"] = f"Peak shaving recovery: SOC {soc:.0f}% < {recovery_soc:.0f}% → charge @ {recovery_rate}W from grid"
                _set_hold(store, None, None, 0)
                store["discharge_hold_start"] = None
                store["balance_hold_start"] = None
            return

        # (c) No action needed
        store["charge_hold_start"] = None
        _set_hold(store, None, None, 0)
        if current_mode not in (MODE_AUTO, MODE_STANDBY):
            await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_AUTO)
        store["decision_reason"] = (
            f"Peak shaving GREEN: projection {projected}W ≤ {pre_emptive_threshold}W "
            f"(threshold {peak_threshold:.0f}W, quarter: {_fmt_mmss(remaining)} left, budget {budget}W) → auto"
        )
        return

    # === NIGHT-SAVE STRATEGY ===
    if strategy == STRATEGY_NIGHT_SAVE:
        is_night = _is_night_time(now_ts, night_start, night_end)

        if is_night:
            store["discharge_hold_start"] = None
            # Charging on surplus stays allowed (unlikely at night, but possible).
            if surplus_w > export_start and soc < soc_max_charge:
                if store.get("charge_hold_start") is None:
                    store["charge_hold_start"] = now
                    _set_hold(store, "charge", now, CHARGE_HOLD_SECONDS)
                    store["decision_reason"] = f"Night save charge pending: surplus {surplus_w:.0f}W (hold {_fmt_mmss(CHARGE_HOLD_SECONDS)})"
                elif now - store["charge_hold_start"] >= CHARGE_HOLD_SECONDS:
                    charge_w = min(max(0, int(smooth_surplus - charge_margin)), DEFAULT_MAX_RATE)
                    if charge_w > 0:
                        if current_mode != MODE_CHARGE:
                            await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_CHARGE)
                        if _should_update_rate(store, "last_charge_rate", "last_charge_rate_update", charge_w, now):
                            await _set_number(hass, data[CONF_SOFAR_CHARGE_RATE_ENTITY], charge_w)
                            store["last_charge_rate_update"] = now
                            store["last_charge_rate"] = charge_w
                        store["decision_reason"] = f"Night save charge: surplus {surplus_w:.0f}W → charge @ {store['last_charge_rate']}W"
                        _set_hold(store, None, None, 0)
                return
            store["charge_hold_start"] = None
            _set_hold(store, None, None, 0)
            # Standby, NOT auto: in auto the SOFAR discharges on its own at
            # night, which is exactly what this strategy must prevent.
            if current_mode != MODE_STANDBY:
                await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_STANDBY)
            store["decision_reason"] = f"Night save: preserving battery ({night_start:02d}:00–{night_end:02d}:00) → standby"
            return
        # During day: fall through to self-consumption logic.

    # === SELF-CONSUMPTION STRATEGY (default, also day-mode for night-save) ===
    # --- CHARGE: surplus export (smoothed + rate-limited) ---
    if surplus_w > export_start and pv_w > pv_min and soc < soc_max_charge:
        if store.get("charge_hold_start") is None:
            store["charge_hold_start"] = now
            _set_hold(store, "charge", now, CHARGE_HOLD_SECONDS)
            store["decision_reason"] = f"Charge pending: surplus {surplus_w:.0f}W > {export_start:.0f}W (hold {_fmt_mmss(CHARGE_HOLD_SECONDS)})"
        elif now - store["charge_hold_start"] >= CHARGE_HOLD_SECONDS:
            charge_w = min(max(0, int(smooth_surplus - charge_margin)), DEFAULT_MAX_RATE)
            if charge_w > 0:
                if current_mode != MODE_CHARGE:
                    await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_CHARGE)
                if _should_update_rate(store, "last_charge_rate", "last_charge_rate_update", charge_w, now):
                    await _set_number(hass, data[CONF_SOFAR_CHARGE_RATE_ENTITY], charge_w)
                    store["last_charge_rate_update"] = now
                    store["last_charge_rate"] = charge_w
                store["discharge_hold_start"] = None
                store["balance_hold_start"] = None
                _set_hold(store, None, None, 0)
                store["decision_reason"] = f"Self-consumption: surplus {surplus_w:.0f}W (avg {smooth_surplus:.0f}W) → charge @ {store['last_charge_rate']}W"
        else:
            store["decision_reason"] = f"Charge pending: {_fmt_mmss(CHARGE_HOLD_SECONDS - (now - store['charge_hold_start']))} left"
        return
    store["charge_hold_start"] = None

    # --- DISCHARGE: import deficit (smoothed + rate-limited) ---
    if import_w > import_start and deficit_w > 0 and soc > soc_min_discharge:
        if store.get("discharge_hold_start") is None:
            store["discharge_hold_start"] = now
            _set_hold(store, "discharge", now, DISCHARGE_HOLD_SECONDS)
            store["decision_reason"] = f"Discharge pending: import {import_w:.0f}W > {import_start:.0f}W (hold {_fmt_mmss(DISCHARGE_HOLD_SECONDS)})"
        elif now - store["discharge_hold_start"] >= DISCHARGE_HOLD_SECONDS:
            discharge_w = min(max(0, int(smooth_deficit + discharge_margin)), DEFAULT_MAX_RATE)
            if discharge_w > 0:
                if current_mode != MODE_DISCHARGE:
                    await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_DISCHARGE)
                if _should_update_rate(store, "last_discharge_rate", "last_discharge_rate_update", discharge_w, now):
                    await _set_number(hass, data[CONF_SOFAR_DISCHARGE_RATE_ENTITY], discharge_w)
                    store["last_discharge_rate_update"] = now
                    store["last_discharge_rate"] = discharge_w
                store["charge_hold_start"] = None
                store["balance_hold_start"] = None
                _set_hold(store, None, None, 0)
                store["decision_reason"] = f"Self-consumption: deficit {deficit_w:.0f}W (avg {smooth_deficit:.0f}W) → discharge @ {store['last_discharge_rate']}W"
        else:
            store["decision_reason"] = f"Discharge pending: {_fmt_mmss(DISCHARGE_HOLD_SECONDS - (now - store['discharge_hold_start']))} left"
        return
    store["discharge_hold_start"] = None

    # --- BALANCE: return to auto ---
    if abs(net_w) < balance_w:
        if store.get("balance_hold_start") is None:
            store["balance_hold_start"] = now
            _set_hold(store, "balance", now, BALANCE_HOLD_SECONDS)
            store["decision_reason"] = f"Balance pending: |net| {abs(net_w):.0f}W < {balance_w:.0f}W (hold {_fmt_mmss(BALANCE_HOLD_SECONDS)})"
        elif now - store["balance_hold_start"] >= BALANCE_HOLD_SECONDS:
            if current_mode not in (MODE_AUTO, MODE_STANDBY):
                await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_AUTO)
            store["charge_hold_start"] = None
            store["discharge_hold_start"] = None
            _set_hold(store, None, None, 0)
            store["decision_reason"] = f"Balance: |net| {abs(net_w):.0f}W < {balance_w:.0f}W → auto"
        else:
            store["decision_reason"] = f"Balance pending: {_fmt_mmss(BALANCE_HOLD_SECONDS - (now - store['balance_hold_start']))} left"
        return
    store["balance_hold_start"] = None
    _set_hold(store, None, None, 0)

    # --- CATCH-ALL: return to auto if in standby ---
    if current_mode == MODE_STANDBY and not store.get("force_charge_active"):
        await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_AUTO)
        store["decision_reason"] = f"Catch-all: standby → auto (SOC {soc:.0f}%, surplus {surplus_w:.0f}W)"
    else:
        store["decision_reason"] = f"No active rule: net {net_w:.0f}W, SOC {soc:.0f}%, mode {current_mode}"


async def _set_mode(hass: HomeAssistant, entity_id: str, mode: str):
    """Set the inverter mode via select entity."""
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": mode},
        blocking=False,
    )


async def _set_number(hass: HomeAssistant, entity_id: str, value: int):
    """Set a number entity value."""
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": float(value)},
        blocking=False,
    )


async def _async_register_services(hass: HomeAssistant):
    """Register manual-control services once, resolving the entry per call.

    With multiple config entries the optional config_entry_id field selects
    the target; with a single entry it can be omitted. (Pre-2.3.0 the
    services silently controlled whichever entry registered last.)
    """
    if hass.services.has_service(DOMAIN, "set_mode"):
        return

    def _resolve_entry_data(call) -> dict:
        entries = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id in hass.data.get(DOMAIN, {})
        ]
        entry_id = call.data.get("config_entry_id")
        if entry_id:
            for e in entries:
                if e.entry_id == entry_id:
                    return e.data
            raise ServiceValidationError(f"Unknown or unloaded config entry: {entry_id}")
        if len(entries) == 1:
            return entries[0].data
        raise ServiceValidationError(
            "Multiple SOFAR entries configured; specify config_entry_id"
        )

    async def _handle_set_mode(call):
        mode = call.data.get("mode", MODE_AUTO)
        if mode not in (MODE_AUTO, MODE_CHARGE, MODE_DISCHARGE, MODE_STANDBY):
            raise ServiceValidationError(f"Invalid mode: {mode}")
        data = _resolve_entry_data(call)
        await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], mode)
        _LOGGER.info("Service set_mode: %s", mode)

    async def _handle_set_charge_rate(call):
        rate = max(0, min(int(call.data.get("rate", 1500)), DEFAULT_MAX_RATE))
        data = _resolve_entry_data(call)
        await _set_number(hass, data[CONF_SOFAR_CHARGE_RATE_ENTITY], rate)
        _LOGGER.info("Service set_charge_rate: %dW", rate)

    async def _handle_set_discharge_rate(call):
        rate = max(0, min(int(call.data.get("rate", 1500)), DEFAULT_MAX_RATE))
        data = _resolve_entry_data(call)
        await _set_number(hass, data[CONF_SOFAR_DISCHARGE_RATE_ENTITY], rate)
        _LOGGER.info("Service set_discharge_rate: %dW", rate)

    hass.services.async_register(DOMAIN, "set_mode", _handle_set_mode)
    hass.services.async_register(DOMAIN, "set_charge_rate", _handle_set_charge_rate)
    hass.services.async_register(DOMAIN, "set_discharge_rate", _handle_set_discharge_rate)
    _LOGGER.info("SOFAR ME3000SP services registered")
