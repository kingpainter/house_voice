# VERSION = "3.4.0"
# File: events/event_chain.py
# Description: Event chain execution engine for House Voice Manager Sprint 2
#              DAG-based chain execution with fail-open error handling

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class ChainActionType(str, Enum):
    """Supported event chain action types."""
    ANNOUNCEMENT = "announcement"
    GROUP_VOLUME_UP = "group_volume_up"
    GROUP_VOLUME_DOWN = "group_volume_down"
    DELAY = "delay"
    CONDITION_CHECK = "condition_check"
    WEBHOOK = "webhook"


@dataclass
class ChainStep:
    """Single step in an event chain."""
    action: ChainActionType
    target: Optional[str] = None  # Group ID or announcement ID
    parameters: dict[str, Any] = field(default_factory=dict)
    delay_ms: Optional[int] = None  # Delay before next step (ms)
    on_error: str = "continue"  # continue, retry, fail
    max_retries: int = 3
    depends_on: list[str] = field(default_factory=list)  # Step IDs this depends on

    @property
    def step_id(self) -> str:
        """Generate unique step ID from action and target."""
        return f"{self.action.value}_{self.target or 'generic'}"


@dataclass
class ChainExecution:
    """Execution state for an event chain."""
    chain_id: str
    started_at: float
    step_results: dict[str, Any] = field(default_factory=dict)
    step_errors: dict[str, Exception] = field(default_factory=dict)
    completed_steps: set[str] = field(default_factory=set)
    failed_steps: set[str] = field(default_factory=set)
    is_complete: bool = False


class EventChainManager:
    """Manages DAG-based event chain execution."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize event chain manager."""
        self.hass = hass
        self.chains: dict[str, list[ChainStep]] = {}
        self.executions: dict[str, ChainExecution] = {}
        self.action_handlers: dict[ChainActionType, Callable] = {}
        self._lock = asyncio.Lock()

    def register_action_handler(
        self,
        action_type: ChainActionType,
        handler: Callable,
    ) -> None:
        """Register a handler for a specific action type."""
        self.action_handlers[action_type] = handler
        _LOGGER.debug("Registered handler for action: %s", action_type.value)

    async def register_chain(
        self,
        chain_id: str,
        steps: list[ChainStep],
    ) -> None:
        """Register a new event chain."""
        async with self._lock:
            self.chains[chain_id] = steps
            _LOGGER.info("Event chain registered: %s (%d steps)", chain_id, len(steps))

    async def execute_chain(self, chain_id: str) -> ChainExecution:
        """Execute an event chain and return execution state."""
        if chain_id not in self.chains:
            raise ValueError(f"Chain not found: {chain_id}")

        steps = self.chains[chain_id]
        execution = ChainExecution(
            chain_id=chain_id,
            started_at=asyncio.get_event_loop().time(),
        )

        self.executions[chain_id] = execution

        try:
            # Build dependency graph
            step_map = {step.step_id: step for step in steps}

            # Execute steps in order (with dependency resolution)
            for step in steps:
                # Check if all dependencies are completed
                if step.depends_on:
                    missing_deps = [
                        dep for dep in step.depends_on
                        if dep not in execution.completed_steps
                    ]
                    if missing_deps:
                        _LOGGER.warning(
                            "Chain %s: skipping step %s (unmet deps: %s)",
                            chain_id,
                            step.step_id,
                            missing_deps,
                        )
                        continue

                # Execute step with retry logic
                success = await self._execute_step_with_retry(
                    step,
                    execution,
                )

                if not success and step.on_error == "fail":
                    _LOGGER.error(
                        "Chain %s: stopping due to failed step: %s",
                        chain_id,
                        step.step_id,
                    )
                    execution.failed_steps.add(step.step_id)
                    break

        finally:
            execution.is_complete = True
            _LOGGER.info(
                "Chain %s execution complete: %d succeeded, %d failed",
                chain_id,
                len(execution.completed_steps),
                len(execution.failed_steps),
            )

        return execution

    async def _execute_step_with_retry(
        self,
        step: ChainStep,
        execution: ChainExecution,
    ) -> bool:
        """Execute a single step with retry logic."""
        handler = self.action_handlers.get(step.action)

        if not handler:
            _LOGGER.warning(
                "No handler registered for action: %s",
                step.action.value,
            )
            return False

        for attempt in range(step.max_retries):
            try:
                # Pre-step delay if specified
                if step.delay_ms:
                    await asyncio.sleep(step.delay_ms / 1000.0)

                # Execute handler
                result = await handler(step, self.hass)
                execution.step_results[step.step_id] = result
                execution.completed_steps.add(step.step_id)

                _LOGGER.debug(
                    "Chain step completed: %s (attempt %d/%d)",
                    step.step_id,
                    attempt + 1,
                    step.max_retries,
                )
                return True

            except Exception as err:
                execution.step_errors[step.step_id] = err
                _LOGGER.warning(
                    "Chain step failed: %s (attempt %d/%d): %s",
                    step.step_id,
                    attempt + 1,
                    step.max_retries,
                    err,
                )

                # If this is the last attempt, mark as failed
                if attempt == step.max_retries - 1:
                    execution.failed_steps.add(step.step_id)
                    return False

                # Exponential backoff: 0.5s, 1s, 2s
                backoff_ms = min(500 * (2 ** attempt), 2000)
                await asyncio.sleep(backoff_ms / 1000.0)

        return False

    def get_execution(self, chain_id: str) -> Optional[ChainExecution]:
        """Get execution state for a chain."""
        return self.executions.get(chain_id)


