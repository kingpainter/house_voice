"""Tests for House Voice Manager diagnostics."""

from unittest.mock import MagicMock, patch
import pytest

from custom_components.house_voice.const import DOMAIN, VERSION
from custom_components.house_voice import HouseVoiceRuntimeData


@pytest.mark.asyncio
async def test_diagnostics_returns_correct_fields(mock_hass, mock_storage, sample_event):
    """Diagnostics returns version, event_ids, events_count, sensor_today, quiet_hours."""
    from custom_components.house_voice.diagnostics import async_get_config_entry_diagnostics

    mock_storage.data = {"ev1": sample_event, "ev2": sample_event}

    sensor = MagicMock()
    sensor._count = 5

    entry = MagicMock()
    entry.options = {}
    entry.runtime_data = HouseVoiceRuntimeData(
        storage=mock_storage,
        groups=MagicMock(),
        conditions=MagicMock(),
        engine=MagicMock(),
        sensor=sensor,
        execution_history=MagicMock(),)

    with patch("custom_components.house_voice.diagnostics.dt_util") as mock_dt:
        mock_dt.now.return_value = MagicMock(hour=14)  # Not quiet hours
        result = await async_get_config_entry_diagnostics(mock_hass, entry)

    assert result["version"] == VERSION
    assert result["events_count"] == 2
    assert set(result["event_ids"]) == {"ev1", "ev2"}
    assert result["sensor_today"] == 5
    assert result["quiet_hours_active"] is False


@pytest.mark.asyncio
async def test_diagnostics_quiet_hours_active(mock_hass, mock_storage):
    """Diagnostics correctly reports quiet hours as active at 23:00."""
    from custom_components.house_voice.diagnostics import async_get_config_entry_diagnostics

    mock_storage.data = {}

    entry = MagicMock()
    entry.options = {}
    entry.runtime_data = HouseVoiceRuntimeData(
        storage=mock_storage,
        groups=MagicMock(),
        conditions=MagicMock(),
        engine=MagicMock(),
        sensor=None,
        execution_history=MagicMock(),)

    with patch("custom_components.house_voice.voice_engine.dt_util") as mock_dt:
        mock_dt.now.return_value = MagicMock(hour=23)
        result = await async_get_config_entry_diagnostics(mock_hass, entry)

    assert result["quiet_hours_active"] is True


@pytest.mark.asyncio
async def test_diagnostics_handles_missing_storage(mock_hass):
    """Diagnostics handles missing storage gracefully."""
    from custom_components.house_voice.diagnostics import async_get_config_entry_diagnostics

    entry = MagicMock()
    entry.options = {}
    entry.runtime_data = HouseVoiceRuntimeData(
        storage=None,
        groups=MagicMock(),
        conditions=MagicMock(),
        engine=MagicMock(),
        sensor=None,
        execution_history=MagicMock(),)

    with patch("custom_components.house_voice.diagnostics.dt_util") as mock_dt:
        mock_dt.now.return_value = MagicMock(hour=10)
        result = await async_get_config_entry_diagnostics(mock_hass, entry)

    assert result["events_count"] == 0
    assert result["event_ids"] == []
    assert result["sensor_today"] == 0


@pytest.mark.asyncio
async def test_diagnostics_handles_missing_sensor(mock_hass, mock_storage):
    """Diagnostics handles missing sensor gracefully."""
    from custom_components.house_voice.diagnostics import async_get_config_entry_diagnostics

    mock_storage.data = {}
    entry = MagicMock()
    entry.options = {}
    entry.runtime_data = HouseVoiceRuntimeData(
        storage=mock_storage,
        groups=MagicMock(),
        conditions=MagicMock(),
        engine=MagicMock(),
        sensor=None,
        execution_history=MagicMock(),)

    with patch("custom_components.house_voice.diagnostics.dt_util") as mock_dt:
        mock_dt.now.return_value = MagicMock(hour=10)
        result = await async_get_config_entry_diagnostics(mock_hass, entry)

    assert result["sensor_today"] == 0
