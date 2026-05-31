# VERSION = "3.2.0"
# File: system_health.py
# Description: System Health info for House Voice Manager

from homeassistant.components.system_health import SystemHealthRegistration
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION


def async_register(
    hass: HomeAssistant, register: SystemHealthRegistration
) -> None:
    """Register House Voice system health info (synchronous – required by HA)."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict:
    """Return system health info."""
    data    = hass.data.get(DOMAIN, {})
    storage = data.get("storage")
    groups  = data.get("groups")
    engine  = data.get("engine")

    return {
        "version":        VERSION,
        "events_count":   len(storage.data) if storage else 0,
        "groups_count":   len(groups.data)  if groups  else 0,
        "storage_loaded": storage is not None,
        "queue_size":     engine._queue.qsize() if engine else 0,
    }
