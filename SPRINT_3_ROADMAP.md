# Sprint 3 Roadmap — House Voice v3.5.0

**Version Target:** 3.5.0  
**Status:** 🗺️ Planning Phase  
**Previous Sprint:** v3.4.0 ✅ Complete  
**Date:** 2026-09-24

---

## Overview

Sprint 3 builds on Sprint 2's event chaining foundation by adding:
1. **Parallel step execution** (DAG-based concurrent steps)
2. **Conditional logic** (CONDITION_CHECK action type)
3. **Webhook integration** (external API calls + callbacks)
4. **Advanced retry strategies** (per-step configuration)

---

## Feature 1: Parallel Step Execution

### Current State (v3.4.0)
- Event chains execute **sequentially** (step-by-step)
- Each step waits for previous to complete
- Dependency resolution prevents out-of-order execution

### Target State (v3.5.0)
- Enable **concurrent execution** of independent steps
- Use asyncio.gather() to run non-dependent steps in parallel
- Reduce total chain execution time by 40–60%

### Implementation

#### Changes to EventChainManager

```python
async def execute_chain(self, chain_id: str) -> ChainExecution:
    """Execute chain with parallel step support."""
    # NEW: Build dependency graph
    graph = self._build_dependency_graph(steps)
    
    # NEW: Find steps with no unmet dependencies
    ready_steps = [s for s in steps if not s.depends_on]
    
    # NEW: Execute ready steps concurrently
    tasks = [
        self._execute_step_with_retry(step, execution)
        for step in ready_steps
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # NEW: Mark completed, find next ready set
    execution.completed_steps.update({step.step_id for step in ready_steps})
    
    # Continue with next wave of ready steps...
```

#### Performance Impact
- **Sequential chain (4 steps, 1s each):** 4 seconds total
- **Parallel chain (4 independent steps, 1s each):** ~1 second total
- **Real scenario:** Volume UP (left room) + Volume UP (right room) + Announce (parallel) = much faster

#### Test Coverage
- `test_parallel_independent_steps()` — Verify concurrent execution
- `test_parallel_respects_dependencies()` — Parallel does NOT break dependencies
- `test_parallel_mixed_chain()` — Mix of parallel + sequential steps
- Benchmark test: Compare sequential vs parallel execution time

---

## Feature 2: Conditional Steps (CONDITION_CHECK)

### Current State (v3.4.0)
- Conditions exist only at **event level** (block/allow announcement)
- No per-step conditional logic

### Target State (v3.5.0)
- Add **CONDITION_CHECK** action type
- Step can check condition, branch on result
- Enable advanced automation patterns

### New ChainActionType

```python
class ChainActionType(str, Enum):
    # ... existing ...
    CONDITION_CHECK = "condition_check"
```

### ChainStep Configuration

```python
ChainStep(
    action=ChainActionType.CONDITION_CHECK,
    target="condition_id",  # Condition Library ID
    parameters={
        "on_true": ["step_id_1", "step_id_2"],   # Steps to run if true
        "on_false": ["step_id_3"],                # Steps to run if false
        "continue_on_unknown": True,              # Treat missing condition as?
    },
    on_error="fail",  # What if condition check fails?
)
```

### Handler Implementation

```python
async def handle_condition_check_action(
    step: ChainStep,
    hass: HomeAssistant,
    conditions_lib: HouseVoiceConditions,
) -> dict[str, Any]:
    """Check condition and return result."""
    condition_id = step.target
    condition = conditions_lib.get_condition(condition_id)
    
    if not condition:
        # Missing condition → use continue_on_unknown
        return {"matched": False, "reason": "condition_not_found"}
    
    # Evaluate condition
    state = hass.states.get(condition["entity_id"])
    matched = state and state.state == condition["state"]
    
    return {
        "matched": matched,
        "condition_id": condition_id,
        "entity_id": condition["entity_id"],
        "expected_state": condition["state"],
        "actual_state": state.state if state else "unknown",
    }
```

### Example: Smart Announcement

