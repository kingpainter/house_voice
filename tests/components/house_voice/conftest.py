"""Shared fixtures for House Voice Manager tests."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from homeassistant.core import HomeAssistant

from custom_components.house_voice.groups import HouseVoiceGroups
from custom_components.house_voice.storage import HouseVoiceStorage
from custom_components.house_voice.voice_engine import VoiceEngine


@pytest.fixture
def mock_hass():
    """Return a mocked HomeAssistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.data = {}
    # Provide a real event loop reference for asyncio.Queue in VoiceEngine
    import asyncio
    hass.loop = asyncio.get_event_loop()
    return hass


@pytest.fixture
def mock_storage(mock_hass):
    """Return a HouseVoiceStorage with mocked Store."""
    with patch("custom_components.house_voice.storage.Store") as mock_store_cls:
        mock_store = MagicMock()
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()
        mock_store_cls.return_value = mock_store

        storage = HouseVoiceStorage(mock_hass)
        storage.store = mock_store
        return storage


@pytest.fixture
def mock_groups(mock_hass):
    """Return a HouseVoiceGroups with mocked Store."""
    with patch("custom_components.house_voice.groups.Store") as mock_store_cls:
        mock_store = MagicMock()
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()
        mock_store_cls.return_value = mock_store

        groups = HouseVoiceGroups(mock_hass)
        groups.store = mock_store
        groups.data = {}
        return groups


@pytest.fixture
def mock_entry():
    """Return a minimal mock ConfigEntry with empty options."""
    entry = MagicMock()
    entry.options = {}
    return entry


@pytest.fixture
def mock_engine(mock_hass, mock_storage, mock_groups, mock_entry):
    """Return a VoiceEngine with mocked dependencies (v2.2.0 signature)."""
    return VoiceEngine(mock_hass, mock_storage, mock_groups, mock_entry)


@pytest.fixture
def sample_event():
    """Return a standard voice event dict."""
    return {
        "message":   "Opvaskeren er færdig",
        "speakers":  ["media_player.kokken"],
        "priority":  "normal",
        "volume":    0.35,
        "condition": "",
    }
