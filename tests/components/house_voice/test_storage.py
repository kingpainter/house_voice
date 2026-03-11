"""Tests for HouseVoiceStorage."""

import pytest

from custom_components.house_voice.storage import HouseVoiceStorage


@pytest.mark.asyncio
async def test_load_empty_storage(mock_storage):
    """Storage returns empty dict when no data exists."""
    result = await mock_storage.async_load()
    assert result == {}
    assert mock_storage.data == {}


@pytest.mark.asyncio
async def test_load_existing_data(mock_storage, sample_event):
    """Storage loads existing data correctly."""
    mock_storage.store.async_load.return_value = {"test_event": sample_event}
    result = await mock_storage.async_load()
    assert "test_event" in result
    assert result["test_event"]["message"] == "Opvaskeren er færdig"


@pytest.mark.asyncio
async def test_add_event(mock_storage, sample_event):
    """Adding an event stores it and saves."""
    await mock_storage.add_event("dishwasher_done", sample_event)
    assert "dishwasher_done" in mock_storage.data
    assert mock_storage.data["dishwasher_done"]["message"] == "Opvaskeren er færdig"
    mock_storage.store.async_save.assert_called_once()


@pytest.mark.asyncio
async def test_add_event_overwrites_existing(mock_storage, sample_event):
    """Adding an event with existing ID overwrites it."""
    await mock_storage.add_event("ev1", sample_event)
    updated = {**sample_event, "message": "Opdateret besked"}
    await mock_storage.add_event("ev1", updated)
    assert mock_storage.data["ev1"]["message"] == "Opdateret besked"


@pytest.mark.asyncio
async def test_delete_event(mock_storage, sample_event):
    """Deleting an existing event removes it and saves."""
    mock_storage.data["ev1"] = sample_event
    await mock_storage.delete_event("ev1")
    assert "ev1" not in mock_storage.data
    mock_storage.store.async_save.assert_called_once()


@pytest.mark.asyncio
async def test_delete_nonexistent_event(mock_storage):
    """Deleting a non-existent event does not raise and does not save."""
    await mock_storage.delete_event("does_not_exist")
    mock_storage.store.async_save.assert_not_called()


def test_get_event(mock_storage, sample_event):
    """get_event returns event data for known ID."""
    mock_storage.data["ev1"] = sample_event
    result = mock_storage.get_event("ev1")
    assert result == sample_event


def test_get_event_missing(mock_storage):
    """get_event returns None for unknown ID."""
    result = mock_storage.get_event("unknown")
    assert result is None
