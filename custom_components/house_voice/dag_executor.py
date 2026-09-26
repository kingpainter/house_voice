# VERSION = "3.12.0"
# Sprint 6: DAG-based parallel chain execution engine

import asyncio
import logging
from typing import Any, Callable
from collections import defaultdict

_LOGGER = logging.getLogger(__name__)


class DAGExecutor:
    """Execute chain steps in parallel based on dependency graph."""

    def __init__(self, step_executor: Callable):
        """
        Initialize DAG executor.
        
        Args:
            step_executor: async function(step, chain_context) -> step_result
        """
        self.step_executor = step_executor

    async def execute_chain(self, chain: dict, chain_context: dict) -> dict:
        """
        Execute chain steps respecting dependencies. Returns execution result.
        
        Chain format:
        {
            "id": "chain_123",
            "steps": [
                {
                    "id": "step_1",
                    "type": "announcement",
                    "depends_on": [],  # Empty = can run immediately
                    ...
                },
                {
                    "id": "step_2",
                    "type": "announcement",
                    "depends_on": ["step_1"],  # Runs after step_1
                    ...
                }
            ]
        }
        """
        try:
            steps = chain.get("steps", [])
            if not steps:
                return {"success": True, "steps": [], "duration": 0}

            # Build dependency graph
            step_map = {s.get("id"): s for s in steps}
            dependencies = self._build_dependency_graph(steps)

            # Execute with parallel support
            completed_steps = {}
            execution_order = []
            start_time = asyncio.get_event_loop().time()

            # Find all steps with no dependencies (can run immediately)
            ready_steps = [s for s in steps if not dependencies.get(s.get("id"), [])]
            pending_steps = set(s.get("id") for s in steps)

            while pending_steps:
                # Execute all ready steps in parallel
                tasks = {}
                for step_id in ready_steps:
                    step = step_map[step_id]
                    tasks[step_id] = asyncio.create_task(
                        self.step_executor(step, chain_context)
                    )

                # Wait for all tasks to complete
                if tasks:
                    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
                    for step_id, result in zip(tasks.keys(), results):
                        if isinstance(result, Exception):
                            completed_steps[step_id] = {
                                "id": step_id,
                                "success": False,
                                "error": str(result),
                            }
                        else:
                            completed_steps[step_id] = result
                        execution_order.append(step_id)
                        pending_steps.discard(step_id)

                # Find newly ready steps (all dependencies completed)
                ready_steps = [
                    s for s in steps
                    if s.get("id") in pending_steps
                    and all(
                        dep_id in completed_steps
                        for dep_id in dependencies.get(s.get("id"), [])
                    )
                ]

                # Break if no progress (circular dependency or error)
                if not ready_steps and pending_steps:
                    _LOGGER.error("DAG execution: no ready steps but %d pending", len(pending_steps))
                    break

            end_time = asyncio.get_event_loop().time()
            duration = int((end_time - start_time) * 1000)

            return {
                "success": True,
                "steps": [completed_steps.get(s.get("id")) for s in steps],
                "execution_order": execution_order,
                "duration": duration,
            }

        except Exception as err:
            _LOGGER.error("DAG execution failed: %s", err)
            return {
                "success": False,
                "error": str(err),
                "steps": [],
            }

    def _build_dependency_graph(self, steps: list) -> dict:
        """Build dependency map: step_id -> list of step_ids it depends on."""
        graph = {}
        for step in steps:
            step_id = step.get("id")
            deps = step.get("depends_on", [])
            graph[step_id] = deps if isinstance(deps, list) else []
        return graph

    def detect_cycles(self, steps: list) -> list[str]:
        """Detect circular dependencies. Returns list of cycle paths, or empty if clean."""
        graph = self._build_dependency_graph(steps)
        errors = []

        def has_cycle_dfs(node: str, visited: set, rec_stack: set) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle_dfs(neighbor, visited, rec_stack):
                        errors.append(f"Cycle detected: {node} → {neighbor}")
                        return True
                elif neighbor in rec_stack:
                    errors.append(f"Cycle: {node} → {neighbor} (back edge)")
                    return True

            rec_stack.remove(node)
            return False

        visited = set()
        for node in graph:
            if node not in visited:
                has_cycle_dfs(node, visited, set())

        return errors
