# VERSION = "3.3.0"
# File: diagnostics.py
# Description: Diagnostics support for House Voice Manager
#              v3.3.0: reads from entry.runtime_data instead of hass.data[DOMAIN].

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    CONF_QUIET_END,
    CONF_QUIET_START,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_START,
    VERSION,
)
from .voice_engine import _is_quiet_hours


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    runtime = getattr(entry, "runtime_data", None)
    storage = getattr(runtime, "storage", None)
    groups  = getattr(runtime, "groups", None)
    sensor  = getattr(runtime, "sensor", None)
    engine  = getattr(runtime, "engine", None)

    event_ids   = list(storage.data.keys()) if storage else []
    group_ids   = list(groups.data.keys())  if groups  else []
    sensor_today = sensor._count if sensor else 0
    history_count = len(engine.get_history()) if engine else 0

    quiet_start = int(entry.options.get(CONF_QUIET_START, DEFAULT_QUIET_START))
    quiet_end   = int(entry.options.get(CONF_QUIET_END,   DEFAULT_QUIET_END))
    quiet_hours_active = _is_quiet_hours(quiet_start, quiet_end)

    return {
        "version":            VERSION,
        "events_count":       len(event_ids),
        "event_ids":          event_ids,
        "groups_count":       len(group_ids),
        "group_ids":          group_ids,
        "sensor_today":       sensor_today,
        "history_count":      history_count,
        "quiet_hours_start":  quiet_start,
        "quiet_hours_end":    quiet_end,
        "quiet_hours_active": quiet_hours_active,
    }
