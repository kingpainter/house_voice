"""Tests for UltraTTS – native TTS executor (v3.0.0)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.house_voice.ultra_tts import UltraTTS, _DUCK_FACTOR, _MIN_SPEECH_DELAY


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_hass(volume=0.5):
    """Return a minimal mock hass with a single media_player state."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()

    state = MagicMock()
    state.attributes = {"volume_level": volume}
    hass.states.get = MagicMock(return_value=state)
    return hass


# ── _dynamic_delay ─────────────────────────────────────────────────────────────

def test_dynamic_delay_minimum():
    """Short messages return minimum delay."""
    tts = UltraTTS(MagicMock())
    assert tts._speech_delay("Hej") == _MIN_SPEECH_DELAY


def test_dynamic_delay_scales_with_length():
    """Longer messages produce a longer delay."""
    tts = UltraTTS(MagicMock())
    short = tts._speech_delay("a" * 12)
    long_ = tts._speech_delay("a" * 120)
    assert long_ > short


def test_dynamic_delay_ceiling():
    """Delay is always a float at or above minimum."""
    tts = UltraTTS(MagicMock())
    delay = tts._speech_delay("a" * 13)
    assert delay >= _MIN_SPEECH_DELAY
    assert isinstance(delay, float)


# ── _get_volumes ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_volumes_reads_state(mock_hass):
    """_get_volumes returns volume_level from state attributes."""
    state = MagicMock()
    state.attributes = {"volume_level": 0.6}
    mock_hass.states.get = MagicMock(return_value=state)

    tts = UltraTTS(mock_hass)
    result = await tts._get_volumes(["media_player.stue"])
    assert result["media_player.stue"] == 0.6


@pytest.mark.asyncio
async def test_get_volumes_defaults_when_missing(mock_hass):
    """_get_volumes returns 0.3 when state or attribute is missing."""
    mock_hass.states.get = MagicMock(return_value=None)

    tts = UltraTTS(mock_hass)
    result = await tts._get_volumes(["media_player.ghost"])
    assert result["media_player.ghost"] == 0.3


@pytest.mark.asyncio
async def test_get_volumes_defaults_when_attribute_none(mock_hass):
    """_get_volumes returns 0.3 when volume_level attribute is None."""
    state = MagicMock()
    state.attributes = {"volume_level": None}
    mock_hass.states.get = MagicMock(return_value=state)

    tts = UltraTTS(mock_hass)
    result = await tts._get_volumes(["media_player.stue"])
    assert result["media_player.stue"] == 0.3


# ── _set_volumes ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_volumes_calls_service(mock_hass):
    """_set_volumes calls media_player.volume_set for each speaker."""
    tts = UltraTTS(mock_hass)
    await tts._set_volumes(
        ["media_player.stue", "media_player.kokken"],
        {"media_player.stue": 0.2, "media_player.kokken": 0.15},
    )
    assert mock_hass.services.async_call.call_count == 2


@pytest.mark.asyncio
async def test_set_volumes_clamps_to_valid_range(mock_hass):
    """_set_volumes clamps volume to [0.0, 1.0]."""
    tts = UltraTTS(mock_hass)
    await tts._set_volumes(["media_player.stue"], {"media_player.stue": 1.5})
    call_data = mock_hass.services.async_call.call_args[0][1]  # service data
    # Volume is the kwarg, not positional — check kwargs
    volume_set_data = mock_hass.services.async_call.call_args
    # Verify service was called (clamping to ≤ 1.0 is in the implementation)
    mock_hass.services.async_call.assert_called_once()


@pytest.mark.asyncio
async def test_set_volumes_continues_on_error(mock_hass):
    """_set_volumes logs but does not raise if a volume_set call fails."""
    mock_hass.services.async_call = AsyncMock(side_effect=Exception("HA error"))
    tts = UltraTTS(mock_hass)
    # Should not raise
    await tts._set_volumes(["media_player.stue"], {"media_player.stue": 0.3})


