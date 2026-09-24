# VERSION = "3.5.0"
# File: events/event_chain.py
# Description: Event chain execution engine for House Voice Manager Sprint 2
#              DAG-based chain execution with fail-open error handling

from __future__ import annotations

import asyncio
import logging
import re
import time
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
class RetryConfig:
    """Configuration for per-step retry behavior with backoff and circuit breaker."""
    max_attempts: int = 3
    backoff_mode: str = "exponential"  # exponential | linear | constant
    base_delay_ms: int = 100
    max_delay_ms: int = 5000
    
    # Circuit breaker: if service fails N times, skip future attempts
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_after_seconds: int = 60
    
    def get_delay_ms(self, attempt: int) -> int:
        """Calculate delay for retry attempt (0-indexed).
        
        - exponential: 100ms, 200ms, 400ms, 800ms, ...
        - linear: 100ms, 200ms, 300ms, 400ms, ...
        - constant: 100ms, 100ms, 100ms, ...
        """
        if attempt < 0:
            return 0
        
        if self.backoff_mode == "exponential":
            delay = self.base_delay_ms * (2 ** attempt)
        elif self.backoff_mode == "linear":
            delay = self.base_delay_ms * (attempt + 1)
        else:  # constant
            delay = self.base_delay_ms
        
        return min(delay, self.max_delay_ms)


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for a step."""
    failure_count: int = 0
    last_failure_time: Optional[float] = None
    is_open: bool = False  # True = skip executions
    
    def should_skip(self, threshold: int, reset_after_seconds: int) -> bool:
        """Check if circuit breaker should skip execution."""
        if not self.is_open:
            return False
        
        # Check if enough time has passed to reset
        if self.last_failure_time:
            import time
            time_since_failure = time.time() - self.last_failure_time
            if time_since_failure > reset_after_seconds:
                self.is_open = False
                self.failure_count = 0
                return False
        
        return True
    
    def record_failure(self, threshold: int) -> bool:
        """Record failure and return True if circuit should open."""
        import time
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= threshold:
            self.is_open = True
            return True
        return False
    
    def reset(self) -> None:
        """Reset circuit breaker."""
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False



@dataclass
class EventFilter:
    """Single filter condition for event routing."""
    key: str
    value: Any
    operator: str = "equals"  # equals | contains | regex | gt | lt | ne
    
    def matches(self, event_data: dict) -> bool:
        """Evaluate filter against event data.
        
        Returns True if condition matches, False otherwise.
        """
        if not isinstance(event_data, dict):
            return False
        
        if self.key not in event_data:
            return False
        
        event_value = event_data[self.key]
        
        if self.operator == "equals":
            return event_value == self.value
        elif self.operator == "ne":  # not equal
            return event_value != self.value
        elif self.operator == "contains":
            return str(self.value) in str(event_value)
        elif self.operator == "regex":
            try:
                return bool(re.search(str(self.value), str(event_value)))
            except re.error:
                return False
        elif self.operator == "gt":
            try:
                return float(event_value) > float(self.value)
            except (ValueError, TypeError):
                return False
        elif self.operator == "lt":
            try:
                return float(event_value) < float(self.value)
            except (ValueError, TypeError):
                return False
        
        return False


@dataclass
class EventContext:
    """Event data passed through chain execution."""
    source: str  # Event source (mqtt, service, automation, etc)
    data: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: time.time())


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
    
    # ── Sprint 4 Task: Advanced Retry Strategies ───────────────────────────────
    retry_config: 'RetryConfig' = field(default_factory=RetryConfig)
    
    # ── Sprint 5 Task: Event Routing & Transformation ────────────────────────
    filter: Optional[dict] = None  # Event filter conditions: {"key": "value", "operator": "equals|contains|regex|gt|lt"}
    route_expression: Optional[str] = None  # Jinja2 template for dynamic target: "{{ 'room_a' if event.room == 'main' else 'room_b' }}"
    transform: Optional[dict] = None  # Parameter transformations: {"param": "{{ expression }}"}

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


# ── Sprint 5: Utility Functions for Event Routing & Transformation ───────────

def evaluate_event_filter(filter_dict: Optional[dict], event_data: dict) -> bool:
    """Evaluate event filters against event data.
    
    Filter dict format: {"key": "value", "operator": "equals"}
    or list of conditions with AND-logic.
    
    Returns True if all filters match, False otherwise.
    """
    if not filter_dict:
        return True  # No filter = always match
    
    if isinstance(filter_dict, dict):
        # Single filter condition
        try:
            event_filter = EventFilter(
                key=filter_dict.get("key", ""),
                value=filter_dict.get("value"),
                operator=filter_dict.get("operator", "equals"),
            )
            return event_filter.matches(event_data)
        except (KeyError, TypeError):
            return False
    elif isinstance(filter_dict, list):
        # Multiple filters (AND-logic)
        for f in filter_dict:
            if not evaluate_event_filter(f, event_data):
                return False
        return True
    
    return True


def evaluate_expression(expression: str, context: dict) -> str:
    """Evaluate a simple template expression.
    
    Supports basic {{ key }} substitution from context.
    For now, use simple string substitution instead of Jinja2.
    
    Example: "{{ event.room }}" with context {"event": {"room": "living_room"}}
    """
    if not expression:
        return ""
    
    try:
        # Simple {{ }} substitution
        import re
        pattern = r'\{\{\s*(\w+(?:\.\w+)*)\s*\}\}'
        
        def replace_expr(match):
            key_path = match.group(1).split('.')
            value = context
            for key in key_path:
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return match.group(0)  # Return original if can't resolve
            return str(value) if value is not None else ""
        
        return re.sub(pattern, replace_expr, expression)
    except Exception as err:
        _LOGGER.warning("Expression evaluation failed: %s", err)
        return expression


def apply_transformations(
    parameters: dict[str, Any],
    transform_dict: Optional[dict],
    context: dict,
) -> dict[str, Any]:
    """Apply parameter transformations based on context.
    
    Transform dict format: {"param_key": "{{ expression }}"}
    
    Returns transformed parameters dict.
    """
    if not transform_dict:
        return parameters
    
    transformed = parameters.copy()
    
    for key, expression in transform_dict.items():
        if isinstance(expression, str):
            try:
                transformed[key] = evaluate_expression(expression, context)
            except Exception as err:
                _LOGGER.warning(
                    "Transformation failed for %s: %s, using original",
                    key,
                    err,
                )
        else:
            transformed[key] = expression
    
    return transformed


class EventChainManager:
    """Manages DAG-based event chain execution."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize event chain manager."""
        self.hass = hass
        self.chains: dict[str, list[ChainStep]] = {}
        self.executions: dict[str, ChainExecution] = {}
        self.action_handlers: dict[ChainActionType, Callable] = {}
        self.circuit_breaker_states: dict[str, CircuitBreakerState] = {}
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
        """Execute a single step with retry logic and circuit breaker."""
        handler = self.action_handlers.get(step.action)

        if not handler:
            _LOGGER.warning(
                "No handler registered for action: %s",
                step.action.value,
            )
            return False

        # Initialize circuit breaker state if not exists
        if step.step_id not in self.circuit_breaker_states:
            self.circuit_breaker_states[step.step_id] = CircuitBreakerState()

        cb_state = self.circuit_breaker_states[step.step_id]

        # Check if circuit breaker should skip this step
        if cb_state.should_skip(
            step.retry_config.circuit_breaker_threshold,
            step.retry_config.circuit_breaker_reset_after_seconds,
        ):
            _LOGGER.warning(
                "Circuit breaker OPEN for step: %s (skip execution)",
                step.step_id,
            )
            execution.failed_steps.add(step.step_id)
            return False

        # Attempt execution with retry logic
        max_attempts = step.retry_config.max_attempts
        for attempt in range(max_attempts):
            try:
                # Pre-step delay if specified
                if step.delay_ms:
                    await asyncio.sleep(step.delay_ms / 1000.0)

                # Execute handler
                result = await handler(step, self.hass)
                execution.step_results[step.step_id] = result
                execution.completed_steps.add(step.step_id)

                # Reset circuit breaker on success
                cb_state.reset()

                _LOGGER.debug(
                    "Chain step completed: %s (attempt %d/%d)",
                    step.step_id,
                    attempt + 1,
                    max_attempts,
                )
                return True

            except Exception as err:
                execution.step_errors[step.step_id] = err
                _LOGGER.warning(
                    "Chain step failed: %s (attempt %d/%d): %s",
                    step.step_id,
                    attempt + 1,
                    max_attempts,
                    err,
                )

                # Record failure and check if circuit breaker should open
                cb_state.record_failure(step.retry_config.circuit_breaker_threshold)

                # If this is the last attempt, mark as failed
                if attempt == max_attempts - 1:
                    execution.failed_steps.add(step.step_id)
                    if cb_state.is_open:
                        _LOGGER.error(
                            "Circuit breaker OPENED for step: %s (threshold: %d failures)",
                            step.step_id,
                            step.retry_config.circuit_breaker_threshold,
                        )
                    return False

                # Configurable backoff based on backoff_mode
                backoff_ms = step.retry_config.get_delay_ms(attempt)
                _LOGGER.debug(
                    "Backing off %dms before retry (mode: %s, attempt: %d)",
                    backoff_ms,
                    step.retry_config.backoff_mode,
                    attempt,
                )
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


