# VERSION = "3.6.0"
# File: test_chain_commands.py
# Description: Comprehensive tests for Phase 5 chain WebSocket commands.
#              Tests all 7 commands: create, update, delete, get, list, publish, validate

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.components import websocket_api
from custom_components.house_voice.const import DOMAIN
from custom_components.house_voice.storage import HouseVoiceChains
from custom_components.house_voice.chain_validator import ChainValidator


@pytest.fixture
def mock_chains():
    """Fixture for HouseVoiceChains mock."""
    chains = MagicMock(spec=HouseVoiceChains)
    chains.data = {}
    chains.async_load = AsyncMock(return_value={})
    chains.async_create_chain = AsyncMock(return_value="chain_1")
    chains.async_update_chain = AsyncMock(return_value=True)
    chains.async_delete_chain = AsyncMock(return_value=True)
    chains.get_chain = MagicMock(return_value={
        "id": "chain_1",
        "name": "Test Chain",
        "status": "draft",
        "steps": [{"type": "tts", "text": "Hello"}]
    })
    chains.list_chains = MagicMock(return_value=[
        {"id": "chain_1", "name": "Test Chain", "status": "draft"}
    ])
    chains.async_publish_chain = AsyncMock(return_value=True)
    return chains


@pytest.fixture
def mock_validator():
    """Fixture for ChainValidator mock."""
    validator = MagicMock(spec=ChainValidator)
    validator.validate_chain = MagicMock(return_value=MagicMock(
        is_valid=True,
        to_dict=MagicMock(return_value={})
    ))
    return validator


@pytest.mark.asyncio
async def test_ws_chain_create(hass: HomeAssistant, mock_chains, mock_validator):
    """Test chain/create command."""
    msg = {
        "id": 1,
        "type": f"{DOMAIN}/chain/create",
        "name": "Test Chain",
        "steps": [{"type": "tts", "text": "Hello"}]
    }
    
    connection = MagicMock(spec=websocket_api.ActiveConnection)
    
    with patch("custom_components.house_voice.websocket._get_chains", return_value=mock_chains), \
         patch("custom_components.house_voice.websocket._get_chain_validator", return_value=mock_validator):
        from custom_components.house_voice.websocket import ws_chain_create
        await ws_chain_create(hass, connection, msg)
    
    connection.send_result.assert_called_once()
    call_args = connection.send_result.call_args
    assert call_args[0][1]["chain_id"] == "chain_1"


@pytest.mark.asyncio
async def test_ws_chain_update(hass: HomeAssistant, mock_chains, mock_validator):
    """Test chain/update command."""
    msg = {
        "id": 2,
        "type": f"{DOMAIN}/chain/update",
        "chain_id": "chain_1",
        "chain_data": {"name": "Updated", "steps": []}
    }
    
    connection = MagicMock(spec=websocket_api.ActiveConnection)
    
    with patch("custom_components.house_voice.websocket._get_chains", return_value=mock_chains), \
         patch("custom_components.house_voice.websocket._get_chain_validator", return_value=mock_validator):
        from custom_components.house_voice.websocket import ws_chain_update
        await ws_chain_update(hass, connection, msg)
    
    connection.send_result.assert_called_once()


@pytest.mark.asyncio
async def test_ws_chain_delete(hass: HomeAssistant, mock_chains):
    """Test chain/delete command."""
    msg = {
        "id": 3,
        "type": f"{DOMAIN}/chain/delete",
        "chain_id": "chain_1"
    }
    
    connection = MagicMock(spec=websocket_api.ActiveConnection)
    
    with patch("custom_components.house_voice.websocket._get_chains", return_value=mock_chains):
        from custom_components.house_voice.websocket import ws_chain_delete
        await ws_chain_delete(hass, connection, msg)
    
    connection.send_result.assert_called_once()


def test_ws_chain_get(hass: HomeAssistant, mock_chains):
    """Test chain/get command."""
    msg = {
        "id": 4,
        "type": f"{DOMAIN}/chain/get",
        "chain_id": "chain_1"
    }
    
    connection = MagicMock(spec=websocket_api.ActiveConnection)
    
    with patch("custom_components.house_voice.websocket._get_chains", return_value=mock_chains):
        from custom_components.house_voice.websocket import ws_chain_get
        ws_chain_get(hass, connection, msg)
    
    connection.send_result.assert_called_once()
    call_args = connection.send_result.call_args
    assert "chain" in call_args[0][1]


