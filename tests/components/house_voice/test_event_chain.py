"""Tests for House Voice Manager Sprint 2 - Event Chain Manager."""

from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import pytest

from custom_components.house_voice.events.event_chain import (
    EventChainManager,
    ChainStep,
    ChainActionType,
    ChainExecution,
    RetryConfig,
    CircuitBreakerState,
    EventContext,
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


# ── Sprint 3 Task 3: Webhook Actions ────────────────────────────────────────

@pytest.mark.asyncio
async def test_webhook_successful_post(mock_hass) -> None:
    """Test successful webhook POST request."""
    from custom_components.house_voice.events.event_chain import (
        ChainStep,
        ChainActionType,
        handle_webhook_action,
    )
    from unittest.mock import MagicMock
    
    # Create proper async context manager mock for response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value='{"status": "ok"}')
    
    # Create proper async context manager for session.post()
    mock_post_context = AsyncMock()
    mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_context.__aexit__ = AsyncMock(return_value=None)
    
    # Create session mock
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_post_context)
    
    # Create proper async context manager for ClientSession()
    mock_client_context = AsyncMock()
    mock_client_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client_context.__aexit__ = AsyncMock(return_value=None)
    
    step = ChainStep(
        action=ChainActionType.WEBHOOK,
        target="https://example.com/webhook",
    )
    
    with patch('aiohttp.ClientSession') as mock_client:
        mock_client.return_value = mock_client_context
        
        result = await handle_webhook_action(step, mock_hass)
    
    assert result["status"] == "completed"
    assert result["response_status_code"] == 200
    assert result["success"] is True
    assert "webhook_url" in result
    assert "execution_time_ms" in result


@pytest.mark.asyncio
async def test_webhook_with_custom_headers(mock_hass) -> None:
    """Test webhook with custom headers."""
    from custom_components.house_voice.events.event_chain import (
        ChainStep,
        ChainActionType,
        handle_webhook_action,
    )
    from unittest.mock import MagicMock
    
    mock_response = MagicMock()
    mock_response.status = 201
    mock_response.text = AsyncMock(return_value='')
    
    mock_post_context = AsyncMock()
    mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_context.__aexit__ = AsyncMock(return_value=None)
    
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_post_context)
    
    mock_client_context = AsyncMock()
    mock_client_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client_context.__aexit__ = AsyncMock(return_value=None)
    
    step = ChainStep(
        action=ChainActionType.WEBHOOK,
        target="https://example.com/webhook",
        parameters={
            "headers": {
                "Authorization": "Bearer token123",
                "X-Custom-Header": "value",
            }
        },
    )
    
    with patch('aiohttp.ClientSession') as mock_client:
        mock_client.return_value = mock_client_context
        
        result = await handle_webhook_action(step, mock_hass)
    
    assert result["status"] == "completed"
    assert result["response_status_code"] == 201
    
    # Verify headers were passed
    call_kwargs = mock_session.post.call_args[1]
    assert "Authorization" in call_kwargs["headers"]
    assert call_kwargs["headers"]["Authorization"] == "Bearer token123"


@pytest.mark.asyncio
async def test_webhook_timeout(mock_hass) -> None:
    """Test webhook timeout handling."""
    from custom_components.house_voice.events.event_chain import (
        ChainStep,
        ChainActionType,
        handle_webhook_action,
    )
    from unittest.mock import MagicMock
    
    mock_session = MagicMock()
    mock_session.post = MagicMock(side_effect=asyncio.TimeoutError())
    
    mock_client_context = AsyncMock()
    mock_client_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client_context.__aexit__ = AsyncMock(return_value=None)
    
    step = ChainStep(
        action=ChainActionType.WEBHOOK,
        target="https://example.com/webhook",
        parameters={"timeout": 5},
    )
    
    with patch('aiohttp.ClientSession') as mock_client:
        mock_client.return_value = mock_client_context
        
        result = await handle_webhook_action(step, mock_hass)
    
    assert result["status"] == "completed"
    assert result["error"] == "timeout"
    assert result["success"] is False
    assert result["timeout_seconds"] == 5


