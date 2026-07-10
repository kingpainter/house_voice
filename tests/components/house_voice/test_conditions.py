"""Tests for the Condition Library – HouseVoiceConditions storage and WebSocket commands (v3.2.0/v3.3.0).

Note: AND-logic evaluation (_eval_conditions) is already covered in
test_voice_engine_v22.py (test_condition_true_allows_playback,
test_condition_false_blocks_playback, test_condition_error_defaults_to_true).
This file fills the remaining gap: the storage class itself and the
get_conditions / save_condition / delete_condition WebSocket commands.

v3.3.0: uses mock_entry.runtime_data (via the make_runtime factory fixture)
instead of the old hass.data[DOMAIN] pattern.
"""

from unittest.mock import MagicMock
import pytest


def _make_connection():
    """Return a mock WebSocket connection."""
    conn = MagicMock()
    conn.send_result = MagicMock()
    conn.send_error = MagicMock()
    return conn


def _make_msg(msg_id=1, **kwargs):
    """Return a mock WebSocket message dict."""
    return {"id": msg_id, **kwargs}


SAMPLE_CONDITION = {
    "label":     "Nogen er hjemme",
    "entity_id": "binary_sensor.nogen_hjemme",
    "state":     "on",
}


# ── HouseVoiceConditions storage ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_conditions_load_empty(mock_conditions):
    """async_load returns an empty dict when no data exists."""
    result = await mock_conditions.async_load()
    assert result == {}
    assert mock_conditions.data == {}


@pytest.mark.asyncio
async def test_conditions_load_existing_data(mock_conditions):
    """async_load returns previously stored conditions."""
    mock_conditions.store.async_load.return_value = {"nogen_hjemme": SAMPLE_CONDITION}
    result = await mock_conditions.async_load()
    assert "nogen_hjemme" in result
    assert result["nogen_hjemme"]["entity_id"] == "binary_sensor.nogen_hjemme"


@pytest.mark.asyncio
async def test_conditions_load_guards_non_dict(mock_conditions):
    """async_load falls back to an empty dict if storage returns something else."""
    mock_conditions.store.async_load.return_value = "corrupt"
    result = await mock_conditions.async_load()
    assert result == {}


@pytest.mark.asyncio
async def test_add_condition(mock_conditions):
    """add_condition stores the condition and persists to disk."""
    await mock_conditions.add_condition("nogen_hjemme", SAMPLE_CONDITION)
    assert "nogen_hjemme" in mock_conditions.data
    assert mock_conditions.data["nogen_hjemme"]["label"] == "Nogen er hjemme"
    mock_conditions.store.async_save.assert_called_once()


@pytest.mark.asyncio
async def test_add_condition_overwrites_existing(mock_conditions):
    """add_condition overwrites an existing condition with the same ID."""
    await mock_conditions.add_condition("nogen_hjemme", SAMPLE_CONDITION)
    updated = {**SAMPLE_CONDITION, "state": "off"}
    await mock_conditions.add_condition("nogen_hjemme", updated)
    assert mock_conditions.data["nogen_hjemme"]["state"] == "off"


@pytest.mark.asyncio
async def test_delete_condition(mock_conditions):
    """delete_condition removes an existing condition and persists to disk."""
    mock_conditions.data["nogen_hjemme"] = SAMPLE_CONDITION
    await mock_conditions.delete_condition("nogen_hjemme")
    assert "nogen_hjemme" not in mock_conditions.data
    mock_conditions.store.async_save.assert_called_once()


@pytest.mark.asyncio
async def test_delete_nonexistent_condition(mock_conditions):
    """delete_condition does not raise and does not save for an unknown ID."""
    await mock_conditions.delete_condition("does_not_exist")
    mock_conditions.store.async_save.assert_not_called()


def test_get_condition(mock_conditions):
    """get_condition returns the stored condition for a known ID."""
    mock_conditions.data["nogen_hjemme"] = SAMPLE_CONDITION
    result = mock_conditions.get_condition("nogen_hjemme")
    assert result == SAMPLE_CONDITION


def test_get_condition_missing(mock_conditions):
    """get_condition returns None for an unknown ID."""
    assert mock_conditions.get_condition("unknown") is None


# ── WebSocket: get_conditions ────────────────────────────────────────────────────

def test_ws_get_conditions_returns_all(mock_hass, mock_conditions, mock_entry, make_runtime):
    """get_conditions returns all stored conditions."""
    from custom_components.house_voice.websocket import ws_get_conditions

    mock_conditions.data = {"nogen_hjemme": SAMPLE_CONDITION}
    mock_entry.runtime_data = make_runtime(conditions=mock_conditions)

    conn = _make_connection()
    ws_get_conditions(mock_hass, conn, _make_msg())

    conn.send_result.assert_called_once()
    result = conn.send_result.call_args[0][1]
    assert "nogen_hjemme" in result["conditions"]


def test_ws_get_conditions_not_ready(mock_hass, mock_entry, make_runtime):
    """get_conditions returns an error if conditions storage is not ready."""
    from custom_components.house_voice.websocket import ws_get_conditions

    mock_entry.runtime_data = make_runtime(conditions=None)

    conn = _make_connection()
    ws_get_conditions(mock_hass, conn, _make_msg())

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "not_ready"


