# VERSION = "2.0.0"
# File: websocket.py
# Description: WebSocket API for the House Voice Manager panel.
#              Exposes get_events, get_media_players, save_event,
#              delete_event and test_event to the frontend panel.

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register all WebSocket commands for the House Voice panel."""
    websocket_api.async_register_command(hass, ws_get_events)
    websocket_api.async_register_command(hass, ws_get_media_players)
    websocket_api.async_register_command(hass, ws_save_event)
    websocket_api.async_register_command(hass, ws_delete_event)
    websocket_api.async_register_command(hass, ws_test_event)
    _LOGGER.info("House Voice WebSocket API registered (5 commands)")


def _get_storage(hass: HomeAssistant):
    return hass.data.get(DOMAIN, {}).get("storage")


def _get_engine(hass: HomeAssistant):
    return hass.data.get(DOMAIN, {}).get("engine")


# ── Get all voice events ───────────────────────────────────────────────────────

@websocket_api.websocket_command({"type": f"{DOMAIN}/get_events"})
@callback
def ws_get_events(hass: HomeAssistant, connection, msg):
    """Return all stored voice events."""
    storage = _get_storage(hass)
    if not storage:
        connection.send_error(msg["id"], "not_ready", "House Voice storage not ready")
        return
    try:
        connection.send_result(msg["id"], {"events": storage.data})
    except Exception as err:
        connection.send_error(msg["id"], "unknown_error", str(err))


# ── Get all media_player entities from HA ─────────────────────────────────────

@websocket_api.websocket_command({"type": f"{DOMAIN}/get_media_players"})
@callback
def ws_get_media_players(hass: HomeAssistant, connection, msg):
    """Return all media_player entities available in Home Assistant."""
    try:
        players = []
        for state in hass.states.async_all("media_player"):
            friendly = state.attributes.get("friendly_name") or state.entity_id
            players.append({
                "entity_id":    state.entity_id,
                "friendly_name": friendly,
            })
        players.sort(key=lambda x: x["friendly_name"].lower())
        connection.send_result(msg["id"], {"media_players": players})
    except Exception as err:
        connection.send_error(msg["id"], "unknown_error", str(err))


# ── Save (add or update) a voice event ────────────────────────────────────────

@websocket_api.websocket_command({
    "type": f"{DOMAIN}/save_event",
    vol.Required("event_id"):  str,
    vol.Required("message"):   str,
    vol.Required("speakers"):  list,
    vol.Optional("priority", default="normal"): str,
    vol.Optional("volume",   default=0.35):     float,
})
@websocket_api.async_response
async def ws_save_event(hass: HomeAssistant, connection, msg):
    """Save (create or update) a voice event."""
    storage = _get_storage(hass)
    if not storage:
        connection.send_error(msg["id"], "not_ready", "House Voice storage not ready")
        return
    try:
        event_id = msg["event_id"].strip()
        if not event_id:
            connection.send_error(msg["id"], "invalid_input", "event_id cannot be empty")
            return
        if not msg["message"].strip():
            connection.send_error(msg["id"], "invalid_input", "message cannot be empty")
            return
        if not msg["speakers"]:
            connection.send_error(msg["id"], "invalid_input", "at least one speaker is required")
            return
        if msg["priority"] not in ("info", "normal", "critical"):
            connection.send_error(msg["id"], "invalid_input", "priority must be info, normal or critical")
            return

        event_data = {
            "message":  msg["message"].strip(),
            "speakers": msg["speakers"],
            "priority": msg["priority"],
            "volume":   round(float(msg["volume"]), 2),
        }
        await storage.add_event(event_id, event_data)
        _LOGGER.info("House Voice: saved event '%s'", event_id)
        connection.send_result(msg["id"], {"success": True, "event_id": event_id})
    except Exception as err:
        _LOGGER.error("House Voice: error saving event: %s", err)
        connection.send_error(msg["id"], "unknown_error", str(err))


# ── Delete a voice event ───────────────────────────────────────────────────────

@websocket_api.websocket_command({
    "type": f"{DOMAIN}/delete_event",
    vol.Required("event_id"): str,
})
@websocket_api.async_response
async def ws_delete_event(hass: HomeAssistant, connection, msg):
    """Delete a voice event by event_id."""
    storage = _get_storage(hass)
    if not storage:
        connection.send_error(msg["id"], "not_ready", "House Voice storage not ready")
        return
    try:
        event_id = msg["event_id"].strip()
        if event_id not in storage.data:
            connection.send_error(msg["id"], "not_found", f"Event '{event_id}' not found")
            return
        await storage.delete_event(event_id)
        _LOGGER.info("House Voice: deleted event '%s'", event_id)
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        _LOGGER.error("House Voice: error deleting event: %s", err)
        connection.send_error(msg["id"], "unknown_error", str(err))


# ── Test a voice event ─────────────────────────────────────────────────────────

@websocket_api.websocket_command({
    "type": f"{DOMAIN}/test_event",
    vol.Required("event_id"): str,
})
@websocket_api.async_response
async def ws_test_event(hass: HomeAssistant, connection, msg):
    """Trigger a voice event immediately (test playback)."""
    engine = _get_engine(hass)
    if not engine:
        connection.send_error(msg["id"], "not_ready", "House Voice engine not ready")
        return
    try:
        event_id = msg["event_id"].strip()
        await engine.say(event_id)
        _LOGGER.info("House Voice: tested event '%s'", event_id)
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        _LOGGER.error("House Voice: error testing event '%s': %s", msg["event_id"], err)
        connection.send_error(msg["id"], "unknown_error", str(err))
