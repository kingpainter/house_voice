# VERSION 3.13.0
"""House Voice Analytics Engine — Phase 9 Advanced Analytics Dashboard."""

from datetime import datetime, timedelta
from collections import defaultdict
from typing import Any
import statistics
import logging
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HouseVoiceAnalytics:
    """Advanced analytics and statistics for execution history."""

    def __init__(self, execution_history):
        """Initialize analytics engine with execution history reference."""
        self.execution_history = execution_history

    def get_statistics(self, start_date=None, end_date=None, chain_id=None):
        """
        Generate comprehensive statistics for filtered executions.

        Args:
            start_date: ISO string or None (all data)
            end_date: ISO string or None (all data)
            chain_id: Filter to single chain or None (all chains)

        Returns:
            dict with:
                - total_executions: int
                - success_rate: float (0-100)
                - failed_executions: int
                - avg_duration_seconds: float
                - min_duration_seconds: float
                - max_duration_seconds: float
                - step_type_distribution: dict[step_type -> count]
                - execution_trend: list of {date, count, success_rate}
        """
        executions = self.execution_history.list_executions_filtered(
            chain_id=chain_id,
            status=None,
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )

        if not executions:
            return {
                "total_executions": 0,
                "success_rate": 0,
                "failed_executions": 0,
                "avg_duration_seconds": 0,
                "min_duration_seconds": 0,
                "max_duration_seconds": 0,
                "step_type_distribution": {},
                "execution_trend": []
            }

        # Basic counts
        total = len(executions)
        failed = sum(1 for e in executions if e.get("status") == "failed")
        success_rate = ((total - failed) / total * 100) if total > 0 else 0

        # Duration stats
        durations = [
            (datetime.fromisoformat(e.get("finished", e.get("started"))) -
             datetime.fromisoformat(e.get("started")))
            .total_seconds()
            for e in executions
            if e.get("started") and e.get("finished")
        ]

        avg_duration = statistics.mean(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        max_duration = max(durations) if durations else 0

        # Step type distribution
        step_types = defaultdict(int)
        for execution in executions:
            for step in execution.get("steps", []):
                step_type = step.get("type", "unknown")
                step_types[step_type] += 1

        # Execution trend (per day)
        trend_by_date = defaultdict(lambda: {"count": 0, "success": 0})
        for e in executions:
            try:
                date_key = datetime.fromisoformat(e.get("started")).date().isoformat()
                trend_by_date[date_key]["count"] += 1
                if e.get("status") != "failed":
                    trend_by_date[date_key]["success"] += 1
            except (ValueError, TypeError):
                pass

        execution_trend = [
            {
                "date": date,
                "count": data["count"],
                "success_rate": (data["success"] / data["count"] * 100) if data["count"] > 0 else 0
            }
            for date, data in sorted(trend_by_date.items())
        ]

        return {
            "total_executions": total,
            "success_rate": round(success_rate, 1),
            "failed_executions": failed,
            "avg_duration_seconds": round(avg_duration, 2),
            "min_duration_seconds": round(min_duration, 2),
            "max_duration_seconds": round(max_duration, 2),
            "step_type_distribution": dict(step_types),
            "execution_trend": execution_trend
        }

    def get_chain_performance(self, start_date=None, end_date=None):
        """
        Get per-chain performance metrics.

        Returns:
            list of {
                chain_id: str,
                chain_name: str,
                executions: int,
                success_rate: float,
                avg_duration_seconds: float,
                last_execution: ISO string
            }
        """
        chains = self.execution_history.hass.data.get(DOMAIN, {}).get("chains", {})
        executions = self.execution_history.list_executions_filtered(
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )

        chain_stats = defaultdict(lambda: {
            "name": "Unknown",
            "total": 0,
            "success": 0,
            "durations": [],
            "last": None
        })

        for e in executions:
            chain_id = e.get("chain_id")
            if not chain_id:
                continue

            # Get chain name if available
            if chain_id in chains:
                chain_stats[chain_id]["name"] = chains[chain_id].get("name", chain_id)

            chain_stats[chain_id]["total"] += 1
            if e.get("status") != "failed":
                chain_stats[chain_id]["success"] += 1

            try:
                duration = (
                    datetime.fromisoformat(e.get("finished", e.get("started"))) -
                    datetime.fromisoformat(e.get("started"))
                ).total_seconds()
                chain_stats[chain_id]["durations"].append(duration)
            except (ValueError, TypeError):
                pass

            if not chain_stats[chain_id]["last"] or e.get("started") > chain_stats[chain_id]["last"]:
                chain_stats[chain_id]["last"] = e.get("started")

        result = []
        for chain_id, stats in chain_stats.items():
            avg_duration = statistics.mean(stats["durations"]) if stats["durations"] else 0
            success_rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0

            result.append({
                "chain_id": chain_id,
                "chain_name": stats["name"],
                "executions": stats["total"],
                "success_rate": round(success_rate, 1),
                "avg_duration_seconds": round(avg_duration, 2),
                "last_execution": stats["last"]
            })

        return sorted(result, key=lambda x: x["executions"], reverse=True)

    def get_step_analytics(self, start_date=None, end_date=None):
        """
        Analyze step-level performance.

        Returns:
            dict with:
                - slowest_steps: list of {step_type, avg_duration, total_runs}
                - fastest_steps: list
                - most_used_steps: list
                - failing_step_types: list of {step_type, failure_rate}
        """
        executions = self.execution_history.list_executions_filtered(
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )

        step_stats = defaultdict(lambda: {
            "durations": [],
            "count": 0,
            "failures": 0
        })

        for execution in executions:
            for step in execution.get("steps", []):
                step_type = step.get("type", "unknown")
                step_stats[step_type]["count"] += 1

                try:
                    duration = (
                        datetime.fromisoformat(step.get("finished", step.get("started"))) -
                        datetime.fromisoformat(step.get("started"))
                    ).total_seconds()
                    step_stats[step_type]["durations"].append(duration)
                except (ValueError, TypeError):
                    pass

                if step.get("status") == "failed":
                    step_stats[step_type]["failures"] += 1

        # Slowest steps
        slowest = []
        for step_type, stats in step_stats.items():
            if stats["durations"]:
                avg = statistics.mean(stats["durations"])
                slowest.append({
                    "step_type": step_type,
                    "avg_duration_seconds": round(avg, 2),
                    "total_runs": stats["count"]
                })
        slowest = sorted(slowest, key=lambda x: x["avg_duration_seconds"], reverse=True)[:5]

        # Fastest steps
        fastest = sorted(
            [
                {
                    "step_type": st,
                    "avg_duration_seconds": round(statistics.mean(stats["durations"]), 2),
                    "total_runs": stats["count"]
                }
                for st, stats in step_stats.items() if stats["durations"]
            ],
            key=lambda x: x["avg_duration_seconds"]
        )[:5]

        # Most used steps
        most_used = sorted(
            [
                {
                    "step_type": st,
                    "total_runs": stats["count"],
                    "avg_duration_seconds": round(
                        statistics.mean(stats["durations"]), 2
                    ) if stats["durations"] else 0
                }
                for st, stats in step_stats.items()
            ],
            key=lambda x: x["total_runs"],
            reverse=True
        )[:5]

        # Failing step types
        failing_steps = []
        for step_type, stats in step_stats.items():
            if stats["count"] > 0:
                failure_rate = (stats["failures"] / stats["count"] * 100)
                if failure_rate > 0:
                    failing_steps.append({
                        "step_type": step_type,
                        "failure_rate": round(failure_rate, 1),
                        "total_runs": stats["count"]
                    })
        failing_steps = sorted(failing_steps, key=lambda x: x["failure_rate"], reverse=True)[:5]

        return {
            "slowest_steps": slowest,
            "fastest_steps": fastest,
            "most_used_steps": most_used,
            "failing_step_types": failing_steps
        }

    def get_execution_timeline(self, chain_id, limit=20):
        """
        Get Gantt chart data for parallel execution timeline visualization.

        Returns:
            dict with:
                - chain_id: str
                - executions: list of {
                    exec_id, started, finished, duration, steps: [
                      {name, started, finished, duration, parallel_group}
                    ]
                  }
        """
        executions = self.execution_history.list_executions_filtered(
            chain_id=chain_id,
            limit=limit
        )

        timeline_data = []
        for execution in executions:
            steps_timeline = []
            earliest_start = None
            latest_end = None

            for step in execution.get("steps", []):
                try:
                    started_str = step.get("started")
                    finished_str = step.get("finished", step.get("started"))
                    
                    if not started_str or not finished_str:
                        continue  # Skip steps without timestamps
                    
                    started = datetime.fromisoformat(started_str)
                    finished = datetime.fromisoformat(finished_str)
                    duration = (finished - started).total_seconds()

                    if earliest_start is None or started < earliest_start:
                        earliest_start = started
                    if latest_end is None or finished > latest_end:
                        latest_end = finished

                    # Calculate relative start time for visualization (ms from exec start)
                    steps_timeline.append({
                        "name": step.get("name", step.get("type", "Unknown")),
                        "type": step.get("type", "unknown"),
                        "started": step.get("started"),
                        "finished": step.get("finished"),
                        "duration_seconds": round(duration, 2),
                        "status": step.get("status", "unknown")
                    })
                except (ValueError, TypeError):
                    pass

            if earliest_start and latest_end:
                total_duration = (latest_end - earliest_start).total_seconds()
                timeline_data.append({
                    "exec_id": execution.get("id"),
                    "started": execution.get("started"),
                    "finished": execution.get("finished"),
                    "duration_seconds": round(total_duration, 2),
                    "steps": steps_timeline
                })

        return {
            "chain_id": chain_id,
            "executions": timeline_data
        }
