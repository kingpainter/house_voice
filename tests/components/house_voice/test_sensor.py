"""Tests for HouseVoiceTodaySensor."""

from datetime import date
from unittest.mock import MagicMock, patch
import pytest

from custom_components.house_voice.sensor import HouseVoiceTodaySensor


def test_initial_state():
    """Sensor starts at 0."""
    sensor = HouseVoiceTodaySensor()
    assert sensor.native_value == 0


def test_increment():
    """Increment increases counter by 1."""
    sensor = HouseVoiceTodaySensor()
    sensor.async_write_ha_state = MagicMock()
    sensor.increment()
    assert sensor.native_value == 1


def test_increment_multiple():
    """Multiple increments accumulate correctly."""
    sensor = HouseVoiceTodaySensor()
    sensor.async_write_ha_state = MagicMock()
    for _ in range(5):
        sensor.increment()
    assert sensor.native_value == 5


def test_increment_resets_at_midnight():
    """Counter resets to 1 when date has changed."""
    sensor = HouseVoiceTodaySensor()
    sensor.async_write_ha_state = MagicMock()

    # Simulate 3 messages yesterday
    sensor._count = 3
    sensor._today = date(2026, 3, 10)

    # Now it's a new day
    with patch("custom_components.house_voice.sensor.date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 11)
        sensor.increment()

    assert sensor.native_value == 1
    assert sensor._today == date(2026, 3, 11)


def test_sensor_attributes():
    """Sensor has correct name, icon and unit."""
    sensor = HouseVoiceTodaySensor()
    assert sensor._attr_name == "House Voice Today"
    assert sensor._attr_unique_id == "house_voice_today"
    assert sensor._attr_icon == "mdi:counter"
    assert sensor._attr_native_unit_of_measurement == "messages"


def test_write_ha_state_called_on_increment():
    """async_write_ha_state is called after each increment."""
    sensor = HouseVoiceTodaySensor()
    sensor.async_write_ha_state = MagicMock()
    sensor.increment()
    sensor.async_write_ha_state.assert_called_once()
