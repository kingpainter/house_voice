"""Tests for House Voice Manager repairs."""

from unittest.mock import MagicMock, patch
import pytest

from custom_components.house_voice.const import DOMAIN
from custom_components.house_voice.repairs import (
    ISSUE_ULTRA_TTS_MISSING,
    raise_issue_ultra_tts_missing,
    clear_issue_ultra_tts_missing,
    async_create_fix_flow,
)


def test_raise_issue_ultra_tts_missing(mock_hass):
    """raise_issue_ultra_tts_missing calls ir.async_create_issue."""
    with patch("custom_components.house_voice.repairs.ir") as mock_ir:
        raise_issue_ultra_tts_missing(mock_hass)

    mock_ir.async_create_issue.assert_called_once()
    call_kwargs = mock_ir.async_create_issue.call_args
    assert call_kwargs[0][1] == DOMAIN
    assert call_kwargs[0][2] == ISSUE_ULTRA_TTS_MISSING
    assert call_kwargs[1]["severity"] == mock_ir.IssueSeverity.ERROR
    assert call_kwargs[1]["is_fixable"] is False


def test_clear_issue_ultra_tts_missing(mock_hass):
    """clear_issue_ultra_tts_missing calls ir.async_delete_issue."""
    with patch("custom_components.house_voice.repairs.ir") as mock_ir:
        clear_issue_ultra_tts_missing(mock_hass)

    mock_ir.async_delete_issue.assert_called_once_with(
        mock_hass, DOMAIN, ISSUE_ULTRA_TTS_MISSING
    )


@pytest.mark.asyncio
async def test_async_create_fix_flow_returns_flow(mock_hass):
    """async_create_fix_flow returns a ConfirmRepairFlow."""
    from homeassistant.components.repairs import ConfirmRepairFlow

    flow = await async_create_fix_flow(mock_hass, ISSUE_ULTRA_TTS_MISSING, None)
    assert isinstance(flow, ConfirmRepairFlow)


@pytest.mark.asyncio
async def test_async_create_fix_flow_unknown_issue(mock_hass):
    """async_create_fix_flow returns ConfirmRepairFlow for any issue_id."""
    from homeassistant.components.repairs import ConfirmRepairFlow

    flow = await async_create_fix_flow(mock_hass, "some_other_issue", None)
    assert isinstance(flow, ConfirmRepairFlow)
