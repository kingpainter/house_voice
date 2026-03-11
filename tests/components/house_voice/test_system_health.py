"""Tests for House Voice Manager system health."""

from unittest.mock import MagicMock
import pytest

from custom_components.house_voice.const import DOMAIN, VERSION


@pytest.mark.asyncio
async def test_system_health_info_returns_correct_fields(mock_hass, mock_storage, sample_event):
    """system_health_info returns version, events_count and storage_loaded."""
    from custom_components.house_voice.system_health import system_health_info

    mock_storage.data = {"ev1": sample_event, "ev2": sample_event}
    mock_hass.data[DOMAIN] = {"storage": mock_storage}

    result = await system_health_info(mock_hass)

    assert result["version"] == VERSION
    assert result["events_count"] == 2
    assert result["storage_loaded"] is True


@pytest.mark.asyncio
async def test_system_health_info_no_storage(mock_hass):
    """system_health_info handles missing storage gracefully."""
    from custom_components.house_voice.system_health import system_health_info

    mock_hass.data[DOMAIN] = {"storage": None}

    result = await system_health_info(mock_hass)

    assert result["events_count"] == 0
    assert result["storage_loaded"] is False


@pytest.mark.asyncio
async def test_system_health_info_empty_domain_data(mock_hass):
    """system_health_info handles missing DOMAIN data gracefully."""
    from custom_components.house_voice.system_health import system_health_info

    mock_hass.data = {}

    result = await system_health_info(mock_hass)

    assert result["version"] == VERSION
    assert result["events_count"] == 0
    assert result["storage_loaded"] is False


def test_async_register_calls_register_info(mock_hass):
    """async_register calls register.async_register_info with system_health_info."""
    from custom_components.house_voice.system_health import async_register, system_health_info

    register = MagicMock()
    async_register(mock_hass, register)

    register.async_register_info.assert_called_once_with(system_health_info)