# ── Built-in action handlers ────────────────────────────────────────────

async def handle_announcement_action(
    step: ChainStep,
    hass: HomeAssistant,
) -> dict[str, Any]:
    """Execute an announcement action."""
    from homeassistant.core import Context

    event_id = step.target
    if not event_id:
        raise ValueError("announcement action requires target (event_id)")

    # Call house_voice.say service
    await hass.services.async_call(
        "house_voice",
        "say",
        {"event": event_id},
        context=Context(),
    )

    return {"event_id": event_id, "status": "queued"}


async def handle_group_volume_action(
    step: ChainStep,
    hass: HomeAssistant,
    direction: str = "up",
) -> dict[str, Any]:
    """Execute group volume adjustment action."""
    from .speaker_control.volume_controller import VolumeControllerV2

    group_id = step.target
    if not group_id:
        raise ValueError(f"group_volume_{direction} action requires target (group_id)")

    volume_step = step.parameters.get("volume_step", 0.1)

    controller = VolumeControllerV2(hass)

    if direction == "up":
        result = await controller.increase_group_volume(group_id, volume_step)
    else:
        result = await controller.decrease_group_volume(group_id, volume_step)

    return result


async def handle_delay_action(
    step: ChainStep,
    hass: HomeAssistant,
) -> dict[str, Any]:
    """Execute a delay action."""
    delay_ms = step.parameters.get("duration_ms", step.delay_ms or 1000)
    await asyncio.sleep(delay_ms / 1000.0)
    return {"duration_ms": delay_ms, "status": "completed"}


# ── Example chain builder ───────────────────────────────────────────────

def create_announcement_chain(
    event_id: str,
    group_id: str,
    volume_increase: float = 0.1,
) -> list[ChainStep]:
    """Create a standard announcement chain: volume up → announce → delay → volume down."""
    return [
        ChainStep(
            action=ChainActionType.GROUP_VOLUME_UP,
            target=group_id,
            parameters={"volume_step": volume_increase},
            on_error="continue",
        ),
        ChainStep(
            action=ChainActionType.ANNOUNCEMENT,
            target=event_id,
            on_error="fail",
        ),
        ChainStep(
            action=ChainActionType.DELAY,
            parameters={"duration_ms": 2000},
        ),
        ChainStep(
            action=ChainActionType.GROUP_VOLUME_DOWN,
            target=group_id,
            parameters={"volume_step": volume_increase},
            on_error="continue",
        ),
    ]
