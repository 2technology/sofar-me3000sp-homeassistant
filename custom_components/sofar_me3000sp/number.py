"""Number platform for SOFAR ME3000SP Controller — tunable thresholds."""

from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_BALANCE_W,
    DEFAULT_CHARGE_MARGIN_W,
    DEFAULT_DISCHARGE_MARGIN_W,
    DEFAULT_EXPORT_START_W,
    DEFAULT_FORCE_CHARGE_RATE,
    DEFAULT_IMPORT_START_W,
    DEFAULT_PV_MIN_W,
    DEFAULT_SOC_FORCE_CHARGE,
    DEFAULT_SOC_FORCE_CHARGE_TARGET,
    DEFAULT_SOC_MAX_CHARGE,
    DEFAULT_SOC_MIN_DISCHARGE,
    DOMAIN,
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
    NUMBER_PEAK_THRESHOLD_W,
    NUMBER_NIGHT_START_HOUR,
    NUMBER_NIGHT_END_HOUR,
    DEFAULT_PEAK_THRESHOLD_W,
    DEFAULT_NIGHT_START_HOUR,
    DEFAULT_NIGHT_END_HOUR,
)
from .entity import _get_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SOFAR ME3000SP number helpers."""
    entities = [
        SofarNumberHelper(entry, NUMBER_EXPORT_START_W, "SOFAR Export Start W", "mdi:transmission-tower-export", 0, 2000, 50, DEFAULT_EXPORT_START_W),
        SofarNumberHelper(entry, NUMBER_IMPORT_START_W, "SOFAR Import Start W", "mdi:transmission-tower-import", 0, 2000, 50, DEFAULT_IMPORT_START_W),
        SofarNumberHelper(entry, NUMBER_PV_MIN_W, "SOFAR PV Min W", "mdi:solar-power", 0, 5000, 50, DEFAULT_PV_MIN_W),
        SofarNumberHelper(entry, NUMBER_BALANCE_W, "SOFAR Balance W", "mdi:scale-balance", 0, 1000, 25, DEFAULT_BALANCE_W),
        SofarNumberHelper(entry, NUMBER_CHARGE_MARGIN_W, "SOFAR Charge Margin W", "mdi:battery-plus", 0, 1000, 25, DEFAULT_CHARGE_MARGIN_W),
        SofarNumberHelper(entry, NUMBER_DISCHARGE_MARGIN_W, "SOFAR Discharge Margin W", "mdi:battery-minus", 0, 1000, 25, DEFAULT_DISCHARGE_MARGIN_W),
        SofarNumberHelper(entry, NUMBER_SOC_MAX_CHARGE, "SOFAR SOC Max Charge %", "mdi:battery-high", 0, 100, 1, DEFAULT_SOC_MAX_CHARGE),
        SofarNumberHelper(entry, NUMBER_SOC_MIN_DISCHARGE, "SOFAR SOC Min Discharge %", "mdi:battery-alert", 0, 100, 1, DEFAULT_SOC_MIN_DISCHARGE),
        SofarNumberHelper(entry, NUMBER_SOC_FORCE_CHARGE, "SOFAR SOC Force Charge %", "mdi:battery-alert-variant-outline", 0, 50, 1, DEFAULT_SOC_FORCE_CHARGE),
        SofarNumberHelper(entry, NUMBER_SOC_FORCE_CHARGE_TARGET, "SOFAR SOC Force Charge Target %", "mdi:battery-charging-high", 20, 100, 1, DEFAULT_SOC_FORCE_CHARGE_TARGET),
        SofarNumberHelper(entry, NUMBER_FORCE_CHARGE_RATE, "SOFAR Force Charge Rate W", "mdi:battery-charging", 100, 3000, 50, DEFAULT_FORCE_CHARGE_RATE),
        SofarNumberHelper(entry, NUMBER_PEAK_THRESHOLD_W, "SOFAR Peak Threshold W", "mdi:chart-line-variant", 500, 5000, 50, DEFAULT_PEAK_THRESHOLD_W),
        SofarNumberHelper(entry, NUMBER_NIGHT_START_HOUR, "SOFAR Night Start Hour", "mdi:weather-night", 18, 23, 1, DEFAULT_NIGHT_START_HOUR),
        SofarNumberHelper(entry, NUMBER_NIGHT_END_HOUR, "SOFAR Night End Hour", "mdi:weather-sunny", 4, 10, 1, DEFAULT_NIGHT_END_HOUR),
    ]
    async_add_entities(entities)


_INVALID_STATES = ("unavailable", "unknown", "none", "")


def _get_number_entity_id(hass: HomeAssistant, entry_id: str, unique_id: str) -> str | None:
    """Find entity_id for a number helper by its unique_id within an entry."""
    store = hass.data.setdefault(DOMAIN, {}).setdefault(entry_id, {})
    mapping = store.setdefault("number_entity_ids", {})
    return mapping.get(f"{DOMAIN}_{unique_id}")


def _get_number_helper(hass: HomeAssistant, entry_id: str, helper_id: str, default: float) -> float:
    """Get value of a number helper, falling back to default if not found or invalid."""
    entity_id = _get_number_entity_id(hass, entry_id, helper_id)
    if entity_id is None:
        return default
    state = hass.states.get(entity_id)
    if state is None or state.state in _INVALID_STATES:
        return default
    try:
        return float(state.state)
    except (ValueError, TypeError):
        return default


class SofarNumberHelper(RestoreNumber):
    """A number helper for tuning automation thresholds."""

    _attr_mode = NumberMode.BOX
    _attr_should_poll = False

    def __init__(
        self,
        entry: ConfigEntry,
        unique_id: str,
        name: str,
        icon: str,
        native_min_value: float,
        native_max_value: float,
        native_step: float,
        initial_value: float,
    ) -> None:
        """Initialize."""
        self._entry = entry
        self._base_unique_id = unique_id
        self._attr_unique_id = f"{DOMAIN}_{unique_id}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_min_value = native_min_value
        self._attr_native_max_value = native_max_value
        self._attr_native_step = native_step
        self._attr_native_value = initial_value

    async def async_added_to_hass(self) -> None:
        """Restore previous value and register entity_id mapping."""
        await super().async_added_to_hass()
        self._attr_device_info = _get_device_info(self._entry)

        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            value = max(self._attr_native_min_value, min(last.native_value, self._attr_native_max_value))
            self._attr_native_value = value

        store = self.hass.data.setdefault(DOMAIN, {}).setdefault(self._entry.entry_id, {})
        mapping = store.setdefault("number_entity_ids", {})
        mapping[self._attr_unique_id] = self.entity_id

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.async_write_ha_state()
