"""Select platform for SOFAR ME3000SP Controller — strategy selector."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    SELECT_STRATEGY,
    STRATEGY_AUTO,
    STRATEGY_LABELS,
    STRATEGY_OPTIONS,
    STRATEGY_SELF_CONSUMPTION,
)
from .entity import _get_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SOFAR strategy selector."""
    async_add_entities([SofarStrategySelect(hass, entry)])


class SofarStrategySelect(SelectEntity, RestoreEntity):
    """Select entity for choosing the battery management strategy."""

    _attr_should_poll = False
    _attr_icon = "mdi:tune-variant"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the strategy selector."""
        self._entry = entry
        self._hass = hass
        self._attr_unique_id = f"{DOMAIN}_{SELECT_STRATEGY}"
        self._attr_name = "SOFAR Strategy"
        self._attr_options = list(STRATEGY_LABELS.values())
        self._attr_current_option = STRATEGY_LABELS[STRATEGY_SELF_CONSUMPTION]
        self._attr_device_info = _get_device_info(entry)
        self._strategy_key = STRATEGY_SELF_CONSUMPTION

    async def async_added_to_hass(self) -> None:
        """Restore the previously selected strategy across restarts."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in STRATEGY_LABELS.values():
            self._attr_current_option = last_state.state
            for key, label in STRATEGY_LABELS.items():
                if label == last_state.state:
                    self._strategy_key = key
                    break

        store = self.hass.data.setdefault(DOMAIN, {}).setdefault(self._entry.entry_id, {})
        # Register this entity for strategy lookups
        store["strategy_entity_id"] = self.entity_id
        store["strategy"] = self._strategy_key

    async def async_select_option(self, option: str) -> None:
        """Change the selected strategy."""
        self._attr_current_option = option
        # Find the key for this label
        for key, label in STRATEGY_LABELS.items():
            if label == option:
                self._strategy_key = key
                store = self.hass.data.setdefault(DOMAIN, {}).setdefault(self._entry.entry_id, {})
                store["strategy"] = key
                break
        self.async_write_ha_state()

    @property
    def strategy_key(self) -> str:
        """Return the current strategy key."""
        return self._strategy_key