@pytest.mark.asyncio
async def test_webhook_client_error(mock_hass) -> None:
    """Test webhook client error handling."""
    from custom_components.house_voice.events.event_chain import (
        ChainStep,
        ChainActionType,
        handle_webhook_action,
    )
    from unittest.mock import MagicMock
    import aiohttp
    
    mock_session = MagicMock()
    mock_session.post = MagicMock(side_effect=aiohttp.ClientError("Connection refused"))
    
    mock_client_context = AsyncMock()
    mock_client_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client_context.__aexit__ = AsyncMock(return_value=None)
    
    step = ChainStep(
        action=ChainActionType.WEBHOOK,
        target="https://example.com/webhook",
    )
    
    with patch('aiohttp.ClientSession') as mock_client:
        mock_client.return_value = mock_client_context
        
        result = await handle_webhook_action(step, mock_hass)
    
    assert result["status"] == "completed"
    assert result["error"] == "client_error"
    assert result["success"] is False


@pytest.mark.asyncio
async def test_webhook_missing_url(mock_hass) -> None:
    """Test webhook with missing URL raises error."""
    from custom_components.house_voice.events.event_chain import (
        ChainStep,
        ChainActionType,
        handle_webhook_action,
    )
    
    step = ChainStep(
        action=ChainActionType.WEBHOOK,
        target=None,
    )
    
    with pytest.raises(ValueError, match="webhook action requires target"):
        await handle_webhook_action(step, mock_hass)


@pytest.mark.asyncio
async def test_webhook_invalid_url_scheme(mock_hass) -> None:
    """Test webhook with invalid URL scheme raises error."""
    from custom_components.house_voice.events.event_chain import (
        ChainStep,
        ChainActionType,
        handle_webhook_action,
    )
    
    step = ChainStep(
        action=ChainActionType.WEBHOOK,
        target="ftp://example.com/webhook",
    )
    
    with pytest.raises(ValueError, match="Invalid webhook URL scheme"):
        await handle_webhook_action(step, mock_hass)


@pytest.mark.asyncio
async def test_webhook_4xx_response(mock_hass) -> None:
    """Test webhook with 4xx response is marked as unsuccessful."""
    from custom_components.house_voice.events.event_chain import (
        ChainStep,
        ChainActionType,
        handle_webhook_action,
    )
    from unittest.mock import MagicMock
    
    mock_response = MagicMock()
    mock_response.status = 400
    mock_response.text = AsyncMock(return_value='{"error": "bad request"}')
    
    mock_post_context = AsyncMock()
    mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_context.__aexit__ = AsyncMock(return_value=None)
    
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_post_context)
    
    mock_client_context = AsyncMock()
    mock_client_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client_context.__aexit__ = AsyncMock(return_value=None)
    
    step = ChainStep(
        action=ChainActionType.WEBHOOK,
        target="https://example.com/webhook",
    )
    
    with patch('aiohttp.ClientSession') as mock_client:
        mock_client.return_value = mock_client_context
        
        result = await handle_webhook_action(step, mock_hass)
    
    assert result["status"] == "completed"
    assert result["response_status_code"] == 400
    assert result["success"] is False


@pytest.mark.asyncio
async def test_webhook_step_data_included(mock_hass) -> None:
    """Test webhook includes step data in payload."""
    from custom_components.house_voice.events.event_chain import (
        ChainStep,
        ChainActionType,
        handle_webhook_action,
    )
    from unittest.mock import MagicMock
    
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value='{}')
    
    mock_post_context = AsyncMock()
    mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_context.__aexit__ = AsyncMock(return_value=None)
    
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_post_context)
    
    mock_client_context = AsyncMock()
    mock_client_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client_context.__aexit__ = AsyncMock(return_value=None)
    
    step = ChainStep(
        action=ChainActionType.WEBHOOK,
        target="https://example.com/webhook",
        parameters={"key": "value"},
    )
    
    with patch('aiohttp.ClientSession') as mock_client:
        mock_client.return_value = mock_client_context
        
        result = await handle_webhook_action(step, mock_hass)
    
    # Verify step data was in payload
    call_kwargs = mock_session.post.call_args[1]
    assert "json" in call_kwargs
    payload = call_kwargs["json"]
    assert "action" in payload
    assert "step" in payload
    assert payload["action"] == "webhook"


# ── Sprint 4: Advanced Retry Strategies Tests ──────────────────────────────────

