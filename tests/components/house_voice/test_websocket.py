"""Tests for House Voice Manager WebSocket API."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from custom_components.house_voice.const import DOMAIN


def _make_connection(msg_id=1):
    """Return a mock WebSocket connection."""
    conn = MagicMock()
    conn.send_result = MagicMock()
    conn.send_error = MagicMock()
    return conn


def _make_msg(msg_id=1, **kwargs):
    """Return a mock WebSocket message dict."""
    return {"id": msg_id, **kwargs}


# ── get_events ─────────────────────────────────────────────────────────────

def test_ws_get_events_returns_all(mock_hass, mock_storage, sample_event):
    """get_events returns all stored events."""
    from custom_components.house_voice.websocket import ws_get_events

    mock_storage.data = {"ev1": sample_event}
    mock_hass.data[DOMAIN] = {"storage": mock_storage}

    conn = _make_connection()
    ws_get_events(mock_hass, conn, _make_msg())

    conn.send_result.assert_called_once()
    result = conn.send_result.call_args[0][1]
    assert "ev1" in result["events"]


def test_ws_get_events_storage_not_ready(mock_hass):
    """get_events returns error if storage is not ready."""
    from custom_components.house_voice.websocket import ws_get_events

    mock_hass.data[DOMAIN] = {"storage": None}

    conn = _make_connection()
    ws_get_events(mock_hass, conn, _make_msg())

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "not_ready"


# ── get_media_players ───────────────────────────────────────────────────────

def test_ws_get_media_players_returns_sorted(mock_hass):
    """get_media_players returns sorted list of media_player entities."""
    from custom_components.house_voice.websocket import ws_get_media_players

    state_a = MagicMock()
    state_a.entity_id = "media_player.stue"
    state_a.attributes = {"friendly_name": "Stue"}

    state_b = MagicMock()
    state_b.entity_id = "media_player.kokken"
    state_b.attributes = {"friendly_name": "Køkken"}

    mock_hass.states.async_all = MagicMock(return_value=[state_a, state_b])

    conn = _make_connection()
    ws_get_media_players(mock_hass, conn, _make_msg())

    conn.send_result.assert_called_once()
    players = conn.send_result.call_args[0][1]["media_players"]
    assert players[0]["friendly_name"] == "Køkken"
    assert players[1]["friendly_name"] == "Stue"


# ── save_event ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ws_save_event_success(mock_hass, mock_storage):
    """save_event stores event and returns success."""
    from custom_components.house_voice.websocket import ws_save_event

    mock_hass.data[DOMAIN] = {"storage": mock_storage}

    conn = _make_connection()
    msg = _make_msg(
        event_id="ev1",
        message="Test besked",
        speakers=["media_player.stue"],
        priority="normal",
        volume=0.4,
    )
    await ws_save_event.__wrapped__(mock_hass, conn, msg)

    conn.send_result.assert_called_once()
    assert conn.send_result.call_args[0][1]["success"] is True
    assert "ev1" in mock_storage.data


@pytest.mark.asyncio
async def test_ws_save_event_empty_event_id(mock_hass, mock_storage):
    """save_event returns error for empty event_id."""
    from custom_components.house_voice.websocket import ws_save_event

    mock_hass.data[DOMAIN] = {"storage": mock_storage}

    conn = _make_connection()
    msg = _make_msg(
        event_id="   ",
        message="Test",
        speakers=["media_player.stue"],
        priority="normal",
        volume=0.35,
    )
    await ws_save_event.__wrapped__(mock_hass, conn, msg)

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "invalid_input"


@pytest.mark.asyncio
async def test_ws_save_event_no_speakers(mock_hass, mock_storage):
    """save_event returns error for empty speakers list."""
    from custom_components.house_voice.websocket import ws_save_event

    mock_hass.data[DOMAIN] = {"storage": mock_storage}

    conn = _make_connection()
    msg = _make_msg(
        event_id="ev1",
        message="Test",
        speakers=[],
        priority="normal",
        volume=0.35,
    )
    await ws_save_event.__wrapped__(mock_hass, conn, msg)

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "invalid_input"


@pytest.mark.asyncio
async def test_ws_save_event_invalid_priority(mock_hass, mock_storage):
    """save_event returns error for invalid priority."""
    from custom_components.house_voice.websocket import ws_save_event

    mock_hass.data[DOMAIN] = {"storage": mock_storage}

    conn = _make_connection()
    msg = _make_msg(
        event_id="ev1",
        message="Test",
        speakers=["media_player.stue"],
        priority="ultra",
        volume=0.35,
    )
    await ws_save_event.__wrapped__(mock_hass, conn, msg)

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "invalid_input"


# ── delete_event ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ws_delete_event_success(mock_hass, mock_storage, sample_event):
    """delete_event removes event and returns success."""
    from custom_components.house_voice.websocket import ws_delete_event

    mock_storage.data["ev1"] = sample_event
    mock_hass.data[DOMAIN] = {"storage": mock_storage}

    conn = _make_connection()
    await ws_delete_event.__wrapped__(mock_hass, conn, _make_msg(event_id="ev1"))

    conn.send_result.assert_called_once()
    assert "ev1" not in mock_storage.data


@pytest.mark.asyncio
async def test_ws_delete_event_not_found(mock_hass, mock_storage):
    """delete_event returns error for unknown event_id."""
    from custom_components.house_voice.websocket import ws_delete_event

    mock_hass.data[DOMAIN] = {"storage": mock_storage}

    conn = _make_connection()
    await ws_delete_event.__wrapped__(mock_hass, conn, _make_msg(event_id="unknown"))

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "not_found"


# ── test_event ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ws_test_event_success(mock_hass, mock_engine):
    """test_event calls engine.say and returns success."""
    from custom_components.house_voice.websocket import ws_test_event

    mock_engine.say = AsyncMock()
    mock_hass.data[DOMAIN] = {"engine": mock_engine}

    conn = _make_connection()
    await ws_test_event.__wrapped__(mock_hass, conn, _make_msg(event_id="ev1"))

    mock_engine.say.assert_called_once_with("ev1")
    conn.send_result.assert_called_once()


@pytest.mark.asyncio
async def test_ws_test_event_engine_not_ready(mock_hass):
    """test_event returns error if engine is not ready."""
    from custom_components.house_voice.websocket import ws_test_event

    mock_hass.data[DOMAIN] = {"engine": None}

    conn = _make_connection()
    await ws_test_event.__wrapped__(mock_hass, conn, _make_msg(event_id="ev1"))

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "not_ready"


# ── get_groups ──────────────────────────────────────────────────────────────────

def test_ws_get_groups_returns_all(mock_hass, mock_groups):
    """get_groups returns all stored groups."""
    from custom_components.house_voice.websocket import ws_get_groups

    mock_groups.data = {
        "alle_rum": {"name": "Alle rum", "speakers": ["media_player.stue"]}
    }
    mock_hass.data[DOMAIN] = {"groups": mock_groups}

    conn = _make_connection()
    ws_get_groups(mock_hass, conn, _make_msg())

    conn.send_result.assert_called_once()
    result = conn.send_result.call_args[0][1]
    assert "alle_rum" in result["groups"]


def test_ws_get_groups_not_ready(mock_hass):
    """get_groups returns error if groups is not ready."""
    from custom_components.house_voice.websocket import ws_get_groups

    mock_hass.data[DOMAIN] = {"groups": None}

    conn = _make_connection()
    ws_get_groups(mock_hass, conn, _make_msg())

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "not_ready"


# ── save_group ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ws_save_group_success(mock_hass, mock_groups):
    """save_group stores group and returns success."""
    from custom_components.house_voice.websocket import ws_save_group

    mock_hass.data[DOMAIN] = {"groups": mock_groups}

    conn = _make_connection()
    msg = _make_msg(
        group_id="alle_rum",
        name="Alle rum",
        speakers=["media_player.stue", "media_player.kokken"],
    )
    await ws_save_group.__wrapped__(mock_hass, conn, msg)

    conn.send_result.assert_called_once()
    assert conn.send_result.call_args[0][1]["success"] is True
    assert "alle_rum" in mock_groups.data


@pytest.mark.asyncio
async def test_ws_save_group_empty_id(mock_hass, mock_groups):
    """save_group returns error for empty group_id."""
    from custom_components.house_voice.websocket import ws_save_group

    mock_hass.data[DOMAIN] = {"groups": mock_groups}

    conn = _make_connection()
    msg = _make_msg(group_id="  ", name="Test", speakers=["media_player.stue"])
    await ws_save_group.__wrapped__(mock_hass, conn, msg)

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "invalid_input"


# ── delete_group ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ws_delete_group_success(mock_hass, mock_groups):
    """delete_group removes group and returns success."""
    from custom_components.house_voice.websocket import ws_delete_group

    mock_groups.data["g1"] = {"name": "Test", "speakers": ["media_player.a"]}
    mock_hass.data[DOMAIN] = {"groups": mock_groups}

    conn = _make_connection()
    await ws_delete_group.__wrapped__(mock_hass, conn, _make_msg(group_id="g1"))

    conn.send_result.assert_called_once()
    assert "g1" not in mock_groups.data


@pytest.mark.asyncio
async def test_ws_delete_group_not_found(mock_hass, mock_groups):
    """delete_group returns error for unknown group_id."""
    from custom_components.house_voice.websocket import ws_delete_group

    mock_hass.data[DOMAIN] = {"groups": mock_groups}

    conn = _make_connection()
    await ws_delete_group.__wrapped__(mock_hass, conn, _make_msg(group_id="unknown"))

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "not_found"


# ── get_history ─────────────────────────────────────────────────────────────────

def test_ws_get_history_returns_list(mock_hass, mock_engine):
    """get_history returns history list from engine."""
    from custom_components.house_voice.websocket import ws_get_history

    mock_engine._log_history("ev1", "Hej", "spoken")
    mock_hass.data[DOMAIN] = {"engine": mock_engine}

    conn = _make_connection()
    ws_get_history(mock_hass, conn, _make_msg())

    conn.send_result.assert_called_once()
    result = conn.send_result.call_args[0][1]
    assert len(result["history"]) == 1
    assert result["history"][0]["event_id"] == "ev1"


def test_ws_get_history_engine_not_ready(mock_hass):
    """get_history returns error if engine is not ready."""
    from custom_components.house_voice.websocket import ws_get_history

    mock_hass.data[DOMAIN] = {"engine": None}

    conn = _make_connection()
    ws_get_history(mock_hass, conn, _make_msg())

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args[0][1] == "not_ready"
