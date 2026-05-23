# VERSION = "3.1.1"
# File: storage.py
# Description: HA Storage API wrapper for House Voice Manager.
#              Persists voice events to .storage/house_voice_events.

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION


class HouseVoiceStorage:
    """Thin wrapper around HA's Storage API for voice event persistence."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, dict] = {}

    async def async_load(self) -> dict[str, dict]:
        """Load stored events from disk. Returns empty dict if no data exists."""
        data = await self.store.async_load()
        self.data = data if isinstance(data, dict) else {}
        return self.data

    async def async_save(self) -> None:
        """Persist current event data to disk."""
        await self.store.async_save(self.data)

    async def add_event(self, event_id: str, event_data: dict) -> None:
        """Add or overwrite a voice event and persist to disk."""
        self.data[event_id] = event_data
        await self.async_save()

    async def delete_event(self, event_id: str) -> None:
        """Delete a voice event if it exists and persist to disk."""
        if event_id in self.data:
            del self.data[event_id]
            await self.async_save()

    def get_event(self, event_id: str) -> dict | None:
        """Return event data for the given ID, or None if not found."""
        return self.data.get(event_id)
