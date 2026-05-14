# VERSION = "2.2.0"
# File: groups.py
# Description: Speaker group management for House Voice Manager.
#              Groups are named collections of media_player entity IDs.
#              Events can target a group ID instead of individual speakers.

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_KEY_GROUPS, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


class HouseVoiceGroups:
    """Manages named speaker groups, persisted via HA Storage API."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY_GROUPS)
        self.data: dict[str, list[str]] = {}
        # data shape: { "group_id": ["media_player.stue", "media_player.kokken"] }

    async def async_load(self) -> dict[str, list[str]]:
        """Load groups from disk. Returns empty dict if no data exists."""
        raw = await self.store.async_load()
        self.data = raw if isinstance(raw, dict) else {}
        return self.data

    async def async_save(self) -> None:
        """Persist current group data to disk."""
        await self.store.async_save(self.data)

    async def add_group(self, group_id: str, speakers: list[str]) -> None:
        """Add or overwrite a speaker group and persist to disk."""
        self.data[group_id] = speakers
        await self.async_save()
        _LOGGER.info("House Voice: saved group '%s' with %d speakers", group_id, len(speakers))

    async def delete_group(self, group_id: str) -> None:
        """Delete a speaker group if it exists and persist to disk."""
        if group_id in self.data:
            del self.data[group_id]
            await self.async_save()
            _LOGGER.info("House Voice: deleted group '%s'", group_id)

    def get_group(self, group_id: str) -> list[str] | None:
        """Return speaker list for the given group ID, or None if not found."""
        return self.data.get(group_id)

    def resolve_speakers(self, speakers: list[str] | str) -> list[str]:
        """Resolve a speaker list, expanding any group IDs to their members.

        A value starting with 'group:' is treated as a group reference.
        Example: ['group:alle_rum', 'media_player.badevaerelse'] resolves to
                 all speakers in 'alle_rum' plus media_player.badevaerelse.
        Plain entity IDs are passed through unchanged.
        """
        if isinstance(speakers, str):
            speakers = [speakers]

        resolved: list[str] = []
        for s in speakers:
            if s.startswith("group:"):
                group_id = s[len("group:"):]
                members = self.get_group(group_id)
                if members:
                    resolved.extend(members)
                else:
                    _LOGGER.warning(
                        "House Voice: group '%s' not found, skipping", group_id
                    )
            else:
                resolved.append(s)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for s in resolved:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        return unique
