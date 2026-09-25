# VERSION = "3.6.0"
# File: storage.py
# Description: HA Storage API wrapper for House Voice Manager.
#              Persists voice events, groups and conditions.

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_CONDITIONS_KEY, STORAGE_KEY, STORAGE_VERSION
import time


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


class HouseVoiceConditions:
    """Storage wrapper for the condition library (house_voice_conditions).

    Each condition maps an ID to a label, entity_id and expected state:
    {
        "nogen_hjemme": {
            "label":     "Nogen er hjemme",
            "entity_id": "binary_sensor.nogen_hjemme",
            "state":     "on"
        }
    }
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store: Store = Store(hass, STORAGE_VERSION, STORAGE_CONDITIONS_KEY)
        self.data: dict[str, dict] = {}

    async def async_load(self) -> dict[str, dict]:
        """Load stored conditions from disk. Returns empty dict if no data exists."""
        data = await self.store.async_load()
        self.data = data if isinstance(data, dict) else {}
        return self.data

    async def async_save(self) -> None:
        """Persist current condition data to disk."""
        await self.store.async_save(self.data)

    async def add_condition(self, condition_id: str, condition_data: dict) -> None:
        """Add or overwrite a condition and persist to disk."""
        self.data[condition_id] = condition_data
        await self.async_save()

    async def delete_condition(self, condition_id: str) -> None:
        """Delete a condition if it exists and persist to disk."""
        if condition_id in self.data:
            del self.data[condition_id]
            await self.async_save()

    def get_condition(self, condition_id: str) -> dict | None:
        """Return condition data for the given ID, or None if not found."""
        return self.data.get(condition_id)


class HouseVoiceChains:
    """Storage wrapper for announcement chains.
    
    Chains are sequences of steps that execute in order, with conditional logic
    and retry capabilities. Each chain can be in draft, published, or active state.
    """
    
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store: Store = Store(hass, STORAGE_VERSION, "house_voice_chains")
        self.data: dict[str, dict] = {}
    
    async def async_load(self) -> dict[str, dict]:
        """Load stored chains from disk. Returns empty dict if no data exists."""
        data = await self.store.async_load()
        self.data = data if isinstance(data, dict) else {}
        return self.data
    
    async def async_save(self) -> None:
        """Persist current chain data to disk."""
        await self.store.async_save(self.data)
    
    async def async_create_chain(self, chain_data: dict) -> str:
        """Create a new chain and persist to disk. Returns chain_id."""
        from datetime import datetime, timezone
        
        chain_id = chain_data.get("id", f"chain_{len(self.data) + 1}")
        
        # Ensure required fields
        if not chain_data.get("name"):
            raise ValueError("Chain must have a name")
        if not chain_data.get("steps"):
            raise ValueError("Chain must have at least one step")
        
        # Set defaults
        now = datetime.now(timezone.utc).isoformat()
        chain_data["id"] = chain_id
        chain_data.setdefault("status", "draft")
        chain_data.setdefault("created", now)
        chain_data.setdefault("modified", now)
        chain_data.setdefault("execution_config", {
            "parallel": False,
            "timeout": 300,
            "on_failure": "stop"
        })
        
        self.data[chain_id] = chain_data
        await self.async_save()
        return chain_id
    
    async def async_update_chain(self, chain_id: str, chain_data: dict) -> bool:
        """Update existing chain and persist. Returns True if successful."""
        from datetime import datetime, timezone
        
        if chain_id not in self.data:
            return False
        
        # Update modified timestamp
        now = datetime.now(timezone.utc).isoformat()
        chain_data["modified"] = now
        chain_data["id"] = chain_id  # Ensure ID doesn't change
        
        self.data[chain_id] = chain_data
        await self.async_save()
        return True
    
    async def async_delete_chain(self, chain_id: str) -> bool:
        """Delete chain if it exists and persist. Returns True if successful."""
        if chain_id not in self.data:
            return False
        
        del self.data[chain_id]
        await self.async_save()
        return True
    
    def get_chain(self, chain_id: str) -> dict | None:
        """Return chain data for the given ID, or None if not found."""
        return self.data.get(chain_id)
    
    def list_chains(self, status: str | None = None) -> list[dict]:
        """Return list of chains, optionally filtered by status."""
        chains = list(self.data.values())
        if status:
            chains = [c for c in chains if c.get("status") == status]
        return chains
    
    async def async_publish_chain(self, chain_id: str) -> bool:
        """Move chain from draft to published status."""
        from datetime import datetime, timezone
        
        if chain_id not in self.data:
            return False
        
        now = datetime.now(timezone.utc).isoformat()
        self.data[chain_id]["status"] = "published"
        self.data[chain_id]["modified"] = now
        await self.async_save()
        return True
    
    async def async_activate_chain(self, chain_id: str) -> bool:
        """Move chain to active status (ready for execution)."""
        from datetime import datetime, timezone
        
        if chain_id not in self.data:
            return False
        
        now = datetime.now(timezone.utc).isoformat()
        self.data[chain_id]["status"] = "active"
        self.data[chain_id]["modified"] = now
        await self.async_save()
        return True
    
    async def async_save_version(self, chain_id: str, version: int, data: dict) -> None:
        """Save a specific version of a chain for versioning support."""
        version_key = f"versions_{chain_id}"
        
        if version_key not in self.data:
            self.data[version_key] = {}
        
        # Store version data with version number as key
        self.data[version_key][str(version)] = {"data": data}
        await self.async_save()
    
    def list_versions(self, chain_id: str) -> list[dict]:
        """Return list of versions for a given chain, sorted by version number."""
        version_key = f"versions_{chain_id}"
        
        if version_key not in self.data:
            return []
        
        versions_dict = self.data[version_key]
        versions = []
        
        for version_str, version_data in versions_dict.items():
            try:
                version_num = int(version_str)
                entry = {"version": version_num}
                entry.update(version_data.get("data", {}))
                versions.append(entry)
            except (ValueError, TypeError):
                # Skip invalid version keys
                continue
        
        # Sort by version number ascending
        versions.sort(key=lambda x: x["version"])
        return versions



# Sprint 6: Persistent Execution History
class HouseVoiceExecutionHistory:
    """Manage persistent execution history for chain executions via HA Storage API."""

    def __init__(self, hass: HomeAssistant):
        """Initialize execution history storage."""
        from homeassistant.helpers.storage import Store
        
        self.hass = hass
        self.store = Store(hass, version=1, key="house_voice_execution_history")
        self.data: dict[str, dict] = {}  # {exec_id: execution_record}

    async def async_load(self) -> dict[str, dict]:
        """Load execution history from disk. Returns empty dict if no data exists."""
        data = await self.store.async_load()
        self.data = data if isinstance(data, dict) else {}
        return self.data

    async def async_save(self) -> None:
        """Persist current execution history to disk."""
        await self.store.async_save(self.data)

    async def async_record_execution(self, execution_data: dict) -> str:
        """Record a chain execution. Returns execution_id."""
        import uuid
        from datetime import datetime, timezone

        exec_id = f"exec_{uuid.uuid4().hex[:8]}"
        
        # Ensure required fields
        if not execution_data.get("chain_id"):
            raise ValueError("Execution must reference a chain_id")
        
        # Set defaults
        now = datetime.now(timezone.utc).isoformat()
        execution_data["id"] = exec_id
        execution_data["started"] = execution_data.get("started", now)
        execution_data.setdefault("finished", None)
        execution_data.setdefault("status", "in_progress")
        execution_data.setdefault("steps", [])
        execution_data.setdefault("error", None)
        
        self.data[exec_id] = execution_data
        await self.async_save()
        return exec_id

    async def async_update_execution(self, exec_id: str, updates: dict) -> bool:
        """Update execution record (status, finished time, error, etc). Returns True if successful."""
        from datetime import datetime, timezone
        
        if exec_id not in self.data:
            return False
        
        # Auto-set finished time if status changed to terminal state
        if updates.get("status") in ("completed", "failed", "blocked_condition"):
            updates.setdefault("finished", datetime.now(timezone.utc).isoformat())
        
        self.data[exec_id].update(updates)
        await self.async_save()
        return True

    async def async_append_step_result(self, exec_id: str, step_result: dict) -> bool:
        """Append a step execution result to an execution record."""
        if exec_id not in self.data:
            return False
        
        if "steps" not in self.data[exec_id]:
            self.data[exec_id]["steps"] = []
        
        self.data[exec_id]["steps"].append(step_result)
        await self.async_save()
        return True

    def get_execution(self, exec_id: str) -> dict | None:
        """Return execution record for the given ID, or None if not found."""
        return self.data.get(exec_id)

    def list_executions(self, chain_id: str | None = None, limit: int = 50) -> list[dict]:
        """Return list of executions, optionally filtered by chain_id. Newest first."""
        executions = list(self.data.values())
        
        # Filter by chain_id if provided
        if chain_id:
            executions = [e for e in executions if e.get("chain_id") == chain_id]
        
        # Sort by started time (newest first)
        executions.sort(key=lambda e: e.get("started", ""), reverse=True)
        
        # Limit results
        return executions[:limit]

    async def async_prune_old_executions(self, keep_count: int = 1000) -> int:
        """Remove old execution records, keeping only the newest keep_count. Returns count deleted."""
        executions = list(self.data.values())
        
        # Sort by started time (oldest first)
        executions.sort(key=lambda e: e.get("started", ""))
        
        to_delete = executions[:-keep_count] if len(executions) > keep_count else []
        
        for exec_record in to_delete:
            if exec_record.get("id"):
                del self.data[exec_record["id"]]
        
        if to_delete:
            await self.async_save()
        
        return len(to_delete)

    # ============================================================================
    # PHASE 7: Chain Versioning
    # ============================================================================
    
    def get_version(self, chain_id: str, version_num: int) -> dict[str, Any] | None:
        """Retrieve a specific version of a chain."""
        versions = self.data.get(f"versions_{chain_id}", {})
        return versions.get(str(version_num))
    
    def list_versions(self, chain_id: str) -> list[dict[str, Any]]:
        """List all versions of a chain."""
        versions = self.data.get(f"versions_{chain_id}", {})
        return [
            {"version": int(v), "data": data}
            for v, data in sorted(versions.items())
        ]
    
    async def async_save_version(
        self,
        chain_id: str,
        version_num: int,
        chain_data: dict[str, Any]
    ) -> None:
        """Save a version snapshot of a chain."""
        versions_key = f"versions_{chain_id}"
        if versions_key not in self.data:
            self.data[versions_key] = {}
        
        self.data[versions_key][str(version_num)] = {
            "timestamp": time.time(),
            "data": chain_data.copy()
        }
        
        await self.store.async_save(self.data)
    
    async def async_rollback_to_version(
        self,
        chain_id: str,
        version_num: int
    ) -> bool:
        """Rollback a chain to a previous version."""
        version_data = self.get_version(chain_id, version_num)
        if not version_data:
            return False
        
        # Restore the chain data
        await self.async_update_chain(chain_id, version_data.get("data", {}))
        return True

