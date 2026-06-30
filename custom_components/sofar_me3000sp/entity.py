"""Base entity classes for SOFAR ME3000SP Controller."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.loader import async_get_integration

from .const import DOMAIN


def _get_device_info(entry: ConfigEntry, hass: HomeAssistant) -> DeviceInfo:
    """Return shared device info for all entities in this integration."""
    integration = async_get_integration(hass, DOMAIN)
    sw_version = integration.version if integration else "unknown"
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="SOFAR ME3000SP Controller",
        manufacturer="SOFAR",
        model="ME3000SP",
        sw_version=sw_version,
        entry_type="service",
    )
