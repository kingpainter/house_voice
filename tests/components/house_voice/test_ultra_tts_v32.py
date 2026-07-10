"""Tests for UltraTTS v3.1.1/3.2.0 behaviour not covered in test_ultra_tts.py:

- Duck threshold (state == 'playing' AND volume_level > 0.25)
- HEOS sibling detection (_find_heos_sibling: device_id, then unique_id)
- MA platform detection via state.attributes['app_id']
- Configurable tts_entity (v3.2.0 Options Flow support)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.house_voice.ultra_tts import UltraTTS


def _make_hass_with_state(volume=0.5, state="idle", app_id=None):
    """Return a mock hass with a single media_player state."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()

    attrs = {"volume_level": volume}
    if app_id is not None:
        attrs["app_id"] = app_id

    mp_state = MagicMock()
    mp_state.state = state
    mp_state.attributes = attrs
    hass.states.get = MagicMock(return_value=mp_state)
    return hass


# ── Duck threshold: state == playing AND volume > 0.25 ─────────────────────────

@pytest.mark.asyncio
async def test_no_duck_when_idle_even_with_high_volume():
    """Idle speaker gets full configured volume, no duck, regardless of volume_level."""
    hass = _make_hass_with_state(volume=0.6, state="idle")
    tts = UltraTTS(hass)

    with patch("asyncio.sleep", new=AsyncMock()):
        await tts.async_speak("media_player.stue", "Test", volume=0.5, priority="normal")

    first_call = hass.services.async_call.call_args_list[0]
    # First call is the duck/set-volume call; idle speakers get the full configured volume
    assert first_call[0][1] == "volume_set"
    assert first_call[0][2]["volume_level"] == 0.5


@pytest.mark.asyncio
async def test_no_duck_when_playing_but_volume_at_or_below_threshold():
    """Playing speaker with volume_level <= 0.25 is still treated as idle (MA quirk)."""
    hass = _make_hass_with_state(volume=0.16, state="playing")
    tts = UltraTTS(hass)

    with patch("asyncio.sleep", new=AsyncMock()):
        await tts.async_speak("media_player.kokken_2", "Test", volume=0.45, priority="normal")

    first_call = hass.services.async_call.call_args_list[0]
    assert first_call[0][2]["volume_level"] == 0.45  # full volume, not ducked


@pytest.mark.asyncio
async def test_duck_applied_when_playing_above_threshold():
    """Playing speaker with volume_level > 0.25 gets ducked (normal = 25%)."""
    hass = _make_hass_with_state(volume=0.5, state="playing")
    tts = UltraTTS(hass)

    with patch("asyncio.sleep", new=AsyncMock()):
        await tts.async_speak("media_player.stue", "Test", volume=0.4, priority="normal")

    first_call = hass.services.async_call.call_args_list[0]
    assert first_call[0][2]["volume_level"] == pytest.approx(0.4 * 0.25)


# ── HEOS sibling detection ───────────────────────────────────────────────────────

def test_find_heos_sibling_via_device_id(mock_hass):
    """_find_heos_sibling finds a HEOS entity sharing the same device_id."""
    ma_entry = MagicMock(device_id="dev1", unique_id="12345")
    heos_sibling = MagicMock(platform="heos", domain="media_player", entity_id="media_player.kokken")

    registry = MagicMock()
    registry.async_get = MagicMock(return_value=ma_entry)
    registry.entities.get_entries_for_device_id = MagicMock(return_value=[heos_sibling])

    with patch("custom_components.house_voice.ultra_tts.er.async_get", return_value=registry):
        tts = UltraTTS(mock_hass)
        result = tts._find_heos_sibling("media_player.kokken_2")

    assert result == "media_player.kokken"


