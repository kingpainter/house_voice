# VERSION = "3.6.0"
# File: test_phase7.py
# Description: Comprehensive tests for Phase 7 features
#              Versioning, Batch Operations, Parallel Execution, Conditions

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.components import websocket_api

from custom_components.house_voice.const import DOMAIN
from custom_components.house_voice.events.event_chain import (
    ConditionEvaluator,
    ChainVersionManager,
    BatchOperationManager,
    ParallelChainExecutor,
    ErrorRecoveryStrategy,
)


class TestConditionEvaluator:
    """Tests for ConditionEvaluator."""
    
    def test_evaluate_empty_expression(self):
        """Empty expression should return True (fail-safe)."""
        hass = MagicMock()
        evaluator = ConditionEvaluator(hass)
        
        assert evaluator.evaluate("") is True
        assert evaluator.evaluate(None) is True
    
    def test_evaluate_simple_boolean(self):
        """Evaluate simple boolean expressions."""
        hass = MagicMock()
        evaluator = ConditionEvaluator(hass)
        
        assert evaluator.evaluate("True") is True
        assert evaluator.evaluate("False") is False
    
    def test_evaluate_numeric_comparison(self):
        """Evaluate numeric comparisons."""
        hass = MagicMock()
        evaluator = ConditionEvaluator(hass)
        
        assert evaluator.evaluate("20 > 10") is True
        assert evaluator.evaluate("20 < 10") is False
        assert evaluator.evaluate("20 >= 20") is True
    
    def test_evaluate_logical_operators(self):
        """Evaluate logical operations."""
        hass = MagicMock()
        evaluator = ConditionEvaluator(hass)
        
        assert evaluator.evaluate("True and True") is True
        assert evaluator.evaluate("True and False") is False
        assert evaluator.evaluate("True or False") is True
    
    def test_evaluate_with_entity_reference(self):
        """Evaluate with entity state reference."""
        hass = MagicMock()
        state_obj = MagicMock()
        state_obj.state = "on"
        hass.states.get.return_value = state_obj
        
        evaluator = ConditionEvaluator(hass)
        result = evaluator.evaluate("'${binary_sensor.motion}' == 'on'")
        
        assert result is True
    
    def test_evaluate_error_returns_true(self):
        """Evaluation errors return True (fail-safe)."""
        hass = MagicMock()
        evaluator = ConditionEvaluator(hass)
        
        result = evaluator.evaluate("invalid syntax here @@@@")
        assert result is True  # Fail-safe


class TestChainVersionManager:
    """Tests for ChainVersionManager."""
    
    def test_save_and_retrieve_version(self):
        """Save and retrieve a chain version."""
        manager = ChainVersionManager()
        chain_data = {"name": "Test", "steps": []}
        
        manager.save_version("chain_1", 1, chain_data)
        retrieved = manager.get_version("chain_1", 1)
        
        assert retrieved is not None
        assert retrieved["name"] == "Test"
    
    def test_get_nonexistent_version(self):
        """Get non-existent version returns None."""
        manager = ChainVersionManager()
        
        result = manager.get_version("chain_1", 999)
        assert result is None
    
    def test_get_diff_between_versions(self):
        """Generate diff between two versions."""
        manager = ChainVersionManager()
        v1_data = {"name": "Test", "priority": "normal"}
        v2_data = {"name": "Test Updated", "priority": "high", "enabled": True}
        
        manager.save_version("chain_1", 1, v1_data)
        manager.save_version("chain_1", 2, v2_data)
        
        diff = manager.get_diff("chain_1", 1, 2)
        
        assert "added" in diff
        assert "enabled" in diff["added"]
        assert "modified" in diff
        assert "priority" in diff["modified"]


class TestBatchOperationManager:
    """Tests for BatchOperationManager."""
    
    @pytest.mark.asyncio
    async def test_queue_operations(self):
        """Queue multiple operations."""
        mock_storage = AsyncMock()
        manager = BatchOperationManager(mock_storage)
        
        await manager.add_batch_create("chain_1", {"name": "Test1"})
        await manager.add_batch_create("chain_2", {"name": "Test2"})
        
        assert len(manager.pending_ops) == 2
    
    @pytest.mark.asyncio
    async def test_commit_creates_chains(self):
        """Commit batch creates chains."""
        mock_storage = AsyncMock()
        mock_storage.async_create_chain = AsyncMock(return_value="chain_1")
        
        manager = BatchOperationManager(mock_storage)
        await manager.add_batch_create("chain_1", {"name": "Test"})
        
        success, msg = await manager.commit()
        
        assert success is True
        assert mock_storage.async_create_chain.called
    
    @pytest.mark.asyncio
    async def test_commit_clears_operations(self):
        """Commit clears pending operations."""
        mock_storage = AsyncMock()
        manager = BatchOperationManager(mock_storage)
        
        await manager.add_batch_create("chain_1", {"name": "Test"})
        await manager.commit()
        
        assert len(manager.pending_ops) == 0


