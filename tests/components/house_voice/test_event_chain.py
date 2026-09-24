"""Tests for House Voice Manager Sprint 2 - Event Chain Manager."""

from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import pytest

from custom_components.house_voice.events.event_chain import (
    EventChainManager,
    ChainStep,
    ChainActionType,
    ChainExecution,
    create_announcement_chain,
    handle_announcement_action,
    handle_delay_action,
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.loop.create_task = MagicMock()
    return hass


@pytest.mark.asyncio
async def test_chain_step_step_id_property():
    """Test ChainStep generates correct step_id."""
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="test_event",
    )
    assert step.step_id == "announcement_test_event"

    step_no_target = ChainStep(action=ChainActionType.DELAY)
    assert step_no_target.step_id == "delay_generic"


@pytest.mark.asyncio
async def test_event_chain_manager_register_action_handler(mock_hass):
    """Test registering action handlers."""
    manager = EventChainManager(mock_hass)
    
    async def test_handler(step, hass):
        return {"status": "ok"}
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, test_handler)
    
    assert ChainActionType.ANNOUNCEMENT in manager.action_handlers
    assert manager.action_handlers[ChainActionType.ANNOUNCEMENT] == test_handler


@pytest.mark.asyncio
async def test_event_chain_manager_register_chain(mock_hass):
    """Test registering a chain."""
    manager = EventChainManager(mock_hass)
    
    steps = [
        ChainStep(action=ChainActionType.ANNOUNCEMENT, target="test_event"),
        ChainStep(action=ChainActionType.DELAY, parameters={"duration_ms": 1000}),
    ]
    
    await manager.register_chain("test_chain", steps)
    
    assert "test_chain" in manager.chains
    assert len(manager.chains["test_chain"]) == 2


@pytest.mark.asyncio
async def test_event_chain_manager_execute_chain_success(mock_hass):
    """Test successful chain execution."""
    manager = EventChainManager(mock_hass)
    
    async def mock_handler(step, hass):
        return {"status": "completed"}
    
    steps = [
        ChainStep(action=ChainActionType.ANNOUNCEMENT, target="event1"),
        ChainStep(action=ChainActionType.DELAY, parameters={"duration_ms": 100}),
    ]
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    manager.register_action_handler(ChainActionType.DELAY, mock_handler)
    
    await manager.register_chain("test_chain", steps)
    execution = await manager.execute_chain("test_chain")
    
    assert execution.is_complete
    assert len(execution.completed_steps) == 2
    assert len(execution.failed_steps) == 0


@pytest.mark.asyncio
async def test_event_chain_manager_execute_chain_with_retry(mock_hass):
    """Test chain execution with retry logic."""
    manager = EventChainManager(mock_hass)
    
    attempt_count = 0
    
    async def failing_handler(step, hass):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise ValueError("Simulated failure")
        return {"status": "ok"}
    
    steps = [
        ChainStep(
            action=ChainActionType.ANNOUNCEMENT,
            target="event1",
            max_retries=3,
        ),
    ]
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, failing_handler)
    await manager.register_chain("retry_chain", steps)
    
    execution = await manager.execute_chain("retry_chain")
    
    assert execution.is_complete
    assert len(execution.completed_steps) == 1
    assert len(execution.failed_steps) == 0
    assert attempt_count == 3


@pytest.mark.asyncio
async def test_event_chain_manager_execute_chain_with_dependency(mock_hass):
    """Test chain execution with step dependencies."""
    manager = EventChainManager(mock_hass)
    
    async def mock_handler(step, hass):
        return {"status": "ok"}
    
    steps = [
        ChainStep(action=ChainActionType.ANNOUNCEMENT, target="event1"),
        ChainStep(
            action=ChainActionType.DELAY,
            parameters={"duration_ms": 100},
            depends_on=["announcement_event1"],
        ),
    ]
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    manager.register_action_handler(ChainActionType.DELAY, mock_handler)
    
    await manager.register_chain("dep_chain", steps)
    execution = await manager.execute_chain("dep_chain")
    
    assert execution.is_complete
    assert len(execution.completed_steps) == 2


@pytest.mark.asyncio
async def test_event_chain_manager_execute_chain_fail_on_error(mock_hass):
    """Test chain stops on fail-on-error step."""
    manager = EventChainManager(mock_hass)
    
    async def failing_handler(step, hass):
        raise ValueError("Fatal error")
    
    async def success_handler(step, hass):
        return {"status": "ok"}
    
    steps = [
        ChainStep(
            action=ChainActionType.ANNOUNCEMENT,
            target="event1",
            on_error="fail",
            depends_on=[],  # Wave 1
        ),
        ChainStep(
            action=ChainActionType.DELAY,
            parameters={"duration_ms": 100},
            on_error="continue",
            depends_on=["announcement_event1"],  # Wave 2 - waits for step 1 to fail
        ),
    ]
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, failing_handler)
    manager.register_action_handler(ChainActionType.DELAY, success_handler)
    
    await manager.register_chain("fail_chain", steps)
    execution = await manager.execute_chain("fail_chain")
    
    assert execution.is_complete
    assert len(execution.failed_steps) == 1
    assert len(execution.completed_steps) == 0


