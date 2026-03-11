"""Tests for House Voice Manager setup, reload and unload."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from homeassistant.const import Platform

from custom_components.house_voice.const import (
    DOMAIN,
    SERVICE_SAY,
    SERVICE_ADD,
    SERVICE_DELETE,
    SERVICE_TEST,
)


@pytest.fixture
def mock_config_entry():
    """Return a minimal mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    return entry


@pytest.mark.asyncio
async def test_async_setup_entry_registers_services(mock_hass, mock_config_entry):
    """Setup registers all 4 HA services."""
    with patch("custom_components.house_voice.HouseVoiceStorage") as mock_storage_cls, \
         patch("custom_components.house_voice.VoiceEngine"), \
         patch("custom_components.house_voice.async_register_panel", new=AsyncMock()), \
         patch("custom_components.house_voice.async_register_websocket_commands"), \
         patch.object(mock_hass.config_entries, "async_forward_entry_setups", new=AsyncMock()):

        mock_storage = MagicMock()
        mock_storage.async_load = AsyncMock()
        mock_storage.data = {}
        mock_storage_cls.return_value = mock_storage

        from custom_components.house_voice import async_setup_entry
        result = await async_setup_entry(mock_hass, mock_config_entry)

    assert result is True
    assert mock_hass.services.async_register.call_count == 4

    registered = {
        call[0][1]
        for call in mock_hass.services.async_register.call_args_list
    }
    assert SERVICE_SAY    in registered
    assert SERVICE_ADD    in registered
    assert SERVICE_DELETE in registered
    assert SERVICE_TEST   in registered


@pytest.mark.asyncio
async def test_async_setup_entry_stores_data(mock_hass, mock_config_entry):
    """Setup stores engine and storage in hass.data."""
    with patch("custom_components.house_voice.HouseVoiceStorage") as mock_storage_cls, \
         patch("custom_components.house_voice.VoiceEngine") as mock_engine_cls, \
         patch("custom_components.house_voice.async_register_panel", new=AsyncMock()), \
         patch("custom_components.house_voice.async_register_websocket_commands"), \
         patch.object(mock_hass.config_entries, "async_forward_entry_setups", new=AsyncMock()):

        mock_storage = MagicMock()
        mock_storage.async_load = AsyncMock()
        mock_storage.data = {}
        mock_storage_cls.return_value = mock_storage

        mock_engine = MagicMock()
        mock_engine_cls.return_value = mock_engine

        from custom_components.house_voice import async_setup_entry
        await async_setup_entry(mock_hass, mock_config_entry)

    assert mock_hass.data[DOMAIN]["storage"] is mock_storage
    assert mock_hass.data[DOMAIN]["engine"] is mock_engine


@pytest.mark.asyncio
async def test_async_unload_entry_removes_services(mock_hass, mock_config_entry):
    """Unload removes all 4 services and clears hass.data."""
    mock_hass.data[DOMAIN] = {
        "storage": MagicMock(),
        "engine":  MagicMock(),
        "sensor":  None,
        "_panel_registered": True,
    }
    mock_hass.services.async_remove = MagicMock()

    with patch("custom_components.house_voice.async_unregister_panel"), \
         patch.object(mock_hass.config_entries, "async_unload_platforms", new=AsyncMock(return_value=True)):

        from custom_components.house_voice import async_unload_entry
        result = await async_unload_entry(mock_hass, mock_config_entry)

    assert result is True
    assert mock_hass.services.async_remove.call_count == 4
    assert DOMAIN not in mock_hass.data
