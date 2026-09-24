# VERSION = "3.5.0"
# File: events/event_chain_parallel.py
# Description: Parallel execution engine for event chains (v3.5.0 Sprint 3)

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

_LOGGER = logging.getLogger(__name__)


class DependencyGraph:
    """Dependency graph for parallel step execution."""

    def __init__(self, steps: list[Any]) -> None:
        """Initialize dependency graph from steps.
        
        Args:
            steps: List of ChainStep objects with depends_on lists.
        """
        self.steps = {step.step_id: step for step in steps}
        self.dependencies = {step.step_id: set(step.depends_on) for step in steps}
        self.dependents = self._build_dependents_map()

    def _build_dependents_map(self) -> dict[str, set[str]]:
        """Build reverse dependency map: which steps depend on each step."""
        dependents = {step_id: set() for step_id in self.steps}
        for step_id, deps in self.dependencies.items():
            for dep in deps:
                if dep in dependents:
                    dependents[dep].add(step_id)
        return dependents

    def get_ready_steps(self, completed: set[str]) -> list[Any]:
        """Get all steps that are ready to execute (dependencies satisfied).
        
        Args:
            completed: Set of step IDs that have already completed.
            
        Returns:
            List of ChainStep objects ready to execute.
        """
        ready = []
        for step_id, step in self.steps.items():
            # Skip already completed steps
            if step_id in completed:
                continue
            
            # Check if all dependencies are satisfied
            if self.dependencies[step_id].issubset(completed):
                ready.append(step)
        
        return ready

    def has_cycles(self) -> bool:
        """Check if dependency graph has cycles (would deadlock).
        
        Returns:
            True if cycles detected, False otherwise.
        """
        visited = set()
        rec_stack = set()
        
        def _has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            
            for dep in self.dependencies[node]:
                if dep not in visited:
                    if _has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for step_id in self.steps:
            if step_id not in visited:
                if _has_cycle(step_id):
                    return True
        
        return False

    def get_execution_waves(self) -> list[list[str]]:
        """Get steps grouped by execution wave (all in wave can run in parallel).
        
        Returns:
            List of lists: each inner list is a wave of step IDs.
            
        Example:
            [[step1, step2], [step3], [step4, step5]]  # step1+step2 parallel, then step3, etc.
        """
        waves = []
        completed = set()
        
        while len(completed) < len(self.steps):
            ready = self.get_ready_steps(completed)
            
            if not ready:
                # Deadlock or all remaining failed
                break
            
            wave = [step.step_id for step in ready]
            waves.append(wave)
            completed.update(wave)
        
        return waves


class ParallelExecutor:
    """Executes steps in parallel respecting dependencies."""

    def __init__(self) -> None:
        """Initialize parallel executor."""
        self.execution_times: dict[str, float] = {}

    async def execute_wave(
        self,
        steps: list[Any],
        handler_func,
        execution,
    ) -> tuple[set[str], set[str]]:
        """Execute a wave of steps in parallel.
        
        Args:
            steps: List of ChainStep objects to execute concurrently.
            handler_func: Async handler function for each step.
            execution: ChainExecution object to track results.
            
        Returns:
            Tuple of (succeeded_step_ids, failed_step_ids).
        """
        tasks = [
            handler_func(step, execution)
            for step in steps
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        succeeded = set()
        failed = set()
        
        for step, result in zip(steps, results):
            if isinstance(result, Exception):
                execution.failed_steps.add(step.step_id)
                execution.step_errors[step.step_id] = result
                failed.add(step.step_id)
                _LOGGER.warning(
                    "Parallel step failed: %s — %s",
                    step.step_id,
                    result,
                )
            else:
                if result:  # Step succeeded
                    execution.completed_steps.add(step.step_id)
                    succeeded.add(step.step_id)
                    _LOGGER.debug("Parallel step completed: %s", step.step_id)
                else:
                    execution.failed_steps.add(step.step_id)
                    failed.add(step.step_id)
        
        return succeeded, failed

    async def execute_all_waves(
        self,
        waves: list[list[str]],
        steps_by_id: dict[str, Any],
        handler_func,
        execution,
    ) -> None:
        """Execute all waves sequentially (each wave parallel).
        
        Args:
            waves: List of execution waves (from DependencyGraph.get_execution_waves).
            steps_by_id: Mapping of step_id to ChainStep.
            handler_func: Async handler for each step.
            execution: ChainExecution to track results.
        """
        for wave_num, wave_step_ids in enumerate(waves):
            steps = [steps_by_id[sid] for sid in wave_step_ids]
            
            _LOGGER.debug(
                "Executing parallel wave %d: %d steps",
                wave_num + 1,
                len(steps),
            )
            
            succeeded, failed = await self.execute_wave(
                steps,
                handler_func,
                execution,
            )
            
            # If any step in wave had on_error="fail", check if we should stop
            for step in steps:
                if step.step_id in failed and step.on_error == "fail":
                    _LOGGER.error(
                        "Wave %d: critical step failed, stopping chain",
                        wave_num + 1,
                    )
                    return


# ── Integration with EventChainManager ────────────────────────────────────

def integrate_parallel_execution(manager_class):
    """Decorator to add parallel execution to EventChainManager.
    
    Usage:
        @integrate_parallel_execution
        class EventChainManager:
            ...
    """
    original_execute = manager_class.execute_chain
    
    async def execute_chain_parallel(self, chain_id: str):
        """Execute chain with parallel step support."""
        if chain_id not in self.chains:
            raise ValueError(f"Chain not found: {chain_id}")
        
        from homeassistant.core import HomeAssistant
        from .event_chain import ChainExecution
        import asyncio
        
        steps = self.chains[chain_id]
        execution = ChainExecution(
            chain_id=chain_id,
            started_at=asyncio.get_event_loop().time(),
        )
        
        self.executions[chain_id] = execution
        
        try:
            # Check for cycles
            graph = DependencyGraph(steps)
            if graph.has_cycles():
                raise ValueError(f"Chain {chain_id} has circular dependencies")
            
            # Get execution waves
            waves = graph.get_execution_waves()
            _LOGGER.info(
                "Chain %s: %d steps in %d parallel waves",
                chain_id,
                len(steps),
                len(waves),
            )
            
            # Execute all waves
            executor = ParallelExecutor()
            steps_by_id = {s.step_id: s for s in steps}
            
            await executor.execute_all_waves(
                waves,
                steps_by_id,
                self._execute_step_with_retry,
                execution,
            )
        
        finally:
            execution.is_complete = True
            _LOGGER.info(
                "Chain %s execution complete: %d succeeded, %d failed",
                chain_id,
                len(execution.completed_steps),
                len(execution.failed_steps),
            )
        
        return execution
    
    manager_class.execute_chain = execute_chain_parallel
    return manager_class
