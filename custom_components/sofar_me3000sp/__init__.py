"""SOFAR ME3000SP Controller — Home Assistant custom integration.

Provides template sensors, binary sensors, number helpers, and internal
automation logic for controlling a SOFAR ME3000SP inverter via ESPHome,
using external smart meter + PV data as the truth source.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_OK,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval

from .const import (
    BALANCE_HOLD_SECONDS,
    BINARY_ALARM_ACTIVE,
    BINARY_BALANCED_GRID,
    BINARY_CHARGING_ACTIVE,
    BINARY_DISCHARGING_ACTIVE,
    BINARY_EXPORTING,
    BINARY_IMPORTING,
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
    NUMBER_IMPORT_START_W,
    NUMBER_PV_MIN_W,
    NUMBER_SOC_MAX_CHARGE,
    NUMBER_SOC_MIN_DISCHARGE,
    SENSOR_FLOW_DIRECTION,
    SENSOR_GRID_DEFICIT_POWER,
    SENSOR_GRID_EXPORT_POWER,
    SENSOR_GRID_IMPORT_POWER,
    SENSOR_GRID_SURPLUS_POWER,
    SENSOR_HOUSE_LOAD_POWER,
    SENSOR_NET_GRID_POWER,
    SENSOR_SMA_PV_POWER,
    SENSOR_VISUAL_SUMMARY,
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

    # Start automation logic after HA is fully started
    async def _start_automation(_event=None):
        _LOGGER.info("SOFAR ME3000SP automation started")
        _setup_automation(hass, entry)

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


def _get_number_helper(hass: HomeAssistant, helper_id: str, default: float) -> float:
    """Get value of a number helper, falling back to default."""
    val = _get_entity_state(hass, f"number.{helper_id}", default)
    return val if val > 0 else default


def _setup_automation(hass: HomeAssistant, entry: ConfigEntry):
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

    @callback
    def _on_state_change(event):
        """Handle state changes and run automation logic."""
        _run_automation(hass, entry, store)

    # Listen to relevant state changes
    async_track_state_change_event(hass, tracked, _on_state_change)

    # Also run periodically as a safety net
    async_track_time_interval(hass, lambda now: _run_automation(hass, entry, store), timedelta(seconds=60))

    _LOGGER.info("SOFAR ME3000SP automation listeners registered for: %s", tracked)


def _run_automation(hass: HomeAssistant, entry: ConfigEntry, store: dict):
    """Run the automation logic: decide mode and set charge/discharge rates."""
    data = entry.data
    now = hass.loop.time() if hass.loop else 0

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
    export_start = _get_number_helper(hass, NUMBER_EXPORT_START_W, DEFAULT_EXPORT_START_W)
    import_start = _get_number_helper(hass, NUMBER_IMPORT_START_W, DEFAULT_IMPORT_START_W)
    pv_min = _get_number_helper(hass, NUMBER_PV_MIN_W, DEFAULT_PV_MIN_W)
    balance_w = _get_number_helper(hass, NUMBER_BALANCE_W, DEFAULT_BALANCE_W)
    charge_margin = _get_number_helper(hass, NUMBER_CHARGE_MARGIN_W, DEFAULT_CHARGE_MARGIN_W)
    discharge_margin = _get_number_helper(hass, NUMBER_DISCHARGE_MARGIN_W, DEFAULT_DISCHARGE_MARGIN_W)
    soc_max_charge = _get_number_helper(hass, NUMBER_SOC_MAX_CHARGE, DEFAULT_SOC_MAX_CHARGE)
    soc_min_discharge = _get_number_helper(hass, NUMBER_SOC_MIN_DISCHARGE, DEFAULT_SOC_MIN_DISCHARGE)

    # --- ALARM: force standby ---
    if fault not in (STATE_OK, STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
        _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_STANDBY)
        return

    # --- FORCE CHARGE: critical low SOC ---
    if soc < DEFAULT_SOC_FORCE_CHARGE and current_mode != MODE_CHARGE:
        if not store.get("force_charge_active"):
            store["force_charge_active"] = True
            store["force_charge_start"] = now
            _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_CHARGE)
            _set_number(hass, data[CONF_SOFAR_CHARGE_RATE_ENTITY], DEFAULT_FORCE_CHARGE_RATE)
            _LOGGER.info("Force charge started: SOC=%.0f%%", soc)
        elif now - store.get("force_charge_start", 0) > FORCE_CHARGE_TIMEOUT:
            store["force_charge_active"] = False
            _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_AUTO)
            _LOGGER.warning("Force charge timeout after 4h")
        elif soc >= DEFAULT_SOC_FORCE_CHARGE_TARGET:
            store["force_charge_active"] = False
            _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_AUTO)
            _LOGGER.info("Force charge complete: SOC=%.0f%%", soc)
        return

    # --- CHARGE: surplus export ---
    if surplus_w > export_start and pv_w > pv_min and soc < soc_max_charge:
        if store.get("charge_hold_start") is None:
            store["charge_hold_start"] = now
        elif now - store["charge_hold_start"] >= CHARGE_HOLD_SECONDS:
            charge_w = min(max(0, int(surplus_w - charge_margin)), DEFAULT_MAX_RATE)
            if charge_w > 0:
                _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_CHARGE)
                _set_number(hass, data[CONF_SOFAR_CHARGE_RATE_ENTITY], charge_w)
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
                _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_DISCHARGE)
                _set_number(hass, data[CONF_SOFAR_DISCHARGE_RATE_ENTITY], discharge_w)
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
                _set_mode(hass, data[CONF_SOFAR_MODE_ENTITY], MODE_AUTO)
            store["charge_hold_start"] = None
            store["discharge_hold_start"] = None
        return
    else:
        store["balance_hold_start"] = None


def _set_mode(hass: HomeAssistant, entity_id: str, mode: str):
    """Set the inverter mode via select entity."""
    hass.async_create_task(
        hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id, "option": mode},
            blocking=False,
        )
    )


def _set_number(hass: HomeAssistant, entity_id: str, value: int):
    """Set a number entity value."""
    hass.async_create_task(
        hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": entity_id, "value": float(value)},
            blocking=False,
        )
    )
