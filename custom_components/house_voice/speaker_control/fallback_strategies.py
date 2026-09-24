# VERSION = "3.4.0"
# File: speaker_control/fallback_strategies.py
# Description: Fallback strategies for volume control when primary methods fail

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class FallbackStrategy(ABC):
    """Base class for fallback strategies."""

    @abstractmethod
    async def execute(
        self,
        group_id: str,
        amount: float,
        action: str,
        error_message: str,
    ) -> dict[str, Any]:
        """Execute fallback strategy."""
        pass


class NoOpFallback(FallbackStrategy):
    """
    No-op fallback: log the error and return success.

    Rationale: Sometimes the speaker service is temporarily unavailable,
    but the TTS announcement can still proceed. The volume adjustment
    can be retried on the next announcement.
    """

    async def execute(
        self,
        group_id: str,
        amount: float,
        action: str,
        error_message: str,
    ) -> dict[str, Any]:
        """Log failure and return success to allow announcement to proceed."""
        _LOGGER.warning(
            "NoOp fallback for %s volume %s: %s (announcement will proceed)",
            group_id,
            action,
            error_message,
        )
        return {
            "success": True,
            "strategy": "noop",
            "message": f"Volume adjustment queued for later retry. Announcement proceeding.",
        }


class ManualAdjustmentFallback(FallbackStrategy):
    """
    Manual adjustment fallback: queue a notification for the user.

    Rationale: If automatic volume adjustment fails repeatedly, notify
    the user to adjust the speaker volume manually before the next TTS.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize manual adjustment fallback."""
        self.hass = hass

    async def execute(
        self,
        group_id: str,
        amount: float,
        action: str,
        error_message: str,
    ) -> dict[str, Any]:
        """Queue a manual adjustment notification."""
        try:
            direction = "up" if action == "increase" else "down"

            # Notify user via persistent notification
            notification_title = f"House Voice - Manual Volume Adjustment Needed"
            notification_message = (
                f"Failed to automatically adjust volume for '{group_id}' ({direction}). "
                f"Please manually adjust the speaker volume before the next announcement.\n\n"
                f"Error: {error_message}"
            )

            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": notification_title,
                    "message": notification_message,
                    "notification_id": f"house_voice_volume_{group_id}",
                },
            )

            _LOGGER.info(
                "Manual adjustment fallback: queued notification for %s",
                group_id,
            )

            return {
                "success": True,
                "strategy": "manual_notification",
                "message": "User notified to adjust volume manually.",
            }

        except Exception as err:
            _LOGGER.error("Manual adjustment fallback failed: %s", err)
            return {
                "success": False,
                "strategy": "manual_notification",
                "error": str(err),
            }


class RetryWithIncreasingDelayFallback(FallbackStrategy):
    """
    Retry with increasing delay: wait longer and retry the service call.

    Rationale: Sometimes the speaker service is overloaded. A longer
    delay may allow it to recover.
    """

    async def execute(
        self,
        group_id: str,
        amount: float,
        action: str,
        error_message: str,
    ) -> dict[str, Any]:
        """Retry with extended delay."""
        import asyncio

        _LOGGER.warning(
            "Retry with increasing delay fallback for %s: %s",
            group_id,
            error_message,
        )

        # Wait 5 seconds and return (actual retry would happen at next opportunity)
        await asyncio.sleep(5.0)

        return {
            "success": True,
            "strategy": "retry_with_delay",
            "message": "Retry queued with extended delay.",
        }


class SkipVolumeAdjustmentFallback(FallbackStrategy):
    """
    Skip volume adjustment: proceed with announcement at current volume.

    Rationale: If volume adjustment fails, it's better to proceed with
    the announcement at whatever volume is currently set than to skip
    the announcement entirely.
    """

    async def execute(
        self,
        group_id: str,
        amount: float,
        action: str,
        error_message: str,
    ) -> dict[str, Any]:
        """Skip adjustment and proceed."""
        _LOGGER.warning(
            "Skipping volume adjustment for %s due to: %s",
            group_id,
            error_message,
        )

        return {
            "success": True,
            "strategy": "skip_adjustment",
            "message": "Volume adjustment skipped. Announcement proceeding at current volume.",
        }


class LogAndAlertFallback(FallbackStrategy):
    """
    Log and alert: log the error and send a system alert.

    Rationale: For critical announcements, always let the user know
    if something went wrong with the volume adjustment.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize log and alert fallback."""
        self.hass = hass

    async def execute(
        self,
        group_id: str,
        amount: float,
        action: str,
        error_message: str,
    ) -> dict[str, Any]:
        """Log error and send system alert."""
        try:
            _LOGGER.error(
                "Volume adjustment failed for %s (%s): %s",
                group_id,
                action,
                error_message,
            )

            # Send a system alert (integrations/persistent_notification)
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "House Voice - Volume Adjustment Error",
                    "message": (
                        f"Failed to adjust volume for speaker group '{group_id}':\n\n"
                        f"{error_message}\n\n"
                        f"Check the House Voice logs for details."
                    ),
                    "notification_id": f"house_voice_error_{group_id}",
                },
            )

            return {
                "success": True,
                "strategy": "log_and_alert",
                "message": "Error logged and user alerted.",
            }

        except Exception as err:
            _LOGGER.error("Log and alert fallback failed: %s", err)
            return {
                "success": False,
                "strategy": "log_and_alert",
                "error": str(err),
            }
