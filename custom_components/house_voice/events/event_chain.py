# VERSION = "3.5.0"
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

from .event_chain_parallel import DependencyGraph, ParallelExecutor

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
    
    # ── Sprint 3 Task 2: Conditional Steps ────────────────────────────────────
    condition: Optional[dict] = None  # Single condition: {"entity_id": "...", "state": "..."}
    conditions: list[dict] = field(default_factory=list)  # Multiple conditions (AND-logic)
    branch_on_condition: dict[str, str] = field(default_factory=dict)  # {"true": step_id, "false": step_id}

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
        """Execute an event chain with parallel step support (v3.5.0)."""
        if chain_id not in self.chains:
            raise ValueError(f"Chain not found: {chain_id}")

        steps = self.chains[chain_id]
        execution = ChainExecution(
            chain_id=chain_id,
            started_at=asyncio.get_event_loop().time(),
        )

        self.executions[chain_id] = execution

        try:
            # Build dependency graph from steps
            graph = DependencyGraph(steps)

            # Check for circular dependencies
            if graph.has_cycles():
                raise ValueError(
                    f"Chain {chain_id} has circular dependencies — deadlock risk"
                )

            # Get execution waves (independent steps that can run in parallel)
            waves = graph.get_execution_waves()
            _LOGGER.info(
                "Chain %s prepared: %d steps in %d parallel waves",
                chain_id,
                len(steps),
                len(waves),
            )

            # Execute all waves (each wave runs steps in parallel)
            executor = ParallelExecutor()
            steps_by_id = {step.step_id: step for step in steps}

            await executor.execute_all_waves(
                waves,
                steps_by_id,
                self._execute_step_with_retry,
                execution,
            )

        finally:
            execution.is_complete = True
            _LOGGER.info(
                "Chain %s execution complete: %d succeeded, %d failed, %d waves",
                chain_id,
                len(execution.completed_steps),
                len(execution.failed_steps),
                len(waves) if 'waves' in locals() else 0,
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


    def _should_execute_step(
        self,
        step: ChainStep,
        execution: ChainExecution,
        steps_by_id: dict[str, ChainStep],
    ) -> tuple[bool, str]:
        """
        Check if a step should execute based on condition routing.
        
        Returns: (should_execute, reason)
        """
        # Check if this step has a branch_on_condition that references a condition step
        for cond_step_id, next_step_map in [(s.step_id, s.branch_on_condition) 
                                             for s in steps_by_id.values() 
                                             if s.branch_on_condition]:
            if step.step_id in next_step_map.values():
                # This step is a target of a conditional branch
                # Check if the condition result allows execution
                if cond_step_id in execution.step_results:
                    cond_result = execution.step_results[cond_step_id]
                    cond_passed = cond_result.get("result", False) if isinstance(cond_result, dict) else False
                    
                    # Check which branch should execute
                    true_target = next_step_map.get("true")
                    false_target = next_step_map.get("false")
                    
                    if cond_passed and step.step_id == true_target:
                        return True, "condition_passed_true_branch"
                    elif not cond_passed and step.step_id == false_target:
                        return True, "condition_passed_false_branch"
                    else:
                        return False, "condition_blocked_alternative_branch"
        
        # No condition gates this step
        return True, "no_condition_gate"

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




async def handle_condition_check_action(
    step: ChainStep,
    hass: HomeAssistant,
) -> dict[str, Any]:
    """Evaluate conditions with AND-logic.
    
    Conditions are a list of dicts with entity_id and expected state.
    All must match for the condition to pass.
    Unavailable entities are treated as FAIL.
    """
    from homeassistant.core import State
    
    conditions = step.parameters.get("conditions", [])
    
    if not conditions:
        # No conditions = pass
        return {
            "result": True,
            "reason": "no_conditions",
            "conditions_evaluated": 0,
            "status": "completed"
        }
    
    _LOGGER.debug(f"Evaluating {len(conditions)} conditions (AND-logic)")
    
    for i, condition in enumerate(conditions):
        entity_id = condition.get("entity_id")
        expected_state = condition.get("state")
        
        if not entity_id or expected_state is None:
            _LOGGER.error(
                f"Condition {i} missing entity_id or state: {condition}"
            )
            return {
                "result": False,
                "reason": "invalid_condition_format",
                "condition_index": i,
                "status": "error"
            }
        
        # Get current state
        state_obj: State | None = hass.states.get(entity_id)
        
        if state_obj is None:
            _LOGGER.warning(
                f"Condition entity {entity_id} not found in hass.states, treating as FAIL"
            )
            return {
                "result": False,
                "reason": "entity_not_found",
                "failed_entity": entity_id,
                "condition_index": i,
                "status": "completed"
            }
        
        current_state = state_obj.state
        
        if current_state == "unavailable" or current_state == "unknown":
            _LOGGER.warning(
                f"Condition entity {entity_id} is {current_state}, treating as FAIL"
            )
            return {
                "result": False,
                "reason": "entity_unavailable",
                "failed_entity": entity_id,
                "entity_state": current_state,
                "condition_index": i,
                "status": "completed"
            }
        
        # Check if state matches expected
        if current_state != str(expected_state):
            _LOGGER.info(
                f"Condition {i} FAILED: {entity_id} state '{current_state}' != '{expected_state}'"
            )
            return {
                "result": False,
                "reason": "condition_mismatch",
                "failed_entity": entity_id,
                "expected_state": str(expected_state),
                "actual_state": current_state,
                "condition_index": i,
                "status": "completed"
            }
        
        _LOGGER.debug(f"Condition {i} OK: {entity_id} = {current_state}")
    
    # All conditions passed
    _LOGGER.info(f"All {len(conditions)} conditions passed (AND-logic)")
    return {
        "result": True,
        "reason": "all_conditions_passed",
        "conditions_evaluated": len(conditions),
        "status": "completed"
    }

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
