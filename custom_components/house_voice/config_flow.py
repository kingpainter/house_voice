# VERSION = "3.1.1"
# File: config_flow.py
# Description: Config Flow + Options Flow for House Voice Manager.
#              Config flow: no fields – user just clicks Submit to install.
#              Options flow: configure quiet hours start/end time.

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_QUIET_END,
    CONF_QUIET_START,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_START,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class HouseVoiceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for House Voice Manager."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Show a confirm dialog – no fields, just a Submit button."""

        # Prevent adding the integration more than once
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        # User clicked Submit → create the entry immediately
        if user_input is not None:
            _LOGGER.info("House Voice Manager: creating config entry")
            return self.async_create_entry(title="House Voice Manager", data={})

        # First visit → show empty form (HA renders a Submit button automatically)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return HouseVoiceOptionsFlow(config_entry)


class HouseVoiceOptionsFlow(OptionsFlow):
    """Handle House Voice options – quiet hours configuration."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Show the options form."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_start = self._config_entry.options.get(CONF_QUIET_START, DEFAULT_QUIET_START)
        current_end   = self._config_entry.options.get(CONF_QUIET_END,   DEFAULT_QUIET_END)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_QUIET_START, default=current_start): vol.All(
                    int, vol.Range(min=0, max=23)
                ),
                vol.Required(CONF_QUIET_END, default=current_end): vol.All(
                    int, vol.Range(min=0, max=23)
                ),
            }),
            description_placeholders={
                "quiet_start": str(current_start),
                "quiet_end":   str(current_end),
            },
        )