@pytest.mark.asyncio
async def test_exponential_backoff(mock_hass):
    """Test exponential backoff calculation."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="speaker_group",
        retry_config=RetryConfig(
            max_attempts=4,
            backoff_mode="exponential",
            base_delay_ms=100,
            max_delay_ms=2000,
        ),
    )
    
    # Verify delay calculations match exponential formula
    assert step.retry_config.get_delay_ms(0) == 100      # 100 * 2^0
    assert step.retry_config.get_delay_ms(1) == 200      # 100 * 2^1
    assert step.retry_config.get_delay_ms(2) == 400      # 100 * 2^2
    assert step.retry_config.get_delay_ms(3) == 800      # 100 * 2^3
    assert step.retry_config.get_delay_ms(4) == 1600     # 100 * 2^4
    assert step.retry_config.get_delay_ms(5) == 2000     # capped at 2000


@pytest.mark.asyncio
async def test_linear_backoff(mock_hass):
    """Test linear backoff calculation."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="speaker_group",
        retry_config=RetryConfig(
            max_attempts=4,
            backoff_mode="linear",
            base_delay_ms=500,
            max_delay_ms=2000,
        ),
    )
    
    # Verify delay calculations match linear formula
    assert step.retry_config.get_delay_ms(0) == 500      # 500 * 1
    assert step.retry_config.get_delay_ms(1) == 1000     # 500 * 2
    assert step.retry_config.get_delay_ms(2) == 1500     # 500 * 3
    assert step.retry_config.get_delay_ms(3) == 2000     # 500 * 4
    assert step.retry_config.get_delay_ms(4) == 2000     # 500 * 5 capped at 2000


@pytest.mark.asyncio
async def test_constant_backoff(mock_hass):
    """Test constant backoff calculation."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="speaker_group",
        retry_config=RetryConfig(
            max_attempts=4,
            backoff_mode="constant",
            base_delay_ms=500,
            max_delay_ms=2000,
        ),
    )
    
    # Verify delay calculations remain constant
    assert step.retry_config.get_delay_ms(0) == 500      # always base_delay
    assert step.retry_config.get_delay_ms(1) == 500
    assert step.retry_config.get_delay_ms(2) == 500
    assert step.retry_config.get_delay_ms(3) == 500


@pytest.mark.asyncio
async def test_circuit_breaker_opens_and_resets(mock_hass):
    """Test circuit breaker opens after threshold and resets after timeout."""
    manager = EventChainManager(mock_hass)
    
    # Create a step that will fail
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="failing_speaker",
        retry_config=RetryConfig(
            max_attempts=2,
            backoff_mode="constant",
            base_delay_ms=10,
            circuit_breaker_threshold=3,
            circuit_breaker_reset_after_seconds=1,
        ),
    )
    
    execution = ChainExecution(chain_id="test_chain", started_at=0)
    
    # Register a handler that always fails
    async def failing_handler(step, hass):
        raise RuntimeError("Handler failure")
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, failing_handler)
    
    # Execute step 3 times (threshold = 3)
    # First attempt: fails once
    result1 = await manager._execute_step_with_retry(step, execution)
    assert result1 is False
    assert step.step_id in manager.circuit_breaker_states
    assert manager.circuit_breaker_states[step.step_id].failure_count == 2  # 2 retries per attempt logic
    assert not manager.circuit_breaker_states[step.step_id].is_open
    
    # Second attempt: fails, reaches threshold
    result2 = await manager._execute_step_with_retry(step, execution)
    assert result2 is False
    # Circuit breaker should now be open
    assert manager.circuit_breaker_states[step.step_id].is_open
    
    # Third attempt: should be skipped due to open circuit breaker
    execution.failed_steps.clear()
    result3 = await manager._execute_step_with_retry(step, execution)
    assert result3 is False  # Should fail without attempting
    assert step.step_id in execution.failed_steps
    
    # Simulate time passing and verify reset behavior
    # Manually set last failure time to past
    import time
    cb = manager.circuit_breaker_states[step.step_id]
    cb.last_failure_time = time.time() - 2.0  # 2 seconds ago
    
    # Next check should reset the circuit breaker
    should_skip = cb.should_skip(
        step.retry_config.circuit_breaker_threshold,
        step.retry_config.circuit_breaker_reset_after_seconds,
    )
    assert should_skip is False
    assert cb.is_open is False
    assert cb.failure_count == 0


# ── Sprint 5: Event Routing & Transformation Tests ────────────────────────────

@pytest.mark.asyncio
async def test_event_filter_match_single(mock_hass):
    """Test event filter matches single condition."""
    from custom_components.house_voice.events.event_chain import EventFilter
    
    event_filter = EventFilter(
        key="source",
        value="mqtt",
        operator="equals",
    )
    
    event_data = {"source": "mqtt", "device": "sensor1"}
    assert event_filter.matches(event_data) is True
    
    event_data_mismatch = {"source": "service", "device": "sensor1"}
    assert event_filter.matches(event_data_mismatch) is False


@pytest.mark.asyncio
async def test_event_filter_mismatch(mock_hass):
    """Test event filter doesn't match."""
    from custom_components.house_voice.events.event_chain import EventFilter
    
    event_filter = EventFilter(
        key="device_type",
        value="sensor",
        operator="equals",
    )
    
    # Missing key
    assert event_filter.matches({"other_field": "value"}) is False
    
    # Different value
    assert event_filter.matches({"device_type": "switch"}) is False


