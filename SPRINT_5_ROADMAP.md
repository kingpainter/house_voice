# Sprint 5: Event Routing & Transformation — Roadmap

**Status:** Planning  
**Version Target:** v3.5.1  
**Estimated Complexity:** Medium (3-4 hours)

---

## Overview

Sprint 5 adds intelligent event routing and transformation capabilities to the House Voice Manager event chain system. This enables dynamic step execution based on event data and parameter modification at runtime.

---

## Features

### Feature 1: Event Filtering
**Goal:** Skip or execute steps conditionally based on event attributes  
**Effort:** ~1 hour

**Details:**
- Add `filter` field to ChainStep: `filter: Optional[dict]`
- Filter format: `{"key": "value", "operator": "equals|contains|regex"}`
- Support multiple filters with AND-logic
- Skip step execution if filter fails (non-fatal)
- Log filter results for debugging

**Example:**
```python
step = ChainStep(
    action=ChainActionType.ANNOUNCEMENT,
    target="speaker_group",
    filter={
        "event_source": "mqtt",
        "device_type": "sensor"
    },
)
```

**Tests:**
- test_event_filter_match_single()
- test_event_filter_mismatch()
- test_event_filter_multiple_conditions()
- test_event_filter_regex()

---

### Feature 2: Dynamic Routing
**Goal:** Select step target dynamically based on event data  
**Effort:** ~1.5 hours

**Details:**
- Add `route_expression` field to ChainStep: `route_expression: Optional[str]`
- Expression format: Jinja2 templates with event data context
- Runtime evaluation of route_expression to determine target
- Fallback to static `target` if expression undefined
- Support for step result data in later steps

**Example:**
```python
step = ChainStep(
    action=ChainActionType.ANNOUNCEMENT,
    route_expression="{{ 'living_room' if event.room == 'main' else 'bedroom' }}",
    parameters={"message": "{{ event.message }}"},
)
```

**Implementation:**
- Use jinja2 template engine (or simple string substitution)
- Pass event context dict to _execute_step()
- Validate route_expression syntax at chain registration

**Tests:**
- test_dynamic_routing_simple()
- test_dynamic_routing_with_conditions()
- test_dynamic_routing_fallback()
- test_dynamic_routing_invalid_expression()

---

### Feature 3: Event Data Transformation
**Goal:** Modify step parameters based on event data  
**Effort:** ~1.5 hours

**Details:**
- Add `transform` field to ChainStep: `transform: Optional[dict]`
- Transform format: `{"param_key": "{{ expression }}"}`
- Apply transformations before step execution
- Support event data, step results, and config values
- Validation of transformation expressions

**Example:**
```python
step = ChainStep(
    action=ChainActionType.ANNOUNCEMENT,
    target="speaker_group",
    parameters={"message": "Original message"},
    transform={
        "message": "{{ event.custom_message or parameters.message }}",
        "volume": "{{ event.volume or 50 }}"
    },
)
```

**Implementation:**
- Extend ChainStep.parameters with transform logic
- Apply transform before handler execution
- Create TransformationError exception for invalid expressions

**Tests:**
- test_parameter_transformation_simple()
- test_parameter_transformation_fallback()
- test_parameter_transformation_with_event_data()
- test_transformation_expression_error()

---

## Architecture Changes

### New Dataclasses

#### EventFilter
```python
@dataclass
class EventFilter:
    """Single filter condition."""
    key: str
    value: Any
    operator: str = "equals"  # equals | contains | regex | gt | lt
    
    def matches(self, event_data: dict) -> bool:
        """Evaluate filter against event data."""
```

#### EventContext
```python
@dataclass
class EventContext:
    """Event data passed through chain execution."""
    source: str
    data: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
```

### Modified Dataclasses

#### ChainStep
Add fields:
```python
filter: Optional[dict] = None  # Single or multiple filters
route_expression: Optional[str] = None  # Jinja2 template
transform: Optional[dict] = None  # Parameter transformations
```

#### EventChainManager._execute_step_with_retry()
Signature change:
```python
async def _execute_step_with_retry(
    self,
    step: ChainStep,
    execution: ChainExecution,
    event_context: Optional[EventContext] = None,  # NEW
) -> bool:
```

---

## Implementation Plan

### Phase 1: Foundation (30 min)
- [ ] Add EventFilter and EventContext dataclasses
- [ ] Update ChainStep with new fields
- [ ] Create expression evaluation utility functions

### Phase 2: Event Filtering (30 min)
- [ ] Implement EventFilter.matches()
- [ ] Update _execute_step_with_retry() to check filters
- [ ] Add filter evaluation logging
- [ ] Write 4 tests

### Phase 3: Dynamic Routing (45 min)
- [ ] Implement route_expression evaluation
- [ ] Modify step.target resolution in _execute_step_with_retry()
- [ ] Add fallback to static target
- [ ] Write 4 tests

### Phase 4: Data Transformation (45 min)
- [ ] Implement parameter transformation logic
- [ ] Create transformation expression evaluator
- [ ] Handle transform errors gracefully
- [ ] Write 4 tests

### Phase 5: Integration & Testing (30 min)
- [ ] Full test suite run (should be 50+ tests total)
- [ ] Integration test: filter + routing + transformation
- [ ] Verify backward compatibility
- [ ] Create documentation

---

## Testing Strategy

### Unit Tests (16 tests)
- 4 Event Filter tests
- 4 Dynamic Routing tests
- 4 Data Transformation tests
- 4 Integration tests (combinations)

### Backward Compatibility
- All existing tests (25) should still pass
- ChainStep without new fields should work as before
- No breaking changes to EventChainManager API

### Test Coverage Target
- 100% of new code paths
- All backoff modes + filters + routing
- Error cases (invalid expressions, missing data)

---

## Success Criteria

✅ 16 new tests, all passing  
✅ 25 existing tests still passing  
✅ Event filtering works with AND-logic  
✅ Dynamic routing supports Jinja2 expressions  
✅ Data transformation updates step parameters  
✅ Backward compatible (no breaking changes)  
✅ Comprehensive logging for debugging  
✅ Documentation with examples  

---

## Known Risks

| Risk | Mitigation |
|------|-----------|
| Jinja2 expression injection | Use sandbox mode, validate expressions at registration |
| Complex transformation logic | Limit to simple {{}} expressions, provide examples |
| Event context data mutations | Make EventContext immutable, validate before use |
| Performance with large chains | Cache compiled expressions, benchmark before release |

---

## Future Enhancements

- Expression caching (compile once, reuse)
- Conditional branching (if/else logic in routing)
- Event aggregation (combine multiple events)
- Custom filter functions
- Expression validation DSL
- Metrics: filter match rates, routing decisions

---

## Related Issues

- Performance optimization for large chains
- Dashboard for event routing visualization
- Expression editor in UI

---

**Next Action:** Implement Phase 1 (Foundation) - dataclasses and utilities

