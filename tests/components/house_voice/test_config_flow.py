"""Tests for House Voice Manager config flow."""

from unittest.mock import AsyncMock, patch
import pytest

from homeassistant.data_entry_flow import FlowResultType

from custom_components.house_voice.const import DOMAIN


@pytest.mark.asyncio
async def test_step_user_shows_form(mock_hass):
    """First visit to user step shows an empty form."""
    from custom_components.house_voice.config_flow import HouseVoiceConfigFlow

    flow = HouseVoiceConfigFlow()
    flow.hass = mock_hass

    with patch.object(flow, "async_set_unique_id", new=AsyncMock()), \
         patch.object(flow, "_abort_if_unique_id_configured"):

        result = await flow.async_step_user(user_input=None)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_step_user_submit_creates_entry(mock_hass):
    """Submitting the form creates a config entry."""
    from custom_components.house_voice.config_flow import HouseVoiceConfigFlow

    flow = HouseVoiceConfigFlow()
    flow.hass = mock_hass

    with patch.object(flow, "async_set_unique_id", new=AsyncMock()), \
         patch.object(flow, "_abort_if_unique_id_configured"), \
         patch.object(flow, "async_create_entry", return_value={
             "type": FlowResultType.CREATE_ENTRY,
             "title": "House Voice Manager",
             "data": {},
         }):

        result = await flow.async_step_user(user_input={})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "House Voice Manager"
    assert result["data"] == {}


@pytest.mark.asyncio
async def test_step_user_abort_if_already_configured(mock_hass):
    """Config flow aborts if integration is already configured."""
    from custom_components.house_voice.config_flow import HouseVoiceConfigFlow
    from homeassistant.exceptions import HomeAssistantError

    flow = HouseVoiceConfigFlow()
    flow.hass = mock_hass

    def raise_abort():
        raise HomeAssistantError("already_configured")

    with patch.object(flow, "async_set_unique_id", new=AsyncMock()), \
         patch.object(flow, "_abort_if_unique_id_configured", side_effect=raise_abort):

        with pytest.raises(HomeAssistantError, match="already_configured"):
            await flow.async_step_user(user_input=None)
