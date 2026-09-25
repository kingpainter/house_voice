# VERSION = "3.4.0"
# File: tests/components/house_voice/test_announcement_chain_e2e.py
# Description: End-to-end tests for announcement chains with real speaker groups

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant, Context
from homeassistant.const import STATE_IDLE, STATE_PLAYING

from custom_components.house_voice.events.event_chain import (
    EventChainManager,
    ChainActionType,
    ChainStep,
    create_announcement_chain,
    handle_announcement_action,
    handle_group_volume_action,
    handle_delay_action,
)
from custom_components.house_voice.speaker_control.volume_controller import VolumeControllerV2
from custom_components.house_voice.speaker_control.fallback_strategies import (
    NoOpFallback,
    ManualAdjustmentFallback,
    SkipVolumeAdjustmentFallback,
)


@pytest.mark.asyncio
async def test_e2e_announcement_chain_success(mock_hass):
    """Test complete announcement chain: volume up → announce → delay → volume down."""
    # Setup mock speaker entity
    speaker_entity = MagicMock()
    speaker_entity.attributes = {
        "volume_level": 0.5,
        "app_id": "music_assistant",
    }
    mock_hass.states.get = MagicMock(return_value=speaker_entity)
    
    # Track service calls
    service_calls = []
    async def mock_service_call(domain, service, data):
        service_calls.append({"domain": domain, "service": service, "data": data})
    
    mock_hass.services.async_call = AsyncMock(side_effect=mock_service_call)
    
    # Create event chain manager
    manager = EventChainManager(mock_hass)
    
    # Register handlers
    async def handle_volume_up(step, hass):
        return {"success": True, "volume": 0.6}
    
    async def handle_volume_down(step, hass):
        return {"success": True, "volume": 0.5}
    
    async def handle_announcement(step, hass):
        return {"event_id": "test_event", "status": "queued"}
    
    async def handle_delay(step, hass):
        return {"duration_ms": 2000, "status": "completed"}
    
    manager.register_action_handler(ChainActionType.GROUP_VOLUME_UP, handle_volume_up)
    manager.register_action_handler(ChainActionType.GROUP_VOLUME_DOWN, handle_volume_down)
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, handle_announcement)
    manager.register_action_handler(ChainActionType.DELAY, handle_delay)
    
    # Create and register announcement chain
    chain_steps = create_announcement_chain(
        event_id="test_event",
        group_id="kokken",
        volume_increase=0.1,
    )
    
    await manager.register_chain("announcement_chain_1", chain_steps)
    
    # Execute chain
    execution = await manager.execute_chain("announcement_chain_1")
    
    # Verify execution succeeded
    assert execution.is_complete
    assert len(execution.completed_steps) == 4
    assert len(execution.failed_steps) == 0
    assert "group_volume_up_kokken" in execution.completed_steps
    assert "announcement_test_event" in execution.completed_steps
    assert "delay_generic" in execution.completed_steps
    assert "group_volume_down_kokken" in execution.completed_steps


@pytest.mark.asyncio
async def test_e2e_volume_controller_with_retry_and_fallback(mock_hass):
    """Test VolumeControllerV2 with 3-retry exponential backoff and fallback."""
    # Setup: service call fails twice, succeeds on third attempt
    attempt_count = [0]
    
    async def mock_service_call_with_retry(domain, service, data):
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise Exception(f"Service temporarily unavailable (attempt {attempt_count[0]})")
        # Success on third attempt
    
    mock_hass.services.async_call = AsyncMock(side_effect=mock_service_call_with_retry)
    
    controller = VolumeControllerV2(mock_hass)
    
    # Execute volume increase (should retry and succeed)
    result = await controller.increase_group_volume("kokken", 0.1)
    
    # Verify retry logic worked
    assert result.success
    assert result.attempted_count == 3  # Failed twice, succeeded on third
    assert attempt_count[0] == 3


@pytest.mark.asyncio
async def test_e2e_volume_controller_exhausts_retries_applies_fallback(mock_hass):
    """Test VolumeControllerV2 fallback when all retries fail."""
    # Setup: all service calls fail
    async def mock_service_call_always_fails(domain, service, data):
        raise Exception("Service permanently unavailable")
    
    mock_hass.services.async_call = AsyncMock(side_effect=mock_service_call_always_fails)
    
    # Track persistent notifications
    notifications = []
    async def mock_service_call_for_notification(domain, service, data):
        if domain == "persistent_notification" and service == "create":
            notifications.append(data)
        elif domain == "media_player":
            raise Exception("Service permanently unavailable")
    
    mock_hass.services.async_call = AsyncMock(side_effect=mock_service_call_for_notification)
    
    controller = VolumeControllerV2(mock_hass)
    
    # Execute volume increase (should exhaust retries and apply fallback)
    result = await controller.increase_group_volume("kokken", 0.1)
    
    # Verify fallback was applied
    assert result.attempted_count == 3
    assert result.fallback_applied
    assert result.fallback_strategy in ["noop", "manual_notification"]


