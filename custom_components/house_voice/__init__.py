# VERSION = "3.2.0"
#              Registers services, WebSocket API, sidebar panel and sensor.

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import (
    DEFAULT_PRIORITY,
    DEFAULT_VOLUME,
    DOMAIN,
    PRIORITIES,
    SERVICE_ADD,
    SERVICE_DELETE,
    SERVICE_SAY,
    SERVICE_SAY_TEXT,
    SERVICE_TEST,
    VERSION,
)
from .groups import HouseVoiceGroups
from .panel import async_register_panel, async_unregister_panel
from .storage import HouseVoiceConditions, HouseVoiceStorage
from .voice_engine import VoiceEngine
from .websocket import async_register_websocket_commands

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up House Voice Manager from a config entry."""

    storage     = HouseVoiceStorage(hass)
    groups      = HouseVoiceGroups(hass)
    conditions  = HouseVoiceConditions(hass)

    try:
        await storage.async_load()
        await groups.async_load()
        await conditions.async_load()
    except Exception as err:
        raise ConfigEntryNotReady(
            f"House Voice: failed to load storage: {err}"
        ) from err

    engine = VoiceEngine(hass, storage, groups, entry)
    engine.start()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = {
        "storage":           storage,
        "groups":            groups,
        "conditions":        conditions,
        "engine":            engine,
        "sensor":            None,
        "_panel_registered": False,
    }

    # ── Load sensor platform ───────────────────────────────────────────────
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ── Register HA services ───────────────────────────────────────────────

    async def handle_say(call) -> None:
        """Handle house_voice.say – speak a stored event."""
        event_id = call.data["event"]
        try:
            await engine.say(event_id)
        except Exception as err:
            _LOGGER.error("House Voice: service 'say' failed for '%s': %s", event_id, err)
            raise

    async def handle_say_text(call) -> None:
        """Handle house_voice.say_text – speak an ad-hoc text message."""
        try:
            await engine.say_text(
                message=call.data["message"],
                speakers=call.data["speakers"],
                priority=call.data.get("priority", DEFAULT_PRIORITY),
                volume=call.data.get("volume", DEFAULT_VOLUME),
            )
        except Exception as err:
            _LOGGER.error("House Voice: service 'say_text' failed: %s", err)
            raise

    async def handle_add(call) -> None:
        """Handle house_voice.add_event – add or update a stored event."""
        event_id = call.data["event"]
        try:
            await storage.add_event(event_id, {
                "message":    call.data["message"],
                "speakers":   call.data["speakers"],
                "priority":   call.data.get("priority", DEFAULT_PRIORITY),
                "volume":     call.data.get("volume", DEFAULT_VOLUME),
                "conditions": call.data.get("conditions", []),
            })
            _LOGGER.info("House Voice: event '%s' saved via service", event_id)
        except Exception as err:
            _LOGGER.error("House Voice: service 'add_event' failed for '%s': %s", event_id, err)
            raise

    async def handle_delete(call) -> None:
        """Handle house_voice.delete_event – remove a stored event."""
        event_id = call.data["event"]
        try:
            await storage.delete_event(event_id)
            _LOGGER.info("House Voice: event '%s' deleted via service", event_id)
        except Exception as err:
            _LOGGER.error("House Voice: service 'delete_event' failed for '%s': %s", event_id, err)
            raise

    async def handle_test(call) -> None:
        """Handle house_voice.test_event – speak immediately, bypassing spam filter."""
        event_id = call.data["event"]
        try:
            await engine.say(event_id, bypass_spam=True)
        except Exception as err:
            _LOGGER.error("House Voice: service 'test_event' failed for '%s': %s", event_id, err)
            raise

    hass.services.async_register(
        DOMAIN, SERVICE_SAY, handle_say,
        schema=vol.Schema({vol.Required("event"): cv.string})
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SAY_TEXT, handle_say_text,
        schema=vol.Schema({
            vol.Required("message"):  cv.string,
            vol.Required("speakers"): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional("priority", default=DEFAULT_PRIORITY): vol.In(list(PRIORITIES)),
            vol.Optional("volume",   default=DEFAULT_VOLUME):   vol.All(vol.Coerce(float), vol.Range(min=0.05, max=1.0)),
        })
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ADD, handle_add,
        schema=vol.Schema({
            vol.Required("event"):    cv.string,
            vol.Required("message"):  cv.string,
            vol.Required("speakers"): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional("priority",  default=DEFAULT_PRIORITY): vol.In(list(PRIORITIES)),
            vol.Optional("volume",    default=DEFAULT_VOLUME):   vol.All(vol.Coerce(float), vol.Range(min=0.05, max=1.0)),
            vol.Optional("conditions", default=[]):              vol.All(cv.ensure_list, [cv.string]),
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

    _LOGGER.info("House Voice Manager v%s setup complete (conditions library loaded)", VERSION)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload House Voice Manager config entry."""

    data = hass.data.get(DOMAIN, {})

    # Stop queue worker
    engine = data.get("engine")
    if engine:
        await engine.stop()

    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    async_unregister_panel(hass)

    for service in (SERVICE_SAY, SERVICE_SAY_TEXT, SERVICE_ADD, SERVICE_DELETE, SERVICE_TEST):
        hass.services.async_remove(DOMAIN, service)

    hass.data.pop(DOMAIN, None)

    _LOGGER.info("House Voice Manager v%s unloaded", VERSION)
    return True
