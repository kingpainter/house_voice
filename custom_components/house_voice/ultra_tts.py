# VERSION = "3.0.1"
# File: ultra_tts.py
# Description: Native Python TTS executor for House Voice Manager.
#              Replaces the YAML script.ultra_tts with a direct Python implementation.
#              Handles: volume ducking, tts.speak, dynamic post-speech delay, volume restore.
#              v3.0.1: HEOS queue cleanup after TTS (clear_playlist, ignore empty-queue error).
#              Called by VoiceEngine._execute_tts instead of script.ultra_tts.

from __future__ import annotations

import asyncio
import logging
import math

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

# TTS entity used for speech output (HA Cloud TTS)
TTS_ENTITY = "tts.home_assistant_cloud"

# Seconds to wait after setting duck volume before speaking
_DUCK_SETTLE_DELAY = 1.0

# Minimum post-speech delay in seconds (allows TTS audio to finish)
_MIN_SPEECH_DELAY = 3.0

# Extra delay added for HEOS speakers to account for buffering + network startup latency
_HEOS_EXTRA_DELAY = 4.0

# Characters per second – used to estimate speech duration
_CHARS_PER_SECOND = 12.0

# Duck volume multipliers per priority
_DUCK_FACTOR: dict[str, float] = {
    "critical": 0.0,   # Mute – critical always cuts through
    "normal":   0.25,  # 25 % of original volume
    "info":     0.40,  # 40 % of original volume
}


