"""Tests for VoiceEngine – say(), spam filter, quiet hours, Jinja2, speakers fix."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from custom_components.house_voice.voice_engine import VoiceEngine


@pytest.mark.asyncio
async def test_say_calls_ultra_tts(mock_engine, mock_storage, sample_event):
    """say() calls script.ultra_tts with correct data."""
    mock_storage.data["ev1"] = sample_event

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False):
        await mock_engine.say("ev1")

    mock_engine.hass.services.async_call.assert_called_once_with(
        "script",
        "ultra_tts",
        {
            "speaker": "media_player.kokken",
            "message": "Opvaskeren er færdig",
            "volume":  0.35,
            "priority": "normal",
        },
        blocking=False,
    )


@pytest.mark.asyncio
async def test_say_unknown_event_raises(mock_engine):
    """say() raises Exception when event_id does not exist."""
    with pytest.raises(Exception, match="not found"):
        await mock_engine.say("does_not_exist")


@pytest.mark.asyncio
async def test_speakers_list_converted_to_string(mock_engine, mock_storage):
    """Speakers stored as list are converted to string before ultra_tts call."""
    mock_storage.data["ev1"] = {
        "message":  "Test",
        "speakers": ["media_player.kokken"],
        "priority": "normal",
        "volume":   0.35,
    }

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False):
        await mock_engine.say("ev1")

    call_kwargs = mock_engine.hass.services.async_call.call_args[0][2]
    assert isinstance(call_kwargs["speaker"], str)
    assert call_kwargs["speaker"] == "media_player.kokken"


@pytest.mark.asyncio
async def test_speakers_multiple_joined(mock_engine, mock_storage):
    """Multiple speakers are joined as comma-separated string."""
    mock_storage.data["ev1"] = {
        "message":  "Test",
        "speakers": ["media_player.stue", "media_player.kokken"],
        "priority": "normal",
        "volume":   0.35,
    }

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False):
        await mock_engine.say("ev1")

    call_kwargs = mock_engine.hass.services.async_call.call_args[0][2]
    assert call_kwargs["speaker"] == "media_player.stue, media_player.kokken"


@pytest.mark.asyncio
async def test_spam_filter_blocks_duplicate(mock_engine, mock_storage, sample_event):
    """Same event called twice within 30 sec is blocked second time."""
    mock_storage.data["ev1"] = sample_event

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False):
        await mock_engine.say("ev1")
        await mock_engine.say("ev1")

    # Only called once – second was blocked
    assert mock_engine.hass.services.async_call.call_count == 1


@pytest.mark.asyncio
async def test_spam_filter_allows_after_reset(mock_engine, mock_storage, sample_event):
    """Same event is allowed again after spam window expires."""
    import time
    mock_storage.data["ev1"] = sample_event

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False):
        await mock_engine.say("ev1")
        # Manually expire the spam timer
        mock_engine._last_spoken["ev1"] = time.monotonic() - 31
        await mock_engine.say("ev1")

    assert mock_engine.hass.services.async_call.call_count == 2


@pytest.mark.asyncio
async def test_quiet_hours_blocks_normal(mock_engine, mock_storage, sample_event):
    """Normal priority event is blocked during quiet hours."""
    mock_storage.data["ev1"] = sample_event  # priority: normal

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=True):
        await mock_engine.say("ev1")

    mock_engine.hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_quiet_hours_allows_critical(mock_engine, mock_storage):
    """Critical priority event passes through quiet hours."""
    mock_storage.data["ev1"] = {
        "message":  "Alarm!",
        "speakers": ["media_player.stue"],
        "priority": "critical",
        "volume":   0.8,
    }

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=True):
        await mock_engine.say("ev1")

    mock_engine.hass.services.async_call.assert_called_once()


@pytest.mark.asyncio
async def test_jinja2_template_rendered(mock_engine, mock_storage):
    """Jinja2 template in message is rendered before TTS call."""
    mock_storage.data["ev1"] = {
        "message":  "Temperaturen er {{ 20 + 2 }} grader",
        "speakers": ["media_player.stue"],
        "priority": "normal",
        "volume":   0.35,
    }

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False), \
         patch("custom_components.house_voice.voice_engine.Template") as mock_tpl_cls:
        mock_tpl = MagicMock()
        mock_tpl.async_render.return_value = "Temperaturen er 22 grader"
        mock_tpl_cls.return_value = mock_tpl

        await mock_engine.say("ev1")

    call_kwargs = mock_engine.hass.services.async_call.call_args[0][2]
    assert call_kwargs["message"] == "Temperaturen er 22 grader"


@pytest.mark.asyncio
async def test_jinja2_template_fallback_on_error(mock_engine, mock_storage):
    """Falls back to raw message if Jinja2 rendering fails."""
    from homeassistant.exceptions import TemplateError

    mock_storage.data["ev1"] = {
        "message":  "{{ invalid template }}",
        "speakers": ["media_player.stue"],
        "priority": "normal",
        "volume":   0.35,
    }

    with patch("custom_components.house_voice.voice_engine._is_quiet_hours", return_value=False), \
         patch("custom_components.house_voice.voice_engine.Template") as mock_tpl_cls:
        mock_tpl = MagicMock()
        mock_tpl.async_render.side_effect = TemplateError("bad template")
        mock_tpl_cls.return_value = mock_tpl

        await mock_engine.say("ev1")

    call_kwargs = mock_engine.hass.services.async_call.call_args[0][2]
    assert call_kwargs["message"] == "{{ invalid template }}"