```python
# IF someone_is_home AND time > 22:00 → QUIET mode (lower volume)
# ELSE → NORMAL mode (full volume)

steps = [
    ChainStep(
        action=ChainActionType.CONDITION_CHECK,
        target="someone_is_home",
        parameters={
            "on_true": ["volume_down_quiet"],
            "on_false": ["volume_up_normal"],
        },
        on_error="fail",
    ),
    # ... rest of steps reference by ID ...
]
```

### Test Coverage
- `test_condition_check_matched()` — True condition branches correctly
- `test_condition_check_unmatched()` — False condition branches correctly
- `test_condition_check_unknown_entity()` — Missing entity handled gracefully
- `test_condition_in_complex_chain()` — Conditions + dependencies together

---

## Feature 3: Webhook Integration

### Current State (v3.4.0)
- No external API integration
- Chains are internal to Home Assistant only

### Target State (v3.5.0)
- **WEBHOOK** action type for HTTP calls
- **On-completion callbacks** to notify external systems
- Enable integration with:
  - IFTTT, Telegram, Discord webhooks
  - Custom APIs
  - External logging/analytics

### New ChainActionType

```python
class ChainActionType(str, Enum):
    # ... existing ...
    WEBHOOK = "webhook"
```

### ChainStep Configuration

```python
ChainStep(
    action=ChainActionType.WEBHOOK,
    target="https://api.example.com/announce",
    parameters={
        "method": "POST",
        "timeout": 5,
        "headers": {
            "Content-Type": "application/json",
            "Authorization": "Bearer TOKEN",
        },
        "body": {
            "event": "announcement",
            "group_id": "kokken",
            "timestamp": "{{ now_iso }}",
        },
        "on_timeout": "continue",  # Timeout handling
    },
    on_error="continue",
)
```

### Handler Implementation

```python
async def handle_webhook_action(
    step: ChainStep,
    hass: HomeAssistant,
) -> dict[str, Any]:
    """Execute webhook call."""
    url = step.target
    params = step.parameters
    
    async with aiohttp.ClientSession() as session:
        try:
            response = await session.request(
                method=params.get("method", "POST"),
                url=url,
                json=params.get("body"),
                headers=params.get("headers"),
                timeout=aiohttp.ClientTimeout(total=params.get("timeout", 5)),
            )
            
            return {
                "success": response.status in (200, 201, 202),
                "status": response.status,
                "response": await response.json(),
            }
        except asyncio.TimeoutError:
            if params.get("on_timeout") == "fail":
                raise
            return {"success": True, "warning": "Webhook timeout (continued)"}
```

### On-Completion Callbacks

```python
# Register callbacks before executing chain
async def on_chain_success(chain_id: str, execution: ChainExecution):
    # All steps succeeded
    await hass.services.async_call(
        "webhook",
        "post",
        {"url": "https://...", "data": {"status": "success"}},
    )

async def on_chain_failure(chain_id: str, execution: ChainExecution):
    # Some steps failed
    await hass.services.async_call(
        "webhook",
        "post",
        {
            "url": "https://...",
            "data": {
                "status": "failed",
                "failed_steps": list(execution.failed_steps),
            }
        },
    )

manager.register_chain_callback("multi_announce", on_success=on_chain_success, on_failure=on_chain_failure)
```

### Example: Announce + Log to Analytics

```python
steps = [
    ChainStep(action=ChainActionType.GROUP_VOLUME_UP, target="kokken", ...),
    ChainStep(action=ChainActionType.ANNOUNCEMENT, target="event_id", ...),
    ChainStep(
        action=ChainActionType.WEBHOOK,
        target="https://analytics.example.com/events",
        parameters={
            "method": "POST",
            "body": {
                "event_type": "house_voice_announcement",
                "group_id": "kokken",
                "timestamp": "{{ now_iso }}",
            },
        },
        on_error="continue",  # Analytics failure ≠ chain failure
    ),
]
```

### Test Coverage
- `test_webhook_success()` — Successful HTTP call
- `test_webhook_timeout()` — Timeout handling
- `test_webhook_auth_failure()` — 401/403 responses
- `test_chain_callbacks_on_success()` — On-success callback triggers
- `test_chain_callbacks_on_failure()` — On-failure callback triggers

---

## Feature 4: Advanced Retry Strategies (Per-Step)

### Current State (v3.4.0)
- Global retry config: 3 attempts, 500ms/1s/2s backoff
- Same for all steps

