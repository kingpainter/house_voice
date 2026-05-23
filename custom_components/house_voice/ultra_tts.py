# VERSION = "3.1.1"
# File: ultra_tts.py
# Description: Native Python TTS executor for House Voice Manager.
#              Handles volume set, tts.speak, dynamic delay, volume restore.
#              HEOS/MA queue pre-clear via sibling entity detection.

from __future__ import annotations

import asyncio
import logging
import math

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

TTS_ENTITY = "tts.home_assistant_cloud"

_PRE_SPEAK_DELAY = 1.0
_MIN_SPEECH_DELAY = 8.0
_CHARS_PER_SECOND = 10.0
_HEOS_BUFFER = 3.0
_IDLE_VOLUME_THRESHOLD = 0.25

_DUCK_FACTOR: dict[str, float] = {
    "critical": 0.0,
    "normal":   0.25,
    "info":     0.40,
}


class UltraTTS:
    """Native Python TTS executor."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def async_speak(
        self,
        speaker: str,
        message: str,
        volume: float,
        priority: str = "normal",
    ) -> None:
        """Set volume, speak, wait for completion, restore volume."""
        speakers = [s.strip() for s in speaker.split(",") if s.strip()]
        if not speakers:
            _LOGGER.warning("UltraTTS: no valid speakers in '%s', skipping", speaker)
            return

        original_volumes = await self._get_volumes(speakers)

        # Duck only if music is actively playing; otherwise use configured volume
        duck_factor = _DUCK_FACTOR.get(priority, _DUCK_FACTOR["normal"])
        tts_volumes = {}
        for sp in speakers:
            state = self.hass.states.get(sp)
            is_playing = state and state.state == "playing"
            if is_playing and original_volumes[sp] > _IDLE_VOLUME_THRESHOLD:
                tts_volumes[sp] = volume * duck_factor
            else:
                tts_volumes[sp] = volume

        # Detect MA/HEOS speakers that need queue management
        heos_like_speakers = [sp for sp in speakers if self._needs_queue_clear(sp)]
        is_heos_like = bool(heos_like_speakers)

        # Find HEOS sibling for each MA speaker (for clear_playlist + volume)
        sibling_map: dict[str, str] = {}
        for sp in heos_like_speakers:
            sibling = self._find_heos_sibling(sp)
            if sibling:
                sibling_map[sp] = sibling

        try:
            # Set TTS volume on MA entity + HEOS sibling
            await self._set_volumes(speakers, tts_volumes)
            if sibling_map:
                sibling_volumes = {sibling_map[sp]: tts_volumes[sp] for sp in sibling_map}
                await self._set_volumes(list(sibling_volumes.keys()), sibling_volumes)
            _LOGGER.debug("UltraTTS: volume → %s (sibling=%s)", tts_volumes, sibling_map)

            await asyncio.sleep(_PRE_SPEAK_DELAY)

            # Clear stale queue on HEOS sibling (or MA entity if no sibling)
            for sp in heos_like_speakers:
                await self._clear_queue(sibling_map.get(sp, sp))

            # Speak
            await self.hass.services.async_call(
                "tts", "speak",
                {
                    "cache": False,
                    "message": message,
                    "media_player_entity_id": speakers[0] if len(speakers) == 1 else speakers,
                },
                target={"entity_id": TTS_ENTITY},
                blocking=False,
            )

            delay = self._speech_delay(message, heos=is_heos_like)
            _LOGGER.debug("UltraTTS: waiting %.1f s (heos=%s)", delay, is_heos_like)
            await asyncio.sleep(delay)

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("UltraTTS: speak failed for '%s': %s", speaker, err)

        finally:
            # Restore volume on MA entity + HEOS sibling
            await self._set_volumes(speakers, original_volumes)
            if sibling_map:
                sibling_restores = {sibling_map[sp]: original_volumes[sp] for sp in sibling_map}
                await self._set_volumes(list(sibling_restores.keys()), sibling_restores)
            _LOGGER.debug("UltraTTS: volume restored → %s", original_volumes)

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _get_volumes(self, speakers: list[str]) -> dict[str, float]:
        """Read current volume_level from state. Falls back to 0.3."""
        result: dict[str, float] = {}
        for entity_id in speakers:
            try:
                state = self.hass.states.get(entity_id)
                vol = state.attributes.get("volume_level") if state else None
                result[entity_id] = float(vol) if vol is not None else 0.3
                if vol is None:
                    _LOGGER.warning("UltraTTS: '%s' volume_level unavailable, defaulting to 0.3", entity_id)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("UltraTTS: _get_volumes error for '%s': %s", entity_id, err)
                result[entity_id] = 0.3
        return result

    async def _set_volumes(self, speakers: list[str], volumes: dict[str, float]) -> None:
        """Call media_player.volume_set for each speaker."""
        for entity_id in speakers:
            target_vol = round(max(0.0, min(1.0, volumes[entity_id])), 3)
            try:
                await self.hass.services.async_call(
                    "media_player", "volume_set",
                    {"volume_level": target_vol},
                    target={"entity_id": entity_id},
                    blocking=False,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("UltraTTS: volume_set failed for '%s': %s", entity_id, err)

    def _needs_queue_clear(self, entity_id: str) -> bool:
        """Return True for MA/HEOS speakers that accumulate TTS in their queue."""
        state = self.hass.states.get(entity_id)
        if state and state.attributes.get("app_id") == "music_assistant":
            return True
        try:
            registry = er.async_get(self.hass)
            entry = registry.async_get(entity_id)
            return entry is not None and entry.platform in ("heos", "music_assistant", "mass")
        except Exception:  # noqa: BLE001
            return False

    def _find_heos_sibling(self, entity_id: str) -> str | None:
        """Find the direct HEOS entity for a Music Assistant speaker.

        Strategy 1: same device_id.
        Strategy 2: matching unique_id (MA uses HEOS player_id as unique_id).
        """
        try:
            registry = er.async_get(self.hass)
            entry = registry.async_get(entity_id)
            if entry is None:
                return None

            # Strategy 1: same device
            if entry.device_id:
                for sibling in registry.entities.get_entries_for_device_id(entry.device_id):
                    if sibling.platform == "heos" and sibling.domain == "media_player":
                        _LOGGER.debug("UltraTTS: HEOS sibling (device) %s → %s", entity_id, sibling.entity_id)
                        return sibling.entity_id

            # Strategy 2: matching unique_id
            for e in registry.entities.values():
                if e.platform == "heos" and e.domain == "media_player" and e.unique_id == entry.unique_id:
                    _LOGGER.debug("UltraTTS: HEOS sibling (uid) %s → %s", entity_id, e.entity_id)
                    return e.entity_id

        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("UltraTTS: sibling lookup failed for '%s': %s", entity_id, err)
        return None

    def _is_heos_speaker(self, entity_id: str) -> bool:
        """Legacy alias for test compatibility."""
        return self._needs_queue_clear(entity_id)

    async def _clear_queue(self, entity_id: str) -> None:
        """Clear MA/HEOS queue. eid=4 (already empty) is silently ignored."""
        try:
            await self.hass.services.async_call(
                "media_player", "clear_playlist", {},
                target={"entity_id": entity_id},
                blocking=True,
            )
            _LOGGER.debug("UltraTTS: queue cleared for '%s'", entity_id)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("UltraTTS: clear_playlist '%s' (likely empty): %s", entity_id, err)

    async def _clear_heos_queue(self, entity_id: str) -> None:
        """Legacy alias for test compatibility."""
        await self._clear_queue(entity_id)

    @staticmethod
    def _speech_delay(message: str, heos: bool = False) -> float:
        """Estimate playback duration. HEOS/MA adds buffer for network latency."""
        estimated = math.ceil(len(message) / _CHARS_PER_SECOND)
        delay = max(_MIN_SPEECH_DELAY, float(estimated))
        if heos:
            delay += _HEOS_BUFFER
        return delay