@pytest.mark.asyncio
async def test_create_announcement_chain():
    """Test announcement chain factory."""
    chain_steps = create_announcement_chain(
        event_id="test_event",
        group_id="test_group",
        volume_increase=0.15,
    )
    
    assert len(chain_steps) == 4
    assert chain_steps[0].action == ChainActionType.GROUP_VOLUME_UP
    assert chain_steps[1].action == ChainActionType.ANNOUNCEMENT
    assert chain_steps[2].action == ChainActionType.DELAY
    assert chain_steps[3].action == ChainActionType.GROUP_VOLUME_DOWN
    
    assert chain_steps[0].parameters["volume_step"] == 0.15
    assert chain_steps[1].target == "test_event"


@pytest.mark.asyncio
async def test_handle_announcement_action(mock_hass):
    """Test announcement action handler."""
    step = ChainStep(action=ChainActionType.ANNOUNCEMENT, target="event_id")
    
    result = await handle_announcement_action(step, mock_hass)
    
    assert result["event_id"] == "event_id"
    assert result["status"] == "queued"
    
    # Verify service was called
    mock_hass.services.async_call.assert_called_once()
    call_args = mock_hass.services.async_call.call_args
    assert call_args[0][0] == "house_voice"
    assert call_args[0][1] == "say"


@pytest.mark.asyncio
async def test_handle_delay_action(mock_hass):
    """Test delay action handler."""
    step = ChainStep(
        action=ChainActionType.DELAY,
        parameters={"duration_ms": 100},
    )
    
    result = await handle_delay_action(step, mock_hass)
    
    assert result["duration_ms"] == 100
    assert result["status"] == "completed"


# ── Sprint 3 Task 2: Conditional Steps Tests ────────────────────────────────

@pytest.mark.asyncio
async def test_should_execute_step_with_condition_true(mock_hass):
    """Test that a step executes when condition is true."""
    manager = EventChainManager(mock_hass)
    
    # Register handlers
    async def mock_condition_handler(step, hass):
        return {"result": True}
    
    async def mock_announcement_handler(step, hass):
        return {"success": True}
    
    manager.register_action_handler(
        ChainActionType.CONDITION_CHECK,
        mock_condition_handler
    )
    manager.register_action_handler(
        ChainActionType.ANNOUNCEMENT,
        mock_announcement_handler
    )
    
    # Create a chain with condition and branching
    cond_step = ChainStep(
        action=ChainActionType.CONDITION_CHECK,
        parameters={"conditions": [
            {"entity_id": "binary_sensor.test", "state": "on"}
        ]},
        branch_on_condition={
            "true": "announcement_execute_this",
            "false": "announcement_skip_this"
        }
    )
    
    true_step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="execute_this",
    )
    
    false_step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="skip_this",
    )
    
    # Set up execution state
    execution = ChainExecution(chain_id="test", started_at=0)
    execution.step_results[cond_step.step_id] = {"result": True}
    
    # Check if steps should execute
    steps_by_id = {
        cond_step.step_id: cond_step,
        true_step.step_id: true_step,
        false_step.step_id: false_step,
    }
    
    true_should_exec, reason = manager._should_execute_step(true_step, execution, steps_by_id)
    false_should_exec, reason_false = manager._should_execute_step(false_step, execution, steps_by_id)
    
    assert true_should_exec is True, "True branch should execute when condition passes"
    assert false_should_exec is False, "False branch should not execute when condition passes"


@pytest.mark.asyncio
async def test_should_execute_step_with_condition_false(mock_hass):
    """Test that correct step executes when condition is false."""
    manager = EventChainManager(mock_hass)
    
    # Create a chain with condition
    cond_step = ChainStep(
        action=ChainActionType.CONDITION_CHECK,
        parameters={"conditions": [
            {"entity_id": "binary_sensor.test", "state": "on"}
        ]},
        branch_on_condition={
            "true": "announcement_execute_this",
            "false": "announcement_skip_this"
        }
    )
    
    true_step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="execute_this",
    )
    
    false_step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="skip_this",
    )
    
    # Set up execution state - condition failed
    execution = ChainExecution(chain_id="test", started_at=0)
    execution.step_results[cond_step.step_id] = {"result": False}
    
    # Check if steps should execute
    steps_by_id = {
        cond_step.step_id: cond_step,
        true_step.step_id: true_step,
        false_step.step_id: false_step,
    }
    
    true_should_exec, reason = manager._should_execute_step(true_step, execution, steps_by_id)
    false_should_exec, reason_false = manager._should_execute_step(false_step, execution, steps_by_id)
    
    assert true_should_exec is False, "True branch should not execute when condition fails"
    assert false_should_exec is True, "False branch should execute when condition fails"


@pytest.mark.asyncio
async def test_step_without_condition_gate_executes(mock_hass):
    """Test that steps without condition gates execute normally."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="normal_step",
    )
    
    execution = ChainExecution(chain_id="test", started_at=0)
    steps_by_id = {step.step_id: step}
    
    should_exec, reason = manager._should_execute_step(step, execution, steps_by_id)
    
    assert should_exec is True, "Steps without condition gates should execute"
    assert reason == "no_condition_gate"
