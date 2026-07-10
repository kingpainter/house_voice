"""Shared fixtures for House Voice Manager tests.

v3.3.0: hass.data[DOMAIN] was replaced by entry.runtime_data. mock_entry now
auto-registers itself into mock_hass.config_entries.async_entries(DOMAIN), so
any test using both mock_hass and mock_entry gets automatic entry resolution
for websocket.py / system_health.py / panel.py, which only receive `hass`.
"""

from types import SimpleNamespace
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
    # No config entries registered by default; mock_entry wires this up when used.
    hass.config_entries = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
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
def mock_entry(mock_hass):
    """Return a minimal mock ConfigEntry, auto-wired into hass.config_entries.

    Any test that requests both mock_hass and mock_entry automatically gets
    hass.config_entries.async_entries(DOMAIN) -> [mock_entry], matching how
    websocket.py / system_health.py / panel.py resolve the single House Voice
    entry in production.
    """
    entry = MagicMock()
    entry.options = {}
    entry.runtime_data = None
    mock_hass.config_entries.async_entries = MagicMock(return_value=[entry])
    return entry


@pytest.fixture
def make_runtime():
    """Factory fixture: build a lightweight entry.runtime_data stand-in.

    Usage: mock_entry.runtime_data = make_runtime(storage=mock_storage)
    Any field not passed defaults to None (or False for panel_registered).
    """
    def _make(**kwargs):
        defaults = {
            "storage": None,
            "groups": None,
            "conditions": None,
            "engine": None,
            "sensor": None,
            "panel_registered": False,
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)
    return _make


@pytest.fixture
def mock_engine(mock_hass, mock_storage, mock_groups, mock_conditions, mock_entry, make_runtime):
    """Return a VoiceEngine with mocked dependencies (v3.3.0: entry.runtime_data)."""
    engine = VoiceEngine(mock_hass, mock_storage, mock_groups, mock_entry)

    # Wire up entry.runtime_data so _eval_conditions / _increment_sensor can find
    # the conditions library and sensor, mirroring production's entry.runtime_data.
    mock_conditions.get_condition = MagicMock(return_value=None)
    mock_entry.runtime_data = make_runtime(
        storage=mock_storage,
        groups=mock_groups,
        conditions=mock_conditions,
        engine=engine,
    )
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