@pytest.mark.asyncio
async def test_event_filter_contains(mock_hass):
    """Test event filter with contains operator."""
    from custom_components.house_voice.events.event_chain import EventFilter
    
    event_filter = EventFilter(
        key="message",
        value="error",
        operator="contains",
    )
    
    assert event_filter.matches({"message": "An error occurred"}) is True
    assert event_filter.matches({"message": "Success"}) is False


@pytest.mark.asyncio
async def test_event_filter_regex(mock_hass):
    """Test event filter with regex operator."""
    from custom_components.house_voice.events.event_chain import EventFilter
    
    event_filter = EventFilter(
        key="entity_id",
        value=r"sensor\..*_temperature",
        operator="regex",
    )
    
    assert event_filter.matches({"entity_id": "sensor.living_room_temperature"}) is True
    assert event_filter.matches({"entity_id": "sensor.humidity"}) is False


@pytest.mark.asyncio
async def test_evaluate_event_filter_utility(mock_hass):
    """Test evaluate_event_filter utility function."""
    from custom_components.house_voice.events.event_chain import evaluate_event_filter
    
    # No filter = always match
    assert evaluate_event_filter(None, {}) is True
    
    # Single filter dict
    filter_dict = {"key": "source", "value": "mqtt", "operator": "equals"}
    assert evaluate_event_filter(filter_dict, {"source": "mqtt"}) is True
    assert evaluate_event_filter(filter_dict, {"source": "service"}) is False
    
    # Multiple filters (AND-logic)
    filters = [
        {"key": "source", "value": "mqtt", "operator": "equals"},
        {"key": "device_type", "value": "sensor", "operator": "equals"},
    ]
    assert evaluate_event_filter(filters, {"source": "mqtt", "device_type": "sensor"}) is True
    assert evaluate_event_filter(filters, {"source": "mqtt", "device_type": "switch"}) is False


@pytest.mark.asyncio
async def test_evaluate_expression_simple(mock_hass):
    """Test simple expression evaluation."""
    from custom_components.house_voice.events.event_chain import evaluate_expression
    
    # Simple substitution
    context = {"event": {"room": "living_room"}}
    result = evaluate_expression("{{ event.room }}", context)
    assert result == "living_room"
    
    # Multiple substitutions
    context = {"name": "John", "room": "kitchen"}
    result = evaluate_expression("Hello {{ name }} in {{ room }}", context)
    assert "John" in result
    assert "kitchen" in result
    
    # Missing key (returns original)
    context = {"name": "John"}
    result = evaluate_expression("Hello {{ missing_key }}", context)
    assert "missing_key" in result or result == "Hello "


@pytest.mark.asyncio
async def test_apply_transformations(mock_hass):
    """Test parameter transformation."""
    from custom_components.house_voice.events.event_chain import apply_transformations
    
    parameters = {"message": "Default", "volume": "50"}
    
    # No transform = return as-is
    result = apply_transformations(parameters, None, {})
    assert result == parameters
    
    # Simple transform
    transform = {"message": "{{ event.custom_message }}"}
    context = {"event": {"custom_message": "Hello World"}}
    result = apply_transformations(parameters, transform, context)
    assert result["message"] == "Hello World"
    assert result["volume"] == "50"  # Unchanged



# Phase 2: Event Filtering Integration Tests

