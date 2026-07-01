"""SOFAR ME3000SP Controller — Home Assistant custom integration.

Provides template sensors, binary sensors, number helpers, and internal
automation logic for controlling a SOFAR ME3000SP inverter via ESPHome,
using external smart meter + PV data as the truth source.
"""

from __future__ import annotations

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
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval

from .number import _get_number_helper

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
    NUMBER_PV_MIN_W,
    NUMBER_SOC_FORCE_CHARGE,
    NUMBER_SOC_FORCE_CHARGE_TARGET,
    NUMBER_SOC_MAX_CHARGE,
    NUMBER_SOC_MIN_DISCHARGE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SOFAR ME3000SP Controller from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    entry_data = dict(entry.data)
    hass.data[DOMAIN][entry.entry_id] = {
        "entry_data": entry_data,
        "charge_hold_start": None,
        "discharge_hold_start": None,
        "balance_hold_start": None,
        "force_charge_active": False,
        "force_charge_start": None,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await _async_register_services(hass, entry)

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
    mode_entity = data[CONF_SOFAR_MODE_ENTITY]
    charge_rate_entity = data[CONF_SOFAR_CHARGE_RATE_ENTITY]
    discharge_rate_entity = data[CONF_SOFAR_DISCHARGE_RATE_ENTITY]
    soc_entity = data[CONF_SOFAR_SOC_ENTITY]
    fault_entity = data[CONF_SOFAR_FAULT_ENTITY]

    tracked = [export_entity, import_entity, pv_entity, soc_entity, fault_entity]
    store = hass.data[DOMAIN][entry.entry_id]

    async def _on_state_change(event):
        """Handle state changes and run automation logic."""
        await _run_automation(hass, entry, store)

    # Listen to relevant state changes
    async_track_state_change_event(hass, tracked, _on_state_change)

    # Also run periodically as a safety net
    async def _periodic_check(_now):
        await _run_automation(hass, entry, store)

    async_track_time_interval(hass, _periodic_check, timedelta(seconds=60))

    _LOGGER.info("SOFAR ME3000SP automation listeners registered for: %s", tracked)


async def _run_automation(hass: HomeAssistant, entry: ConfigEntry, store: dict):
    """Run the automation logic: decide mode and set charge/discharge rates."""
    data = entry.data
    now = time.monotonic()

    export_w = _get_entity_state(hass, data[CONF_EXPORT_ENTITY]) * 1000  # kW → W
    import_w = _get_entity_state(hass, data[CONF_IMPORT_ENTITY]) * 1000
    pv_w = _get_entity_state(hass, data[CONF_PV_ENTITY])
    soc = _get_entity_state(hass, data[CONF_SOFAR_SOC_ENTITY])
    fault = _get_entity_str(hass, data[CONF_SOFAR_FAULT_ENTITY])
    current_mode = _get_entity_str(hass, data[CONF_SOFAR_MODE_ENTITY])

    net_w = export_w - import_w
    surplus_w = max(0, net_w)
    deficit_w = max(0, -net_w)

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

    # --- ALARM: force standby ---
    if fault.lower() not in (STATE_OK, STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
        await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_STANDBY)
        return

    # --- FORCE CHARGE: critical low SOC ---
    if soc < soc_force_charge:
        if not store.get("force_charge_active"):
            store["force_charge_active"] = True
            store["force_charge_start"] = now
            await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_CHARGE)
            await _set_number(hass, data[CONF_SOFAR_CHARGE_RATE_ENTITY], int(force_charge_rate))
            _LOGGER.info("Force charge started: SOC=%.0f%% < %.0f%%, rate=%.0fW", soc, soc_force_charge, force_charge_rate)
        else:
            elapsed = now - store.get("force_charge_start", now)
            if soc >= soc_force_charge_target:
                store["force_charge_active"] = False
                await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_AUTO)
                _LOGGER.info("Force charge complete: SOC=%.0f%% >= %.0f%%", soc, soc_force_charge_target)
            elif elapsed > FORCE_CHARGE_TIMEOUT:
                store["force_charge_active"] = False
                await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_AUTO)
                _LOGGER.warning("Force charge timeout after %.0fs", FORCE_CHARGE_TIMEOUT)
        return
    else:
        if store.get("force_charge_active"):
            store["force_charge_active"] = False
            _LOGGER.info("Force charge cleared: SOC=%.0f%% >= %.0f%%", soc, soc_force_charge)

    # --- CHARGE: surplus export ---
    if surplus_w > export_start and pv_w > pv_min and soc < soc_max_charge:
        if store.get("charge_hold_start") is None:
            store["charge_hold_start"] = now
        elif now - store["charge_hold_start"] >= CHARGE_HOLD_SECONDS:
            charge_w = min(max(0, int(surplus_w - charge_margin)), DEFAULT_MAX_RATE)
            if charge_w > 0:
                await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_CHARGE)
                await _set_number(hass, data[CONF_SOFAR_CHARGE_RATE_ENTITY], charge_w)
                store["discharge_hold_start"] = None
                store["balance_hold_start"] = None
        return
    else:
        store["charge_hold_start"] = None

    # --- DISCHARGE: import deficit ---
    if import_w > import_start and deficit_w > 0 and soc > soc_min_discharge:
        if store.get("discharge_hold_start") is None:
            store["discharge_hold_start"] = now
        elif now - store["discharge_hold_start"] >= DISCHARGE_HOLD_SECONDS:
            discharge_w = min(max(0, int(deficit_w + discharge_margin)), DEFAULT_MAX_RATE)
            if discharge_w > 0:
                await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_DISCHARGE)
                await _set_number(hass, data[CONF_SOFAR_DISCHARGE_RATE_ENTITY], discharge_w)
                store["charge_hold_start"] = None
                store["balance_hold_start"] = None
        return
    else:
        store["discharge_hold_start"] = None

    # --- BALANCE: return to auto ---
    if abs(net_w) < balance_w:
        if store.get("balance_hold_start") is None:
            store["balance_hold_start"] = now
        elif now - store["balance_hold_start"] >= BALANCE_HOLD_SECONDS:
            if current_mode not in (MODE_AUTO, MODE_STANDBY):
                await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_AUTO)
            store["charge_hold_start"] = None
            store["discharge_hold_start"] = None
        return
    else:
        store["balance_hold_start"] = None

    # --- CATCH-ALL: return to auto if in standby without active condition ---
    # If we reach here, no charge/discharge/balance condition is met.
    # If the inverter is in standby (e.g. left over from a previous alarm),
    # return it to auto so it can self-balance.
    if current_mode == MODE_STANDBY and not store.get("force_charge_active"):
        await _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_AUTO)
        _LOGGER.info("Catch-all: standby → auto (no active condition, SOC=%.0f%%, surplus=%.0fW)", soc, surplus_w)


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


