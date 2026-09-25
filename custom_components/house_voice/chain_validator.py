"""Chain validation engine for House Voice Manager.

Validates chain structure, entity resolution, Jinja2 expressions,
cycle detection, and step dependencies.
"""

from __future__ import annotations

import logging
from typing import Any

import jinja2

_LOGGER = logging.getLogger(__name__)


class ValidationResult:
    """Result of chain validation."""
    
    def __init__(self, is_valid: bool = True, errors: list[str] | None = None, warnings: list[str] | None = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
    
    def to_dict(self) -> dict:
        """Convert to dictionary for WebSocket response."""
        return {
            "valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings
        }


class ChainValidator:
    """Validate chain structure and contents."""
    
    def __init__(self, hass: Any) -> None:
        self.hass = hass
        self.errors = []
        self.warnings = []
    
    def validate_chain(self, chain: dict) -> ValidationResult:
        """
        Validate chain structure and contents.
        
        Checks:
        - Structural errors (missing fields, invalid types)
        - Entity resolution (do targets exist?)
        - Jinja2 syntax (valid expressions)
        - DAG cycles (no loops)
        - Step dependencies
        """
        self.errors = []
        self.warnings = []
        
        # Check required fields
        self._check_required_fields(chain)
        if self.errors:
            return ValidationResult(False, self.errors, self.warnings)
        
        # Validate chain structure
        self._validate_chain_structure(chain)
        
        # Validate steps
        if "steps" in chain:
            self._validate_steps(chain["steps"], chain)
        
        # Check for cycles
        if "steps" in chain:
            cycles = self._detect_cycles(chain["steps"])
            if cycles:
                self.errors.append(f"Circular dependency detected: {' → '.join(cycles)}")
        
        is_valid = len(self.errors) == 0
        return ValidationResult(is_valid, self.errors, self.warnings)
    
    def _check_required_fields(self, chain: dict) -> None:
        """Check if required fields are present."""
        required = ["name", "steps"]
        for field in required:
            if field not in chain or not chain[field]:
                self.errors.append(f"Required field '{field}' is missing or empty")
    
    def _validate_chain_structure(self, chain: dict) -> None:
        """Validate chain-level structure."""
        # Check status
        if "status" in chain:
            valid_statuses = ["draft", "published", "active"]
            if chain["status"] not in valid_statuses:
                self.errors.append(f"Invalid status '{chain['status']}'. Must be one of: {', '.join(valid_statuses)}")
        
        # Check execution_config
        if "execution_config" in chain:
            config = chain["execution_config"]
            if "timeout" in config:
                if not isinstance(config["timeout"], (int, float)) or config["timeout"] <= 0:
                    self.errors.append("execution_config.timeout must be a positive number")
            
            if "on_failure" in config:
                valid_options = ["stop", "continue", "rollback"]
                if config["on_failure"] not in valid_options:
                    self.errors.append(f"Invalid on_failure option. Must be one of: {', '.join(valid_options)}")
    
    def _validate_steps(self, steps: list, chain: dict) -> None:
        """Validate all steps in the chain."""
        if not isinstance(steps, list):
            self.errors.append("'steps' must be a list")
            return
        
        step_ids = set()
        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                self.errors.append(f"Step {idx}: must be an object, got {type(step).__name__}")
                continue
            
            # Check unique IDs
            step_id = step.get("id")
            if step_id and step_id in step_ids:
                self.errors.append(f"Duplicate step ID: '{step_id}'")
            if step_id:
                step_ids.add(step_id)
            
            # Check required step fields
            if "type" not in step:
                self.errors.append(f"Step {idx}: missing 'type' field")
                continue
            
            step_type = step["type"]
            if step_type not in ["announce", "delay", "condition_check", "light", "switch"]:
                self.warnings.append(f"Step {idx}: unknown action type '{step_type}' (may be custom)")
            
            # Validate target
            if "target" in step:
                target = step["target"]
                if not self._is_valid_entity_id(target):
                    self.warnings.append(f"Step {idx}: target '{target}' may not be a valid entity ID")
                elif not self._check_entity_exists(target):
                    self.warnings.append(f"Step {idx}: entity '{target}' does not exist in Home Assistant")
            
            # Validate Jinja2 expressions
            if "parameters" in step:
                self._validate_jinja2_in_dict(step["parameters"], f"Step {idx}.parameters")
            
            if "route_expression" in step and step["route_expression"]:
                self._validate_jinja2_expression(step["route_expression"], f"Step {idx}.route_expression")
    
    def _validate_jinja2_in_dict(self, obj: Any, path: str) -> None:
        """Recursively validate Jinja2 expressions in a dictionary."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                self._validate_jinja2_in_dict(value, f"{path}.{key}")
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                self._validate_jinja2_in_dict(item, f"{path}[{idx}]")
        elif isinstance(obj, str):
            if "{{" in obj or "{%" in obj:
                self._validate_jinja2_expression(obj, path)
    
    def _validate_jinja2_expression(self, expression: str, path: str) -> None:
        """Check if a Jinja2 expression is syntactically valid."""
        try:
            env = jinja2.Environment()
            env.compile_expression(expression)
        except jinja2.exceptions.TemplateSyntaxError as e:
            self.errors.append(f"Invalid Jinja2 in {path}: {str(e)}")
        except jinja2.exceptions.UndefinedError:
            # This is OK - undefined variables are expected at validation time
            pass
        except Exception as e:
            self.errors.append(f"Error validating Jinja2 in {path}: {str(e)}")
    
    def _is_valid_entity_id(self, entity_id: str) -> bool:
        """Check if entity_id has valid format."""
        if not isinstance(entity_id, str):
            return False
        
        # Support group:xyz and entity.domain formats
        if entity_id.startswith("group:"):
            return len(entity_id) > 6
        
        if "." in entity_id:
            parts = entity_id.split(".")
            return len(parts) == 2 and all(p for p in parts)
        
        return False
    
    def _check_entity_exists(self, entity_id: str) -> bool:
        """Check if entity exists in Home Assistant."""
        try:
            # Handle group: prefix
            if entity_id.startswith("group:"):
                # Assume groups are valid (they're created dynamically)
                return True
            
            state = self.hass.states.get(entity_id)
            return state is not None
        except Exception:
            return False
    
    def _detect_cycles(self, steps: list) -> list | None:
        """Detect if there are circular dependencies in steps.
        
        Returns the cycle path if found, None otherwise.
        """
        if not steps:
            return None
        
        # Build adjacency list from step dependencies
        dependencies = {}
        for step in steps:
            step_id = step.get("id", str(steps.index(step)))
            dependencies[step_id] = []
            
            # Detect dependencies from route_expression or parameters
            # For now, simple implementation: no explicit dependencies
            # Can be extended to parse route_expression for dependencies
        
        # Check for cycles using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(node: str, path: list) -> list | None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in dependencies.get(node, []):
                if neighbor not in visited:
                    result = has_cycle(neighbor, path.copy())
                    if result:
                        return result
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor) if neighbor in path else 0
                    return path[cycle_start:] + [neighbor]
            
            rec_stack.remove(node)
            return None
        
        for step_id in dependencies:
            if step_id not in visited:
                cycle = has_cycle(step_id, [])
                if cycle:
                    return cycle
        
        return None


    # Sprint 6: Conditional step validation

    def _validate_dag_dependencies(self, steps: list) -> list[str]:
        """Validate step dependencies and detect cycles."""
        from .dag_executor import DAGExecutor
        
        errors = []
        
        # Check that all dependency references exist
        step_ids = {s.get("id") for s in steps}
        for step in steps:
            step_id = step.get("id")
            depends_on = step.get("depends_on", [])
            
            for dep_id in depends_on:
                if dep_id not in step_ids:
                    errors.append(f"Step {step_id}: dependency '{dep_id}' not found")
        
        # Detect cycles using DAGExecutor
        executor = DAGExecutor(None)  # No executor needed for cycle detection
        cycle_errors = executor.detect_cycles(steps)
        errors.extend(cycle_errors)
        
        return errors

    def _validate_conditional_step(self, step: dict) -> list[str]:
        """Validate a CONDITION_CHECK step."""
        errors = []
        
        # Required fields for conditional
        if not step.get("condition"):
            errors.append(f"Step {step.get('id', '?')}: CONDITION_CHECK requires 'condition' field")
            return errors
        
        condition = step.get("condition")
        
        # Validate condition type
        if condition.get("type") not in ("entity_state", "jinja2", "logical"):
            errors.append(f"Step {step.get('id', '?')}: condition type must be entity_state | jinja2 | logical")
        
        # Validate entity_state condition
        if condition.get("type") == "entity_state":
            if not condition.get("entity_id"):
                errors.append(f"Step {step.get('id', '?')}: entity_state condition requires entity_id")
            if not condition.get("expected_state"):
                errors.append(f"Step {step.get('id', '?')}: entity_state condition requires expected_state")
        
        # Validate jinja2 condition
        if condition.get("type") == "jinja2":
            if not condition.get("template"):
                errors.append(f"Step {step.get('id', '?')}: jinja2 condition requires template")
            else:
                # Try to compile template
                jinja_errors = self._validate_jinja2_expression(condition.get("template", ""))
                if jinja_errors:
                    errors.append(f"Step {step.get('id', '?')}: jinja2 template error: {jinja_errors[0]}")
        
        # Validate logical condition
        if condition.get("type") == "logical":
            if not condition.get("operator") in ("AND", "OR", "NOT"):
                errors.append(f"Step {step.get('id', '?')}: logical condition requires operator AND|OR|NOT")
            if not condition.get("conditions"):
                errors.append(f"Step {step.get('id', '?')}: logical condition requires conditions array")
        
        # Validate branches
        if not step.get("on_true"):
            errors.append(f"Step {step.get('id', '?')}: CONDITION_CHECK requires on_true branch (step_id)")
        if not step.get("on_false"):
            errors.append(f"Step {step.get('id', '?')}: CONDITION_CHECK requires on_false branch (step_id)")
        
        return errors