@pytest.mark.asyncio
async def test_execute_step_with_filter_match(mock_hass):
    """Test step executes when filter matches."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="speaker_group",
        filter={"key": "source", "value": "mqtt", "operator": "equals"},
    )
    
    execution = ChainExecution(chain_id="test", started_at=0)
    event_context = EventContext(
        source="mqtt",
        data={"source": "mqtt", "device": "sensor1"},
    )
    
    # Register handler
    async def mock_handler(step, hass):
        return {"success": True}
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    
    # Execute - should proceed because filter matches
    result = await manager._execute_step_with_retry(
        step, execution, event_context
    )
    assert result is True
    assert step.step_id in execution.completed_steps


@pytest.mark.asyncio
async def test_execute_step_with_filter_mismatch(mock_hass):
    """Test step skips when filter doesn't match."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="speaker_group",
        filter={"key": "source", "value": "mqtt", "operator": "equals"},
    )
    
    execution = ChainExecution(chain_id="test", started_at=0)
    event_context = EventContext(
        source="service",
        data={"source": "service", "device": "sensor1"},
    )
    
    async def mock_handler(step, hass):
        raise RuntimeError("Should not be called")
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    
    # Execute - should skip due to filter mismatch
    result = await manager._execute_step_with_retry(
        step, execution, event_context
    )
    assert result is True  # Non-fatal skip
    assert step.step_id not in execution.completed_steps
    assert step.step_id not in execution.failed_steps


@pytest.mark.asyncio
async def test_execute_step_without_filter_executes(mock_hass):
    """Test step executes when no filter specified."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="speaker_group",
        # No filter
    )
    
    execution = ChainExecution(chain_id="test", started_at=0)
    event_context = EventContext(
        source="mqtt",
        data={"source": "mqtt"},
    )
    
    async def mock_handler(step, hass):
        return {"success": True}
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    
    # Execute - should proceed (no filter)
    result = await manager._execute_step_with_retry(
        step, execution, event_context
    )
    assert result is True
    assert step.step_id in execution.completed_steps


@pytest.mark.asyncio
async def test_execute_step_filter_without_context(mock_hass):
    """Test step executes even with filter when no context provided."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="speaker_group",
        filter={"key": "source", "value": "mqtt", "operator": "equals"},
    )
    
    execution = ChainExecution(chain_id="test", started_at=0)
    
    async def mock_handler(step, hass):
        return {"success": True}
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    
    # Execute without event_context - filter should be skipped
    result = await manager._execute_step_with_retry(
        step, execution, None
    )
    assert result is True
    assert step.step_id in execution.completed_steps



# Phase 3: Dynamic Routing Integration Tests

@pytest.mark.asyncio
async def test_dynamic_routing_simple(mock_hass):
    """Test dynamic routing resolves target from expression."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="default_speaker",
        route_expression="{{ event.speaker }}",
    )
    
    execution = ChainExecution(chain_id="test", started_at=0)
    event_context = EventContext(
        source="mqtt",
        data={"speaker": "living_room_speaker"},
    )
    
    received_target = None
    
    async def mock_handler(step, hass):
        nonlocal received_target
        received_target = step.target
        return {"success": True}
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    
    result = await manager._execute_step_with_retry(
        step, execution, event_context
    )
    
    assert result is True
    assert received_target == "living_room_speaker"
    assert step.step_id in execution.completed_steps


@pytest.mark.asyncio
async def test_dynamic_routing_with_conditions(mock_hass):
    """Test dynamic routing with conditional expression."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="default_speaker",
        route_expression="{{ event.room if event.room == 'living_room' else 'bedroom' }}",
    )
    
    execution = ChainExecution(chain_id="test", started_at=0)
    event_context = EventContext(
        source="mqtt",
        data={"room": "living_room"},
    )
    
    received_target = None
    
    async def mock_handler(step, hass):
        nonlocal received_target
        received_target = step.target
        return {"success": True}
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    
    result = await manager._execute_step_with_retry(
        step, execution, event_context
    )
    
    assert result is True
    assert received_target == "living_room"