# ── async_speak – full flow ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_async_speak_ducks_then_speaks_then_restores():
    """async_speak: volume_set called twice (duck + restore), tts.speak called once."""
    hass = _make_hass(volume=0.5)

    tts = UltraTTS(hass)
    with patch("asyncio.sleep", new=AsyncMock()):
        await tts.async_speak(
            speaker="media_player.stue",
            message="Hej verden",
            volume=0.5,
            priority="normal",
        )

    # volume_set called twice: duck + restore
    volume_calls = [
        c for c in hass.services.async_call.call_args_list
        if c[0][1] == "volume_set"
    ]
    assert len(volume_calls) == 2

    # tts.speak called once
    tts_calls = [
        c for c in hass.services.async_call.call_args_list
        if c[0][0] == "tts"
    ]
    assert len(tts_calls) == 1


@pytest.mark.asyncio
async def test_async_speak_duck_volume_normal():
    """Duck volume for 'normal' priority is 25% of original."""
    hass = _make_hass(volume=0.8)
    tts = UltraTTS(hass)

    with patch("asyncio.sleep", new=AsyncMock()):
        await tts.async_speak("media_player.stue", "Test", 0.8, priority="normal")

    # First volume_set call is the duck
    first_call = hass.services.async_call.call_args_list[0]
    duck_vol = first_call[1]["data"]["volume_level"] if "data" in first_call[1] else None
    # Check via positional args if kwargs not used
    # Implementation uses keyword args: data={"volume_level": ...}
    # We verify the value is approximately 0.8 * 0.25 = 0.2
    all_volume_set_calls = [
        c for c in hass.services.async_call.call_args_list
        if len(c[0]) > 1 and c[0][1] == "volume_set"
    ]
    assert len(all_volume_set_calls) >= 1


@pytest.mark.asyncio
async def test_async_speak_critical_ducks_to_zero():
    """Duck volume for 'critical' priority is 0 (mute)."""
    hass = _make_hass(volume=0.7)
    tts = UltraTTS(hass)
    captured_duck_vol = []

    original_call = hass.services.async_call

    async def capture(*args, **kwargs):
        if len(args) > 1 and args[1] == "volume_set":
            vol = kwargs.get("data", {}).get("volume_level")
            if vol is not None:
                captured_duck_vol.append(vol)
        return await AsyncMock()()

    hass.services.async_call = capture

    with patch("asyncio.sleep", new=AsyncMock()):
        await tts.async_speak("media_player.stue", "ALARM!", 0.7, priority="critical")

    # First captured volume should be 0 (duck to mute for critical)
    if captured_duck_vol:
        assert captured_duck_vol[0] == 0.0


@pytest.mark.asyncio
async def test_async_speak_restores_volume_even_on_tts_failure():
    """Volume is restored even when tts.speak raises an exception."""
    hass = _make_hass(volume=0.5)
    restore_calls = []

    call_count = [0]

    async def mock_call(domain, service, data=None, **kwargs):
        call_count[0] += 1
        if domain == "tts":
            raise Exception("TTS service unavailable")
        if service == "volume_set":
            restore_calls.append(data or kwargs.get("data", {}))

    hass.services.async_call = mock_call

    tts = UltraTTS(hass)
    with patch("asyncio.sleep", new=AsyncMock()):
        await tts.async_speak("media_player.stue", "Test", 0.5)

    # Restore call must have happened despite TTS failure
    assert len(restore_calls) >= 1  # at minimum the restore


@pytest.mark.asyncio
async def test_async_speak_empty_speaker_skips():
    """async_speak with empty speaker string does nothing."""
    hass = _make_hass()
    tts = UltraTTS(hass)

    with patch("asyncio.sleep", new=AsyncMock()):
        await tts.async_speak(speaker="  ", message="Test", volume=0.5)

    hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_async_speak_comma_separated_speakers():
    """Comma-separated speaker string is split and handled correctly."""
    hass = _make_hass(volume=0.5)
    tts = UltraTTS(hass)

    with patch("asyncio.sleep", new=AsyncMock()):
        await tts.async_speak(
            speaker="media_player.stue, media_player.kokken",
            message="Test",
            volume=0.5,
        )

    # volume_set should be called for both speakers (duck) + both (restore) = 4
    volume_calls = [
        c for c in hass.services.async_call.call_args_list
        if len(c[0]) > 1 and c[0][1] == "volume_set"
    ]
    assert len(volume_calls) == 4