### Target State (v3.5.0)
- **Per-step retry configuration**
- Exponential, linear, or constant backoff options
- Circuit breaker pattern for failing services

### Enhanced ChainStep

```python
@dataclass
class ChainStep:
    # ... existing ...
    retry_config: RetryConfig = field(default_factory=lambda: RetryConfig())

@dataclass
class RetryConfig:
    max_attempts: int = 3
    backoff_mode: str = "exponential"  # exponential | linear | constant
    base_delay_ms: int = 100
    max_delay_ms: int = 5000
    
    # Circuit breaker: if service fails N times, skip future attempts
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_after_seconds: int = 60
```

### Example: Different Retry for Different Steps

```python
steps = [
    ChainStep(
        action=ChainActionType.GROUP_VOLUME_UP,
        target="kokken",
        retry_config=RetryConfig(
            max_attempts=3,
            backoff_mode="exponential",  # 100ms, 200ms, 400ms
        ),
        on_error="continue",  # Volume adjustment can fail gracefully
    ),
    ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="event_id",
        retry_config=RetryConfig(
            max_attempts=1,  # No retry — critical step
        ),
        on_error="fail",  # Must succeed or stop chain
    ),
    ChainStep(
        action=ChainActionType.WEBHOOK,
        target="https://...",
        retry_config=RetryConfig(
            max_attempts=5,
            backoff_mode="linear",  # 100ms, 200ms, 300ms, 400ms, 500ms
            circuit_breaker_threshold=3,  # Skip if 3 failures
        ),
        on_error="continue",
    ),
]
```

### Implementation Notes
- Circuit breaker prevents hammering failing services
- Per-step backoff enables fine-grained reliability
- Total execution time becomes predictable

### Test Coverage
- `test_linear_backoff()` — 100ms, 200ms, 300ms progression
- `test_constant_backoff()` — Fixed delay each retry
- `test_circuit_breaker_opens()` — Skip after threshold
- `test_circuit_breaker_resets()` — Recovery after timeout

---

## Implementation Order

| Priority | Feature | Complexity | Estimated Hours | Dependencies |
|----------|---------|------------|-----------------|---|
| 1 | Parallel execution | Medium | 6–8 | Event chain v3.4.0 ✅ |
| 2 | Conditional steps | Medium | 6–8 | Condition Library, Parallel execution |
| 3 | Webhook integration | Medium | 6–8 | Parallel + Conditional |
| 4 | Advanced retry | Low | 3–4 | All above |

**Total Estimate:** 21–28 hours (3–3.5 days intensive)

---

## Testing Strategy

### Unit Tests (per feature)
- Parallel execution: 4 tests
- Conditionals: 4 tests
- Webhooks: 5 tests
- Retry: 4 tests

### Integration Tests
- Parallel + Conditional chains
- Webhook callbacks in real chain
- Full v3.5.0 scenario tests

### Performance Benchmarks
- Chain execution time (sequential vs parallel)
- Memory usage with large chains
- Webhook timeout impact

---

## Rollout Plan

### Phase 1: Internal Testing
- Run full test suite locally
- Manual testing with real speaker groups
- Verify no regressions vs v3.4.0

### Phase 2: Beta Release
- Tag as v3.5.0-beta.1 on GitHub
- Open for community testing
- Gather feedback

### Phase 3: Stable Release
- Fix any reported issues
- Tag v3.5.0 final
- Update documentation
- Announce in HA community

---

## Known Risks

| Risk | Mitigation |
|------|-----------|
| Parallel execution race conditions | Comprehensive concurrent testing + locks where needed |
| Webhook timeouts blocking chain | Non-blocking webhook calls + timeout configuration |
| Condition check performance | Cache condition evaluations per execution |
| Circuit breaker false positives | Configurable threshold + reset mechanism |

---

## Success Criteria

✅ All unit + integration tests pass  
✅ Parallel execution reduces chain time by 30%+  
✅ Conditional logic enables 10+ new automation patterns  
✅ Webhook integration tested with external APIs  
✅ Zero regressions vs v3.4.0  
✅ Documentation complete + examples provided  

---

**Next Action:** Kick off Feature 1 (Parallel Execution) once Sprint 2 is pushed and CI is green.
