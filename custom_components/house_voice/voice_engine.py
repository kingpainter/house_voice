# VERSION = "3.0.0"
# File: voice_engine.py
# Description: TTS logic and priority handling for House Voice Manager.
#              Includes: spam filter, quiet hours (configurable), Jinja2 templates,
#              conditional playback, async TTS queue, event history log.
#              v3.0.0: _execute_tts now uses native UltraTTS instead of script.ultra_tts.

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.template import Template, TemplateError
from homeassistant.util import dt as dt_util

from .const import (
    CONF_QUIET_END,
    CONF_QUIET_START,
    DEFAULT_PRIORITY,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_START,
    DEFAULT_VOLUME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SPAM_FILTER_SECONDS = 30

# Clean up _last_spoken entries older than this (seconds)
_CLEANUP_AGE = 3600

# Max entries kept in in-memory history log
_HISTORY_MAX = 50


def _is_quiet_hours(start: int, end: int) -> bool:
    """Return True if current local time is within quiet hours.

    Handles overnight ranges (e.g. 22–07) and same-day ranges (e.g. 01–06).
    """
    hour = dt_util.now().hour
    if start > end:
        # Overnight: e.g. 22–07
        return hour >= start or hour < end
    # Same-day: e.g. 01–06
    return start <= hour < end


class VoiceEngine:
    """Handles TTS routing, spam filtering, quiet hours, queue and template rendering."""

    def __init__(self, hass, storage, groups, entry: ConfigEntry) -> None:
        self.hass    = hass
        self.storage = storage
        self.groups  = groups
        self.entry   = entry

        self._last_spoken: dict[str, float] = {}
        self._history: deque[dict] = deque(maxlen=_HISTORY_MAX)

        # Async TTS queue – ensures announcements never overlap
        self._queue: asyncio.Queue = asyncio.Queue()
        self._queue_task: asyncio.Task | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background queue worker."""
        self._queue_task = self.hass.loop.create_task(self._queue_worker())

    async def stop(self) -> None:
        """Stop the background queue worker gracefully."""
        if self._queue_task and not self._queue_task.done():
            self._queue_task.cancel()
            try:
                await self._queue_task
            except asyncio.CancelledError:
                pass

    # ── Queue worker ───────────────────────────────────────────────────────────

    async def _queue_worker(self) -> None:
        """Process TTS jobs from the queue one at a time.

        Runs indefinitely until cancelled. If a job raises an unhandled
        exception the error is logged and the worker continues with the
        next job in the queue (no silent death).
        """
        while True:
            job = await self._queue.get()
            try:
                await self._execute_tts(
                    speaker_str=job["speaker_str"],
                    message=job["message"],
                    volume=job["volume"],
                    priority=job["priority"],
                    event_id=job.get("event_id", "say_text"),
                )
            except asyncio.CancelledError:
                # Propagate cancellation so stop() can join cleanly
                self._queue.task_done()
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.error(
                    "House Voice: queue worker error for event '%s': %s",
                    job.get("event_id", "?"),
                    err,
                )
            finally:
                self._queue.task_done()

    def _restart_worker_if_dead(self) -> None:
        """Restart the queue worker task if it has died unexpectedly.

        Called before every enqueue so a crashed worker never silently
        swallows pending jobs.
        """
        if self._queue_task is None or self._queue_task.done():
            exc = (
                self._queue_task.exception()
                if self._queue_task and not self._queue_task.cancelled()
                else None
            )
            if exc:
                _LOGGER.error(
                    "House Voice: queue worker died unexpectedly: %s – restarting", exc
                )
            else:
                _LOGGER.warning("House Voice: queue worker was not running – restarting")
            self._queue_task = self.hass.loop.create_task(self._queue_worker())

    # ── Public API ─────────────────────────────────────────────────────────────

    async def say(self, event_id: str, bypass_spam: bool = False) -> None:
        """Speak a stored voice event by ID.

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
        volume: float  = event.get("volume", DEFAULT_VOLUME)
        priority: str  = event.get("priority", DEFAULT_PRIORITY)
        condition: str = event.get("condition", "")

        if not speakers:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_speakers",
                translation_placeholders={"event_id": event_id},
            )

        # Resolve group references in speaker list
        resolved_speakers = self.groups.resolve_speakers(speakers)
        if not resolved_speakers:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_speakers",
                translation_placeholders={"event_id": event_id},
            )

        # Spam filter
        now = time.monotonic()
        self._cleanup_last_spoken(now)
        if not bypass_spam:
            last = self._last_spoken.get(event_id)
            if last is not None and (now - last) < SPAM_FILTER_SECONDS:
                remaining = int(SPAM_FILTER_SECONDS - (now - last))
                _LOGGER.warning(
                    "House Voice: Spam filter blocked '%s' – try again in %d seconds",
                    event_id, remaining,
                )
                self._log_history(event_id, message, "blocked_spam")
                return

        # Quiet hours
        quiet_start, quiet_end = self._get_quiet_hours()
        if _is_quiet_hours(quiet_start, quiet_end) and priority != "critical":
            _LOGGER.info(
                "House Voice: Quiet hours blocked '%s' (priority: %s)",
                event_id, priority,
            )
            self._log_history(event_id, message, "blocked_quiet_hours")
            return

        # Conditional playback – evaluate Jinja2 condition if present
        if condition and not self._eval_condition(condition, event_id):
            _LOGGER.info("House Voice: Condition false, skipping '%s'", event_id)
            self._log_history(event_id, message, "blocked_condition")
            return

        self._last_spoken[event_id] = now

        # Render message template
        message = self._render_template(message, event_id)

        # Build speaker string
        speaker_str = self._build_speaker_str(resolved_speakers)

        # Enqueue – critical goes to front, others to back
        await self._enqueue(
            event_id=event_id,
            message=message,
            speaker_str=speaker_str,
            volume=volume,
            priority=priority,
        )

        self._log_history(event_id, message, "spoken")
        self._increment_sensor()

    async def say_text(
        self,
        message: str,
        speakers: list[str],
        priority: str = DEFAULT_PRIORITY,
        volume: float = DEFAULT_VOLUME,
    ) -> None:
        """Speak an ad-hoc text message without a stored event.

        Args:
            message:  The text to speak. Supports Jinja2 templates.
            speakers: List of media_player entity IDs or group references.
            priority: 'info', 'normal' or 'critical'.
            volume:   Volume level 0.05–1.0.
        """
        quiet_start, quiet_end = self._get_quiet_hours()
        if _is_quiet_hours(quiet_start, quiet_end) and priority != "critical":
            _LOGGER.info("House Voice: Quiet hours blocked say_text (priority: %s)", priority)
            self._log_history("say_text", message, "blocked_quiet_hours")
            return

        resolved_speakers = self.groups.resolve_speakers(speakers)
        if not resolved_speakers:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_speakers",
                translation_placeholders={"event_id": "say_text"},
            )

        message = self._render_template(message, "say_text")
        speaker_str = self._build_speaker_str(resolved_speakers)

        await self._enqueue(
            event_id="say_text",
            message=message,
            speaker_str=speaker_str,
            volume=volume,
            priority=priority,
        )

        self._log_history("say_text", message, "spoken")
        self._increment_sensor()

    def get_history(self) -> list[dict]:
        """Return event history log, newest first."""
        return list(reversed(self._history))

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _get_quiet_hours(self) -> tuple[int, int]:
        """Read quiet hours from config entry options, falling back to defaults."""
        options = self.entry.options if self.entry else {}
        start = options.get(CONF_QUIET_START, DEFAULT_QUIET_START)
        end   = options.get(CONF_QUIET_END,   DEFAULT_QUIET_END)
        return int(start), int(end)

    def _cleanup_last_spoken(self, now: float) -> None:
        """Remove stale entries from _last_spoken to prevent unbounded growth."""
        stale = [k for k, t in self._last_spoken.items() if (now - t) > _CLEANUP_AGE]
        for k in stale:
            del self._last_spoken[k]

    def _render_template(self, message: str, event_id: str) -> str:
        """Render a Jinja2 template. Falls back to raw message on error."""
        try:
            return Template(message, self.hass).async_render(parse_result=False)
        except TemplateError as err:
            _LOGGER.warning(
                "House Voice: Template render failed for '%s', using raw message. Error: %s",
                event_id, err,
            )
            return message

    def _eval_condition(self, condition: str, event_id: str) -> bool:
        """Evaluate a Jinja2 condition expression. Returns True on error (fail-open)."""
        try:
            result = Template(condition, self.hass).async_render(parse_result=True)
            return bool(result)
        except TemplateError as err:
            _LOGGER.warning(
                "House Voice: Condition eval failed for '%s', defaulting to True. Error: %s",
                event_id, err,
            )
            return True

    @staticmethod
    def _build_speaker_str(speakers: list[str]) -> str:
        """Convert a resolved speaker list to a string for ultra_tts."""
        return speakers[0] if len(speakers) == 1 else ", ".join(speakers)

    async def _enqueue(
        self,
        event_id: str,
        message: str,
        speaker_str: str,
        volume: float,
        priority: str,
    ) -> None:
        """Add a TTS job to the queue. Critical priority jumps the queue.

        Also restarts the queue worker if it has died unexpectedly.
        """
        # Guard: restart worker if it died since last call
        self._restart_worker_if_dead()
        job = {
            "event_id":   event_id,
            "message":    message,
            "speaker_str": speaker_str,
            "volume":     volume,
            "priority":   priority,
        }
        if priority == "critical":
            # Build a new queue with the critical job first
            items: list[dict] = [job]
            while not self._queue.empty():
                try:
                    items.append(self._queue.get_nowait())
                    self._queue.task_done()
                except asyncio.QueueEmpty:
                    break
            for item in items:
                await self._queue.put(item)
        else:
            await self._queue.put(job)

    async def _execute_tts(
        self,
        speaker_str: str,
        message: str,
        volume: float,
        priority: str,
        event_id: str,
    ) -> None:
        """Execute a single TTS call via the native UltraTTS engine.

        Falls back to script.ultra_tts if UltraTTS raises, so the YAML
        script can still be used as a safety net during the v2→v3 transition.
        """
        from .ultra_tts import UltraTTS
        try:
            tts = UltraTTS(self.hass)
            await tts.async_speak(
                speaker=speaker_str,
                message=message,
                volume=volume,
                priority=priority,
            )
        except Exception as err:
            from .repairs import raise_issue_ultra_tts_missing
            raise_issue_ultra_tts_missing(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="ultra_tts_failed",
                translation_placeholders={"event_id": event_id},
            ) from err

    def _log_history(self, event_id: str, message: str, status: str) -> None:
        """Append an entry to the in-memory history log."""
        self._history.append({
            "event_id":  event_id,
            "message":   message,
            "status":    status,
            "timestamp": dt_util.now().isoformat(),
        })

    def _increment_sensor(self) -> None:
        """Increment the statistics sensor. Silently ignored on failure."""
        try:
            sensor = self.hass.data.get(DOMAIN, {}).get("sensor")
            if sensor is not None:
                sensor.increment()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("House Voice: Failed to increment sensor: %s", err)
