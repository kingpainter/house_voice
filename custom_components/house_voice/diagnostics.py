# VERSION = "2.0.0"
# File: diagnostics.py
# Description: Diagnostics support for House Voice Manager

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN, VERSION


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    data = hass.data.get(DOMAIN, {})
    storage = data.get("storage")
    sensor = data.get("sensor")

    event_ids = list(storage.data.keys()) if storage else []
    events_count = len(event_ids)

    # Quiet hours: 22:00–07:00
    hour = dt_util.now().hour
    quiet_hours_active = hour >= 22 or hour < 7

    # Sensor state
    sensor_today = sensor._count if sensor else 0

    return {
        "version": VERSION,
        "events_count": events_count,
        "event_ids": event_ids,
        "sensor_today": sensor_today,
        "quiet_hours_active": quiet_hours_active,
    }
