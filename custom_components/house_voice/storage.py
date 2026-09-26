# VERSION = "3.12.0"
# File: storage.py
# Description: HA Storage API wrapper for House Voice Manager.
#              Persists voice events, groups and conditions.

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_CONDITIONS_KEY, STORAGE_KEY, STORAGE_VERSION
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
    def get_statistics(self, chain_id: str | None = None, start_date: str | None = None, end_date: str | None = None) -> dict:
        """Return aggregated statistics for executions.
        
        Args:
            chain_id: Optional chain ID to filter by
            start_date: Optional ISO date string to filter from
            end_date: Optional ISO date string to filter to
            
        Returns:
            dict with: total_executions, success_count, failed_count, success_rate, avg_duration_seconds
        """
        from datetime import datetime
        
        executions = list(self.data.values())
        
        # Filter by chain_id if provided
        if chain_id:
            executions = [e for e in executions if e.get("chain_id") == chain_id]
        
        # Filter by date range if provided
        if start_date:
            executions = [e for e in executions if e.get("started", "") >= start_date]
        if end_date:
            executions = [e for e in executions if e.get("started", "") <= end_date]
        
        # Only count completed/failed executions (not in_progress)
        completed = [e for e in executions if e.get("status") in ("completed", "failed", "blocked_condition")]
        successful = [e for e in completed if e.get("status") == "completed"]
        failed = [e for e in completed if e.get("status") in ("failed", "blocked_condition")]
        
        # Calculate average duration
        durations = []
        for exec_record in completed:
            started = exec_record.get("started")
            finished = exec_record.get("finished")
            if started and finished:
                try:
                    start_dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
                    finish_dt = datetime.fromisoformat(finished.replace('Z', '+00:00'))
                    duration_seconds = (finish_dt - start_dt).total_seconds()
                    if duration_seconds >= 0:
                        durations.append(duration_seconds)
                except (ValueError, AttributeError):
                    pass
        
        avg_duration = sum(durations) / len(durations) if durations else 0
        total = len(completed)
        success_rate = (len(successful) / total * 100) if total > 0 else 0
        
        return {
            "total_executions": total,
            "success_count": len(successful),
            "failed_executions": len(failed),
            "success_rate": round(success_rate, 1),
            "avg_duration_seconds": round(avg_duration, 2),
        }

    def get_chain_performance(self, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
        """Return per-chain performance metrics.
        
        Returns list of dicts with: chain_id, chain_name, executions, success_rate, avg_duration_seconds
        """
        from datetime import datetime
        
        executions = list(self.data.values())
        
        # Filter by date range
        if start_date:
            executions = [e for e in executions if e.get("started", "") >= start_date]
        if end_date:
            executions = [e for e in executions if e.get("started", "") <= end_date]
        
        # Group by chain_id
        chains_data = {}
        for exec_record in executions:
            if exec_record.get("status") not in ("completed", "failed", "blocked_condition"):
                continue
            
            chain_id = exec_record.get("chain_id", "unknown")
            if chain_id not in chains_data:
                chains_data[chain_id] = {
                    "total": 0,
                    "successful": 0,
                    "durations": [],
                }
            
            chains_data[chain_id]["total"] += 1
            if exec_record.get("status") == "completed":
                chains_data[chain_id]["successful"] += 1
            
            # Calculate duration
            started = exec_record.get("started")
            finished = exec_record.get("finished")
            if started and finished:
                try:
                    start_dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
                    finish_dt = datetime.fromisoformat(finished.replace('Z', '+00:00'))
                    duration_seconds = (finish_dt - start_dt).total_seconds()
                    if duration_seconds >= 0:
                        chains_data[chain_id]["durations"].append(duration_seconds)
                except (ValueError, AttributeError):
                    pass
        
        # Build result list
        result = []
        for chain_id, data in chains_data.items():
            success_rate = (data["successful"] / data["total"] * 100) if data["total"] > 0 else 0
            avg_duration = sum(data["durations"]) / len(data["durations"]) if data["durations"] else 0
            
            # Get chain name from chains storage if available
            chain_name = chain_id  # Use chain_id directly (chains feature removed)
            
            result.append({
                "chain_id": chain_id,
                "chain_name": chain_name,  # ← Now resolves from chains storage
                "executions": data["total"],
                "success_rate": round(success_rate, 1),
                "avg_duration_seconds": round(avg_duration, 2),
            })
        
        # Sort by avg_duration (slowest first)
        result.sort(key=lambda x: x["avg_duration_seconds"], reverse=True)
        
        return result

    def get_step_analytics(self, start_date: str | None = None, end_date: str | None = None) -> dict:
        """Return step-level analytics: top failing, slowest, most-used steps.
        
        Returns dict with: top_failing_steps, slowest_steps, most_used_steps, step_type_distribution
        """
        from datetime import datetime
        from collections import Counter
        
        executions = list(self.data.values())
        
        # Filter by date range
        if start_date:
            executions = [e for e in executions if e.get("started", "") >= start_date]
        if end_date:
            executions = [e for e in executions if e.get("started", "") <= end_date]
        
        step_stats = {}  # {step_name: {total: N, failed: N, durations: [...]}}
        step_types = Counter()
        
        for exec_record in executions:
            steps = exec_record.get("steps", [])
            for step in steps:
                step_name = step.get("name", "unknown")
                step_type = step.get("type", "unknown")
                step_status = step.get("status", "unknown")
                step_duration = step.get("duration", 0)
                
                if step_name not in step_stats:
                    step_stats[step_name] = {"total": 0, "failed": 0, "durations": []}
                
                step_stats[step_name]["total"] += 1
                if step_status in ("failed", "error"):
                    step_stats[step_name]["failed"] += 1
                if isinstance(step_duration, (int, float)) and step_duration >= 0:
                    step_stats[step_name]["durations"].append(step_duration)
                
                step_types[step_type] += 1
        
        # Top failing steps
        top_failing = []
        for step_name, stats in step_stats.items():
            if stats["total"] > 0:
                failure_rate = (stats["failed"] / stats["total"] * 100)
                if stats["failed"] > 0:  # Only include steps that have failed at least once
                    top_failing.append({
                        "name": step_name,
                        "failures": stats["failed"],
                        "failure_rate": round(failure_rate, 1),
                    })
        top_failing.sort(key=lambda x: x["failures"], reverse=True)
        
        # Slowest steps
        slowest = []
        for step_name, stats in step_stats.items():
            if stats["durations"]:
                avg_duration = sum(stats["durations"]) / len(stats["durations"])
                slowest.append({
                    "name": step_name,
                    "avg_duration": round(avg_duration, 2),
                    "executions": len(stats["durations"]),
                })
        slowest.sort(key=lambda x: x["avg_duration"], reverse=True)
        
        # Most used steps
        most_used = []
        for step_name, stats in step_stats.items():
            most_used.append({
                "name": step_name,
                "executions": stats["total"],
            })
        most_used.sort(key=lambda x: x["executions"], reverse=True)
        
        return {
            "top_failing_steps": top_failing[:10],
            "slowest_steps": slowest[:10],
            "most_used_steps": most_used[:10],
            "step_type_distribution": dict(step_types),
        }

    def get_timeline(self, chain_id: str | None = None, limit: int = 50) -> list[dict]:
        """Return ordered timeline data for visualization (Gantt chart).
        
        Returns list of execution records sorted by start time (newest first), with calculated duration.
        """
        from datetime import datetime
        
        executions = list(self.data.values())
        
        # Filter by chain_id if provided
        if chain_id:
            executions = [e for e in executions if e.get("chain_id") == chain_id]
        
        # Only include completed/failed executions (not in_progress)
        executions = [e for e in executions if e.get("status") in ("completed", "failed", "blocked_condition")]
        
        # Sort by started time (newest first)
        executions.sort(key=lambda e: e.get("started", ""), reverse=True)
        
        # Calculate duration and format for timeline
        timeline = []
        for exec_record in executions[:limit]:
            started = exec_record.get("started")
            finished = exec_record.get("finished")
            duration = 0
            
            if started and finished:
                try:
                    start_dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
                    finish_dt = datetime.fromisoformat(finished.replace('Z', '+00:00'))
                    duration = (finish_dt - start_dt).total_seconds()
                except (ValueError, AttributeError):
                    pass
            
            timeline.append({
                "id": exec_record.get("id"),
                "chain_id": exec_record.get("chain_id"),
                "started": started,
                "finished": finished,
                "duration_seconds": round(duration, 2),
                "status": exec_record.get("status"),
                "step_count": len(exec_record.get("steps", [])),
            })
        
        return timeline


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

    
    def list_executions_filtered(
        self,
        chain_id: str | None = None,
        status: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 50,
        search_text: str | None = None
    ) -> list[dict]:
        """Return filtered list of executions with optional full-text search.
        
        Args:
            chain_id: Filter by specific chain ID
            status: Filter by execution status
            start_date: Filter by start date (ISO format)
            end_date: Filter by end date (ISO format)
            limit: Maximum number of results to return
            search_text: Search in step names and error messages
        
        Returns:
            List of execution records matching filters, newest first.
        """
        results = list(self.data.values())
        
        # Filter by chain_id
        if chain_id:
            results = [e for e in results if e.get("chain_id") == chain_id]
        
        # Filter by status
        if status:
            results = [e for e in results if e.get("status") == status]
        
        # Filter by date range
        if start_date:
            results = [e for e in results if e.get("started", "") >= start_date]
        if end_date:
            results = [e for e in results if e.get("started", "") <= end_date]
        
        # Full-text search in steps
        if search_text:
            search_lower = search_text.lower()
            filtered = []
            for e in results:
                # Search in step IDs and error messages
                found = False
                for step in e.get("steps", []):
                    if (search_lower in step.get("id", "").lower() or
                        search_lower in step.get("error", "").lower()):
                        found = True
                        break
                if found or search_lower in e.get("error", "").lower():
                    filtered.append(e)
            results = filtered
        
        # Sort by started time (newest first)
        results.sort(key=lambda e: e.get("started", ""), reverse=True)
        
        # Limit results
        return results[:limit]
    
    def get_execution_detail(self, exec_id: str) -> dict | None:
        """Return full execution record with all step details and timing info."""
        execution = self.data.get(exec_id)
        if not execution:
            return None
        
        # Calculate total duration if finished
        if execution.get("finished") and execution.get("started"):
            from datetime import datetime
            try:
                started = datetime.fromisoformat(execution["started"])
                finished = datetime.fromisoformat(execution["finished"])
                duration = (finished - started).total_seconds()
                execution["duration_seconds"] = duration
            except (ValueError, TypeError):
                execution["duration_seconds"] = None
        
        return execution
    
    def list_execution_summary(self, chain_id: str | None = None, limit: int = 50) -> list[dict]:
        """Return minimal execution summary (for table display).
        
        Each record contains: id, chain_id, status, started, step_count.
        """
        executions = list(self.data.values())
        
        if chain_id:
            executions = [e for e in executions if e.get("chain_id") == chain_id]
        
        # Sort by started time (newest first)
        executions.sort(key=lambda e: e.get("started", ""), reverse=True)
        
        # Return summary fields only
        summary = []
        for e in executions[:limit]:
            summary.append({
                "id": e.get("id"),
                "chain_id": e.get("chain_id"),
                "status": e.get("status"),
                "started": e.get("started"),
                "finished": e.get("finished"),
                "step_count": len(e.get("steps", [])),
                "error": e.get("error"),
            })
        
        return summary