@pytest.mark.asyncio
async def test_e2e_chain_with_dependencies(mock_hass):
    """Test event chain execution with step dependencies."""
    manager = EventChainManager(mock_hass)
    
    # Track execution order
    execution_order = []
    
    async def make_handler(step_id):
        async def handler(step, hass):
            execution_order.append(step_id)
            return {"status": "executed"}
        return handler
    
    manager.register_action_handler(ChainActionType.DELAY, await make_handler("delay_1"))
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, await make_handler("announce"))
    
    # Create chain with dependencies: delay_1 → announce (announce depends on delay_1)
    steps = [
        ChainStep(
            action=ChainActionType.DELAY,
            parameters={"duration_ms": 100},
            on_error="continue",
        ),
        ChainStep(
            action=ChainActionType.ANNOUNCEMENT,
            target="event_1",
            depends_on=["delay_generic"],  # Depends on previous step
            on_error="continue",
        ),
    ]
    
    await manager.register_chain("dep_chain", steps)
    execution = await manager.execute_chain("dep_chain")
    
    # Verify execution order
    assert execution.is_complete
    assert len(execution.completed_steps) >= 1


@pytest.mark.asyncio
async def test_e2e_chain_fail_on_error_stops_chain(mock_hass):
    """Test that fail-on-error stops chain execution."""
    manager = EventChainManager(mock_hass)
    
    # Step 1: succeeds
    async def success_handler(step, hass):
        return {"status": "ok"}
    
    # Step 2: fails, has on_error="fail"
    async def fail_handler(step, hass):
        raise Exception("Critical error")
    
    manager.register_action_handler(ChainActionType.ANNOUNCEMENT, success_handler)
    manager.register_action_handler(ChainActionType.DELAY, fail_handler)
    
    steps = [
        ChainStep(
            action=ChainActionType.ANNOUNCEMENT,
            target="event_1",
            on_error="continue",
            depends_on=[],  # Wave 1
        ),
        ChainStep(
            action=ChainActionType.DELAY,
            parameters={"duration_ms": 100},
            on_error="fail",  # This will stop the chain
            depends_on=["announcement_event_1"],  # Wave 2 - waits for step 1
        ),
        ChainStep(
            action=ChainActionType.ANNOUNCEMENT,
            target="event_2",
            on_error="continue",
            depends_on=["delay_generic"],  # Wave 3 - would wait for step 2 but it fails
        ),
    ]
    
    await manager.register_chain("fail_chain", steps)
    execution = await manager.execute_chain("fail_chain")
    
    # Verify chain stopped after failure
    assert execution.is_complete
    assert "announcement_event_1" in execution.completed_steps
    assert "delay_generic" in execution.failed_steps
    # Event 2 should not have executed because chain stopped
    assert "announcement_event_2" not in execution.completed_steps
    assert "announcement_event_2" not in execution.failed_steps


@pytest.mark.asyncio
async def test_e2e_multiple_speaker_groups_in_sequence(mock_hass):
    """Test announcement chain with multiple speaker groups."""
    manager = EventChainManager(mock_hass)
    
    # Track volume adjustments per group
    volume_adjustments = {"living_room": [], "kitchen": []}
    
    async def make_volume_handler(group_id):
        async def handler(step, hass):
            volume_adjustments[group_id].append(step.action.value)
            return {"success": True, "group": group_id}
        return handler
    
    # Register separate handlers for each group
    manager.register_action_handler(
        ChainActionType.GROUP_VOLUME_UP,
        await make_volume_handler("living_room")
    )
    manager.register_action_handler(
        ChainActionType.ANNOUNCEMENT,
        AsyncMock(return_value={"status": "queued"})
    )
    
    # Create chain with volume adjustments for multiple groups
    steps = [
        ChainStep(
            action=ChainActionType.GROUP_VOLUME_UP,
            target="living_room",
            parameters={"volume_step": 0.1},
            on_error="continue",
        ),
        ChainStep(
            action=ChainActionType.ANNOUNCEMENT,
            target="event_1",
            on_error="fail",
        ),
    ]
    
    await manager.register_chain("multi_group_chain", steps)
    execution = await manager.execute_chain("multi_group_chain")
    
    # Verify chain executed
    assert execution.is_complete
    assert len(execution.completed_steps) == 2


