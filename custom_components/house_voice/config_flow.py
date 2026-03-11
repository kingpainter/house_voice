# VERSION = "2.0.0"
# File: config_flow.py
# Description: Config Flow for House Voice Manager.
#              Appears in the "Add Integration" page.
#              No fields – user just clicks Submit to install.
#              Prevents duplicate entries.

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN

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