# ── WebSocket: save_condition ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ws_save_condition_success(mock_hass, mock_conditions, mock_entry, make_runtime):
    """save_condition stores the condition and returns success."""
    from custom_components.house_voice.websocket import ws_save_condition

    mock_entry.runtime_data = make_runtime(conditions=mock_conditions)

    conn = _make_connection()
    msg = _make_msg(
        condition_id="nogen_hjemme",
        label="Nogen er hjemme",
        entity_id="binary_sensor.nogen_hjemme",
        state="on",
    )
    await ws_save_condition.__wrapped__(mock_hass, conn, msg)

    conn.send_result.assert_called_once()
    assert conn.send_result.call_args[0][1]["success"] is True
    assert "nogen_hjemme" in mock_conditions.data


@pytest.mark.asyncio
async def test_ws_save_condition_defaults_state_to_on(mock_hass, mock_conditions, mock_entry, make_runtime):
    """save_condition defaults state to 'on' when not provided."""
    from custom_components.house_voice.websocket import ws_save_condition

    mock_entry.runtime_data = make_runtime(conditions=mock_conditions)

    conn = _make_connection()
    msg = _make_msg(
        condition_id="nogen_hjemme",
        label="Nogen er hjemme",
        entity_id="binary_sensor.nogen_hjemme",
    )
    await ws_save_condition.__wrapped__(mock_hass, conn, msg)

    assert mock_conditions.data["nogen_hjemme"]["state"] == "on"


@pytest.mark.asyncio
async def test_ws_save_condition_empty_id(mock_hass, mock_conditions, mock_entry, make_runtime):
    """save_condition returns an error for an empty condition_id."""
    from custom_components.house_voice.websocket import ws_save_condition

    mock_entry.runtime_data = make_runtime(conditions=mock_conditions)

    conn = _make_connection()
    msg = _make_msg(condition_id="  ", label="Test", entity_id="binary_sensor.x")
    await ws_save_condition.__wrapped__(mock_hass, conn, msg)

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "invalid_input"


@pytest.mark.asyncio
async def test_ws_save_condition_empty_label(mock_hass, mock_conditions, mock_entry, make_runtime):
    """save_condition returns an error for an empty label."""
    from custom_components.house_voice.websocket import ws_save_condition

    mock_entry.runtime_data = make_runtime(conditions=mock_conditions)

    conn = _make_connection()
    msg = _make_msg(condition_id="nogen_hjemme", label="  ", entity_id="binary_sensor.x")
    await ws_save_condition.__wrapped__(mock_hass, conn, msg)

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "invalid_input"


@pytest.mark.asyncio
async def test_ws_save_condition_empty_entity_id(mock_hass, mock_conditions, mock_entry, make_runtime):
    """save_condition returns an error for an empty entity_id."""
    from custom_components.house_voice.websocket import ws_save_condition

    mock_entry.runtime_data = make_runtime(conditions=mock_conditions)

    conn = _make_connection()
    msg = _make_msg(condition_id="nogen_hjemme", label="Test", entity_id="  ")
    await ws_save_condition.__wrapped__(mock_hass, conn, msg)

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "invalid_input"


@pytest.mark.asyncio
async def test_ws_save_condition_not_ready(mock_hass, mock_entry, make_runtime):
    """save_condition returns an error if conditions storage is not ready."""
    from custom_components.house_voice.websocket import ws_save_condition

    mock_entry.runtime_data = make_runtime(conditions=None)

    conn = _make_connection()
    msg = _make_msg(condition_id="x", label="Test", entity_id="binary_sensor.x")
    await ws_save_condition.__wrapped__(mock_hass, conn, msg)

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "not_ready"


# ── WebSocket: delete_condition ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ws_delete_condition_success(mock_hass, mock_conditions, mock_entry, make_runtime):
    """delete_condition removes the condition and returns success."""
    from custom_components.house_voice.websocket import ws_delete_condition

    mock_conditions.data["nogen_hjemme"] = SAMPLE_CONDITION
    mock_entry.runtime_data = make_runtime(conditions=mock_conditions)

    conn = _make_connection()
    await ws_delete_condition.__wrapped__(mock_hass, conn, _make_msg(condition_id="nogen_hjemme"))

    conn.send_result.assert_called_once()
    assert "nogen_hjemme" not in mock_conditions.data


@pytest.mark.asyncio
async def test_ws_delete_condition_not_found(mock_hass, mock_conditions, mock_entry, make_runtime):
    """delete_condition returns an error for an unknown condition_id."""
    from custom_components.house_voice.websocket import ws_delete_condition

    mock_entry.runtime_data = make_runtime(conditions=mock_conditions)

    conn = _make_connection()
    await ws_delete_condition.__wrapped__(mock_hass, conn, _make_msg(condition_id="unknown"))

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "not_found"


@pytest.mark.asyncio
async def test_ws_delete_condition_not_ready(mock_hass, mock_entry, make_runtime):
    """delete_condition returns an error if conditions storage is not ready."""
    from custom_components.house_voice.websocket import ws_delete_condition

    mock_entry.runtime_data = make_runtime(conditions=None)

    conn = _make_connection()
    await ws_delete_condition.__wrapped__(mock_hass, conn, _make_msg(condition_id="x"))

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "not_ready"
</content>
