# VERSION = "2.0.0"
# File: system_health.py
# Description: System Health info for House Voice Manager

from homeassistant.components.system_health import SystemHealthRegistration
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION


async def async_register(
    hass: HomeAssistant, register: SystemHealthRegistration
) -> None:
    """Register House Voice system health info."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict:
    """Return system health info."""
    data = hass.data.get(DOMAIN, {})
    storage = data.get("storage")

    events_count = len(storage.data) if storage else 0
    storage_loaded = storage is not None

    return {
        "version": VERSION,
        "events_count": events_count,
        "storage_loaded": storage_loaded,
    }
