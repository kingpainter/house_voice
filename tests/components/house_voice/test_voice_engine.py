"""Tests for VoiceEngine – say(), spam filter, quiet hours, Jinja2, speakers fix.

NOTE: VoiceEngine now uses native UltraTTS (not script.ultra_tts).
      These tests patch UltraTTS.async_speak and flush the async queue.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.house_voice.voice_engine import VoiceEngine


async def _flush_queue(engine):
    """Let the event loop process one cycle so the queue worker can run."""
    await asyncio.sleep(0)
    await engine._queue.join()


@pytest.mark.asyncio
async def test_say_calls_ultra_tts(mock_engine, mock_storage, sample_event):
    """say() calls UltraTTS.async_speak with correct data."""
    mock_storage.data["ev1"] = sample_event
    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False), \
         patch("custom_components.house_voice.ultra_tts.UltraTTS.async_speak", new=AsyncMock()) as mock_speak:
        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)

    mock_speak.assert_called_once()
    call_kwargs = mock_speak.call_args[1]
    assert call_kwargs["speaker"] == "media_player.kokken"
    assert call_kwargs["message"] == "Opvaskeren er færdig"
    assert call_kwargs["volume"] == 0.35
    assert call_kwargs["priority"] == "normal"
    await mock_engine.stop()


@pytest.mark.asyncio
async def test_say_unknown_event_raises(mock_engine):
    """say() raises ServiceValidationError when event_id does not exist."""
    from homeassistant.exceptions import ServiceValidationError
    with pytest.raises(ServiceValidationError):
        await mock_engine.say("does_not_exist")


@pytest.mark.asyncio
async def test_speakers_list_converted_to_string(mock_engine, mock_storage):
    """Speakers stored as list are converted to string before UltraTTS call."""
    mock_storage.data["ev1"] = {
        "message":    "Test",
        "speakers":   ["media_player.kokken"],
        "priority":   "normal",
        "volume":     0.35,
        "conditions": [],
    }
    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False), \
         patch("custom_components.house_voice.ultra_tts.UltraTTS.async_speak", new=AsyncMock()) as mock_speak:
        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)

    assert mock_speak.call_args[1]["speaker"] == "media_player.kokken"
    await mock_engine.stop()


@pytest.mark.asyncio
async def test_speakers_multiple_joined(mock_engine, mock_storage):
    """Multiple speakers are joined as comma-separated string."""
    mock_storage.data["ev1"] = {
        "message":    "Test",
        "speakers":   ["media_player.stue", "media_player.kokken"],
        "priority":   "normal",
        "volume":     0.35,
        "conditions": [],
    }
    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False), \
         patch("custom_components.house_voice.ultra_tts.UltraTTS.async_speak", new=AsyncMock()) as mock_speak:
        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)

    assert mock_speak.call_args[1]["speaker"] == "media_player.stue, media_player.kokken"
    await mock_engine.stop()


@pytest.mark.asyncio
async def test_spam_filter_blocks_duplicate(mock_engine, mock_storage, sample_event):
    """Same event called twice within 30 sec is blocked second time."""
    mock_storage.data["ev1"] = sample_event
    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False), \
         patch("custom_components.house_voice.ultra_tts.UltraTTS.async_speak", new=AsyncMock()) as mock_speak:
        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)
        await mock_engine.say("ev1")  # blocked
        await _flush_queue(mock_engine)

    assert mock_speak.call_count == 1
    await mock_engine.stop()


@pytest.mark.asyncio
async def test_spam_filter_allows_after_reset(mock_engine, mock_storage, sample_event):
    """Same event is allowed again after spam window expires."""
    mock_storage.data["ev1"] = sample_event
    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False), \
         patch("custom_components.house_voice.ultra_tts.UltraTTS.async_speak", new=AsyncMock()) as mock_speak:
        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)
        mock_engine._last_spoken["ev1"] = time.monotonic() - 31
        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)

    assert mock_speak.call_count == 2
    await mock_engine.stop()


@pytest.mark.asyncio
async def test_quiet_hours_blocks_normal(mock_engine, mock_storage, sample_event):
    """Normal priority event is blocked during quiet hours."""
    mock_storage.data["ev1"] = sample_event

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=True), \
         patch("custom_components.house_voice.ultra_tts.UltraTTS.async_speak", new=AsyncMock()) as mock_speak:
        await mock_engine.say("ev1")

    mock_speak.assert_not_called()


@pytest.mark.asyncio
async def test_quiet_hours_allows_critical(mock_engine, mock_storage):
    """Critical priority event passes through quiet hours."""
    mock_storage.data["ev1"] = {
        "message":    "Alarm!",
        "speakers":   ["media_player.stue"],
        "priority":   "critical",
        "volume":     0.8,
        "conditions": [],
    }
    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=True), \
         patch("custom_components.house_voice.ultra_tts.UltraTTS.async_speak", new=AsyncMock()) as mock_speak:
        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)

    mock_speak.assert_called_once()
    await mock_engine.stop()


@pytest.mark.asyncio
async def test_jinja2_template_rendered(mock_engine, mock_storage):
    """Jinja2 template in message is rendered before TTS call."""
    mock_storage.data["ev1"] = {
        "message":    "Temperaturen er {{ 20 + 2 }} grader",
        "speakers":   ["media_player.stue"],
        "priority":   "normal",
        "volume":     0.35,
        "conditions": [],
    }
    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False), \
         patch("custom_components.house_voice.voice_engine.Template") as mock_tpl_cls, \
         patch("custom_components.house_voice.ultra_tts.UltraTTS.async_speak", new=AsyncMock()) as mock_speak:
        mock_tpl = MagicMock()
        mock_tpl.async_render.return_value = "Temperaturen er 22 grader"
        mock_tpl_cls.return_value = mock_tpl

        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)

    assert mock_speak.call_args[1]["message"] == "Temperaturen er 22 grader"
    await mock_engine.stop()


@pytest.mark.asyncio
async def test_jinja2_template_fallback_on_error(mock_engine, mock_storage):
    """Falls back to raw message if Jinja2 rendering fails."""
    from homeassistant.helpers.template import TemplateError

    mock_storage.data["ev1"] = {
        "message":    "{{ invalid template }}",
        "speakers":   ["media_player.stue"],
        "priority":   "normal",
        "volume":     0.35,
        "conditions": [],
    }
    mock_engine.start()

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False), \
         patch("custom_components.house_voice.voice_engine.Template") as mock_tpl_cls, \
         patch("custom_components.house_voice.ultra_tts.UltraTTS.async_speak", new=AsyncMock()) as mock_speak:
        mock_tpl = MagicMock()
        mock_tpl.async_render.side_effect = TemplateError("bad template")
        mock_tpl_cls.return_value = mock_tpl

        await mock_engine.say("ev1")
        await _flush_queue(mock_engine)

    assert mock_speak.call_args[1]["message"] == "{{ invalid template }}"
    await mock_engine.stop()
