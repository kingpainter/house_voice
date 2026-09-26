# VERSION = "3.13.0"
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

import time
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
    websocket_api.async_register_command(hass, ws_list_execution_history)
    
    # Phase 7: Versioning, Batch, Parallel, Conditions
    # Phase 8: Execution History Viewer
    websocket_api.async_register_command(hass, ws_query_executions)
    websocket_api.async_register_command(hass, ws_get_execution_detail)
    
    # Phase 9: Advanced Analytics Dashboard
    websocket_api.async_register_command(hass, ws_get_analytics_statistics)
    websocket_api.async_register_command(hass, ws_get_chain_performance)
    websocket_api.async_register_command(hass, ws_get_step_analytics)
    websocket_api.async_register_command(hass, ws_get_execution_timeline)
    
    _LOGGER.info("House Voice WebSocket API registered (36 commands — Phase 9 in progress")


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

def _get_execution_history(hass: HomeAssistant) -> Any | None:
    """Return execution history instance or None."""
    entry = _get_entry(hass)
    return getattr(entry.runtime_data, "execution_history", None) if entry else None



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

def _get_chain_validator(hass: HomeAssistant) -> Any | None:
    """Return chain validator instance or None."""
    entry = _get_entry(hass)
    return getattr(entry.runtime_data, "chain_validator", None) if entry else None


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
            except (ValueError, TypeError):
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

