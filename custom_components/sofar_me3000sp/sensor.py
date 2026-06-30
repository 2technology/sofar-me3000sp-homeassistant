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
    DEFAULT_BALANCE_W,
    DOMAIN,
    NUMBER_BALANCE_W,
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

        if fault not in ("OK", "unavailable", "unknown", ""):
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