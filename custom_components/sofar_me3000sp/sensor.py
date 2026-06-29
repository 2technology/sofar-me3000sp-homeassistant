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
    DOMAIN,
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SOFAR ME3000SP sensors."""
    data = entry.data
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
        """Initialize the sensor."""
        self._attr_unique_id = f"{DOMAIN}_{unique_id}"
        self._attr_name = name
        self._attr_icon = icon
        self._sensor_type = sensor_type
        self._entry = entry
        self._hass = hass
        self._attr_native_value = 0.0
        self._attr_available = False

    async def async_added_to_hass(self) -> None:
        """Register state change listener."""
        data = self._entry.data
        tracked = [data[CONF_EXPORT_ENTITY], data[CONF_IMPORT_ENTITY], data[CONF_PV_ENTITY]]
        self.async_on_remove(
            async_track_state_change_event(self._hass, tracked, self._on_state_change)
        )
        self._update_state()

    @callback
    def _on_state_change(self, event) -> None:
        """Handle state changes."""
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        """Update the sensor value."""
        data = self._entry.data
        export_w = self._get_float(data[CONF_EXPORT_ENTITY]) * 1000
        import_w = self._get_float(data[CONF_IMPORT_ENTITY]) * 1000
        pv_w = self._get_float(data[CONF_PV_ENTITY])
        net_w = export_w - import_w

        self._attr_available = True

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

    def _get_float(self, entity_id: str) -> float:
        """Get float value from an entity."""
        state = self._hass.states.get(entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            self._attr_available = False
            return 0.0
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return 0.0


class SofarFlowDirectionSensor(SensorEntity):
    """Sensor that shows the current flow direction."""

    _attr_should_poll = False
    _attr_icon = "mdi:state-machine"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self._attr_unique_id = f"{DOMAIN}_{SENSOR_FLOW_DIRECTION}"
        self._attr_name = "SOFAR Flow Direction"
        self._entry = entry
        self._hass = hass
        self._attr_native_value = "unknown"
        self._attr_available = False

    async def async_added_to_hass(self) -> None:
        """Register listener."""
        data = self._entry.data
        tracked = [
            data[CONF_EXPORT_ENTITY],
            data[CONF_IMPORT_ENTITY],
            data[CONF_SOFAR_MODE_ENTITY],
            data[CONF_SOFAR_FAULT_ENTITY],
        ]
        self.async_on_remove(
            async_track_state_change_event(self._hass, tracked, self._on_state_change)
        )
        self._update_state()

    @callback
    def _on_state_change(self, event) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        data = self._entry.data
        fault = self._get_str(data[CONF_SOFAR_FAULT_ENTITY])
        mode = self._get_str(data[CONF_SOFAR_MODE_ENTITY])
        export_w = self._get_float(data[CONF_EXPORT_ENTITY]) * 1000
        import_w = self._get_float(data[CONF_IMPORT_ENTITY]) * 1000

        self._attr_available = True

        if fault not in ("OK", "unavailable", "unknown", ""):
            self._attr_native_value = "alarm"
        elif mode == "standby":
            self._attr_native_value = "standby"
        elif mode == "charge":
            self._attr_native_value = "charging"
        elif mode == "discharge":
            self._attr_native_value = "discharging"
        elif abs(export_w - import_w) < 150:
            self._attr_native_value = "balanced"
        elif export_w > import_w:
            self._attr_native_value = "exporting"
        else:
            self._attr_native_value = "importing"

    def _get_float(self, entity_id: str) -> float:
        state = self._hass.states.get(entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return 0.0
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return 0.0

    def _get_str(self, entity_id: str) -> str:
        state = self._hass.states.get(entity_id)
        if state is None:
            return ""
        return str(state.state)


class SofarVisualSummarySensor(SensorEntity):
    """Sensor that shows a compact visual summary."""

    _attr_should_poll = False
    _attr_icon = "mdi:chart-box-outline"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self._attr_unique_id = f"{DOMAIN}_{SENSOR_VISUAL_SUMMARY}"
        self._attr_name = "SOFAR Visual Summary"
        self._entry = entry
        self._hass = hass
        self._attr_native_value = ""
        self._attr_available = False

    async def async_added_to_hass(self) -> None:
        data = self._entry.data
        tracked = [data[CONF_EXPORT_ENTITY], data[CONF_IMPORT_ENTITY], data[CONF_PV_ENTITY], data[CONF_SOFAR_MODE_ENTITY]]
        self.async_on_remove(
            async_track_state_change_event(self._hass, tracked, self._on_state_change)
        )
        self._update_state()

    @callback
    def _on_state_change(self, event) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        data = self._entry.data
        pv = self._get_float(data[CONF_PV_ENTITY])
        export_w = self._get_float(data[CONF_EXPORT_ENTITY]) * 1000
        import_w = self._get_float(data[CONF_IMPORT_ENTITY]) * 1000
        mode = self._get_str(data[CONF_SOFAR_MODE_ENTITY])
        net_w = export_w - import_w

        self._attr_available = True
        self._attr_native_value = (
            f"PV {round(pv)} W · "
            f"Export {round(export_w)} W · "
            f"Import {round(import_w)} W · "
            f"Netto {round(net_w)} W · "
            f"Mode {mode}"
        )

    def _get_float(self, entity_id: str) -> float:
        state = self._hass.states.get(entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return 0.0
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return 0.0

    def _get_str(self, entity_id: str) -> str:
        state = self._hass.states.get(entity_id)
        if state is None:
            return ""
        return str(state.state)
