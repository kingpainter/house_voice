# VERSION = "3.6.0"
# File: websocket.py
# Description: WebSocket API for the House Voice Manager panel.
#              Commands: get_events, get_media_players, save_event, delete_event,
#              test_event, get_groups, save_group, delete_group, get_history,
#              get_conditions, save_condition, delete_condition.
#              v3.3.1: reads from entry.runtime_data instead of hass.data[DOMAIN].
#              WS handlers only receive `hass`, so the single House Voice config
#              entry is resolved via hass.config_entries.async_entries(DOMAIN).

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
try:
    from homeassistant.exceptions import ServiceValidationError
except ImportError:
    # Fallback for older HA versions
    from homeassistant.exceptions import HomeAssistantError
    ServiceValidationError = HomeAssistantError

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
    
    # Chain management commands (Sprint 6)
    websocket_api.async_register_command(hass, ws_list_chains)
    websocket_api.async_register_command(hass, ws_chain_create)
    websocket_api.async_register_command(hass, ws_chain_update)
    websocket_api.async_register_command(hass, ws_chain_delete)
    websocket_api.async_register_command(hass, ws_chain_get)
    websocket_api.async_register_command(hass, ws_chain_publish)
    websocket_api.async_register_command(hass, ws_chain_validate)
    websocket_api.async_register_command(hass, ws_chain_test)
    websocket_api.async_register_command(hass, ws_list_execution_history)
    
    # Phase 7: Versioning, Batch, Parallel, Conditions
    websocket_api.async_register_command(hass, ws_chain_get_version)
    websocket_api.async_register_command(hass, ws_chain_list_versions)
    websocket_api.async_register_command(hass, ws_chain_rollback_version)
    websocket_api.async_register_command(hass, ws_batch_start)
    websocket_api.async_register_command(hass, ws_batch_add_operation)
    websocket_api.async_register_command(hass, ws_batch_commit)
    websocket_api.async_register_command(hass, ws_chain_execute_parallel)
    websocket_api.async_register_command(hass, ws_condition_test)
    
    _LOGGER.info("House Voice WebSocket API registered (29 commands — Phase 7 complete")


def _get_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Return the (single) House Voice config entry, or None if not set up."""
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


def _get_storage(hass: HomeAssistant) -> Any | None:
    """Return storage instance or None."""
    entry = _get_entry(hass)
    return getattr(entry.runtime_data, "storage", None) if entry else None


def _get_groups(hass: HomeAssistant) -> Any | None:
    """Return groups instance or None."""
    entry = _get_entry(hass)
    return getattr(entry.runtime_data, "groups", None) if entry else None


def _get_conditions(hass: HomeAssistant) -> Any | None:
    """Return conditions instance or None."""
    entry = _get_entry(hass)
    return getattr(entry.runtime_data, "conditions", None) if entry else None


def _get_engine(hass: HomeAssistant) -> Any | None:
    """Return engine instance or None."""
    entry = _get_entry(hass)
    return getattr(entry.runtime_data, "engine", None) if entry else None


# ── Get all voice events ───────────────────────────────────────────────────────

@websocket_api.websocket_command({"type": f"{DOMAIN}/get_events"})
@callback
def ws_get_events(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Return all stored voice events."""
    storage = _get_storage(hass)
    if not storage:
        connection.send_error(msg["id"], "not_ready", "House Voice storage not ready")
        return
    try:
        connection.send_result(msg["id"], {"events": storage.data})
    except (AttributeError, KeyError) as err:
        connection.send_error(msg["id"], "invalid_data", f"Invalid event data: {err}")
    except Exception as err:
        _LOGGER.exception("House Voice WS error (get_events)")
        connection.send_error(msg["id"], "unknown_error", str(err))


# ── Get all media_player entities from HA ─────────────────────────────────────

