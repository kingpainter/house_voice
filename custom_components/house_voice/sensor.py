# VERSION = "3.3.0"
# File: sensor.py
# Description: Statistics sensor for House Voice Manager – counts TTS messages today
#              v3.3.0: registers itself on entry.runtime_data instead of hass.data[DOMAIN].

from __future__ import annotations

import logging
from datetime import date

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up House Voice sensor from config entry."""
    sensor = HouseVoiceTodaySensor()
    if getattr(entry, "runtime_data", None) is not None:
        entry.runtime_data.sensor = sensor
    async_add_entities([sensor])


class HouseVoiceTodaySensor(SensorEntity):
    """Sensor that counts how many TTS messages have been spoken today."""

    _attr_name = "House Voice Today"
    _attr_unique_id = "house_voice_today"
    _attr_icon = "mdi:counter"
    _attr_native_unit_of_measurement = "messages"

    def __init__(self) -> None:
        self._count: int = 0
        self._today: date = date.today()

    @property
    def native_value(self) -> int:
        return self._count

    def increment(self) -> None:
        """Increment counter – resets automatically if date has changed."""
        today = date.today()
        if today != self._today:
            self._count = 0
            self._today = today
        self._count += 1
        self.async_write_ha_state()
