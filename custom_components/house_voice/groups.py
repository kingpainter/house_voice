# VERSION = "2.2.0"
# File: groups.py
# Description: Speaker group storage for House Voice Manager.
#              Groups map a friendly name to a list of media_player entity IDs.
#              Events can reference a group ID instead of individual speakers.

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_GROUPS_KEY, STORAGE_VERSION


class HouseVoiceGroups:
    """Storage wrapper for speaker groups."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store: Store = Store(hass, STORAGE_VERSION, STORAGE_GROUPS_KEY)
        self.data: dict[str, dict] = {}
        # data format:
        # {
        #   "alle_rum": {
        #       "name": "Alle rum",
        #       "speakers": ["media_player.stue", "media_player.kokken"]
        #   }
        # }

    async def async_load(self) -> dict[str, dict]:
        """Load groups from disk. Returns empty dict if no data exists."""
        data = await self.store.async_load()
        self.data = data if isinstance(data, dict) else {}
        return self.data

    async def async_save(self) -> None:
        """Persist current group data to disk."""
        await self.store.async_save(self.data)

    async def add_group(self, group_id: str, group_data: dict) -> None:
        """Add or overwrite a speaker group and persist to disk."""
        self.data[group_id] = group_data
        await self.async_save()

    async def delete_group(self, group_id: str) -> None:
        """Delete a speaker group if it exists and persist to disk."""
        if group_id in self.data:
            del self.data[group_id]
            await self.async_save()

    def get_group(self, group_id: str) -> dict | None:
        """Return group data for the given ID, or None if not found."""
        return self.data.get(group_id)

    def resolve_speakers(self, speakers: list[str]) -> list[str]:
        """Resolve a list of speaker IDs, expanding any group references.

        A speaker entry starting with 'group:' is treated as a group reference.
        Example: ['group:alle_rum', 'media_player.badevaerelse']
        Returns a flat, deduplicated list of media_player entity IDs.
        """
        resolved: list[str] = []
        seen: set[str] = set()

        for entry in speakers:
            if entry.startswith("group:"):
                group_id = entry[len("group:"):]
                group = self.get_group(group_id)
                if group:
                    for sp in group.get("speakers", []):
                        if sp not in seen:
                            resolved.append(sp)
                            seen.add(sp)
            else:
                if entry not in seen:
                    resolved.append(entry)
                    seen.add(entry)

        return resolved