def test_find_heos_sibling_via_unique_id_fallback(mock_hass):
    """_find_heos_sibling falls back to matching unique_id when device_id doesn't match."""
    ma_entry = MagicMock(device_id=None, unique_id="155202784")
    heos_entity = MagicMock(platform="heos", domain="media_player",
                             unique_id="155202784", entity_id="media_player.kokken")

    registry = MagicMock()
    registry.async_get = MagicMock(return_value=ma_entry)
    registry.entities = MagicMock()
    registry.entities.values = MagicMock(return_value=[heos_entity])

    with patch("custom_components.house_voice.ultra_tts.er.async_get", return_value=registry):
        tts = UltraTTS(mock_hass)
        result = tts._find_heos_sibling("media_player.kokken_2")

    assert result == "media_player.kokken"


def test_find_heos_sibling_returns_none_when_no_match(mock_hass):
    """_find_heos_sibling returns None when neither strategy finds a match."""
    ma_entry = MagicMock(device_id=None, unique_id="unknown_id")

    registry = MagicMock()
    registry.async_get = MagicMock(return_value=ma_entry)
    registry.entities = MagicMock()
    registry.entities.values = MagicMock(return_value=[])

    with patch("custom_components.house_voice.ultra_tts.er.async_get", return_value=registry):
        tts = UltraTTS(mock_hass)
        result = tts._find_heos_sibling("media_player.kokken_2")

    assert result is None


def test_find_heos_sibling_returns_none_when_entry_missing(mock_hass):
    """_find_heos_sibling returns None if the entity isn't in the registry at all."""
    registry = MagicMock()
    registry.async_get = MagicMock(return_value=None)

    with patch("custom_components.house_voice.ultra_tts.er.async_get", return_value=registry):
        tts = UltraTTS(mock_hass)
        result = tts._find_heos_sibling("media_player.unknown")

    assert result is None


# ── MA platform detection via app_id ─────────────────────────────────────────────

def test_needs_queue_clear_true_via_app_id(mock_hass):
    """_needs_queue_clear returns True when state.attributes['app_id'] == 'music_assistant'."""
    state = MagicMock()
    state.attributes = {"app_id": "music_assistant"}
    mock_hass.states.get = MagicMock(return_value=state)

    tts = UltraTTS(mock_hass)
    assert tts._needs_queue_clear("media_player.kokken_2") is True


def test_needs_queue_clear_false_when_no_app_id_and_not_heos_platform(mock_hass):
    """_needs_queue_clear falls back to registry platform check when app_id is absent."""
    state = MagicMock()
    state.attributes = {}
    mock_hass.states.get = MagicMock(return_value=state)

    entry = MagicMock(platform="cast")
    registry = MagicMock()
    registry.async_get = MagicMock(return_value=entry)

    with patch("custom_components.house_voice.ultra_tts.er.async_get", return_value=registry):
        tts = UltraTTS(mock_hass)
        assert tts._needs_queue_clear("media_player.stue") is False


# ── Configurable tts_entity (v3.2.0) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_default_tts_entity_used_when_not_specified():
    """UltraTTS uses the default tts.home_assistant_cloud entity when none is given."""
    hass = _make_hass_with_state(volume=0.5, state="idle")
    tts = UltraTTS(hass)

    with patch("asyncio.sleep", new=AsyncMock()):
        await tts.async_speak("media_player.stue", "Test", volume=0.5)

    tts_calls = [c for c in hass.services.async_call.call_args_list if c[0][0] == "tts"]
    assert len(tts_calls) == 1
    assert tts_calls[0][1]["target"]["entity_id"] == "tts.home_assistant_cloud"


@pytest.mark.asyncio
async def test_custom_tts_entity_is_used():
    """UltraTTS uses a custom tts_entity when configured via the constructor."""
    hass = _make_hass_with_state(volume=0.5, state="idle")
    tts = UltraTTS(hass, tts_entity="tts.piper")

    with patch("asyncio.sleep", new=AsyncMock()):
        await tts.async_speak("media_player.stue", "Test", volume=0.5)

    tts_calls = [c for c in hass.services.async_call.call_args_list if c[0][0] == "tts"]
    assert len(tts_calls) == 1
    assert tts_calls[0][1]["target"]["entity_id"] == "tts.piper"
</content>
