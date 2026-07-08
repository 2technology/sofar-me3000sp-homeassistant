"""Sensor platform for SOFAR ME3000SP Controller."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval

from .const import (
    CONF_EXPORT_ENTITY,
    CONF_IMPORT_ENTITY,
    CONF_PV_ENTITY,
    CONF_SOFAR_FAULT_ENTITY,
    CONF_SOFAR_MODE_ENTITY,
    CONF_SOFAR_SOC_ENTITY,
    DEFAULT_BALANCE_W,
    DEFAULT_PEAK_THRESHOLD_W,
    DOMAIN,
    NUMBER_BALANCE_W,
    NUMBER_PEAK_THRESHOLD_W,
    QUARTER_SECONDS,
    SENSOR_DECISION_REASON,
    SENSOR_FLOW_DIRECTION,
    SENSOR_GRID_DEFICIT_POWER,
    SENSOR_GRID_EXPORT_POWER,
    SENSOR_GRID_IMPORT_POWER,
    SENSOR_GRID_SURPLUS_POWER,
    SENSOR_HOUSE_LOAD_POWER,
    SENSOR_MONTHLY_PEAK_W,
    SENSOR_NET_GRID_POWER,
    SENSOR_QUARTER_AVG_W,
    SENSOR_QUARTER_BUDGET_W,
    SENSOR_QUARTER_PROJECTED_W,
    SENSOR_QUARTER_TIME_REMAINING,
    SENSOR_SMA_PV_POWER,
    SENSOR_STRATEGY_STATUS,
    SENSOR_VISUAL_SUMMARY,
    SIGNAL_UPDATE,
    STRATEGY_LABELS,
    STRATEGY_SELF_CONSUMPTION,
)
from .entity import _get_device_info
from .number import _get_number_helper

_INVALID_STATES = ("unavailable", "unknown", "none", "")


def _get_float(hass: HomeAssistant, entity_id: str) -> float:
    """Get float value from an entity."""
    state = hass.states.get(entity_id)
    if state is None or state.state in _INVALID_STATES:
        return 0.0
    try:
        return float(state.state)
    except (ValueError, TypeError):
        return 0.0


def _get_str(hass: HomeAssistant, entity_id: str) -> str:
    """Get string state of an entity."""
    state = hass.states.get(entity_id)
    if state is None:
        return ""
    return str(state.state)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SOFAR ME3000SP sensors."""
    entities = [
        SofarDerivedSensor(hass, entry, SENSOR_GRID_EXPORT_POWER, "SOFAR Grid Export Power", "mdi:transmission-tower-export", "export"),
        SofarDerivedSensor(hass, entry, SENSOR_GRID_IMPORT_POWER, "SOFAR Grid Import Power", "mdi:transmission-tower-import", "import"),
        SofarDerivedSensor(hass, entry, SENSOR_NET_GRID_POWER, "SOFAR Net Grid Power", "mdi:home-lightning-bolt", "net"),
        SofarDerivedSensor(hass, entry, SENSOR_GRID_SURPLUS_POWER, "SOFAR Grid Surplus Power", "mdi:weather-sunny-arrow-right", "surplus"),
        SofarDerivedSensor(hass, entry, SENSOR_GRID_DEFICIT_POWER, "SOFAR Grid Deficit Power", "mdi:weather-sunny-clock", "deficit"),
        SofarDerivedSensor(hass, entry, SENSOR_HOUSE_LOAD_POWER, "SOFAR House Load Power", "mdi:home-lightning-bolt-outline", "house_load"),
        SofarDerivedSensor(hass, entry, SENSOR_SMA_PV_POWER, "SOFAR SMA PV Power", "mdi:solar-power", "pv"),
        SofarFlowDirectionSensor(hass, entry),
        SofarVisualSummarySensor(hass, entry),
        SofarDecisionReasonSensor(hass, entry),
        SofarMonthlyPeakSensor(hass, entry),
        SofarStrategyStatusSensor(hass, entry),
        SofarQuarterStoreSensor(hass, entry, SENSOR_QUARTER_AVG_W, "SOFAR Quarter Avg W", "mdi:chart-timeline-variant", "q_avg_w"),
        SofarQuarterStoreSensor(hass, entry, SENSOR_QUARTER_PROJECTED_W, "SOFAR Quarter Projected W", "mdi:chart-line", "q_projected_w"),
        SofarQuarterStoreSensor(hass, entry, SENSOR_QUARTER_BUDGET_W, "SOFAR Quarter Budget W", "mdi:speedometer", "q_budget_w"),
        SofarQuarterTimeRemainingSensor(hass, entry),
    ]
    async_add_entities(entities)


