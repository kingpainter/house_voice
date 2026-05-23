"""Tests for HouseVoiceGroups – storage and speaker resolution."""

import pytest
from unittest.mock import AsyncMock

from custom_components.house_voice.groups import HouseVoiceGroups


# ── async_load ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_load_empty(mock_groups):
    """Loading with no stored data returns empty dict."""
    result = await mock_groups.async_load()
    assert result == {}
    assert mock_groups.data == {}


@pytest.mark.asyncio
async def test_load_existing(mock_groups):
    """Loading with existing data populates .data."""
    mock_groups.store.async_load = AsyncMock(return_value={
        "alle_rum": {"name": "Alle rum", "speakers": ["media_player.stue"]}
    })
    result = await mock_groups.async_load()
    assert "alle_rum" in result
    assert result["alle_rum"]["name"] == "Alle rum"


# ── add_group / delete_group ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_group_stores_and_saves(mock_groups):
    """add_group persists the group and calls async_save."""
    await mock_groups.add_group("koekken", {"name": "Køkken", "speakers": ["media_player.kokken"]})
    assert "koekken" in mock_groups.data
    assert mock_groups.data["koekken"]["name"] == "Køkken"
    mock_groups.store.async_save.assert_called_once()


@pytest.mark.asyncio
async def test_add_group_overwrites(mock_groups):
    """add_group overwrites an existing group with same ID."""
    await mock_groups.add_group("g1", {"name": "Gammel", "speakers": ["media_player.a"]})
    await mock_groups.add_group("g1", {"name": "Ny", "speakers": ["media_player.b"]})
    assert mock_groups.data["g1"]["name"] == "Ny"


@pytest.mark.asyncio
async def test_delete_group_removes_and_saves(mock_groups):
    """delete_group removes the group and calls async_save."""
    mock_groups.data["g1"] = {"name": "Test", "speakers": ["media_player.a"]}
    await mock_groups.delete_group("g1")
    assert "g1" not in mock_groups.data
    mock_groups.store.async_save.assert_called_once()


@pytest.mark.asyncio
async def test_delete_group_nonexistent_silent(mock_groups):
    """delete_group on unknown ID does nothing and does not save."""
    await mock_groups.delete_group("does_not_exist")
    mock_groups.store.async_save.assert_not_called()


# ── get_group ──────────────────────────────────────────────────────────────────

def test_get_group_known(mock_groups):
    """get_group returns data for known ID."""
    mock_groups.data["g1"] = {"name": "Test", "speakers": ["media_player.a"]}
    result = mock_groups.get_group("g1")
    assert result["name"] == "Test"


def test_get_group_unknown(mock_groups):
    """get_group returns None for unknown ID."""
    assert mock_groups.get_group("unknown") is None


# ── resolve_speakers ───────────────────────────────────────────────────────────

def test_resolve_plain_speakers(mock_groups):
    """Plain entity IDs are returned unchanged."""
    result = mock_groups.resolve_speakers(["media_player.stue", "media_player.kokken"])
    assert result == ["media_player.stue", "media_player.kokken"]


def test_resolve_group_reference(mock_groups):
    """group:<id> is expanded to the group's speaker list."""
    mock_groups.data["alle_rum"] = {
        "name": "Alle rum",
        "speakers": ["media_player.stue", "media_player.kokken"],
    }
    result = mock_groups.resolve_speakers(["group:alle_rum"])
    assert result == ["media_player.stue", "media_player.kokken"]


def test_resolve_mixed_group_and_plain(mock_groups):
    """Mix of group reference and plain entity ID is deduplicated correctly."""
    mock_groups.data["stue_gruppe"] = {
        "name": "Stue",
        "speakers": ["media_player.stue"],
    }
    result = mock_groups.resolve_speakers(["group:stue_gruppe", "media_player.stue", "media_player.bad"])
    assert result == ["media_player.stue", "media_player.bad"]


def test_resolve_unknown_group_skipped(mock_groups):
    """Unknown group references are silently skipped."""
    result = mock_groups.resolve_speakers(["group:findesikke", "media_player.stue"])
    assert result == ["media_player.stue"]


def test_resolve_deduplication(mock_groups):
    """Duplicate speaker IDs are deduplicated."""
    result = mock_groups.resolve_speakers(["media_player.a", "media_player.a", "media_player.b"])
    assert result == ["media_player.a", "media_player.b"]


def test_resolve_empty_list(mock_groups):
    """Empty input returns empty list."""
    assert mock_groups.resolve_speakers([]) == []