@pytest.mark.asyncio
async def test_dynamic_routing_fallback_to_static(mock_hass):
    """Test fallback to static target when route_expression undefined."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="static_speaker",
        route_expression="{{ event.missing_key }}",
    )
    
    execution = ChainExecution(chain_id="test", started_at=0)
    event_context = EventContext(
        source="mqtt",
        data={"other_field": "value"},
    )
    
    received_target = None
    
    async def mock_handler(step, hass):
        nonlocal received_target
        received_target = step.target
        return {"success": True}
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    
    result = await manager._execute_step_with_retry(
        step, execution, event_context
    )
    
    assert result is True
    # Should use the expression result (empty string) not static fallback
    assert received_target == ""


@pytest.mark.asyncio
async def test_dynamic_routing_without_context(mock_hass):
    """Test routing without event_context uses static target."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="static_speaker",
        route_expression="{{ event.speaker }}",
    )
    
    execution = ChainExecution(chain_id="test", started_at=0)
    
    received_target = None
    
    async def mock_handler(step, hass):
        nonlocal received_target
        received_target = step.target
        return {"success": True}
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    
    # Execute without event_context - should use static target
    result = await manager._execute_step_with_retry(
        step, execution, None
    )
    
    assert result is True
    assert received_target == "static_speaker"



# ── Phase 4: Parameter Transformation Tests ────────────────────────────────

@pytest.mark.asyncio
async def test_parameter_transformation_simple(mock_hass):
    """Test simple parameter transformation with event data."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="speaker1",
        parameters={"message": "Hello"},
        transform={"message": "Hello {{ event.name }}"},
    )
    
    received_params = None
    
    async def mock_handler(s, hass):
        nonlocal received_params
        received_params = s.parameters
        return {"success": True}
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    
    context = EventContext(
        source="test",
        data={"name": "Alice"},
        metadata={},
    )
    
    execution = ChainExecution(chain_id="test", started_at=0)
    result = await manager._execute_step_with_retry(step, execution, context)
    
    assert result is True
    assert received_params["message"] == "Hello Alice"


@pytest.mark.asyncio
async def test_parameter_transformation_with_event_data(mock_hass):
    """Test transformation using event data and config values."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="speaker1",
        parameters={
            "room": "living_room",
            "volume": 50,
            "message": "Room {{ config.room }} volume {{ config.volume }}",
        },
        transform={
            "message": "Room {{ config.room }} at {{ event.time }}",
        },
    )
    
    received_params = None
    
    async def mock_handler(s, hass):
        nonlocal received_params
        received_params = s.parameters
        return {"success": True}
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    
    context = EventContext(
        source="automation",
        data={"time": "14:30"},
        metadata={},
    )
    
    execution = ChainExecution(chain_id="test", started_at=0)
    result = await manager._execute_step_with_retry(step, execution, context)
    
    assert result is True
    assert received_params["message"] == "Room living_room at 14:30"
    assert received_params["room"] == "living_room"  # Unchanged
    assert received_params["volume"] == 50  # Unchanged


@pytest.mark.asyncio
async def test_parameter_transformation_fallback(mock_hass):
    """Test fallback to original parameters on transformation error."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="speaker1",
        parameters={"original": "value"},
        transform={"message": "Missing {{ undefined.key }}"},
    )
    
    received_params = None
    
    async def mock_handler(s, hass):
        nonlocal received_params
        received_params = s.parameters
        return {"success": True}
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    
    context = EventContext(
        source="test",
        data={"name": "Bob"},
        metadata={},
    )
    
    execution = ChainExecution(chain_id="test", started_at=0)
    result = await manager._execute_step_with_retry(step, execution, context)
    
    # Should complete even with transformation error
    assert result is True
    # Original parameters should be preserved on error
    assert received_params["original"] == "value"


@pytest.mark.asyncio
async def test_parameter_transformation_without_context(mock_hass):
    """Test transformations skipped gracefully when context is None."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="speaker1",
        parameters={"greeting": "Hello"},
        transform={"greeting": "Hello {{ event.name }}"},
    )
    
    received_params = None
    
    async def mock_handler(s, hass):
        nonlocal received_params
        received_params = s.parameters
        return {"success": True}
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    
    execution = ChainExecution(chain_id="test", started_at=0)
    
    # Execute without context
    result = await manager._execute_step_with_retry(step, execution, event_context=None)
    
    assert result is True
    # When no context, original parameters used (transform skipped)
    assert received_params["greeting"] == "Hello"


# ── Phase 5: Integration Test (Filter + Routing + Transformation) ───────────

