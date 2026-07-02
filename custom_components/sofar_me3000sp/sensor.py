"""Sensor platform for SOFAR ME3000SP Controller."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_EXPORT_ENTITY,
    CONF_IMPORT_ENTITY,
    CONF_PV_ENTITY,
    CONF_SOFAR_FAULT_ENTITY,
    CONF_SOFAR_MODE_ENTITY,
    CONF_SOFAR_SOC_ENTITY,
    DEFAULT_BALANCE_W,
    DEFAULT_CHARGE_MARGIN_W,
    DEFAULT_DISCHARGE_MARGIN_W,
    DEFAULT_EXPORT_START_W,
    DEFAULT_IMPORT_START_W,
    DEFAULT_PV_MIN_W,
    DEFAULT_SOC_FORCE_CHARGE,
    DEFAULT_SOC_MAX_CHARGE,
    DEFAULT_SOC_MIN_DISCHARGE,
    DOMAIN,
    NUMBER_BALANCE_W,
    NUMBER_CHARGE_MARGIN_W,
    NUMBER_DISCHARGE_MARGIN_W,
    NUMBER_EXPORT_START_W,
    NUMBER_IMPORT_START_W,
    NUMBER_PV_MIN_W,
    NUMBER_SOC_FORCE_CHARGE,
    NUMBER_SOC_MAX_CHARGE,
    NUMBER_SOC_MIN_DISCHARGE,
    SENSOR_DECISION_REASON,
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
    """Sensor that explains WHY the current mode was chosen."""

    _attr_should_poll = False
    _attr_icon = "mdi:clipboard-text-clock"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{DOMAIN}_{SENSOR_DECISION_REASON}"
        self._attr_name = "SOFAR Decision Reason"
        self._entry = entry
        self._hass = hass
        self._attr_native_value = "Initializing..."
        self._attr_available = False
        self._attr_device_info = _get_device_info(entry)

    async def async_added_to_hass(self) -> None:
        data = self._entry.data
        tracked = [
            data[CONF_EXPORT_ENTITY],
            data[CONF_IMPORT_ENTITY],
            data[CONF_PV_ENTITY],
            data[CONF_SOFAR_MODE_ENTITY],
            data[CONF_SOFAR_FAULT_ENTITY],
            data[CONF_SOFAR_SOC_ENTITY],
        ]
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
        fault_state = self._hass.states.get(data[CONF_SOFAR_FAULT_ENTITY])
        soc_state = self._hass.states.get(data[CONF_SOFAR_SOC_ENTITY])

        self._attr_available = (
            export_state is not None and export_state.state not in _INVALID_STATES
            and import_state is not None and import_state.state not in _INVALID_STATES
            and pv_state is not None and pv_state.state not in _INVALID_STATES
            and mode_state is not None and mode_state.state not in _INVALID_STATES
            and fault_state is not None and fault_state.state not in _INVALID_STATES
            and soc_state is not None and soc_state.state not in _INVALID_STATES
        )

        if not self._attr_available:
            return

        fault = _get_str(self._hass, data[CONF_SOFAR_FAULT_ENTITY])
        mode = _get_str(self._hass, data[CONF_SOFAR_MODE_ENTITY])
        export_w = _get_float(self._hass, data[CONF_EXPORT_ENTITY]) * 1000
        import_w = _get_float(self._hass, data[CONF_IMPORT_ENTITY]) * 1000
        pv_w = _get_float(self._hass, data[CONF_PV_ENTITY])
        soc = _get_float(self._hass, data[CONF_SOFAR_SOC_ENTITY])
        net_w = export_w - import_w
        surplus_w = max(0, net_w)
        deficit_w = max(0, -net_w)

        balance_w = _get_number_helper(self._hass, self._entry.entry_id, NUMBER_BALANCE_W, DEFAULT_BALANCE_W)
        export_start = _get_number_helper(self._hass, self._entry.entry_id, NUMBER_EXPORT_START_W, DEFAULT_EXPORT_START_W)
        import_start = _get_number_helper(self._hass, self._entry.entry_id, NUMBER_IMPORT_START_W, DEFAULT_IMPORT_START_W)
        pv_min = _get_number_helper(self._hass, self._entry.entry_id, NUMBER_PV_MIN_W, DEFAULT_PV_MIN_W)
        soc_max = _get_number_helper(self._hass, self._entry.entry_id, NUMBER_SOC_MAX_CHARGE, DEFAULT_SOC_MAX_CHARGE)
        soc_min = _get_number_helper(self._hass, self._entry.entry_id, NUMBER_SOC_MIN_DISCHARGE, DEFAULT_SOC_MIN_DISCHARGE)
        soc_force = _get_number_helper(self._hass, self._entry.entry_id, NUMBER_SOC_FORCE_CHARGE, DEFAULT_SOC_FORCE_CHARGE)

        # Build the reason string based on the same logic as _run_automation
        if fault.lower() not in ("ok", "unavailable", "unknown", ""):
            self._attr_native_value = f"Alarm: {fault} → standby"
        elif soc < soc_force:
            self._attr_native_value = f"Force charge: SOC {soc:.0f}% < {soc_force:.0f}% → charge"
        elif surplus_w > export_start and pv_w > pv_min and soc < soc_max:
            charge_w = max(0, int(surplus_w - _get_number_helper(self._hass, self._entry.entry_id, NUMBER_CHARGE_MARGIN_W, DEFAULT_CHARGE_MARGIN_W)))
            if mode == "charge":
                self._attr_native_value = f"Charging: surplus {surplus_w:.0f}W > {export_start:.0f}W, PV {pv_w:.0f}W > {pv_min:.0f}W, SOC {soc:.0f}% < {soc_max:.0f}% → charge @ {charge_w}W"
            else:
                self._attr_native_value = f"Charge pending: surplus {surplus_w:.0f}W > {export_start:.0f}W (waiting for hold time)"
        elif import_w > import_start and deficit_w > 0 and soc > soc_min:
            discharge_w = max(0, int(deficit_w + _get_number_helper(self._hass, self._entry.entry_id, NUMBER_DISCHARGE_MARGIN_W, DEFAULT_DISCHARGE_MARGIN_W)))
            if mode == "discharge":
                self._attr_native_value = f"Discharging: import {import_w:.0f}W > {import_start:.0f}W, deficit {deficit_w:.0f}W, SOC {soc:.0f}% > {soc_min:.0f}% → discharge @ {discharge_w}W"
            else:
                self._attr_native_value = f"Discharge pending: import {import_w:.0f}W > {import_start:.0f}W (waiting for hold time)"
        elif abs(net_w) < balance_w:
            if mode in ("auto", "standby"):
                self._attr_native_value = f"Balanced: |net| {abs(net_w):.0f}W < {balance_w:.0f}W → auto"
            else:
                self._attr_native_value = f"Balance pending: |net| {abs(net_w):.0f}W < {balance_w:.0f}W (waiting for hold time)"
        elif mode == "standby":
            self._attr_native_value = f"Standby (no active rule) → auto"
        else:
            self._attr_native_value = f"Auto: net {net_w:.0f}W, surplus {surplus_w:.0f}W, deficit {deficit_w:.0f}W, SOC {soc:.0f}%"


class SofarMonthlyPeakSensor(SensorEntity):
    """Sensor that tracks the highest 15-min average import peak this month."""

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
        self._peak_history = []  # (timestamp, import_w) pairs

    async def async_added_to_hass(self) -> None:
        data = self._entry.data
        self.async_on_remove(async_track_state_change_event(self._hass, [data[CONF_IMPORT_ENTITY]], self._on_state_change))
        self._update_state()

    @callback
    def _on_state_change(self, event) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        import time as _time
        data = self._entry.data
        import_w = _get_float(self._hass, data[CONF_IMPORT_ENTITY]) * 1000
        now = _time.time()

        # Add to history
        self._peak_history.append((now, import_w))

        # Keep only last 15 minutes of data
        cutoff = now - 900  # 15 min
        self._peak_history = [(t, w) for t, w in self._peak_history if t >= cutoff]

        # Calculate current 15-min average
        if len(self._peak_history) >= 3:
            avg = sum(w for _, w in self._peak_history) / len(self._peak_history)
        else:
            avg = import_w

        # Track the monthly peak (stored in hass.data)
        store = self._hass.data.setdefault(DOMAIN, {}).setdefault(self._entry.entry_id, {})
        monthly_peak = store.get("monthly_peak_w", 0)
        if avg > monthly_peak:
            monthly_peak = avg
            store["monthly_peak_w"] = monthly_peak

        self._attr_native_value = round(monthly_peak)


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
        data = self._entry.data
        tracked = [
            data[CONF_EXPORT_ENTITY],
            data[CONF_IMPORT_ENTITY],
            data[CONF_SOFAR_MODE_ENTITY],
            data[CONF_SOFAR_SOC_ENTITY],
        ]
        self.async_on_remove(async_track_state_change_event(self._hass, tracked, self._on_state_change))
        self._update_state()

    @callback
    def _on_state_change(self, event) -> None:
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