class SofarDerivedSensor(SensorEntity):
    """A sensor that derives its value from external entities."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, unique_id: str, name: str, icon: str, sensor_type: str) -> None:
        self._attr_unique_id = f"{DOMAIN}_{unique_id}"
        self._attr_name = name
        self._attr_icon = icon
        self._sensor_type = sensor_type
        self._entry = entry
        self._hass = hass
        self._attr_native_value = 0.0
        self._attr_available = False
        self._attr_device_info = _get_device_info(entry)

    async def async_added_to_hass(self) -> None:
        data = self._entry.data
        tracked = [data[CONF_EXPORT_ENTITY], data[CONF_IMPORT_ENTITY], data[CONF_PV_ENTITY]]
        self.async_on_remove(async_track_state_change_event(self._hass, tracked, self._on_state_change))
        self._update_state()

    @callback
    def _on_state_change(self, event) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        data = self._entry.data
        export_state = self._hass.states.get(data[CONF_EXPORT_ENTITY])
        import_state = self._hass.states.get(data[CONF_IMPORT_ENTITY])
        pv_state = self._hass.states.get(data[CONF_PV_ENTITY])

        self._attr_available = (
            export_state is not None and export_state.state not in _INVALID_STATES
            and import_state is not None and import_state.state not in _INVALID_STATES
        )

        if self._sensor_type == "house_load":
            self._attr_available = (
                self._attr_available
                and pv_state is not None and pv_state.state not in _INVALID_STATES
            )
        elif self._sensor_type == "pv":
            self._attr_available = pv_state is not None and pv_state.state not in _INVALID_STATES

        export_w = _get_float(self._hass, data[CONF_EXPORT_ENTITY]) * 1000
        import_w = _get_float(self._hass, data[CONF_IMPORT_ENTITY]) * 1000
        pv_w = _get_float(self._hass, data[CONF_PV_ENTITY])
        net_w = export_w - import_w

        if self._sensor_type == "export":
            self._attr_native_value = round(export_w)
        elif self._sensor_type == "import":
            self._attr_native_value = round(import_w)
        elif self._sensor_type == "net":
            self._attr_native_value = round(net_w)
        elif self._sensor_type == "surplus":
            self._attr_native_value = round(max(0, net_w))
        elif self._sensor_type == "deficit":
            self._attr_native_value = round(max(0, -net_w))
        elif self._sensor_type == "house_load":
            self._attr_native_value = round(pv_w + import_w - export_w)
        elif self._sensor_type == "pv":
            self._attr_native_value = round(pv_w)


class SofarFlowDirectionSensor(SensorEntity):
    """Sensor that shows the current flow direction."""

    _attr_should_poll = False
    _attr_icon = "mdi:state-machine"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{DOMAIN}_{SENSOR_FLOW_DIRECTION}"
        self._attr_name = "SOFAR Flow Direction"
        self._entry = entry
        self._hass = hass
        self._attr_native_value = "unknown"
        self._attr_available = False
        self._attr_device_info = _get_device_info(entry)

    async def async_added_to_hass(self) -> None:
        data = self._entry.data
        tracked = [data[CONF_EXPORT_ENTITY], data[CONF_IMPORT_ENTITY], data[CONF_SOFAR_MODE_ENTITY], data[CONF_SOFAR_FAULT_ENTITY]]
        self.async_on_remove(async_track_state_change_event(self._hass, tracked, self._on_state_change))
        self._update_state()

    @callback
    def _on_state_change(self, event) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        data = self._entry.data
        fault_state = self._hass.states.get(data[CONF_SOFAR_FAULT_ENTITY])
        mode_state = self._hass.states.get(data[CONF_SOFAR_MODE_ENTITY])
        export_state = self._hass.states.get(data[CONF_EXPORT_ENTITY])
        import_state = self._hass.states.get(data[CONF_IMPORT_ENTITY])

        self._attr_available = (
            fault_state is not None and fault_state.state not in _INVALID_STATES
            and mode_state is not None and mode_state.state not in _INVALID_STATES
            and export_state is not None and export_state.state not in _INVALID_STATES
            and import_state is not None and import_state.state not in _INVALID_STATES
        )

        fault = _get_str(self._hass, data[CONF_SOFAR_FAULT_ENTITY])
        mode = _get_str(self._hass, data[CONF_SOFAR_MODE_ENTITY])
        export_w = _get_float(self._hass, data[CONF_EXPORT_ENTITY]) * 1000
        import_w = _get_float(self._hass, data[CONF_IMPORT_ENTITY]) * 1000

        balance_w = _get_number_helper(self._hass, self._entry.entry_id, NUMBER_BALANCE_W, DEFAULT_BALANCE_W)

        if fault.lower() not in ("ok", "unavailable", "unknown", ""):
            self._attr_native_value = "alarm"
        elif mode == "standby":
            self._attr_native_value = "standby"
        elif mode == "charge":
            self._attr_native_value = "charging"
        elif mode == "discharge":
            self._attr_native_value = "discharging"
        elif abs(export_w - import_w) < balance_w:
            self._attr_native_value = "balanced"
        elif export_w > import_w:
            self._attr_native_value = "exporting"
        else:
            self._attr_native_value = "importing"


class SofarVisualSummarySensor(SensorEntity):
    """Sensor that shows a compact visual summary."""

    _attr_should_poll = False
    _attr_icon = "mdi:chart-box-outline"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{DOMAIN}_{SENSOR_VISUAL_SUMMARY}"
        self._attr_name = "SOFAR Visual Summary"
        self._entry = entry
        self._hass = hass
        self._attr_native_value = ""
        self._attr_available = False
        self._attr_device_info = _get_device_info(entry)

    async def async_added_to_hass(self) -> None:
        data = self._entry.data
        tracked = [data[CONF_EXPORT_ENTITY], data[CONF_IMPORT_ENTITY], data[CONF_PV_ENTITY], data[CONF_SOFAR_MODE_ENTITY]]
        self.async_on_remove(async_track_state_change_event(self._hass, tracked, self._on_state_change))
        self._update_state()

    @callback
    def _on_state_change(self, event) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        data = self._entry.data
        export_state = self._hass.states.get(data[CONF_EXPORT_ENTITY])
        import_state = self._hass.states.get(data[CONF_IMPORT_ENTITY])
        pv_state = self._hass.states.get(data[CONF_PV_ENTITY])
        mode_state = self._hass.states.get(data[CONF_SOFAR_MODE_ENTITY])

        self._attr_available = (
            export_state is not None and export_state.state not in _INVALID_STATES
            and import_state is not None and import_state.state not in _INVALID_STATES
            and pv_state is not None and pv_state.state not in _INVALID_STATES
            and mode_state is not None and mode_state.state not in _INVALID_STATES
        )

        pv = _get_float(self._hass, data[CONF_PV_ENTITY])
        export_w = _get_float(self._hass, data[CONF_EXPORT_ENTITY]) * 1000
        import_w = _get_float(self._hass, data[CONF_IMPORT_ENTITY]) * 1000
        mode = _get_str(self._hass, data[CONF_SOFAR_MODE_ENTITY])
        net_w = export_w - import_w

        self._attr_native_value = (
            f"PV {round(pv)} W · "
            f"Export {round(export_w)} W · "
            f"Import {round(import_w)} W · "
            f"Netto {round(net_w)} W · "
            f"Mode {mode}"
        )

class SofarDecisionReasonSensor(SensorEntity):
    """Reports WHY the automation chose the current mode.

    Single source of truth: this sensor only reads store["decision_reason"]
    as written by the automation loop. It never re-derives the logic, so
    what you see is exactly what the automation decided — for every
    strategy, including holds and honest edge cases.
    """

    _attr_should_poll = False
    _attr_icon = "mdi:clipboard-text-clock"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{DOMAIN}_{SENSOR_DECISION_REASON}"
        self._attr_name = "SOFAR Decision Reason"
        self._entry = entry
        self._hass = hass
        self._attr_native_value = "Initializing..."
        self._attr_available = True
        self._attr_device_info = _get_device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass, f"{SIGNAL_UPDATE}_{self._entry.entry_id}", self._on_update
            )
        )
        self._update_state()

    @callback
    def _on_update(self) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        import time as _time
        store = self._hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        self._attr_native_value = store.get("decision_reason", "Waiting for first automation run...")

        # Machine-readable context for dashboards and automations.
        hold = store.get("active_hold")
        hold_remaining = None
        if hold and store.get("active_hold_start") is not None:
            elapsed = _time.monotonic() - store["active_hold_start"]
            hold_remaining = max(0, round(store.get("active_hold_duration", 0) - elapsed))
        self._attr_extra_state_attributes = {
            "strategy": STRATEGY_LABELS.get(store.get("strategy", STRATEGY_SELF_CONSUMPTION)),
            "active_hold": hold,
            "hold_remaining_s": hold_remaining,
            "last_charge_rate_w": store.get("last_charge_rate"),
            "last_discharge_rate_w": store.get("last_discharge_rate"),
            "quarter_avg_w": store.get("q_avg_w"),
            "quarter_projected_w": store.get("q_projected_w"),
            "quarter_budget_w": store.get("q_budget_w"),
            "quarter_remaining_s": store.get("q_remaining_s"),
            "last_quarter_avg_w": store.get("last_quarter_avg_w"),
            "forecast_today_kwh": store.get("forecast_today_kwh"),
            "forecast_tomorrow_kwh": store.get("forecast_tomorrow_kwh"),
            "forecast_next_hour_wh": store.get("forecast_next_hour_wh"),
            "forecast_available": store.get("forecast_available", False),
        }


class SofarMonthlyPeakSensor(RestoreSensor):
    """Highest closed clock-quarter import average this month.

    The quarter tracker in the automation loop (single source of truth)
    computes this per Fluvius rules: clock-aligned quarters, time-weighted
    average, monthly rollover. This sensor reports it and restores it
    across restarts.
    """

    _attr_should_poll = False
    _attr_icon = "mdi:chart-line-variant"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{DOMAIN}_{SENSOR_MONTHLY_PEAK_W}"
        self._attr_name = "SOFAR Monthly Peak W"
        self._entry = entry
        self._hass = hass
        self._attr_native_value = 0
        self._attr_available = True
        self._attr_device_info = _get_device_info(entry)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        store = self._hass.data.setdefault(DOMAIN, {}).setdefault(self._entry.entry_id, {})

        # Restore the peak across restarts — but only into the store if the
        # tracker hasn't produced anything yet, and only if the restored
        # value belongs to the current month.
        last = await self.async_get_last_state()
        last_data = await self.async_get_last_sensor_data()
        if last_data is not None and last_data.native_value is not None and not store.get("monthly_peak_w"):
            import datetime as _dt
            restored_month = (last.attributes.get("peak_month") if last else None)
            current_month = _dt.datetime.now().strftime("%Y-%m")
            if restored_month == current_month:
                try:
                    store["monthly_peak_w"] = round(float(last_data.native_value))
                    store["peak_month"] = restored_month
                    store["monthly_peak_ts"] = last.attributes.get("peaked_at") if last else None
                except (ValueError, TypeError):
                    pass

        self.async_on_remove(
            async_dispatcher_connect(
                self._hass, f"{SIGNAL_UPDATE}_{self._entry.entry_id}", self._on_update
            )
        )
        self._update_state()

    @callback
    def _on_update(self) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        store = self._hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        self._attr_native_value = store.get("monthly_peak_w", 0)
        self._attr_extra_state_attributes = {
            "peak_month": store.get("peak_month"),
            "peaked_at": store.get("monthly_peak_ts"),
            "last_quarter_avg_w": store.get("last_quarter_avg_w"),
            "forecast_today_kwh": store.get("forecast_today_kwh"),
            "forecast_tomorrow_kwh": store.get("forecast_tomorrow_kwh"),
            "forecast_next_hour_wh": store.get("forecast_next_hour_wh"),
            "forecast_available": store.get("forecast_available", False),
        }


class SofarStrategyStatusSensor(SensorEntity):
    """Sensor that shows the current strategy and its status."""

    _attr_should_poll = False
    _attr_icon = "mdi:clipboard-text-clock"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{DOMAIN}_{SENSOR_STRATEGY_STATUS}"
        self._attr_name = "SOFAR Strategy Status"
        self._entry = entry
        self._hass = hass
        self._attr_native_value = "Initializing..."
        self._attr_available = True
        self._attr_device_info = _get_device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass, f"{SIGNAL_UPDATE}_{self._entry.entry_id}", self._on_update
            )
        )
        self._update_state()

    @callback
    def _on_update(self) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        store = self._hass.data.setdefault(DOMAIN, {}).setdefault(self._entry.entry_id, {})
        strategy = store.get("strategy", STRATEGY_SELF_CONSUMPTION)
        decision_reason = store.get("decision_reason", "...")
        strategy_label = STRATEGY_LABELS.get(strategy, strategy)

        data = self._entry.data
        import_w = _get_float(self._hass, data[CONF_IMPORT_ENTITY]) * 1000
        soc = _get_float(self._hass, data[CONF_SOFAR_SOC_ENTITY])
        monthly_peak = store.get("monthly_peak_w", 0)
        peak_threshold = _get_number_helper(self._hass, self._entry.entry_id, NUMBER_PEAK_THRESHOLD_W, DEFAULT_PEAK_THRESHOLD_W)

        self._attr_native_value = (
            f"Strategie: {strategy_label} | "
            f"Import: {import_w:.0f}W | "
            f"SOC: {soc:.0f}% | "
            f"Piek: {monthly_peak:.0f}W / {peak_threshold:.0f}W | "
            f"{decision_reason}"
        )


class SofarQuarterStoreSensor(SensorEntity):
    """Power sensor that reports a value from the quarter tracker store."""

    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, unique_id: str, name: str, icon: str, store_key: str) -> None:
        self._attr_unique_id = f"{DOMAIN}_{unique_id}"
        self._attr_name = name
        self._attr_icon = icon
        self._store_key = store_key
        self._entry = entry
        self._hass = hass
        self._attr_native_value = None
        self._attr_available = True
        self._attr_device_info = _get_device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass, f"{SIGNAL_UPDATE}_{self._entry.entry_id}", self._on_update
            )
        )
        self._update_state()

    @callback
    def _on_update(self) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        store = self._hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        self._attr_native_value = store.get(self._store_key)


class SofarQuarterTimeRemainingSensor(SensorEntity):
    """Seconds until the current clock quarter (:00/:15/:30/:45) closes.

    Answers "hoelang geldt de lopende meting nog": when this hits zero the
    running quarter is settled and a fresh measurement window starts.
    Ticks every 10 s independent of the automation loop.
    """

    _attr_should_poll = False
    _attr_icon = "mdi:timer-sand"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{DOMAIN}_{SENSOR_QUARTER_TIME_REMAINING}"
        self._attr_name = "SOFAR Quarter Time Remaining"
        self._entry = entry
        self._hass = hass
        self._attr_native_value = None
        self._attr_available = True
        self._attr_device_info = _get_device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_track_time_interval(self._hass, self._on_tick, timedelta(seconds=10))
        )
        self._update_state()

    @callback
    def _on_tick(self, _now) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        import datetime as _dt
        import time as _time
        now = _time.time()
        remaining = QUARTER_SECONDS - (now % QUARTER_SECONDS)
        self._attr_native_value = round(remaining)
        quarter_end = _dt.datetime.fromtimestamp(now + remaining)
        self._attr_extra_state_attributes = {
            "quarter_ends_at": quarter_end.strftime("%H:%M"),
            "remaining_mmss": f"{int(remaining) // 60}:{int(remaining) % 60:02d}",
        }
