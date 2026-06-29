"""Config flow for SOFAR ME3000SP Controller integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_EXPORT_ENTITY,
    CONF_IMPORT_ENTITY,
    CONF_PV_ENTITY,
    CONF_SOFAR_CHARGE_RATE_ENTITY,
    CONF_SOFAR_DISCHARGE_RATE_ENTITY,
    CONF_SOFAR_FAULT_ENTITY,
    CONF_SOFAR_MODE_ENTITY,
    CONF_SOFAR_SOC_ENTITY,
    DOMAIN,
)


class SofarME3000SPConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SOFAR ME3000SP Controller."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — entity selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate that entities exist
            for key, label in [
                (CONF_EXPORT_ENTITY, "Export entity"),
                (CONF_IMPORT_ENTITY, "Import entity"),
                (CONF_PV_ENTITY, "PV power entity"),
                (CONF_SOFAR_MODE_ENTITY, "SOFAR mode select entity"),
                (CONF_SOFAR_CHARGE_RATE_ENTITY, "SOFAR charge rate number entity"),
                (CONF_SOFAR_DISCHARGE_RATE_ENTITY, "SOFAR discharge rate number entity"),
                (CONF_SOFAR_SOC_ENTITY, "SOFAR battery SOC sensor entity"),
                (CONF_SOFAR_FAULT_ENTITY, "SOFAR fault messages sensor entity"),
            ]:
                if not user_input.get(key):
                    errors[key] = f"{label} is required"
                elif not user_input[key].startswith(("sensor.", "select.", "number.")):
                    errors[key] = f"Must be a valid entity ID (sensor.xxx, select.xxx, or number.xxx)"

            if not errors:
                return self.async_create_entry(
                    title="SOFAR ME3000SP Controller",
                    data=user_input,
                )

        # Build the form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_EXPORT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_IMPORT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_PV_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_SOFAR_MODE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="select")
                ),
                vol.Required(CONF_SOFAR_CHARGE_RATE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="number")
                ),
                vol.Required(CONF_SOFAR_DISCHARGE_RATE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="number")
                ),
                vol.Required(CONF_SOFAR_SOC_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_SOFAR_FAULT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
