"""Shared fixtures for House Voice Manager tests."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from homeassistant.core import HomeAssistant

from custom_components.house_voice.storage import HouseVoiceStorage
from custom_components.house_voice.voice_engine import VoiceEngine


@pytest.fixture
def mock_hass():
    """Return a mocked HomeAssistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.data = {}
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
def mock_engine(mock_hass, mock_storage):
    """Return a VoiceEngine with mocked dependencies."""
    return VoiceEngine(mock_hass, mock_storage)


@pytest.fixture
def sample_event():
    """Return a standard voice event dict."""
    return {
        "message":  "Opvaskeren er færdig",
        "speakers": ["media_player.kokken"],
        "priority": "normal",
        "volume":   0.35,
    }