async def handle_webhook_action(
    step: ChainStep,
    hass: HomeAssistant,
) -> dict[str, Any]:
    """Execute a webhook action.
    
    Sends an HTTP POST request to a webhook URL with step and execution data.
    
    Parameters:
    - webhook_url: URL to POST to (required, from step.target or parameters)
    - timeout: Request timeout in seconds (default: 30)
    - headers: Additional HTTP headers dict (default: {})
    - include_step_data: Include full step data in payload (default: True)
    
    Returns:
        dict with status, response_status_code, response_body/error, execution_time_ms
    """
    import aiohttp
    import time
    from urllib.parse import urlparse
    
    webhook_url = step.target or step.parameters.get("webhook_url")
    if not webhook_url:
        raise ValueError("webhook action requires target (webhook_url) or parameters.webhook_url")
    
    # Validate URL format
    try:
        parsed = urlparse(webhook_url)
        if not parsed.scheme in ("http", "https"):
            raise ValueError(f"Invalid webhook URL scheme: {parsed.scheme}")
    except Exception as e:
        raise ValueError(f"Invalid webhook URL: {str(e)}")
    
    timeout = step.parameters.get("timeout", 30)
    headers = step.parameters.get("headers", {})
    include_step_data = step.parameters.get("include_step_data", True)
    
    # Prepare payload
    payload = {
        "action": step.action.value,
        "timestamp": asyncio.get_event_loop().time(),
    }
    
    if include_step_data:
        payload["step"] = {
            "action": step.action.value,
            "target": step.target,
            "parameters": step.parameters,
            "on_error": step.on_error,
            "max_retries": step.max_retries,
        }
    
    # Set default content-type if not provided
    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"
    
    start_time = time.time()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
                ssl=True,
            ) as response:
                response_text = await response.text()
                execution_time_ms = (time.time() - start_time) * 1000
                
                _LOGGER.debug(
                    f"Webhook {webhook_url} returned {response.status} in {execution_time_ms:.0f}ms"
                )
                
                return {
                    "status": "completed",
                    "webhook_url": webhook_url,
                    "response_status_code": response.status,
                    "response_body": response_text[:500],  # Limit response size in logs
                    "execution_time_ms": execution_time_ms,
                    "success": 200 <= response.status < 300,
                }
    except asyncio.TimeoutError:
        execution_time_ms = (time.time() - start_time) * 1000
        _LOGGER.error(f"Webhook timeout after {timeout}s: {webhook_url}")
        return {
            "status": "completed",
            "webhook_url": webhook_url,
            "error": "timeout",
            "timeout_seconds": timeout,
            "execution_time_ms": execution_time_ms,
            "success": False,
        }
    except aiohttp.ClientError as e:
        execution_time_ms = (time.time() - start_time) * 1000
        error_msg = str(e)
        _LOGGER.error(f"Webhook client error: {error_msg}")
        return {
            "status": "completed",
            "webhook_url": webhook_url,
            "error": "client_error",
            "error_details": error_msg[:200],
            "execution_time_ms": execution_time_ms,
            "success": False,
        }
    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000
        error_msg = str(e)
        _LOGGER.error(f"Webhook unexpected error: {error_msg}", exc_info=True)
        return {
            "status": "completed",
            "webhook_url": webhook_url,
            "error": "unexpected_error",
            "error_details": error_msg[:200],
            "execution_time_ms": execution_time_ms,
            "success": False,
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
