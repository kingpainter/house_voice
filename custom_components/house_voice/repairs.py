# VERSION = "2.0.0"
# File: repairs.py
# Description: Repairs support for House Voice Manager.
#              Creates a HA repair issue if script.ultra_tts is not found.

from __future__ import annotations

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

ISSUE_ULTRA_TTS_MISSING = "ultra_tts_missing"


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict | None,
) -> RepairsFlow:
    """Create a repair flow for the given issue."""
    return ConfirmRepairFlow()


def raise_issue_ultra_tts_missing(hass: HomeAssistant) -> None:
    """Create a repair issue if script.ultra_tts is not available."""
    from homeassistant.helpers import issue_registry as ir

    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_ULTRA_TTS_MISSING,
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_ULTRA_TTS_MISSING,
    )


def clear_issue_ultra_tts_missing(hass: HomeAssistant) -> None:
    """Remove the ultra_tts_missing repair issue."""
    from homeassistant.helpers import issue_registry as ir

    ir.async_delete_issue(hass, DOMAIN, ISSUE_ULTRA_TTS_MISSING)