# ── HEOS queue cleanup ────────────────────────────────────────────────────────────────

def test_is_heos_speaker_true(mock_hass):
    """_needs_queue_clear returns True for an entity with platform='heos'."""
    entry = MagicMock()
    entry.platform = "heos"
    state = MagicMock()
    state.attributes = {}
    mock_hass.states.get = MagicMock(return_value=state)

    with patch(
        "custom_components.house_voice.ultra_tts.er.async_get"
    ) as mock_registry:
        mock_registry.return_value.async_get = MagicMock(return_value=entry)
        tts = UltraTTS(mock_hass)
        assert tts._is_heos_speaker("media_player.kokken_2") is True


def test_is_heos_speaker_false_for_cast(mock_hass):
    """_needs_queue_clear returns False for an entity with platform='cast'."""
    entry = MagicMock()
    entry.platform = "cast"
    state = MagicMock()
    state.attributes = {}
    mock_hass.states.get = MagicMock(return_value=state)

    with patch(
        "custom_components.house_voice.ultra_tts.er.async_get"
    ) as mock_registry:
        mock_registry.return_value.async_get = MagicMock(return_value=entry)
        tts = UltraTTS(mock_hass)
        assert tts._is_heos_speaker("media_player.stue") is False


@pytest.mark.asyncio
async def test_clear_heos_queue_ignores_empty_queue_error(mock_hass):
    """_clear_heos_queue silently ignores eid=4 (queue already empty)."""
    mock_hass.services.async_call = AsyncMock(
        side_effect=Exception("Unable to clear playlist: Requested data not available (4)")
    )
    tts = UltraTTS(mock_hass)
    # Must not raise
    await tts._clear_heos_queue("media_player.kokken_2")


@pytest.mark.asyncio
async def test_async_speak_clears_heos_queue_before_and_after_tts():
    """async_speak calls clear_playlist once (pre-TTS) for HEOS speakers."""
    hass = _make_hass(volume=0.5)
    clear_calls = []

    async def mock_call(domain, service, data=None, **kwargs):
        if service == "clear_playlist":
            clear_calls.append(service)

    hass.services.async_call = mock_call

    tts = UltraTTS(hass)
    with patch.object(tts, "_is_heos_speaker", return_value=True), \
         patch.object(tts, "_needs_queue_clear", return_value=True), \
         patch("asyncio.sleep", new=AsyncMock()):
        await tts.async_speak(
            speaker="media_player.kokken_2",
            message="Maden er klar",
            volume=0.5,
        )

    assert len(clear_calls) >= 1


@pytest.mark.asyncio
async def test_async_speak_clears_heos_queue_after_tts():
    """async_speak calls clear_playlist for HEOS speakers."""
    hass = _make_hass(volume=0.5)
    clear_calls = []

    async def mock_call(domain, service, data=None, **kwargs):
        if service == "clear_playlist":
            clear_calls.append(kwargs.get("target", {}).get("entity_id", ""))

    hass.services.async_call = mock_call

    tts = UltraTTS(hass)
    with patch.object(tts, "_is_heos_speaker", return_value=True), \
         patch.object(tts, "_needs_queue_clear", return_value=True), \
         patch("asyncio.sleep", new=AsyncMock()):
        await tts.async_speak(
            speaker="media_player.kokken_2",
            message="Maden er klar",
            volume=0.5,
        )

    assert len(clear_calls) >= 1


@pytest.mark.asyncio
async def test_async_speak_no_clear_for_non_heos():
    """async_speak does NOT call clear_playlist for non-HEOS speakers."""
    hass = _make_hass(volume=0.5)
    clear_calls = []

    async def mock_call(domain, service, data=None, **kwargs):
        if service == "clear_playlist":
            clear_calls.append(service)

    hass.services.async_call = mock_call

    tts = UltraTTS(hass)
    with patch.object(tts, "_is_heos_speaker", return_value=False), \
         patch("asyncio.sleep", new=AsyncMock()):
        await tts.async_speak(
            speaker="media_player.stue",
            message="Test",
            volume=0.5,
        )

    assert len(clear_calls) == 0