def test_ws_list_chains(hass: HomeAssistant, mock_chains):
    """Test list_chains command."""
    msg = {
        "id": 5,
        "type": f"{DOMAIN}/list_chains"
    }
    
    connection = MagicMock(spec=websocket_api.ActiveConnection)
    
    with patch("custom_components.house_voice.websocket._get_chains", return_value=mock_chains):
        from custom_components.house_voice.websocket import ws_list_chains
        ws_list_chains(hass, connection, msg)
    
    connection.send_result.assert_called_once()
    call_args = connection.send_result.call_args
    assert "chains" in call_args[0][1]


@pytest.mark.asyncio
async def test_ws_chain_publish(hass: HomeAssistant, mock_chains):
    """Test chain/publish command."""
    msg = {
        "id": 6,
        "type": f"{DOMAIN}/chain/publish",
        "chain_id": "chain_1"
    }
    
    connection = MagicMock(spec=websocket_api.ActiveConnection)
    
    with patch("custom_components.house_voice.websocket._get_chains", return_value=mock_chains):
        from custom_components.house_voice.websocket import ws_chain_publish
        await ws_chain_publish(hass, connection, msg)
    
    connection.send_result.assert_called_once()


def test_ws_chain_validate(hass: HomeAssistant, mock_validator):
    """Test chain/validate command."""
    msg = {
        "id": 7,
        "type": f"{DOMAIN}/chain/validate",
        "chain_data": {"name": "Test", "steps": []}
    }
    
    connection = MagicMock(spec=websocket_api.ActiveConnection)
    
    with patch("custom_components.house_voice.websocket._get_chain_validator", return_value=mock_validator):
        from custom_components.house_voice.websocket import ws_chain_validate
        ws_chain_validate(hass, connection, msg)
    
    connection.send_result.assert_called_once()


@pytest.mark.asyncio
async def test_ws_chain_create_not_ready(hass: HomeAssistant):
    """Test chain/create when chains not ready."""
    msg = {
        "id": 8,
        "type": f"{DOMAIN}/chain/create",
        "name": "Test"
    }
    
    connection = MagicMock(spec=websocket_api.ActiveConnection)
    
    with patch("custom_components.house_voice.websocket._get_chains", return_value=None),          patch("custom_components.house_voice.websocket._get_chain_validator", return_value=None):
        from custom_components.house_voice.websocket import ws_chain_create
        await ws_chain_create(hass, connection, msg)
    
    connection.send_error.assert_called_once()


def test_ws_chain_get_not_found(hass: HomeAssistant):
    """Test chain/get with non-existent chain."""
    msg = {
        "id": 9,
        "type": f"{DOMAIN}/chain/get",
        "chain_id": "nonexistent"
    }
    
    connection = MagicMock(spec=websocket_api.ActiveConnection)
    mock_chains = MagicMock()
    mock_chains.get_chain = MagicMock(return_value=None)
    
    with patch("custom_components.house_voice.websocket._get_chains", return_value=mock_chains):
        from custom_components.house_voice.websocket import ws_chain_get
        ws_chain_get(hass, connection, msg)
    
    connection.send_error.assert_called_once()


@pytest.mark.asyncio
async def test_ws_chain_validate_invalid(hass: HomeAssistant):
    """Test chain/validate with invalid chain."""
    msg = {
        "id": 10,
        "type": f"{DOMAIN}/chain/validate",
        "chain_data": {"name": ""}  # Invalid: empty name
    }
    
    connection = MagicMock(spec=websocket_api.ActiveConnection)
    mock_validator = MagicMock()
    mock_validator.validate_chain = MagicMock(return_value=MagicMock(
        is_valid=False,
        to_dict=MagicMock(return_value={"errors": ["Name required"]})
    ))
    
    with patch("custom_components.house_voice.websocket._get_chain_validator", return_value=mock_validator):
        from custom_components.house_voice.websocket import ws_chain_validate
        ws_chain_validate(hass, connection, msg)
    
    connection.send_error.assert_called_once()


