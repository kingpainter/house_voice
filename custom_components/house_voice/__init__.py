# VERSION = "2.0.0"
# File: __init__.py
# Description: House Voice Manager setup via config entry (UI-based, no YAML).
#              Registers services, WebSocket API, sidebar panel and sensor.

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, SERVICE_SAY, SERVICE_ADD, SERVICE_DELETE, SERVICE_TEST
from .panel import async_register_panel, async_unregister_panel
from .storage import HouseVoiceStorage
from .voice_engine import VoiceEngine
from .websocket import async_register_websocket_commands

_LOGGER = logging.getLogger(__name__)

# Tell HA this integration is set up via config entries only – no YAML setup
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up House Voice Manager from a config entry."""

    storage = HouseVoiceStorage(hass)

    try:
        await storage.async_load()
    except Exception as err:
        raise ConfigEntryNotReady(
            f"House Voice: failed to load storage: {err}"
        ) from err

    engine = VoiceEngine(hass, storage)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = {
        "storage":           storage,
        "engine":            engine,
        "sensor":            None,
        "_panel_registered": False,
    }

    # ── Load sensor platform ───────────────────────────────────────────────
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ── Register HA services ───────────────────────────────────────────────

    async def handle_say(call):
        event_id = call.data["event"]
        try:
            await engine.say(event_id)
        except Exception as err:
            _LOGGER.error("House Voice: service 'say' failed for '%s': %s", event_id, err)
            raise

    async def handle_add(call):
        event_id = call.data["event"]
        try:
            await storage.add_event(event_id, {
                "message":  call.data["message"],
                "speakers": call.data["speakers"],
                "priority": call.data.get("priority", "normal"),
                "volume":   call.data.get("volume", 0.35),
            })
            _LOGGER.info("House Voice: event '%s' saved via service", event_id)
        except Exception as err:
            _LOGGER.error("House Voice: service 'add_event' failed for '%s': %s", event_id, err)
            raise

    async def handle_delete(call):
        event_id = call.data["event"]
        try:
            await storage.delete_event(event_id)
            _LOGGER.info("House Voice: event '%s' deleted via service", event_id)
        except Exception as err:
            _LOGGER.error("House Voice: service 'delete_event' failed for '%s': %s", event_id, err)
            raise

    async def handle_test(call):
        event_id = call.data["event"]
        try:
            await engine.say(event_id)
        except Exception as err:
            _LOGGER.error("House Voice: service 'test_event' failed for '%s': %s", event_id, err)
            raise

    hass.services.async_register(
        DOMAIN, SERVICE_SAY, handle_say,
        schema=vol.Schema({vol.Required("event"): cv.string})
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ADD, handle_add,
        schema=vol.Schema({
            vol.Required("event"):    cv.string,
            vol.Required("message"):  cv.string,
            vol.Required("speakers"): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional("priority", default="normal"): vol.In(["info", "normal", "critical"]),
            vol.Optional("volume",   default=0.35): vol.All(vol.Coerce(float), vol.Range(min=0.05, max=1.0)),
        })
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE, handle_delete,
        schema=vol.Schema({vol.Required("event"): cv.string})
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TEST, handle_test,
        schema=vol.Schema({vol.Required("event"): cv.string})
    )

    # ── Register WebSocket API ─────────────────────────────────────────────
    async_register_websocket_commands(hass)

    # ── Register sidebar panel ─────────────────────────────────────────────
    await async_register_panel(hass)

    _LOGGER.info("House Voice Manager v2.0.0 setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload House Voice Manager config entry."""

    # Unload sensor platform
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Remove sidebar panel
    async_unregister_panel(hass)

    # Remove services
    for service in (SERVICE_SAY, SERVICE_ADD, SERVICE_DELETE, SERVICE_TEST):
        hass.services.async_remove(DOMAIN, service)

    # Clear runtime data
    hass.data.pop(DOMAIN, None)

    _LOGGER.info("House Voice Manager unloaded")
    return True