async def _async_register_services(hass: HomeAssistant, entry: ConfigEntry):
    """Register custom services for manual mode/rate control."""

    async def _handle_set_mode(call):
        """Handle set_mode service call."""
        mode = call.data.get("mode", MODE_AUTO)
        if mode not in (MODE_AUTO, MODE_CHARGE, MODE_DISCHARGE, MODE_STANDBY):
            _LOGGER.warning("Invalid mode: %s", mode)
            return
        await _set_mode(hass, entry.data[CONF_SOFAR_MODE_ENTITY], mode)
        _LOGGER.info("Service set_mode: %s", mode)

    async def _handle_set_charge_rate(call):
        """Handle set_charge_rate service call."""
        rate = int(call.data.get("rate", 1500))
        rate = max(0, min(rate, DEFAULT_MAX_RATE))
        await _set_number(hass, entry.data[CONF_SOFAR_CHARGE_RATE_ENTITY], rate)
        _LOGGER.info("Service set_charge_rate: %dW", rate)

    async def _handle_set_discharge_rate(call):
        """Handle set_discharge_rate service call."""
        rate = int(call.data.get("rate", 1500))
        rate = max(0, min(rate, DEFAULT_MAX_RATE))
        await _set_number(hass, entry.data[CONF_SOFAR_DISCHARGE_RATE_ENTITY], rate)
        _LOGGER.info("Service set_discharge_rate: %dW", rate)

    hass.services.async_register(DOMAIN, "set_mode", _handle_set_mode)
    hass.services.async_register(DOMAIN, "set_charge_rate", _handle_set_charge_rate)
    hass.services.async_register(DOMAIN, "set_discharge_rate", _handle_set_discharge_rate)
    _LOGGER.info("SOFAR ME3000SP services registered")
