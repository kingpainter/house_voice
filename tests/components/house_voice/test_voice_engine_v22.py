"""Tests for VoiceEngine v2.2.0 – queue, conditions, say_text, history, bypass_spam."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.house_voice.voice_engine import VoiceEngine


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_engine(mock_hass, mock_storage, mock_groups, mock_entry):
    """Return a fresh VoiceEngine without starting the queue worker."""
    return VoiceEngine(mock_hass, mock_storage, mock_groups, mock_entry)


async def _flush_queue(engine):
    """Let the event loop process one cycle so the queue worker can run."""
    await asyncio.sleep(0)
    await engine._queue.join()


# ── say() – basic behaviour (v2.2.0 signature) ────────────────────────────────

@pytest.mark.asyncio
async def test_say_calls_ultra_tts(mock_engine, mock_storage, sample_event):
    """say() enqueues a job that calls script.ultra_tts."""
    mock_storage.data["ev1"] = sample_event
    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False):
        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)

    mock_engine.hass.services.async_call.assert_called_once_with(
        "script",
        "ultra_tts",
        {
            "speaker":  "media_player.kokken",
            "message":  "Opvaskeren er færdig",
            "volume":   0.35,
            "priority": "normal",
        },
        blocking=False,
    )
    await mock_engine.stop()


@pytest.mark.asyncio
async def test_say_unknown_event_raises(mock_engine):
    """say() raises ServiceValidationError when event_id does not exist."""
    from homeassistant.exceptions import ServiceValidationError
    with pytest.raises(ServiceValidationError):
        await mock_engine.say("does_not_exist")


@pytest.mark.asyncio
async def test_say_no_speakers_raises(mock_engine, mock_storage):
    """say() raises ServiceValidationError when speakers list is empty."""
    from homeassistant.exceptions import ServiceValidationError
    mock_storage.data["ev1"] = {
        "message": "Test", "speakers": [], "priority": "normal", "volume": 0.35, "condition": "",
    }
    with pytest.raises(ServiceValidationError):
        await mock_engine.say("ev1")


# ── bypass_spam ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bypass_spam_allows_immediate_repeat(mock_engine, mock_storage, sample_event):
    """bypass_spam=True allows the same event to play again within spam window."""
    mock_storage.data["ev1"] = sample_event
    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False):
        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)
        # Normally blocked by spam filter
        await mock_engine.say("ev1", bypass_spam=True)
        await _flush_queue(mock_engine)

    assert mock_engine.hass.services.async_call.call_count == 2
    await mock_engine.stop()


@pytest.mark.asyncio
async def test_spam_filter_blocks_without_bypass(mock_engine, mock_storage, sample_event):
    """Same event without bypass is blocked within spam window."""
    mock_storage.data["ev1"] = sample_event
    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False):
        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)
        await mock_engine.say("ev1")  # blocked
        await _flush_queue(mock_engine)

    assert mock_engine.hass.services.async_call.call_count == 1
    await mock_engine.stop()


# ── Conditions ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_condition_true_allows_playback(mock_engine, mock_storage, mock_hass):
    """A condition that is met allows playback."""
    mock_storage.data["ev1"] = {
        "message": "Test", "speakers": ["media_player.stue"],
        "priority": "normal", "volume": 0.35, "conditions": ["nogen_hjemme"],
    }
    # Set up condition in library: entity is 'on'
    cond_mock = mock_hass.data["house_voice"]["conditions"]
    cond_mock.get_condition = MagicMock(return_value={
        "label": "Nogen er hjemme", "entity_id": "binary_sensor.nogen_hjemme", "state": "on"
    })
    state_mock = MagicMock()
    state_mock.state = "on"
    mock_hass.states.get = MagicMock(return_value=state_mock)

    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False), \
         patch("custom_components.house_voice.voice_engine.Template") as mock_tpl_cls:
        mock_tpl = MagicMock()
        mock_tpl.async_render.return_value = "Test"
        mock_tpl_cls.return_value = mock_tpl

        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)

    mock_engine.hass.services.async_call.assert_called_once()
    await mock_engine.stop()


@pytest.mark.asyncio
async def test_condition_false_blocks_playback(mock_engine, mock_storage, mock_hass):
    """A condition that is not met blocks playback and logs to history."""
    mock_storage.data["ev1"] = {
        "message": "Test", "speakers": ["media_player.stue"],
        "priority": "normal", "volume": 0.35, "conditions": ["nogen_hjemme"],
    }
    # Set up condition in library: entity is 'off' but expected 'on'
    cond_mock = mock_hass.data["house_voice"]["conditions"]
    cond_mock.get_condition = MagicMock(return_value={
        "label": "Nogen er hjemme", "entity_id": "binary_sensor.nogen_hjemme", "state": "on"
    })
    state_mock = MagicMock()
    state_mock.state = "off"  # condition NOT met
    mock_hass.states.get = MagicMock(return_value=state_mock)

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False):
        await mock_engine.say("ev1")

    mock_engine.hass.services.async_call.assert_not_called()
    history = mock_engine.get_history()
    assert history[0]["status"] == "blocked_condition"


@pytest.mark.asyncio
async def test_condition_error_defaults_to_true(mock_engine, mock_storage, mock_hass):
    """An unavailable entity fails open (event plays)."""
    mock_storage.data["ev1"] = {
        "message": "Test", "speakers": ["media_player.stue"],
        "priority": "normal", "volume": 0.35, "conditions": ["nogen_hjemme"],
    }
    # Condition exists but entity is unavailable (states.get returns None)
    cond_mock = mock_hass.data["house_voice"]["conditions"]
    cond_mock.get_condition = MagicMock(return_value={
        "label": "Nogen er hjemme", "entity_id": "binary_sensor.nogen_hjemme", "state": "on"
    })
    mock_hass.states.get = MagicMock(return_value=None)  # entity not found

    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False), \
         patch("custom_components.house_voice.voice_engine.Template") as mock_tpl_cls:
        mock_tpl = MagicMock()
        mock_tpl.async_render.return_value = "Test"
        mock_tpl_cls.return_value = mock_tpl

        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)

    # Fail-open: unavailable entity skips check, event plays
    mock_engine.hass.services.async_call.assert_called_once()
    await mock_engine.stop()


# ── say_text() ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_say_text_enqueues_and_plays(mock_engine):
    """say_text() enqueues a job and calls ultra_tts."""
    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False), \
         patch("custom_components.house_voice.voice_engine.Template") as mock_tpl_cls:
        mock_tpl = MagicMock()
        mock_tpl.async_render.return_value = "Hej verden"
        mock_tpl_cls.return_value = mock_tpl

        await mock_engine.say_text(
            message="Hej verden",
            speakers=["media_player.stue"],
            priority="normal",
            volume=0.5,
        )
        await _flush_queue(mock_engine)

    mock_engine.hass.services.async_call.assert_called_once()
    call_data = mock_engine.hass.services.async_call.call_args[0][2]
    assert call_data["message"] == "Hej verden"
    assert call_data["speaker"] == "media_player.stue"
    assert call_data["volume"] == 0.5
    await mock_engine.stop()


@pytest.mark.asyncio
async def test_say_text_blocked_by_quiet_hours(mock_engine):
    """say_text() is blocked during quiet hours for non-critical priority."""
    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=True):
        await mock_engine.say_text(
            message="Stille besked",
            speakers=["media_player.stue"],
            priority="normal",
        )

    mock_engine.hass.services.async_call.assert_not_called()
    history = mock_engine.get_history()
    assert history[0]["status"] == "blocked_quiet_hours"


@pytest.mark.asyncio
async def test_say_text_critical_bypasses_quiet_hours(mock_engine):
    """say_text() with critical priority plays during quiet hours."""
    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=True), \
         patch("custom_components.house_voice.voice_engine.Template") as mock_tpl_cls:
        mock_tpl = MagicMock()
        mock_tpl.async_render.return_value = "ALARM!"
        mock_tpl_cls.return_value = mock_tpl

        await mock_engine.say_text(
            message="ALARM!",
            speakers=["media_player.stue"],
            priority="critical",
        )
        await _flush_queue(mock_engine)

    mock_engine.hass.services.async_call.assert_called_once()
    await mock_engine.stop()


@pytest.mark.asyncio
async def test_say_text_no_speakers_raises(mock_engine):
    """say_text() raises ServiceValidationError when resolved speakers is empty."""
    from homeassistant.exceptions import ServiceValidationError

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False):
        with pytest.raises(ServiceValidationError):
            await mock_engine.say_text(
                message="Test",
                speakers=[],  # empty after resolve
            )


# ── Group resolution via VoiceEngine ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_say_resolves_group_reference(mock_engine, mock_storage, mock_groups):
    """say() resolves group:<id> references in event speakers."""
    mock_groups.data["alle_rum"] = {
        "name": "Alle rum",
        "speakers": ["media_player.stue", "media_player.kokken"],
    }
    mock_storage.data["ev1"] = {
        "message": "Test", "speakers": ["group:alle_rum"],
        "priority": "normal", "volume": 0.35, "condition": "",
    }
    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False), \
         patch("custom_components.house_voice.voice_engine.Template") as mock_tpl_cls:
        mock_tpl = MagicMock()
        mock_tpl.async_render.return_value = "Test"
        mock_tpl_cls.return_value = mock_tpl

        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)

    call_data = mock_engine.hass.services.async_call.call_args[0][2]
    assert call_data["speaker"] == "media_player.stue, media_player.kokken"
    await mock_engine.stop()


# ── History ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_history_records_spoken(mock_engine, mock_storage, sample_event):
    """A spoken event appears in history with status 'spoken'."""
    mock_storage.data["ev1"] = sample_event
    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False):
        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)

    history = mock_engine.get_history()
    assert history[0]["event_id"] == "ev1"
    assert history[0]["status"] == "spoken"
    await mock_engine.stop()


@pytest.mark.asyncio
async def test_history_records_blocked_spam(mock_engine, mock_storage, sample_event):
    """A spam-blocked event appears in history with status 'blocked_spam'."""
    mock_storage.data["ev1"] = sample_event
    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False):
        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)
        await mock_engine.say("ev1")  # blocked by spam filter

    history = mock_engine.get_history()
    statuses = [h["status"] for h in history]
    assert "blocked_spam" in statuses
    await mock_engine.stop()


@pytest.mark.asyncio
async def test_history_records_blocked_quiet_hours(mock_engine, mock_storage, sample_event):
    """A quiet-hours-blocked event appears in history with correct status."""
    mock_storage.data["ev1"] = sample_event

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=True):
        await mock_engine.say("ev1")

    history = mock_engine.get_history()
    assert history[0]["status"] == "blocked_quiet_hours"


def test_history_newest_first(mock_engine):
    """get_history returns entries newest first."""
    mock_engine._log_history("a", "msg", "spoken")
    mock_engine._log_history("b", "msg", "spoken")
    history = mock_engine.get_history()
    assert history[0]["event_id"] == "b"
    assert history[1]["event_id"] == "a"


def test_history_max_50(mock_engine):
    """History deque is capped at 50 entries."""
    for i in range(60):
        mock_engine._log_history(f"ev{i}", "msg", "spoken")
    assert len(mock_engine.get_history()) == 50


# ── Quiet hours config from entry.options ─────────────────────────────────────

def test_quiet_hours_reads_from_options(mock_engine, mock_entry):
    """_get_quiet_hours returns values from config entry options."""
    mock_entry.options = {"quiet_hours_start": 23, "quiet_hours_end": 6}
    start, end = mock_engine._get_quiet_hours()
    assert start == 23
    assert end == 6


def test_quiet_hours_defaults_when_empty(mock_engine, mock_entry):
    """_get_quiet_hours returns defaults when options are empty."""
    mock_entry.options = {}
    start, end = mock_engine._get_quiet_hours()
    assert start == 22
    assert end == 7


# ── Queue worker lifecycle ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_engine_start_creates_queue_task(mock_engine):
    """start() creates a running asyncio task."""
    mock_engine.start()
    assert mock_engine._queue_task is not None
    assert not mock_engine._queue_task.done()
    await mock_engine.stop()


@pytest.mark.asyncio
async def test_engine_stop_cancels_queue_task(mock_engine):
    """stop() cancels the queue task cleanly."""
    mock_engine.start()
    await mock_engine.stop()
    assert mock_engine._queue_task.done()
