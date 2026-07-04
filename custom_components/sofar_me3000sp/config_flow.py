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


def _build_schema(defaults: dict[str, str] | None = None) -> vol.Schema:
    """Build the entity selection schema, optionally with default values."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_EXPORT_ENTITY, default=defaults.get(CONF_EXPORT_ENTITY)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_IMPORT_ENTITY, default=defaults.get(CONF_IMPORT_ENTITY)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_PV_ENTITY, default=defaults.get(CONF_PV_ENTITY)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_SOFAR_MODE_ENTITY, default=defaults.get(CONF_SOFAR_MODE_ENTITY)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="select")
            ),
            vol.Required(CONF_SOFAR_CHARGE_RATE_ENTITY, default=defaults.get(CONF_SOFAR_CHARGE_RATE_ENTITY)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="number")
            ),
            vol.Required(CONF_SOFAR_DISCHARGE_RATE_ENTITY, default=defaults.get(CONF_SOFAR_DISCHARGE_RATE_ENTITY)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="number")
            ),
            vol.Required(CONF_SOFAR_SOC_ENTITY, default=defaults.get(CONF_SOFAR_SOC_ENTITY)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_SOFAR_FAULT_ENTITY, default=defaults.get(CONF_SOFAR_FAULT_ENTITY)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
        }
    )


def _validate_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate user input; values map to keys in translations config.error."""
    errors: dict[str, str] = {}
    for key in (
        CONF_EXPORT_ENTITY,
        CONF_IMPORT_ENTITY,
        CONF_PV_ENTITY,
        CONF_SOFAR_MODE_ENTITY,
        CONF_SOFAR_CHARGE_RATE_ENTITY,
        CONF_SOFAR_DISCHARGE_RATE_ENTITY,
        CONF_SOFAR_SOC_ENTITY,
        CONF_SOFAR_FAULT_ENTITY,
    ):
        value = user_input.get(key, "")
        if not value.startswith(("sensor.", "select.", "number.")):
            errors[key] = "must_be_entity_id"
    return errors


class SofarME3000SPConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SOFAR ME3000SP Controller."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — entity selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_input(user_input)

            if not errors:
                # Check for duplicate entries with the same SOFAR mode entity
                mode_entity = user_input[CONF_SOFAR_MODE_ENTITY]
                for existing_entry in self._async_current_entries():
                    if existing_entry.data.get(CONF_SOFAR_MODE_ENTITY) == mode_entity:
                        errors[CONF_SOFAR_MODE_ENTITY] = "already_configured"
                        break
                else:
                    return self.async_create_entry(
                        title="SOFAR ME3000SP Controller",
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_input(user_input)

            if not errors:
                # Check for duplicates (excluding the entry being reconfigured)
                mode_entity = user_input[CONF_SOFAR_MODE_ENTITY]
                for existing_entry in self._async_current_entries():
                    if existing_entry.entry_id == entry.entry_id:
                        continue
                    if existing_entry.data.get(CONF_SOFAR_MODE_ENTITY) == mode_entity:
                        errors[CONF_SOFAR_MODE_ENTITY] = "already_configured"
                        break
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        data={**entry.data, **user_input},
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_schema(defaults=dict(entry.data)),
            errors=errors,
        )
