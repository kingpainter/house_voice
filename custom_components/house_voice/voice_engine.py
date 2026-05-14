# VERSION = "2.1.0"
# File: voice_engine.py
# Description: TTS logic and priority handling for House Voice Manager

import logging
import time

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.template import Template, TemplateError
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SPAM_FILTER_SECONDS = 30
QUIET_HOURS_START = 22
QUIET_HOURS_END = 7

# Clean up _last_spoken entries older than this (seconds)
_CLEANUP_AGE = 3600


def _is_quiet_hours() -> bool:
    """Return True if current local time is within quiet hours (22:00–07:00)."""
    now = dt_util.now()
    hour = now.hour
    return hour >= QUIET_HOURS_START or hour < QUIET_HOURS_END


class VoiceEngine:
    """Handles TTS routing, spam filtering, quiet hours and template rendering."""

    def __init__(self, hass, storage) -> None:
        self.hass = hass
        self.storage = storage
        self._last_spoken: dict[str, float] = {}

    def _cleanup_last_spoken(self, now: float) -> None:
        """Remove stale entries from _last_spoken to prevent unbounded growth."""
        stale = [k for k, t in self._last_spoken.items() if (now - t) > _CLEANUP_AGE]
        for k in stale:
            del self._last_spoken[k]

    async def say(self, event_id: str, bypass_spam: bool = False) -> None:
        """Speak a voice event by ID.

        Args:
            event_id:    The ID of the stored voice event to speak.
            bypass_spam: If True, skip the spam filter (used for test playback).
        """
        event = self.storage.get_event(event_id)

        if not event:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="event_not_found",
                translation_placeholders={"event_id": event_id},
            )

        message: str  = event.get("message", "")
        speakers       = event.get("speakers", [])
        volume: float  = event.get("volume", 0.35)
        priority: str  = event.get("priority", "normal")

        # Guard: empty speakers – user configuration error
        if not speakers:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_speakers",
                translation_placeholders={"event_id": event_id},
            )

        # Spam filter – block same event within 30 seconds (skipped for test calls)
        now = time.monotonic()
        self._cleanup_last_spoken(now)
        if not bypass_spam:
            last = self._last_spoken.get(event_id)
            if last is not None and (now - last) < SPAM_FILTER_SECONDS:
                remaining = int(SPAM_FILTER_SECONDS - (now - last))
                _LOGGER.warning(
                    "House Voice: Spam filter blocked '%s' – try again in %d seconds",
                    event_id,
                    remaining,
                )
                return

        # Quiet hours – block non-critical messages between 22:00 and 07:00
        if _is_quiet_hours() and priority != "critical":
            _LOGGER.info(
                "House Voice: Quiet hours blocked '%s' (priority: %s)",
                event_id,
                priority,
            )
            return

        self._last_spoken[event_id] = now

        # Render Jinja2 templates in message – fall back to raw message on error
        try:
            message = Template(message, self.hass).async_render(parse_result=False)
        except TemplateError as err:
            _LOGGER.warning(
                "House Voice: Template render failed for '%s', using raw message. Error: %s",
                event_id,
                err,
            )

        # Ensure speakers is a string – ultra_tts expects a plain entity ID string
        if isinstance(speakers, list):
            speaker_str = speakers[0] if len(speakers) == 1 else ", ".join(speakers)
        else:
            speaker_str = str(speakers)

        # Call ultra_tts – non-blocking to avoid stalling HA's event loop.
        # ultra_tts can run 3–30+ seconds; blocking=True would freeze the loop.
        # Errors are surfaced via the HA Repair issue mechanism instead.
        try:
            await self.hass.services.async_call(
                "script",
                "ultra_tts",
                {
                    "speaker":  speaker_str,
                    "message":  message,
                    "volume":   volume,
                    "priority": priority,
                },
                blocking=False,
            )
        except Exception as err:
            from .repairs import raise_issue_ultra_tts_missing
            raise_issue_ultra_tts_missing(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="ultra_tts_failed",
                translation_placeholders={"event_id": event_id},
            ) from err

        # Increment statistics sensor – safely, never let this crash TTS
        try:
            sensor = self.hass.data.get(DOMAIN, {}).get("sensor")
            if sensor is not None:
                sensor.increment()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("House Voice: Failed to increment sensor: %s", err)
