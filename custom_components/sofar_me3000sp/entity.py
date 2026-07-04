"""Base entity classes for SOFAR ME3000SP Controller."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, VERSION


def _get_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return shared device info for all entities in this integration."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="SOFAR ME3000SP Controller",
        manufacturer="SOFAR",
        model="ME3000SP",
        sw_version=VERSION,
        entry_type=DeviceEntryType.SERVICE,
    )