class TestErrorRecoveryStrategy:
    """Tests for ErrorRecoveryStrategy."""
    
    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Successful execution returns success."""
        async def step_fn():
            return "success"
        
        strategy = ErrorRecoveryStrategy("no_op")
        success, msg = await strategy.execute_with_recovery(step_fn)
        
        assert success is True
        assert msg == "Success"
    
    @pytest.mark.asyncio
    async def test_failed_execution_no_rollback(self):
        """Failed execution without rollback."""
        async def step_fn():
            raise ValueError("Test error")
        
        strategy = ErrorRecoveryStrategy("no_op")
        success, msg = await strategy.execute_with_recovery(step_fn)
        
        assert success is False
        assert "Test error" in msg
    
    @pytest.mark.asyncio
    async def test_rollback_on_failure(self):
        """Rollback executes on failure."""
        rollback_called = []
        
        async def step_fn():
            raise ValueError("Test error")
        
        async def rollback_fn():
            rollback_called.append(True)
        
        strategy = ErrorRecoveryStrategy("rollback")
        success, msg = await strategy.execute_with_recovery(step_fn, rollback_fn)
        
        assert success is False
        assert len(rollback_called) == 1


class TestParallelChainExecutor:
    """Tests for ParallelChainExecutor."""
    
    @pytest.mark.asyncio
    async def test_detect_circular_dependency(self):
        """Detect circular dependencies in chain."""
        hass = MagicMock()
        executor = ParallelChainExecutor(hass)
        
        chain_data = {
            "steps": [
                {"id": "step_1", "depends_on": ["step_2"]},
                {"id": "step_2", "depends_on": ["step_1"]},
            ]
        }
        
        success, results = await executor.execute_parallel(chain_data)
        
        assert success is False
        assert "Circular" in results[0].get("error", "")
    
    @pytest.mark.asyncio
    async def test_empty_chain_execution(self):
        """Empty chain executes successfully."""
        hass = MagicMock()
        executor = ParallelChainExecutor(hass)
        
        chain_data = {"steps": []}
        
        success, results = await executor.execute_parallel(chain_data)
        
        assert success is True
        assert results == []


# WebSocket command tests
def test_ws_chain_get_version():
    """Test WebSocket chain/get_version command."""
    hass = MagicMock()
    connection = MagicMock(spec=websocket_api.ActiveConnection)
    
    mock_chains = MagicMock()
    mock_chains.get_version = MagicMock(return_value={"name": "Test"})
    
    msg = {
        "id": 1,
        "type": f"{DOMAIN}/chain/get_version",
        "chain_id": "chain_1",
        "version_num": 1,
    }
    
    with patch("custom_components.house_voice.websocket._get_chains", return_value=mock_chains):
        from custom_components.house_voice.websocket import ws_chain_get_version
        ws_chain_get_version(hass, connection, msg)
    
    connection.send_result.assert_called_once()


def test_ws_batch_start():
    """Test WebSocket batch/start command."""
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    connection = MagicMock(spec=websocket_api.ActiveConnection)
    
    msg = {
        "id": 1,
        "type": f"{DOMAIN}/batch/start",
    }
    
    from custom_components.house_voice.websocket import ws_batch_start
    ws_batch_start(hass, connection, msg)
    
    connection.send_result.assert_called_once()
    call_args = connection.send_result.call_args
    assert "batch_id" in call_args[0][1]


def test_ws_condition_test():
    """Test WebSocket condition/test command."""
    hass = MagicMock()
    connection = MagicMock(spec=websocket_api.ActiveConnection)
    
    msg = {
        "id": 1,
        "type": f"{DOMAIN}/condition/test",
        "expression": "True and True",
    }
    
    from custom_components.house_voice.websocket import ws_condition_test
    ws_condition_test(hass, connection, msg)
    
    connection.send_result.assert_called_once()
    call_args = connection.send_result.call_args
    assert call_args[0][1]["result"] is True


# Storage tests
@pytest.mark.asyncio
async def test_storage_save_version(hass: HomeAssistant):
    """Test saving chain version in storage."""
    from custom_components.house_voice.storage import HouseVoiceChains
    
    mock_store = MagicMock()
    mock_store.data = {}
    mock_store.async_save = AsyncMock()
    
    chains = HouseVoiceChains(hass, mock_store)
    
    await chains.async_save_version("chain_1", 1, {"name": "Test"})
    
    assert "versions_chain_1" in mock_store.data
    assert mock_store.async_save.called


@pytest.mark.asyncio
async def test_storage_list_versions(hass: HomeAssistant):
    """Test listing versions in storage."""
    from custom_components.house_voice.storage import HouseVoiceChains
    
    mock_store = MagicMock()
    mock_store.data = {
        "versions_chain_1": {
            "1": {"data": {"name": "Test1"}},
            "2": {"data": {"name": "Test2"}},
        }
    }
    
    chains = HouseVoiceChains(hass, mock_store)
    versions = chains.list_versions("chain_1")
    
    assert len(versions) == 2
    assert versions[0]["version"] == 1
    assert versions[1]["version"] == 2