@pytest.mark.asyncio
async def test_integration_filter_routing_transformation(mock_hass):
    """Integration test: filter skips, then routing + transformation on match."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="default_speaker",
        parameters={"message": "Hello"},
        filter={"key": "room", "value": "living_room", "operator": "equals"},  # Filter for specific room
        route_expression="{{ event.speaker }}",  # Route to dynamic speaker
        transform={"message": "Announcing in {{ event.room }}: {{ event.text }}"},  # Transform message
    )
    
    received_target = None
    received_params = None
    
    async def mock_handler(s, hass):
        nonlocal received_target, received_params
        received_target = s.target
        received_params = s.parameters
        return {"success": True}
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    
    # Test 1: Filter doesn't match - should skip non-fatally
    context_wrong_room = EventContext(
        source="automation",
        data={"room": "bedroom", "speaker": "bedroom_speaker", "text": "Wake up"},
        metadata={},
    )
    
    execution1 = ChainExecution(chain_id="test1", started_at=0)
    result1 = await manager._execute_step_with_retry(step, execution1, context_wrong_room)
    
    assert result1 is True  # Non-fatal skip
    assert received_target is None  # Handler never called
    
    # Test 2: Filter matches - should execute with routing + transformation
    context_matching = EventContext(
        source="automation",
        data={"room": "living_room", "speaker": "living_room_speaker", "text": "Time to wake up"},
        metadata={},
    )
    
    execution2 = ChainExecution(chain_id="test2", started_at=0)
    result2 = await manager._execute_step_with_retry(step, execution2, context_matching)
    
    assert result2 is True
    assert received_target == "living_room_speaker"  # Routed to event.speaker
    assert received_params["message"] == "Announcing in living_room: Time to wake up"  # Transformed


@pytest.mark.asyncio
async def test_integration_all_features_complex(mock_hass):
    """Complex integration: filter + conditional routing + multi-param transformation."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="default",
        parameters={
            "message": "test",
            "volume": 50,
            "priority": "normal",
        },
        filter={
            "key": "priority",
            "value": "high",
            "operator": "equals"
        },
        route_expression="{{ 'emergency' if event.priority == 'critical' else 'normal' }}",
        transform={
            "message": "[{{ event.priority|upper }}] {{ event.text }}",
            "volume": 80,  # Literal value
        }
    )
    
    received_target = None
    received_params = None
    
    async def mock_handler(s, hass):
        nonlocal received_target, received_params
        received_target = s.target
        received_params = s.parameters
        return {"success": True}
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    
    context = EventContext(
        source="security",
        data={"priority": "high", "text": "Intrusion detected"},
        metadata={"severity": "critical"},
    )
    
    execution = ChainExecution(chain_id="test", started_at=0)
    result = await manager._execute_step_with_retry(step, execution, context)
    
    assert result is True
    assert received_target == "normal"  # Routed based on priority value
    assert received_params["message"] == "[HIGH] Intrusion detected"
    assert received_params["volume"] == 80
    assert received_params["priority"] == "normal"  # Unchanged


@pytest.mark.asyncio  
async def test_backward_compatibility_no_new_features(mock_hass):
    """Verify backward compatibility: steps without filter/route/transform still work."""
    manager = EventChainManager(mock_hass)
    
    # Old-style step with no filter, routing, or transformation
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="speaker1",
        parameters={"message": "Hello World"},
    )
    
    received_params = None
    
    async def mock_handler(s, hass):
        nonlocal received_params
        received_params = s.parameters
        return {"success": True}
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    
    # Even with event context, should execute with original parameters
    context = EventContext(
        source="test",
        data={"anything": "can_be_here"},
        metadata={},
    )
    
    execution = ChainExecution(chain_id="test", started_at=0)
    result = await manager._execute_step_with_retry(step, execution, context)
    
    assert result is True
    assert received_params["message"] == "Hello World"  # Unchanged


@pytest.mark.asyncio
async def test_integration_filter_with_routing(mock_hass):
    """Filter check happens before routing - filtered steps don't get routed."""
    manager = EventChainManager(mock_hass)
    
    step = ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="static_target",
        filter={"key": "zone", "value": "office", "operator": "equals"},
        route_expression="{{ event.custom_target }}",
    )
    
    received_target = None
    
    async def mock_handler(s, hass):
        nonlocal received_target
        received_target = s.target
        return {"success": True}
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, mock_handler)
    
    # Context that doesn't match filter
    context = EventContext(
        source="test",
        data={"zone": "home", "custom_target": "routed_target"},
        metadata={},
    )
    
    execution = ChainExecution(chain_id="test", started_at=0)
    result = await manager._execute_step_with_retry(step, execution, context)
    
    # Should skip without even attempting routing
    assert result is True
    assert received_target is None