class UltraTTS:
    """Native Python TTS executor.

    Performs the full duck → speak → wait → restore cycle for a single
    media player. For multi-speaker events, VoiceEngine passes one speaker
    at a time (or a comma-separated string – see async_speak for details).
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def async_speak(
        self,
        speaker: str,
        message: str,
        volume: float,
        priority: str = "normal",
    ) -> None:
        """Duck, speak and restore volume for the given speaker.

        Args:
            speaker:  A single media_player entity ID.
                      Comma-separated multi-speaker strings are split and
                      handled as parallel duck/restore with sequential speak.
            message:  The text to speak.
            volume:   Target playback volume (used as the post-restore level).
            priority: 'info', 'normal' or 'critical'. Controls duck depth.
        """
        # Support comma-separated speaker strings from legacy callers
        speakers = [s.strip() for s in speaker.split(",") if s.strip()]
        if not speakers:
            _LOGGER.warning("UltraTTS: no valid speakers in '%s', skipping", speaker)
            return

        # Read current volumes before we change anything – needed for restore
        original_volumes = await self._get_volumes(speakers)

        duck_factor = _DUCK_FACTOR.get(priority, _DUCK_FACTOR["normal"])

        # Determine TTS playback volume per speaker:
        #   - Music playing (original > 0.05): duck the music, speak at volume
        #   - Idle (original <= 0.05): just set to the configured volume directly
        # In both cases the speaker ends up at the right loudness for TTS.
        # After TTS we always restore to original_volume.
        tts_volumes = {
            sp: (
                volume * duck_factor   # lower the music, TTS rides on top at volume
                if original_volumes[sp] > 0.05
                else volume            # idle: straight to configured volume
            )
            for sp in speakers
        }

        # Brief pause so duck takes effect before speech starts
        await asyncio.sleep(_DUCK_SETTLE_DELAY)

        await self._set_volumes(speakers, tts_volumes)
        _LOGGER.debug("UltraTTS: volume set for TTS: %s", tts_volumes)

        # HEOS pre-clear: remove stale TTS files before speaking
        # so old messages don’t replay first.
        heos_speakers = [sp for sp in speakers if self._is_heos_speaker(sp)]
        for sp in heos_speakers:
            await self._clear_heos_queue(sp)

        # Speak via HA Cloud TTS
        try:
            await self.hass.services.async_call(
                "tts",
                "speak",
                {
                    "cache":                   False,
                    "message":                 message,
                    "media_player_entity_id":  speakers[0] if len(speakers) == 1 else speakers,
                },
                target={"entity_id": TTS_ENTITY},
                blocking=False,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("UltraTTS: tts.speak failed for '%s': %s", speaker, err)
        finally:
            # Wait for playback to finish on each speaker.
            # Uses state-based waiting (idle/paused after playing) so we never
            # restore volume while audio is still playing.
            # Falls back to estimated delay if state never reaches 'playing'.
            estimated = self._dynamic_delay(message) + _HEOS_EXTRA_DELAY
            for sp in speakers:
                await self._wait_for_idle(sp, estimated)

            # Restore all speakers to their pre-TTS volume
            await self._set_volumes(speakers, original_volumes)
            _LOGGER.debug("UltraTTS: volume restored to original: %s", original_volumes)

            # NOTE: No post-speak clear_playlist here.
            # Clearing the queue while HEOS is still playing stops playback immediately.
            # The pre-speak clear above is sufficient to prevent queue accumulation.

    # ── Internal helpers ───────────────────────────────────────────────────────

    async def _get_volumes(self, speakers: list[str]) -> dict[str, float]:
        """Read current volume_level for each speaker.

        Falls back to 0.3 if the attribute is unavailable.
        """
        result: dict[str, float] = {}
        for entity_id in speakers:
            state = self.hass.states.get(entity_id)
            if state is not None:
                vol = state.attributes.get("volume_level")
                result[entity_id] = float(vol) if vol is not None else 0.3
            else:
                _LOGGER.warning(
                    "UltraTTS: speaker '%s' not found in state machine, defaulting volume to 0.3",
                    entity_id,
                )
                result[entity_id] = 0.3
        return result

    async def _set_volumes(
        self,
        speakers: list[str],
        volumes: dict[str, float],
    ) -> None:
        """Set volume_level on each speaker.

        Sends individual volume_set calls. Errors are logged but do not
        stop the TTS flow so speech is not lost due to a volume failure.
        """
        for entity_id in speakers:
            target_vol = round(max(0.0, min(1.0, volumes[entity_id])), 3)
            try:
                await self.hass.services.async_call(
                    "media_player",
                    "volume_set",
                    {"volume_level": target_vol},
                    target={"entity_id": entity_id},
                    blocking=False,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "UltraTTS: volume_set failed for '%s': %s", entity_id, err
                )

    def _is_heos_speaker(self, entity_id: str) -> bool:
        """Return True if this entity is provided by the HEOS integration.

        Uses the entity registry to look up the platform. Falls back to False
        if the entity is not registered (custom/manual entities).
        """
        try:
            registry = er.async_get(self.hass)
            entry = registry.async_get(entity_id)
            return entry is not None and entry.platform == "heos"
        except Exception:  # noqa: BLE001
            return False

    async def _clear_heos_queue(self, entity_id: str) -> None:
        """Clear the HEOS internal queue after TTS playback.

        HEOS accumulates TTS mp3 files in its queue and replays them on
        subsequent TTS calls unless cleared. This is a known HEOS behaviour.

        The clear_playlist call returns eid=4 ('Requested data not available')
        when the queue is already empty – this is normal and silently ignored.
        Since HA 2025.2, this error is raised as an exception instead of logged.
        """
        try:
            await self.hass.services.async_call(
                "media_player",
                "clear_playlist",
                {},
                target={"entity_id": entity_id},
                blocking=True,
            )
            _LOGGER.debug("UltraTTS: HEOS queue cleared for '%s'", entity_id)
        except Exception as err:  # noqa: BLE001
            # eid=4 = queue already empty – not an error, ignore silently
            _LOGGER.debug(
                "UltraTTS: HEOS clear_playlist for '%s' returned (expected if queue empty): %s",
                entity_id,
                err,
            )

    @staticmethod
    def _dynamic_delay(message: str) -> float:
        """Estimate how long the TTS audio will take to play.

        Formula: ceil(len(message) / 12), minimum 3 seconds.
        Matches the YAML script.ultra_tts dynamic_delay logic.
        """
        estimated = math.ceil(len(message) / _CHARS_PER_SECOND)
        return max(_MIN_SPEECH_DELAY, float(estimated))
