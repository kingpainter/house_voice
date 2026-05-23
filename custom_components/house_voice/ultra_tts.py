# VERSION = "3.1.0"
# File: ultra_tts.py
# Description: Native Python TTS executor for House Voice Manager.
#              v3.1.0: Simplified – volume set before TTS, fixed delay after,
#              no state polling (unreliable with Music Assistant/HEOS).
#              HEOS queue pre-clear before speak only.

from __future__ import annotations

import asyncio
import logging
import math

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

# TTS entity used for speech output (HA Cloud TTS)
TTS_ENTITY = "tts.home_assistant_cloud"

# Seconds between volume_set and tts.speak so the speaker settles
_PRE_SPEAK_DELAY = 1.0

# Minimum post-speech delay (seconds) before volume restore
_MIN_SPEECH_DELAY = 4.0

# Characters per second – used to estimate speech duration
_CHARS_PER_SECOND = 10.0

# Extra seconds added for HEOS/network latency on top of estimated duration
_HEOS_BUFFER = 3.0

# Volume threshold below which we treat the speaker as idle.
# Music Assistant reports ~0.16 at idle/low – we use 0.25 as cutoff
# so we never accidentally duck a silent speaker down further.
_IDLE_VOLUME_THRESHOLD = 0.25

# Duck volume multipliers per priority (only used when music is actively playing)
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

        # Read original volumes for restore
        original_volumes = await self._get_volumes(speakers)

        # Determine per-speaker TTS volume:
        # idle (original <= threshold) → set to configured volume directly
        # music playing (original > threshold) → duck to volume * duck_factor
        duck_factor = _DUCK_FACTOR.get(priority, _DUCK_FACTOR["normal"])
        tts_volumes = {
            sp: volume if original_volumes[sp] <= _IDLE_VOLUME_THRESHOLD else volume * duck_factor
            for sp in speakers
        }

        # Detect platform for platform-specific behaviour
        heos_like_speakers = [sp for sp in speakers if self._needs_queue_clear(sp)]
        is_heos_like = bool(heos_like_speakers)

        try:
            # 1. Set TTS volume
            await self._set_volumes(speakers, tts_volumes)
            _LOGGER.debug("UltraTTS: volume → %s", tts_volumes)

            # 2. Let volume settle
            await asyncio.sleep(_PRE_SPEAK_DELAY)

            # 3. Clear stale queue entries before speaking (HEOS + Music Assistant)
            for sp in heos_like_speakers:
                await self._clear_queue(sp)

            # 4. Speak
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
            _LOGGER.debug("UltraTTS: tts.speak sent for '%s'", speaker)

            # 5. Wait for playback to finish.
            # HEOS/Music Assistant entity state is unreliable for polling
            # (state may not reflect TTS playback accurately), so we use a
            # calculated delay: estimated speech duration + HEOS buffer.
            delay = self._speech_delay(message, heos=is_heos_like)
            _LOGGER.debug(
                "UltraTTS: waiting %.1f s for '%s' (heos=%s, len=%d)",
                delay, speaker, is_heos_like, len(message),
            )
            await asyncio.sleep(delay)

        except Exception as err:  # noqa: BLE001
            _LOGGER.error("UltraTTS: speak failed for '%s': %s", speaker, err)

        finally:
            # 6. Restore volume unconditionally
            await self._set_volumes(speakers, original_volumes)
            _LOGGER.debug("UltraTTS: volume restored → %s", original_volumes)

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _get_volumes(self, speakers: list[str]) -> dict[str, float]:
        """Read current volume_level from state. Falls back to 0.3."""
        result: dict[str, float] = {}
        for entity_id in speakers:
            state = self.hass.states.get(entity_id)
            vol = state.attributes.get("volume_level") if state else None
            result[entity_id] = float(vol) if vol is not None else 0.3
            if vol is None:
                _LOGGER.warning(
                    "UltraTTS: '%s' volume_level unavailable, defaulting to 0.3", entity_id
                )
        return result

    async def _set_volumes(self, speakers: list[str], volumes: dict[str, float]) -> None:
        """Call media_player.volume_set for each speaker. Errors are logged, not raised."""
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
        """Return True for platforms that accumulate TTS in an internal queue.

        Currently: heos (Denon/Marantz) and music_assistant.
        Both require clear_playlist before speaking to prevent old messages
        replaying. Music Assistant is also slower to start, so gets extra buffer.
        """
        try:
            registry = er.async_get(self.hass)
            entry = registry.async_get(entity_id)
            return entry is not None and entry.platform in ("heos", "music_assistant")
        except Exception:  # noqa: BLE001
            return False

    def _is_heos_speaker(self, entity_id: str) -> bool:
        """Legacy alias – kept for test compatibility."""
        return self._needs_queue_clear(entity_id)

    async def _clear_queue(self, entity_id: str) -> None:
        """Clear the internal queue on HEOS/Music Assistant speakers.

        eid=4 (already empty) is silently ignored.
        """
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
        """Legacy alias – kept for test compatibility."""
        await self._clear_queue(entity_id)

    @staticmethod
    def _speech_delay(message: str, heos: bool = False) -> float:
        """Estimate playback duration + buffer.

        Formula: ceil(len / chars_per_sec), minimum _MIN_SPEECH_DELAY.
        HEOS adds _HEOS_BUFFER for network/buffering latency.
        """
        estimated = math.ceil(len(message) / _CHARS_PER_SECOND)
        delay = max(_MIN_SPEECH_DELAY, float(estimated))
        if heos:
            delay += _HEOS_BUFFER
        return delay