@websocket_api.websocket_command({"type": f"{DOMAIN}/query_executions"})
@callback
def ws_query_executions(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Query execution history with filters.
    
    Request payload:
    {
        "type": "house_voice/query_executions",
        "chain_id": "chain_1",          # optional
        "status": "completed",           # optional: in_progress|completed|failed|blocked_condition
        "start_date": "2026-09-01T00:00:00Z",  # optional (ISO format)
        "end_date": "2026-09-30T23:59:59Z",    # optional (ISO format)
        "search_text": "kitchen",        # optional: search in step names
        "limit": 50                      # optional, default 50
    }
    """
    try:
        history = _get_execution_history(hass)
        if not history:
            connection.send_error(msg["id"], "not_ready", "Execution history not ready")
            return
        
        chain_id = msg.get("chain_id")
        status = msg.get("status")
        start_date = msg.get("start_date")
        end_date = msg.get("end_date")
        search_text = msg.get("search_text")
        limit = msg.get("limit", 50)
        
        results = history.list_executions_filtered(
            chain_id=chain_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            search_text=search_text
        )
        
        connection.send_result(msg["id"], {"executions": results})
        _LOGGER.debug("House Voice: returned %d filtered executions", len(results))
    except Exception as err:
        _LOGGER.exception("House Voice WS error (query_executions)")
        connection.send_error(msg["id"], "unknown_error", str(err))

@websocket_api.websocket_command({"type": f"{DOMAIN}/get_execution_detail"})
@callback
def ws_get_execution_detail(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Return full execution record with all step details.
    
    Request payload:
    {
        "type": "house_voice/get_execution_detail",
        "exec_id": "exec_abc123"
    }
    """
    try:
        history = _get_execution_history(hass)
        if not history:
            connection.send_error(msg["id"], "not_ready", "Execution history not ready")
            return
        
        exec_id = msg.get("exec_id")
        if not exec_id:
            connection.send_error(msg["id"], "invalid_request", "exec_id required")
            return
        
        execution = history.get_execution_detail(exec_id)
        if not execution:
            connection.send_error(msg["id"], "not_found", f"Execution {exec_id} not found")
            return
        
        connection.send_result(msg["id"], {"execution": execution})
        _LOGGER.debug("House Voice: returned execution detail for %s", exec_id)
    except Exception as err:
        _LOGGER.exception("House Voice WS error (get_execution_detail)")
        connection.send_error(msg["id"], "unknown_error", str(err))


# ── PHASE 9: Advanced Analytics Dashboard ──────────────────────────────────────

@websocket_api.websocket_command({
    "type":                      f"{DOMAIN}/get_analytics_statistics",
    vol.Optional("chain_id"):    str,
    vol.Optional("start_date"):  str,
    vol.Optional("end_date"):    str,
})
@callback
def ws_get_analytics_statistics(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Get comprehensive statistics for execution history.
    
    Returns:
    {
        "total_executions": int,
        "success_count": int,
        "failed_executions": int,
        "success_rate": float,
        "avg_duration_seconds": float
    }
    """
    try:
        from .analytics import HouseVoiceAnalytics
        
        history = _get_execution_history(hass)
        if not history:
            connection.send_error(msg["id"], "not_ready", "Execution history not ready")
            return
        
        analytics = HouseVoiceAnalytics(history)
        stats = analytics.get_statistics(
            chain_id=msg.get("chain_id"),
            start_date=msg.get("start_date"),
            end_date=msg.get("end_date")
        )
        
        connection.send_result(msg["id"], stats)
        _LOGGER.debug("House Voice: returned analytics statistics")
    except Exception as err:
        _LOGGER.exception("House Voice WS error (get_analytics_statistics)")
        connection.send_error(msg["id"], "unknown_error", str(err))


@websocket_api.websocket_command({
    "type":                      f"{DOMAIN}/get_chain_performance",
    vol.Optional("start_date"):  str,
    vol.Optional("end_date"):    str,
})
@callback
def ws_get_chain_performance(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Get per-chain performance metrics.
    
    Returns: [{chain_id, chain_name, executions, success_rate, avg_duration_seconds}]
    """
    try:
        from .analytics import HouseVoiceAnalytics
        
        history = _get_execution_history(hass)
        if not history:
            connection.send_error(msg["id"], "not_ready", "Execution history not ready")
            return
        
        analytics = HouseVoiceAnalytics(history)
        performance = analytics.get_chain_performance(
            start_date=msg.get("start_date"),
            end_date=msg.get("end_date")
        )
        
        connection.send_result(msg["id"], {"chains": performance})
        _LOGGER.debug("House Voice: returned chain performance metrics")
    except Exception as err:
        _LOGGER.exception("House Voice WS error (get_chain_performance)")
        connection.send_error(msg["id"], "unknown_error", str(err))


@websocket_api.websocket_command({
    "type":                      f"{DOMAIN}/get_step_analytics",
    vol.Optional("start_date"):  str,
    vol.Optional("end_date"):    str,
})
@callback
def ws_get_step_analytics(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Get step-level performance analytics.
    
    Returns:
    {
        "top_failing_steps": [{step_name, failure_rate, failures}],
        "slowest_steps": [{step_name, avg_duration_seconds, executions}],
        "most_used_steps": [{step_name, executions}],
        "step_type_distribution": {step_type: count}
    }
    """
    try:
        from .analytics import HouseVoiceAnalytics
        
        history = _get_execution_history(hass)
        if not history:
            connection.send_error(msg["id"], "not_ready", "Execution history not ready")
            return
        
        analytics = HouseVoiceAnalytics(history)
        analytics_data = analytics.get_step_analytics(
            start_date=msg.get("start_date"),
            end_date=msg.get("end_date")
        )
        
        connection.send_result(msg["id"], analytics_data)
        _LOGGER.debug("House Voice: returned step analytics")
    except Exception as err:
        _LOGGER.exception("House Voice WS error (get_step_analytics)")
        connection.send_error(msg["id"], "unknown_error", str(err))


@websocket_api.websocket_command({
    "type":                      f"{DOMAIN}/get_execution_timeline",
    vol.Required("chain_id"):    str,
    vol.Optional("limit"):       int,
})
@callback
def ws_get_execution_timeline(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any]
) -> None:
    """Get Gantt chart data for execution timeline visualization.
    
    Returns: [{exec_id, started, finished, duration_seconds, status, step_count}]
    """
    try:
        from .analytics import HouseVoiceAnalytics
        
        history = _get_execution_history(hass)
        if not history:
            connection.send_error(msg["id"], "not_ready", "Execution history not ready")
            return
        
        analytics = HouseVoiceAnalytics(history)
        timeline = analytics.get_execution_timeline(
            chain_id=msg.get("chain_id"),
            limit=msg.get("limit", 20)
        )
        
        connection.send_result(msg["id"], timeline)
        _LOGGER.debug("House Voice: returned execution timeline for %s", msg.get("chain_id"))
    except Exception as err:
        _LOGGER.exception("House Voice WS error (get_execution_timeline)")
        connection.send_error(msg["id"], "unknown_error", str(err))
