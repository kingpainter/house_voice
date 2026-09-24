# VERSION = "3.5.0"
# File: speaker_control/volume_controller.py
# Description: Volume controller with 3-retry exponential backoff and fallback strategies

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


@dataclass
class VolumeAdjustmentResult:
    """Result of a volume adjustment operation."""
    success: bool
    group_id: str
    action: str  # "increase", "decrease"
    attempted_count: int
    final_volume: Optional[float] = None
    error_message: Optional[str] = None
    fallback_applied: bool = False
    fallback_strategy: Optional[str] = None


class VolumeControllerV2:
    """Advanced volume controller with retry logic and fallback strategies."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize volume controller."""
        self.hass = hass
        self._speaker_volumes: dict[str, float] = {}
        self._lock = asyncio.Lock()

        # Retry configuration
        self.max_retries = 3
        self.retry_delays_ms = [500, 1000, 2000]  # Exponential backoff

    async def increase_group_volume(
        self,
        group_id: str,
        amount: float = 0.1,
    ) -> VolumeAdjustmentResult:
        """Increase volume for a speaker group with retry and fallback."""
        return await self._adjust_volume(group_id, amount, "increase")

    async def decrease_group_volume(
        self,
        group_id: str,
        amount: float = 0.1,
    ) -> VolumeAdjustmentResult:
        """Decrease volume for a speaker group with retry and fallback."""
        return await self._adjust_volume(group_id, -amount, "decrease")

    async def _adjust_volume(
        self,
        group_id: str,
        amount: float,
        action: str,
    ) -> VolumeAdjustmentResult:
        """Adjust volume with retry logic."""
        async with self._lock:
            result = VolumeAdjustmentResult(
                success=False,
                group_id=group_id,
                action=action,
                attempted_count=0,
            )

            # Attempt with retries
            for attempt in range(self.max_retries):
                result.attempted_count = attempt + 1

                try:
                    # Get current group volume
                    current_volume = await self._get_group_volume(group_id)
                    if current_volume is None:
                        raise ValueError(f"Group not found: {group_id}")

                    # Calculate new volume
                    new_volume = max(0.0, min(1.0, current_volume + amount))

                    # Call service with retry
                    success = await self._call_volume_service(
                        group_id,
                        new_volume,
                    )

                    if success:
                        result.success = True
                        result.final_volume = new_volume
                        self._speaker_volumes[group_id] = new_volume
                        _LOGGER.debug(
                            "Volume adjusted: %s → %.2f (attempt %d/%d)",
                            group_id,
                            new_volume,
                            attempt + 1,
                            self.max_retries,
                        )
                        return result

                except Exception as err:
                    result.error_message = str(err)
                    _LOGGER.warning(
                        "Volume adjustment failed: %s (attempt %d/%d): %s",
                        group_id,
                        attempt + 1,
                        self.max_retries,
                        err,
                    )

                    # If not the last attempt, wait before retry
                    if attempt < self.max_retries - 1:
                        delay_ms = self.retry_delays_ms[attempt]
                        _LOGGER.debug(
                            "Retrying volume adjustment in %dms...",
                            delay_ms,
                        )
                        await asyncio.sleep(delay_ms / 1000.0)

            # All retries failed — apply fallback strategy
            _LOGGER.warning(
                "All volume adjustment retries failed for %s, applying fallback",
                group_id,
            )

            fallback_result = await self._apply_fallback_strategy(
                group_id,
                amount,
                action,
                result.error_message or "All retries exhausted",
            )

            if fallback_result:
                result.fallback_applied = True
                result.success = fallback_result.get("success", False)
                result.fallback_strategy = fallback_result.get("strategy")

            return result

    async def _get_group_volume(self, group_id: str) -> Optional[float]:
        """Get current volume for a group."""
        # Check cache first
        if group_id in self._speaker_volumes:
            return self._speaker_volumes[group_id]

        # Query from HA (integrate with speaker groups storage)
        # For now, default to 0.5
        return 0.5

    async def _call_volume_service(
        self,
        group_id: str,
        volume: float,
    ) -> bool:
        """Call the actual volume service (Music Assistant, HEOS, etc.)."""
        try:
            # Attempt Music Assistant first
            await self.hass.services.async_call(
                "media_player",
                "volume_set",
                {
                    "entity_id": f"media_player.{group_id}",
                    "volume_level": volume,
                },
            )
            return True
        except Exception as err:
            _LOGGER.debug("Volume service call failed: %s", err)
            raise

    async def _apply_fallback_strategy(
        self,
        group_id: str,
        amount: float,
        action: str,
        error_message: str,
    ) -> dict[str, Any]:
        """Apply fallback strategy when all retries fail."""
        from .fallback_strategies import FallbackStrategy, NoOpFallback, ManualAdjustmentFallback

        # Strategy: Try no-op first (speaker may recover), then manual adjustment
        strategies = [
            NoOpFallback(),
            ManualAdjustmentFallback(self.hass),
        ]

        for strategy in strategies:
            try:
                result = await strategy.execute(
                    group_id=group_id,
                    amount=amount,
                    action=action,
                    error_message=error_message,
                )

                if result["success"]:
                    _LOGGER.info(
                        "Fallback strategy succeeded: %s for %s",
                        strategy.__class__.__name__,
                        group_id,
                    )
                    return result

            except Exception as err:
                _LOGGER.warning(
                    "Fallback strategy %s failed: %s",
                    strategy.__class__.__name__,
                    err,
                )
                continue

        # All fallbacks failed
        _LOGGER.error(
            "All fallback strategies failed for %s",
            group_id,
        )
        return {
            "success": False,
            "strategy": "none",
            "error": "All fallback strategies failed",
        }
