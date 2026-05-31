# VERSION = "3.2.0"
# File: websocket.py
# Description: WebSocket API for the House Voice Manager panel.
#              Commands: get_events, get_media_players, save_event, delete_event,
#              test_event, get_groups, save_group, delete_group, get_history,
#              get_conditions, save_condition, delete_condition.

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN, PRIORITIES

_LOGGER = logging.getLogger(__name__)


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register all WebSocket commands for the House Voice panel."""
    websocket_api.async_register_command(hass, ws_get_events)
    websocket_api.async_register_command(hass, ws_get_media_players)
    websocket_api.async_register_command(hass, ws_save_event)
    websocket_api.async_register_command(hass, ws_delete_event)
    websocket_api.async_register_command(hass, ws_test_event)
    websocket_api.async_register_command(hass, ws_get_groups)
    websocket_api.async_register_command(hass, ws_save_group)
    websocket_api.async_register_command(hass, ws_delete_group)
    websocket_api.async_register_command(hass, ws_get_history)
    websocket_api.async_register_command(hass, ws_get_conditions)
    websocket_api.async_register_command(hass, ws_save_condition)
    websocket_api.async_register_command(hass, ws_delete_condition)
    _LOGGER.info("House Voice WebSocket API registered (12 commands)")


def _get_storage(hass: HomeAssistant):
    """Return storage instance or None."""
    return hass.data.get(DOMAIN, {}).get("storage")


def _get_groups(hass: HomeAssistant):
    """Return groups instance or None."""
    return hass.data.get(DOMAIN, {}).get("groups")


def _get_conditions(hass: HomeAssistant):
    """Return conditions instance or None."""
    return hass.data.get(DOMAIN, {}).get("conditions")


def _get_engine(hass: HomeAssistant):
    """Return engine instance or None."""
    return hass.data.get(DOMAIN, {}).get("engine")


# ── Get all voice events ───────────────────────────────────────────────────────

@websocket_api.websocket_command({"type": f"{DOMAIN}/get_events"})
@callback
def ws_get_events(hass: HomeAssistant, connection, msg) -> None:
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
def ws_get_media_players(hass: HomeAssistant, connection, msg) -> None:
    """Return all media_player entities available in Home Assistant."""
    try:
        players = [
            {
                "entity_id":     state.entity_id,
                "friendly_name": state.attributes.get("friendly_name") or state.entity_id,
            }
            for state in hass.states.async_all("media_player")
        ]
        players.sort(key=lambda x: x["friendly_name"].lower())
        connection.send_result(msg["id"], {"media_players": players})
    except Exception as err:
        connection.send_error(msg["id"], "unknown_error", str(err))


# ── Save (add or update) a voice event ────────────────────────────────────────

@websocket_api.websocket_command({
    "type":                                        f"{DOMAIN}/save_event",
    vol.Required("event_id"):                      str,
    vol.Required("message"):                       str,
    vol.Required("speakers"):                      vol.All(list, vol.Length(min=1)),
    vol.Optional("priority",  default="normal"):   vol.In(PRIORITIES),
    vol.Optional("volume",    default=0.35):       vol.All(float, vol.Range(min=0.05, max=1.0)),
    vol.Optional("conditions", default=[]):        list,
})
@websocket_api.async_response
async def ws_save_event(hass: HomeAssistant, connection, msg) -> None:
    """Save (create or update) a voice event."""
    storage = _get_storage(hass)
    if not storage:
        connection.send_error(msg["id"], "not_ready", "House Voice storage not ready")
        return

    event_id = msg["event_id"].strip()
    if not event_id:
        connection.send_error(msg["id"], "invalid_input", "event_id cannot be empty")
        return

    message = msg["message"].strip()
    if not message:
        connection.send_error(msg["id"], "invalid_input", "message cannot be empty")
        return

    speakers = msg.get("speakers", [])
    if not speakers:
        connection.send_error(msg["id"], "invalid_input", "at least one speaker is required")
        return

    priority = msg.get("priority", "normal")
    if priority not in PRIORITIES:
        connection.send_error(msg["id"], "invalid_input", "priority must be info, normal or critical")
        return

    try:
        event_data = {
            "message":    message,
            "speakers":   speakers,
            "priority":   priority,
            "volume":     round(float(msg.get("volume", 0.35)), 2),
            "conditions": [c for c in msg.get("conditions", []) if isinstance(c, str)],
        }
        await storage.add_event(event_id, event_data)
        _LOGGER.info("House Voice: saved event '%s'", event_id)
        connection.send_result(msg["id"], {"success": True, "event_id": event_id})
    except Exception as err:
        _LOGGER.error("House Voice: error saving event: %s", err)
        connection.send_error(msg["id"], "unknown_error", str(err))


# ── Delete a voice event ───────────────────────────────────────────────────────

@websocket_api.websocket_command({
    "type":                   f"{DOMAIN}/delete_event",
    vol.Required("event_id"): str,
})
@websocket_api.async_response
async def ws_delete_event(hass: HomeAssistant, connection, msg) -> None:
    """Delete a voice event by event_id."""
    storage = _get_storage(hass)
    if not storage:
        connection.send_error(msg["id"], "not_ready", "House Voice storage not ready")
        return

    event_id = msg["event_id"].strip()
    if event_id not in storage.data:
        connection.send_error(msg["id"], "not_found", f"Event '{event_id}' not found")
        return

    try:
        await storage.delete_event(event_id)
        _LOGGER.info("House Voice: deleted event '%s'", event_id)
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        _LOGGER.error("House Voice: error deleting event: %s", err)
        connection.send_error(msg["id"], "unknown_error", str(err))


# ── Test a voice event ─────────────────────────────────────────────────────────

@websocket_api.websocket_command({
    "type":                   f"{DOMAIN}/test_event",
    vol.Required("event_id"): str,
})
@websocket_api.async_response
async def ws_test_event(hass: HomeAssistant, connection, msg) -> None:
    """Trigger a voice event immediately (test playback), bypassing spam filter."""
    engine = _get_engine(hass)
    if not engine:
        connection.send_error(msg["id"], "not_ready", "House Voice engine not ready")
        return

    event_id = msg["event_id"].strip()
    try:
        await engine.say(event_id, bypass_spam=True)
        _LOGGER.info("House Voice: tested event '%s'", event_id)
        connection.send_result(msg["id"], {"success": True})
    except ServiceValidationError as err:
        _LOGGER.warning("House Voice: test_event validation error for '%s': %s", event_id, err)
        connection.send_error(msg["id"], "invalid_event", str(err))
    except Exception as err:
        _LOGGER.error("House Voice: error testing event '%s': %s", event_id, err)
        connection.send_error(msg["id"], "unknown_error", str(err))


# ── Get all speaker groups ─────────────────────────────────────────────────────

@websocket_api.websocket_command({"type": f"{DOMAIN}/get_groups"})
@callback
def ws_get_groups(hass: HomeAssistant, connection, msg) -> None:
    """Return all stored speaker groups."""
    groups = _get_groups(hass)
    if not groups:
        connection.send_error(msg["id"], "not_ready", "House Voice groups not ready")
        return
    try:
        connection.send_result(msg["id"], {"groups": groups.data})
    except Exception as err:
        connection.send_error(msg["id"], "unknown_error", str(err))


# ── Save (add or update) a speaker group ──────────────────────────────────────

@websocket_api.websocket_command({
    "type":                    f"{DOMAIN}/save_group",
    vol.Required("group_id"):  str,
    vol.Required("name"):      str,
    vol.Required("speakers"):  vol.All(list, vol.Length(min=1)),
})
@websocket_api.async_response
async def ws_save_group(hass: HomeAssistant, connection, msg) -> None:
    """Save (create or update) a speaker group."""
    groups = _get_groups(hass)
    if not groups:
        connection.send_error(msg["id"], "not_ready", "House Voice groups not ready")
        return

    group_id = msg["group_id"].strip()
    if not group_id:
        connection.send_error(msg["id"], "invalid_input", "group_id cannot be empty")
        return

    name = msg["name"].strip()
    if not name:
        connection.send_error(msg["id"], "invalid_input", "name cannot be empty")
        return

    try:
        await groups.add_group(group_id, {
            "name":     name,
            "speakers": msg["speakers"],
        })
        _LOGGER.info("House Voice: saved group '%s'", group_id)
        connection.send_result(msg["id"], {"success": True, "group_id": group_id})
    except Exception as err:
        _LOGGER.error("House Voice: error saving group: %s", err)
        connection.send_error(msg["id"], "unknown_error", str(err))


# ── Delete a speaker group ─────────────────────────────────────────────────────

@websocket_api.websocket_command({
    "type":                    f"{DOMAIN}/delete_group",
    vol.Required("group_id"):  str,
})
@websocket_api.async_response
async def ws_delete_group(hass: HomeAssistant, connection, msg) -> None:
    """Delete a speaker group by group_id."""
    groups = _get_groups(hass)
    if not groups:
        connection.send_error(msg["id"], "not_ready", "House Voice groups not ready")
        return

    group_id = msg["group_id"].strip()
    if group_id not in groups.data:
        connection.send_error(msg["id"], "not_found", f"Group '{group_id}' not found")
        return

    try:
        await groups.delete_group(group_id)
        _LOGGER.info("House Voice: deleted group '%s'", group_id)
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        _LOGGER.error("House Voice: error deleting group: %s", err)
        connection.send_error(msg["id"], "unknown_error", str(err))


# ── Get event history ──────────────────────────────────────────────────────────

@websocket_api.websocket_command({"type": f"{DOMAIN}/get_history"})
@callback
def ws_get_history(hass: HomeAssistant, connection, msg) -> None:
    """Return the in-memory TTS history log (newest first)."""
    engine = _get_engine(hass)
    if not engine:
        connection.send_error(msg["id"], "not_ready", "House Voice engine not ready")
        return
    try:
        connection.send_result(msg["id"], {"history": engine.get_history()})
    except Exception as err:
        connection.send_error(msg["id"], "unknown_error", str(err))


# ── Get all conditions ─────────────────────────────────────────────────────────

@websocket_api.websocket_command({"type": f"{DOMAIN}/get_conditions"})
@callback
def ws_get_conditions(hass: HomeAssistant, connection, msg) -> None:
    """Return all stored conditions from the condition library."""
    conditions = _get_conditions(hass)
    if not conditions:
        connection.send_error(msg["id"], "not_ready", "House Voice conditions not ready")
        return
    try:
        connection.send_result(msg["id"], {"conditions": conditions.data})
    except Exception as err:
        connection.send_error(msg["id"], "unknown_error", str(err))


# ── Save (add or update) a condition ──────────────────────────────────────────

@websocket_api.websocket_command({
    "type":                          f"{DOMAIN}/save_condition",
    vol.Required("condition_id"):    str,
    vol.Required("label"):           str,
    vol.Required("entity_id"):       str,
    vol.Optional("state", default="on"): str,
})
@websocket_api.async_response
async def ws_save_condition(hass: HomeAssistant, connection, msg) -> None:
    """Save (create or update) a condition in the condition library."""
    conditions = _get_conditions(hass)
    if not conditions:
        connection.send_error(msg["id"], "not_ready", "House Voice conditions not ready")
        return

    condition_id = msg["condition_id"].strip()
    if not condition_id:
        connection.send_error(msg["id"], "invalid_input", "condition_id cannot be empty")
        return

    label = msg["label"].strip()
    if not label:
        connection.send_error(msg["id"], "invalid_input", "label cannot be empty")
        return

    entity_id = msg["entity_id"].strip()
    if not entity_id:
        connection.send_error(msg["id"], "invalid_input", "entity_id cannot be empty")
        return

    try:
        await conditions.add_condition(condition_id, {
            "label":     label,
            "entity_id": entity_id,
            "state":     msg.get("state", "on").strip(),
        })
        _LOGGER.info("House Voice: saved condition '%s'", condition_id)
        connection.send_result(msg["id"], {"success": True, "condition_id": condition_id})
    except Exception as err:
        _LOGGER.error("House Voice: error saving condition: %s", err)
        connection.send_error(msg["id"], "unknown_error", str(err))


# ── Delete a condition ─────────────────────────────────────────────────────────

@websocket_api.websocket_command({
    "type":                          f"{DOMAIN}/delete_condition",
    vol.Required("condition_id"):    str,
})
@websocket_api.async_response
async def ws_delete_condition(hass: HomeAssistant, connection, msg) -> None:
    """Delete a condition from the condition library."""
    conditions = _get_conditions(hass)
    if not conditions:
        connection.send_error(msg["id"], "not_ready", "House Voice conditions not ready")
        return

    condition_id = msg["condition_id"].strip()
    if condition_id not in conditions.data:
        connection.send_error(msg["id"], "not_found", f"Condition '{condition_id}' not found")
        return

    try:
        await conditions.delete_condition(condition_id)
        _LOGGER.info("House Voice: deleted condition '%s'", condition_id)
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        _LOGGER.error("House Voice: error deleting condition: %s", err)
        connection.send_error(msg["id"], "unknown_error", str(err))
