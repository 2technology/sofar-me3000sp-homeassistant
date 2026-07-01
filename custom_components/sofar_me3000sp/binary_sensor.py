"""Binary sensor platform for SOFAR ME3000SP Controller."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    BINARY_ALARM_ACTIVE,
    BINARY_BALANCED_GRID,
    BINARY_CHARGING_ACTIVE,
    BINARY_DISCHARGING_ACTIVE,
    BINARY_EXPORTING,
    BINARY_IMPORTING,
    CONF_EXPORT_ENTITY,
    CONF_IMPORT_ENTITY,
    CONF_SOFAR_CHARGE_RATE_ENTITY,
    CONF_SOFAR_DISCHARGE_RATE_ENTITY,
    CONF_SOFAR_FAULT_ENTITY,
    CONF_SOFAR_MODE_ENTITY,
    DEFAULT_BALANCE_W,
    DOMAIN,
    NUMBER_BALANCE_W,
)
from .entity import _get_device_info
from .number import _get_number_helper
from .sensor import _get_float, _get_str


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SOFAR ME3000SP binary sensors."""
    entities = [
        SofarBinarySensor(hass, entry, BINARY_CHARGING_ACTIVE, "SOFAR Charging Active", "mdi:battery-arrow-up", "charging"),
        SofarBinarySensor(hass, entry, BINARY_DISCHARGING_ACTIVE, "SOFAR Discharging Active", "mdi:battery-arrow-down", "discharging"),
        SofarBinarySensor(hass, entry, BINARY_EXPORTING, "SOFAR Exporting", "mdi:transmission-tower-export", "exporting"),
        SofarBinarySensor(hass, entry, BINARY_IMPORTING, "SOFAR Importing", "mdi:transmission-tower-import", "importing"),
        SofarBinarySensor(hass, entry, BINARY_BALANCED_GRID, "SOFAR Balanced Grid", "mdi:scale-balance", "balanced"),
        SofarBinarySensor(hass, entry, BINARY_ALARM_ACTIVE, "SOFAR Alarm Active", "mdi:alert-circle", "alarm"),
    ]
    async_add_entities(entities)


class SofarBinarySensor(BinarySensorEntity):
    """Binary sensor for SOFAR ME3000SP status."""

    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, unique_id: str, name: str, icon: str, sensor_type: str) -> None:
        self._attr_unique_id = f"{DOMAIN}_{unique_id}"
        self._attr_name = name
        self._attr_icon = icon
        self._sensor_type = sensor_type
        self._entry = entry
        self._hass = hass
        self._attr_is_on = False
        self._attr_available = False
        self._attr_device_info = _get_device_info(entry)

    async def async_added_to_hass(self) -> None:
        data = self._entry.data
        tracked = [
            data[CONF_EXPORT_ENTITY],
            data[CONF_IMPORT_ENTITY],
            data[CONF_SOFAR_MODE_ENTITY],
            data[CONF_SOFAR_FAULT_ENTITY],
            data[CONF_SOFAR_CHARGE_RATE_ENTITY],
            data[CONF_SOFAR_DISCHARGE_RATE_ENTITY],
        ]
        self.async_on_remove(async_track_state_change_event(self._hass, tracked, self._on_state_change))
        self._update_state()

    @callback
    def _on_state_change(self, event) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        data = self._entry.data
        mode_state = self._hass.states.get(data[CONF_SOFAR_MODE_ENTITY])
        fault_state = self._hass.states.get(data[CONF_SOFAR_FAULT_ENTITY])
        export_state = self._hass.states.get(data[CONF_EXPORT_ENTITY])
        import_state = self._hass.states.get(data[CONF_IMPORT_ENTITY])
        charge_state = self._hass.states.get(data[CONF_SOFAR_CHARGE_RATE_ENTITY])
        discharge_state = self._hass.states.get(data[CONF_SOFAR_DISCHARGE_RATE_ENTITY])

        mode = _get_str(self._hass, data[CONF_SOFAR_MODE_ENTITY])
        fault = _get_str(self._hass, data[CONF_SOFAR_FAULT_ENTITY])
        export_w = _get_float(self._hass, data[CONF_EXPORT_ENTITY]) * 1000
        import_w = _get_float(self._hass, data[CONF_IMPORT_ENTITY]) * 1000
        charge_rate = _get_float(self._hass, data[CONF_SOFAR_CHARGE_RATE_ENTITY])
        discharge_rate = _get_float(self._hass, data[CONF_SOFAR_DISCHARGE_RATE_ENTITY])

        if self._sensor_type == "charging":
            self._attr_available = mode_state is not None and charge_state is not None
            self._attr_is_on = mode == "charge" and charge_rate > 0
        elif self._sensor_type == "discharging":
            self._attr_available = mode_state is not None and discharge_state is not None
            self._attr_is_on = mode == "discharge" and discharge_rate > 0
        elif self._sensor_type == "exporting":
            self._attr_available = export_state is not None and import_state is not None
            self._attr_is_on = export_w > import_w
        elif self._sensor_type == "importing":
            self._attr_available = export_state is not None and import_state is not None
            self._attr_is_on = import_w > export_w
        elif self._sensor_type == "balanced":
            balance_w = _get_number_helper(self._hass, self._entry.entry_id, NUMBER_BALANCE_W, DEFAULT_BALANCE_W)
            self._attr_available = export_state is not None and import_state is not None
            self._attr_is_on = abs(export_w - import_w) <= balance_w
        elif self._sensor_type == "alarm":
            self._attr_available = fault_state is not None
            self._attr_is_on = fault.lower() not in ("ok", "unavailable", "unknown", "")