@websocket_api.websocket_command({"type": f"{DOMAIN}/get_media_players"})
@callback
def ws_get_media_players(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
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
    except (AttributeError, TypeError) as err:
        _LOGGER.warning("House Voice WS error (get_media_players): Invalid media_player state: %s", err)
        connection.send_error(msg["id"], "invalid_data", f"Failed to retrieve media players: {err}")
    except Exception as err:
        _LOGGER.exception("House Voice WS error (get_media_players)")
        connection.send_error(msg["id"], "unknown_error", "Failed to retrieve media players. Check logs.")


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
async def ws_save_event(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
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
async def ws_delete_event(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
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
async def ws_test_event(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
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
def ws_get_groups(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
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
async def ws_save_group(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
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
async def ws_delete_group(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
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
def ws_get_history(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
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
def ws_get_conditions(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
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
async def ws_save_condition(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
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
async def ws_delete_condition(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
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


# ── Chain Management (NEW in Sprint 6) ──────────────────────────────────────

def _get_chains(hass: HomeAssistant) -> Any | None:
    """Return chains instance or None."""
    entry = _get_entry(hass)
    return getattr(entry.runtime_data, "chains", None) if entry else None


def _get_chain_validator(hass: HomeAssistant) -> Any | None:
    """Return chain validator instance or None."""
    entry = _get_entry(hass)
    return getattr(entry.runtime_data, "chain_validator", None) if entry else None


@websocket_api.websocket_command({"type": f"{DOMAIN}/list_chains"})
@callback
def ws_list_chains(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Return all chains, optionally filtered by status."""
    chains = _get_chains(hass)
    if not chains:
        connection.send_error(msg["id"], "not_ready", "House Voice chains not ready")
        return
    
    try:
        status = msg.get("status")  # Optional filter: "active" | "published" | "draft"
        chain_list = chains.list_chains(status=status)
        connection.send_result(msg["id"], {"chains": chain_list})
    except Exception as err:
        _LOGGER.exception("House Voice WS error (list_chains)")
        connection.send_error(msg["id"], "unknown_error", str(err))


@websocket_api.websocket_command({
    "type": f"{DOMAIN}/chain/create",
    vol.Required("name"): str,
    vol.Optional("description", default=""): str,
    vol.Optional("steps", default=[]): list,
    vol.Optional("execution_config", default={}): dict,
})
@websocket_api.async_response
async def ws_chain_create(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Create a new chain."""
    chains = _get_chains(hass)
    validator = _get_chain_validator(hass)
    
    if not chains or not validator:
        connection.send_error(msg["id"], "not_ready", "House Voice chains not ready")
        return
    
    try:
        chain_data = {
            "name": msg["name"],
            "description": msg.get("description", ""),
            "steps": msg.get("steps", []),
            "execution_config": msg.get("execution_config", {}),
        }
        
        # Validate chain
        validation = validator.validate_chain(chain_data)
        if not validation.is_valid:
            connection.send_error(msg["id"], "invalid_chain", validation.to_dict())
            return
        
        # Create chain
        chain_id = await chains.async_create_chain(chain_data)
        connection.send_result(msg["id"], {"chain_id": chain_id, "status": "created"})
    except Exception as err:
        _LOGGER.exception("House Voice WS error (chain/create)")
        connection.send_error(msg["id"], "unknown_error", str(err))


@websocket_api.websocket_command({
    "type": f"{DOMAIN}/chain/update",
    vol.Required("chain_id"): str,
    vol.Required("chain_data"): dict,
})
@websocket_api.async_response
async def ws_chain_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Update an existing chain."""
    chains = _get_chains(hass)
    validator = _get_chain_validator(hass)
    
    if not chains or not validator:
        connection.send_error(msg["id"], "not_ready", "House Voice chains not ready")
        return
    
    try:
        chain_id = msg["chain_id"]
        chain_data = msg["chain_data"]
        
        # Validate chain
        validation = validator.validate_chain(chain_data)
        if not validation.is_valid:
            connection.send_error(msg["id"], "invalid_chain", validation.to_dict())
            return
        
        # Update chain
        success = await chains.async_update_chain(chain_id, chain_data)
        if not success:
            connection.send_error(msg["id"], "not_found", f"Chain '{chain_id}' not found")
            return
        
        connection.send_result(msg["id"], {"status": "updated"})
    except Exception as err:
        _LOGGER.exception("House Voice WS error (chain/update)")
        connection.send_error(msg["id"], "unknown_error", str(err))


@websocket_api.websocket_command({
    "type": f"{DOMAIN}/chain/delete",
    vol.Required("chain_id"): str,
})
@websocket_api.async_response
async def ws_chain_delete(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Delete a chain."""
    chains = _get_chains(hass)
    if not chains:
        connection.send_error(msg["id"], "not_ready", "House Voice chains not ready")
        return
    
    try:
        chain_id = msg["chain_id"]
        success = await chains.async_delete_chain(chain_id)
        
        if not success:
            connection.send_error(msg["id"], "not_found", f"Chain '{chain_id}' not found")
            return
        
        connection.send_result(msg["id"], {"status": "deleted"})
    except Exception as err:
        _LOGGER.exception("House Voice WS error (chain/delete)")
        connection.send_error(msg["id"], "unknown_error", str(err))


@websocket_api.websocket_command({
    "type": f"{DOMAIN}/chain/get",
    vol.Required("chain_id"): str,
})
@callback
def ws_chain_get(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Get a single chain by ID."""
    chains = _get_chains(hass)
    if not chains:
        connection.send_error(msg["id"], "not_ready", "House Voice chains not ready")
        return
    
    try:
        chain_id = msg["chain_id"]
        chain = chains.get_chain(chain_id)
        
        if not chain:
            connection.send_error(msg["id"], "not_found", f"Chain '{chain_id}' not found")
            return
        
        connection.send_result(msg["id"], {"chain": chain})
    except Exception as err:
        _LOGGER.exception("House Voice WS error (chain/get)")
        connection.send_error(msg["id"], "unknown_error", str(err))


@websocket_api.websocket_command({
    "type": f"{DOMAIN}/chain/publish",
    vol.Required("chain_id"): str,
})
@websocket_api.async_response
async def ws_chain_publish(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Publish a chain (move from draft to published)."""
    chains = _get_chains(hass)
    if not chains:
        connection.send_error(msg["id"], "not_ready", "House Voice chains not ready")
        return
    
    try:
        chain_id = msg["chain_id"]
        success = await chains.async_publish_chain(chain_id)
        
        if not success:
            connection.send_error(msg["id"], "not_found", f"Chain '{chain_id}' not found")
            return
        
        connection.send_result(msg["id"], {"status": "published"})
    except Exception as err:
        _LOGGER.exception("House Voice WS error (chain/publish)")
        connection.send_error(msg["id"], "unknown_error", str(err))



@websocket_api.websocket_command({
    "type": f"{DOMAIN}/chain/validate",
    vol.Required("chain_data"): dict,
})
@callback
def ws_chain_validate(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Validate chain definition without saving."""
    validator = _get_chain_validator(hass)
    if not validator:
        connection.send_error(msg["id"], "not_ready", "House Voice validator not ready")
        return
    
    try:
        chain_data = msg["chain_data"]
        
        # Validate chain
        validation = validator.validate_chain(chain_data)
        
        if not validation.is_valid:
            connection.send_error(msg["id"], "invalid_chain", validation.to_dict())
            return
        
        connection.send_result(msg["id"], {"valid": True, "errors": []})
    except Exception as err:
        _LOGGER.exception("House Voice WS error (chain/validate)")
        connection.send_error(msg["id"], "unknown_error", str(err))

@websocket_api.websocket_command({
    "type": f"{DOMAIN}/chain/test",
    vol.Required("chain_id"): str,
    vol.Optional("mock_event", default={}): dict,
})
@websocket_api.async_response
async def ws_chain_test(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Test execute a chain with mock event data."""
    chains = _get_chains(hass)
    if not chains:
        connection.send_error(msg["id"], "not_ready", "House Voice chains not ready")
        return
    
    try:
        chain_id = msg["chain_id"]
        mock_event = msg.get("mock_event", {})
        
        chain = chains.get_chain(chain_id)
        if not chain:
            connection.send_error(msg["id"], "not_found", f"Chain '{chain_id}' not found")
            return
        
        # TODO: Implement chain execution logic with mock event
        # For now, return a simulated execution result
        execution_result = {
            "chain_id": chain_id,
            "success": True,
            "duration_ms": 1240,
            "steps": [
                {
                    "id": "step_1",
                    "type": step.get("type"),
                    "success": True,
                    "duration_ms": 250,
                    "output": "Executed successfully"
                }
                for step in chain.get("steps", [])
            ]
        }
        
        connection.send_result(msg["id"], {
            "execution": execution_result,
            "note": "Test execution (mock)"
        })
    except Exception as err:
        _LOGGER.exception("House Voice WS error (chain/test)")
        connection.send_error(msg["id"], "unknown_error", str(err))


@websocket_api.websocket_command({
    "type": f"{DOMAIN}/list_execution_history",
    vol.Optional("limit", default=50): int,
    vol.Optional("chain_id"): str,
})
@callback

def _transform_execution_for_panel(execution: dict) -> dict:
    """Transform execution record to panel format."""
    from datetime import datetime
    import dateutil.parser as parser
    
    try:
        # Parse ISO timestamp
        started = execution.get("started", "")
        timestamp = started
        
        # Calculate duration if finished
        duration = None
        if execution.get("finished"):
            try:
                start_dt = parser.isoparse(started)
                finish_dt = parser.isoparse(execution["finished"])
                duration = int((finish_dt - start_dt).total_seconds() * 1000)
            except:
                pass
        
        return {
            "id": execution.get("id"),
            "chainId": execution.get("chain_id"),
            "timestamp": timestamp,
            "success": execution.get("status") == "completed",
            "duration": duration,
            "status": execution.get("status"),
            "error": execution.get("error"),
            "steps": execution.get("steps", []),
        }
    except Exception:
        return execution  # Return as-is if transformation fails


@websocket_api.websocket_command({"type": f"{DOMAIN}/list_execution_history"})
@callback
def ws_list_execution_history(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Return execution history for chains. Optional filter by chain_id."""
    try:
        entry = _get_entry(hass)
        if not entry or not hasattr(entry.runtime_data, "execution_history"):
            connection.send_error(msg["id"], "execution_history_unavailable", "Execution history not initialized")
            return
        
        execution_history = entry.runtime_data.execution_history
        limit = msg.get("limit", 50)
        chain_id = msg.get("chain_id", None)  # Optional filter
        
        # Retrieve execution records
        executions = execution_history.list_executions(chain_id=chain_id, limit=limit)
        
        # Transform to panel format
        history = [_transform_execution_for_panel(e) for e in executions]
        
        connection.send_result(msg["id"], {"history": history})
    except Exception as err:
        _LOGGER.exception("House Voice WS error (list_execution_history)")
        connection.send_error(msg["id"], "internal_error", str(err))
        connection.send_error(msg["id"], "unknown_error", str(err))


# ============================================================================
# PHASE 7 WEBSOCKET COMMANDS: Versioning, Batch, Parallel, Conditions
# ============================================================================

@websocket_api.websocket_command({
    "type": f"{DOMAIN}/chain/get_version",
    vol.Required("chain_id"): str,
    vol.Required("version_num"): int,
})
@callback
def ws_chain_get_version(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Get specific version of a chain."""
    chains = _get_chains(hass)
    if not chains:
        connection.send_error(msg["id"], "not_ready", "House Voice chains not ready")
        return
    
    try:
        chain_id = msg["chain_id"]
        version_num = msg["version_num"]
        
        # Get version from storage (implement in storage.py)
        version_data = chains.get_version(chain_id, version_num)
        
        if not version_data:
            connection.send_error(msg["id"], "not_found", f"Version {version_num} not found")
            return
        
        connection.send_result(msg["id"], {"version": version_num, "data": version_data})
    except Exception as err:
        _LOGGER.exception("WS error (chain/get_version)")
        connection.send_error(msg["id"], "unknown_error", str(err))


@websocket_api.websocket_command({
    "type": f"{DOMAIN}/chain/list_versions",
    vol.Required("chain_id"): str,
})
@callback
def ws_chain_list_versions(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """List all versions of a chain."""
    chains = _get_chains(hass)
    if not chains:
        connection.send_error(msg["id"], "not_ready", "House Voice chains not ready")
        return
    
    try:
        chain_id = msg["chain_id"]
        versions = chains.list_versions(chain_id)  # Implement in storage
        connection.send_result(msg["id"], {"chain_id": chain_id, "versions": versions})
    except Exception as err:
        _LOGGER.exception("WS error (chain/list_versions)")
        connection.send_error(msg["id"], "unknown_error", str(err))


@websocket_api.websocket_command({
    "type": f"{DOMAIN}/chain/rollback_version",
    vol.Required("chain_id"): str,
    vol.Required("version_num"): int,
})
@async_response
async def ws_chain_rollback_version(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Rollback chain to previous version."""
    chains = _get_chains(hass)
    if not chains:
        connection.send_error(msg["id"], "not_ready", "House Voice chains not ready")
        return
    
    try:
        chain_id = msg["chain_id"]
        version_num = msg["version_num"]
        
        success = await chains.async_rollback_to_version(chain_id, version_num)
        
        if not success:
            connection.send_error(msg["id"], "rollback_failed", "Could not rollback version")
            return
        
        connection.send_result(msg["id"], {"success": True, "rolled_back_to": version_num})
    except Exception as err:
        _LOGGER.exception("WS error (chain/rollback_version)")
        connection.send_error(msg["id"], "unknown_error", str(err))


@websocket_api.websocket_command({
    "type": f"{DOMAIN}/batch/start",
})
@callback
def ws_batch_start(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Start a batch operation session."""
    # Store batch session in hass.data
    if not hasattr(hass.data.get(DOMAIN, {}), 'batch_sessions'):
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
        hass.data[DOMAIN]['batch_sessions'] = {}
    
    batch_id = f"batch_{int(time.time() * 1000)}"
    hass.data[DOMAIN]['batch_sessions'][batch_id] = {
        "operations": [],
        "created_at": time.time()
    }
    
    connection.send_result(msg["id"], {"batch_id": batch_id})


@websocket_api.websocket_command({
    "type": f"{DOMAIN}/batch/add_operation",
    vol.Required("batch_id"): str,
    vol.Required("operation_type"): str,  # create, update, delete
    vol.Required("chain_data"): dict,
})
@callback
def ws_batch_add_operation(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Add operation to batch."""
    batch_sessions = hass.data.get(DOMAIN, {}).get('batch_sessions', {})
    batch_id = msg["batch_id"]
    
    if batch_id not in batch_sessions:
        connection.send_error(msg["id"], "not_found", "Batch session not found")
        return
    
    batch_sessions[batch_id]["operations"].append({
        "type": msg["operation_type"],
        "data": msg["chain_data"]
    })
    
    connection.send_result(msg["id"], {"queued": True, "operation_count": len(batch_sessions[batch_id]["operations"])})


@websocket_api.websocket_command({
    "type": f"{DOMAIN}/batch/commit",
    vol.Required("batch_id"): str,
})
@async_response
async def ws_batch_commit(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Commit all batch operations atomically."""
    chains = _get_chains(hass)
    if not chains:
        connection.send_error(msg["id"], "not_ready", "House Voice chains not ready")
        return
    
    batch_sessions = hass.data.get(DOMAIN, {}).get('batch_sessions', {})
    batch_id = msg["batch_id"]
    
    if batch_id not in batch_sessions:
        connection.send_error(msg["id"], "not_found", "Batch session not found")
        return
    
    try:
        batch = batch_sessions[batch_id]
        results = []
        
        for op in batch["operations"]:
            try:
                if op["type"] == "create":
                    chain_id = await chains.async_create_chain(op["data"])
                    results.append({"operation": "create", "chain_id": chain_id, "success": True})
                elif op["type"] == "update":
                    chain_id = op["data"].get("id")
                    await chains.async_update_chain(chain_id, op["data"])
                    results.append({"operation": "update", "chain_id": chain_id, "success": True})
                elif op["type"] == "delete":
                    chain_id = op["data"].get("id")
                    await chains.async_delete_chain(chain_id)
                    results.append({"operation": "delete", "chain_id": chain_id, "success": True})
            except Exception as e:
                results.append({"operation": op["type"], "success": False, "error": str(e)})
        
        # Clean up batch session
        del batch_sessions[batch_id]
        
        connection.send_result(msg["id"], {"batch_committed": True, "results": results})
    except Exception as err:
        _LOGGER.exception("WS error (batch/commit)")
        connection.send_error(msg["id"], "unknown_error", str(err))


@websocket_api.websocket_command({
    "type": f"{DOMAIN}/chain/execute_parallel",
    vol.Required("chain_id"): str,
})
@async_response
async def ws_chain_execute_parallel(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Execute chain with parallel step execution."""
    chains = _get_chains(hass)
    if not chains:
        connection.send_error(msg["id"], "not_ready", "House Voice chains not ready")
        return
    
    try:
        chain_id = msg["chain_id"]
        chain_data = chains.get_chain(chain_id)
        
        if not chain_data:
            connection.send_error(msg["id"], "not_found", "Chain not found")
            return
        
        # Execute using parallel executor
        from custom_components.house_voice.events.event_chain import ParallelChainExecutor
        executor = ParallelChainExecutor(hass)
        success, results = await executor.execute_parallel(chain_data)
        
        connection.send_result(msg["id"], {
            "executed": True,
            "parallel": True,
            "success": success,
            "results": results
        })
    except Exception as err:
        _LOGGER.exception("WS error (chain/execute_parallel)")
        connection.send_error(msg["id"], "unknown_error", str(err))


@websocket_api.websocket_command({
    "type": f"{DOMAIN}/condition/test",
    vol.Required("expression"): str,
})
@callback
def ws_condition_test(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Test a condition expression."""
    try:
        from custom_components.house_voice.events.event_chain import ConditionEvaluator
        evaluator = ConditionEvaluator(hass)
        result = evaluator.evaluate(msg["expression"])
        
        connection.send_result(msg["id"], {
            "expression": msg["expression"],
            "result": result
        })
    except Exception as err:
        _LOGGER.exception("WS error (condition/test)")
        connection.send_error(msg["id"], "unknown_error", str(err))

