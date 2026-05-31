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
    hass.states = MagicMock()
    hass.states.async_all = MagicMock(return_value=[])
    hass.states.get = MagicMock(return_value=None)
    # Provide a real event loop reference for asyncio.Queue in VoiceEngine
    import asyncio
    hass.loop = asyncio.get_event_loop()
    return hass


@pytest.fixture
def mock_storage(mock_hass):
    """Return a HouseVoiceStorage with mocked Store."""
    mock_store = MagicMock()
    mock_store.async_load = AsyncMock(return_value=None)
    mock_store.async_save = AsyncMock()

    with patch("custom_components.house_voice.storage.Store", return_value=mock_store):
        storage = HouseVoiceStorage(mock_hass)
        storage.store = mock_store
        yield storage


@pytest.fixture
def mock_groups(mock_hass):
    """Return a HouseVoiceGroups with mocked Store."""
    mock_store = MagicMock()
    mock_store.async_load = AsyncMock(return_value=None)
    mock_store.async_save = AsyncMock()

    with patch("custom_components.house_voice.groups.Store", return_value=mock_store):
        groups = HouseVoiceGroups(mock_hass)
        groups.store = mock_store
        groups.data = {}
        yield groups


@pytest.fixture
def mock_conditions(mock_hass):
    """Return a HouseVoiceConditions with mocked Store."""
    from custom_components.house_voice.storage import HouseVoiceConditions
    mock_store = MagicMock()
    mock_store.async_load = AsyncMock(return_value=None)
    mock_store.async_save = AsyncMock()

    with patch("custom_components.house_voice.storage.Store", return_value=mock_store):
        conditions = HouseVoiceConditions(mock_hass)
        conditions.store = mock_store
        conditions.data = {}
        yield conditions


@pytest.fixture
def mock_entry():
    """Return a minimal mock ConfigEntry with empty options."""
    entry = MagicMock()
    entry.options = {}
    return entry


@pytest.fixture
def mock_engine(mock_hass, mock_storage, mock_groups, mock_entry):
    """Return a VoiceEngine with mocked dependencies (v3.x signature)."""
    engine = VoiceEngine(mock_hass, mock_storage, mock_groups, mock_entry)
    # Register conditions in hass.data so _eval_conditions can find them
    mock_hass.data["house_voice"] = {"conditions": MagicMock()}
    mock_hass.data["house_voice"]["conditions"].data = {}
    mock_hass.data["house_voice"]["conditions"].get_condition = MagicMock(return_value=None)
    return engine


@pytest.fixture
def sample_event():
    """Return a standard voice event dict."""
    return {
        "message":    "Opvaskeren er færdig",
        "speakers":   ["media_player.kokken"],
        "priority":   "normal",
        "volume":     0.35,
        "conditions": [],
    }