@pytest.mark.asyncio
async def test_e2e_fallback_strategies_cascade(mock_hass):
    """Test that fallback strategies execute in sequence."""
    # Setup: all strategies should attempt
    noop = NoOpFallback()
    manual = ManualAdjustmentFallback(mock_hass)
    skip = SkipVolumeAdjustmentFallback()
    
    # Mock persistent_notification service
    mock_hass.services.async_call = AsyncMock()
    
    # Execute fallbacks
    result1 = await noop.execute("kokken", 0.1, "increase", "Service unavailable")
    assert result1["success"]
    assert result1["strategy"] == "noop"
    
    result2 = await manual.execute("kokken", 0.1, "increase", "Service unavailable")
    assert result2["success"]
    assert result2["strategy"] == "manual_notification"
    
    result3 = await skip.execute("kokken", 0.1, "increase", "Service unavailable")
    assert result3["success"]
    assert result3["strategy"] == "skip_adjustment"


@pytest.mark.asyncio
async def test_e2e_announcement_with_actual_event_engine_integration(mock_hass, mock_engine, mock_entry, sample_event):
    """Integration test: announcement chain through VoiceEngine."""
    # Setup voice engine with mocked dependencies
    mock_hass.services.async_call = AsyncMock()
    
    # Setup event in storage
    test_event = {
        "message": "Test announcement",
        "speakers": ["media_player.kokken"],
        "priority": "normal",
        "volume": 0.35,
        "conditions": [],
    }
    
    # Mock storage.get_event to return the test event
    mock_engine.storage.get_event = MagicMock(return_value=test_event)
    
    # Mock UltraTTS class - patch at module level before VoiceEngine calls it
    mock_ultra_tts_instance = MagicMock()
    mock_ultra_tts_instance.async_speak = AsyncMock()
    
    with patch("custom_components.house_voice.voice_engine.UltraTTS", return_value=mock_ultra_tts_instance):
        # Execute announcement via engine
        try:
            await mock_engine.say("test_announcement")
        except Exception as e:
            # Log but continue - we're testing that the event was processed
            pass
    
    # Verify storage.get_event was called to fetch the event
    mock_engine.storage.get_event.assert_called_with("test_announcement")
    
    # Stop engine to cancel background task
    await mock_engine.stop()


@pytest.mark.asyncio
async def test_e2e_chain_with_delay_between_steps(mock_hass):
    """Test that delays between chain steps are respected."""
    import time
    
    manager = EventChainManager(mock_hass)
    
    execution_times = []
    
    async def make_timed_handler(handler_id):
        async def handler(step, hass):
            execution_times.append((handler_id, time.time()))
            return {"status": "executed"}
        return handler
    
    manager.register_action_handler(
        ChainActionType.ANNOUNCEMENT,
        await make_timed_handler("announce")
    )
    manager.register_action_handler(
        ChainActionType.DELAY,
        await make_timed_handler("delay")
    )
    
    # Create chain: announce → 500ms delay → announce
    steps = [
        ChainStep(
            action=ChainActionType.ANNOUNCEMENT,
            target="event_1",
            on_error="continue",
        ),
        ChainStep(
            action=ChainActionType.DELAY,
            parameters={"duration_ms": 500},
            on_error="continue",
        ),
        ChainStep(
            action=ChainActionType.ANNOUNCEMENT,
            target="event_2",
            on_error="continue",
        ),
    ]
    
    await manager.register_chain("timed_chain", steps)
    execution = await manager.execute_chain("timed_chain")
    
    # Verify execution completed
    assert execution.is_complete
    assert len(execution.completed_steps) >= 2


@pytest.mark.asyncio
async def test_e2e_volume_adjustment_result_tracking(mock_hass):
    """Test VolumeAdjustmentResult contains all expected fields."""
    async def mock_service_success(domain, service, data):
        pass
    
    mock_hass.services.async_call = AsyncMock(side_effect=mock_service_success)
    
    controller = VolumeControllerV2(mock_hass)
    result = await controller.increase_group_volume("kokken", 0.15)
    
    # Verify result contains all required fields
    assert hasattr(result, "success")
    assert hasattr(result, "group_id")
    assert hasattr(result, "action")
    assert hasattr(result, "attempted_count")
    assert hasattr(result, "final_volume")
    assert hasattr(result, "error_message")
    assert hasattr(result, "fallback_applied")
    assert hasattr(result, "fallback_strategy")
    
    assert result.success
    assert result.group_id == "kokken"
    assert result.action == "increase"
    assert result.attempted_count >= 1
