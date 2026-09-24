# Sprint 3 Implementation Plan — Breaking Down the Work

**Version:** 3.5.0  
**Current Status:** 🎯 Ready to Begin  
**Date:** 2026-09-24

---

## Task Breakdown

### Task 1: Parallel Execution Engine (6–8 hrs)

#### 1.1 Build Dependency Graph (2 hrs)

**File:** `events/event_chain.py` (new method in EventChainManager)

```python
def _build_dependency_graph(self, steps: list[ChainStep]) -> dict[str, set[str]]:
    """Build dependency graph: {step_id: set of dependent step_ids}."""
    graph = {step.step_id: set(step.depends_on) for step in steps}
    return graph

def _get_ready_steps(
    self,
    all_steps: list[ChainStep],
    completed: set[str],
    graph: dict[str, set[str]],
) -> list[ChainStep]:
    """Find steps with all dependencies satisfied."""
    ready = []
    for step in all_steps:
        if step.step_id in completed:
            continue
        if all(dep in completed for dep in graph[step.step_id]):
            ready.append(step)
    return ready
```

**Tests:**
- `test_dependency_graph_simple.py` — 2-step chain with dependency
- `test_dependency_graph_complex.py` — 5-step chain with multiple paths
- `test_ready_steps_detection.py` — Correctly identifies ready steps

#### 1.2 Parallel Execution Loop (3 hrs)

**File:** `events/event_chain.py` (modify `execute_chain()`)

```python
async def execute_chain(self, chain_id: str) -> ChainExecution:
    """Execute chain with parallel step support."""
    steps = self.chains[chain_id]
    execution = ChainExecution(chain_id=chain_id, started_at=asyncio.get_event_loop().time())
    
    graph = self._build_dependency_graph(steps)
    all_steps_by_id = {s.step_id: s for s in steps}
    
    # Execute in waves until all complete
    while len(execution.completed_steps) + len(execution.failed_steps) < len(steps):
        ready = self._get_ready_steps(steps, execution.completed_steps, graph)
        
        if not ready:
            # Deadlock or all remaining failed
            break
        
        # Execute ready steps in parallel
        tasks = [
            self._execute_step_with_retry(step, execution)
            for step in ready
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for step, result in zip(ready, results):
            if isinstance(result, Exception):
                execution.failed_steps.add(step.step_id)
                execution.step_errors[step.step_id] = result
            else:
                if result:  # Step succeeded
                    execution.completed_steps.add(step.step_id)
                else:  # Step failed
                    execution.failed_steps.add(step.step_id)
    
    execution.is_complete = True
    return execution
```

**Tests:**
- `test_parallel_independent_steps.py` — 4 independent steps run simultaneously
- `test_parallel_execution_time.py` — Verify 40%+ speedup
- `test_parallel_respects_dependencies.py` — Parallel doesn't break depends_on
- `test_parallel_mixed_chain.py` — Sequential + parallel mixed

#### 1.3 Benchmarking (1 hr)

**File:** `tests/components/house_voice/test_chain_performance.py`

```python
@pytest.mark.asyncio
async def test_chain_execution_speedup():
    """Parallel execution should be ~4x faster for 4 independent steps."""
    # Create 4 independent steps, 0.5s each
    # Sequential: 2.0s, Parallel: 0.5s
    # Assert speedup > 3x
```

---

### Task 2: Conditional Steps (6–8 hrs)

#### 2.1 Add CONDITION_CHECK ActionType (1 hr)

**File:** `events/event_chain.py`

```python
class ChainActionType(str, Enum):
    ANNOUNCEMENT = "announcement"
    GROUP_VOLUME_UP = "group_volume_up"
    GROUP_VOLUME_DOWN = "group_volume_down"
    DELAY = "delay"
    CONDITION_CHECK = "condition_check"  # NEW
    WEBHOOK = "webhook"
```

#### 2.2 Implement Condition Check Handler (3 hrs)

**File:** `events/event_chain.py` (new function)

```python
async def handle_condition_check_action(
    step: ChainStep,
    hass: HomeAssistant,
    conditions_lib: HouseVoiceConditions,  # Injected from VoiceEngine
) -> dict[str, Any]:
    """Evaluate condition and return result."""
    condition_id = step.target
    condition = conditions_lib.get_condition(condition_id)
    
    if not condition:
        return {
            "matched": False,
            "reason": "condition_not_found",
            "condition_id": condition_id,
        }
    
    entity_id = condition["entity_id"]
    expected = condition["state"]
    
    entity = hass.states.get(entity_id)
    actual = entity.state if entity else "unknown"
    matched = actual == expected
    
    return {
        "matched": matched,
        "condition_id": condition_id,
        "entity_id": entity_id,
        "expected_state": expected,
        "actual_state": actual,
    }
```

#### 2.3 Conditional Branch Logic (2 hrs)

**File:** `events/event_chain.py` (modify `execute_chain()`)

```python
# After condition check, resolve next steps based on result
if step.action == ChainActionType.CONDITION_CHECK:
    result = await handler(step, hass)
    matched = result["matched"]
    
    # Get branch targets from parameters
    on_true = step.parameters.get("on_true", [])
    on_false = step.parameters.get("on_false", [])
    
    branch_targets = on_true if matched else on_false
    
    # Mark branch targets as ready (skip to them)
    for target_id in branch_targets:
        # Resolve step ID and add to graph as "already checked"
        pass
```

#### 2.4 Conditional Tests (2 hrs)

**File:** `tests/components/house_voice/test_conditional_steps.py`

```python
@pytest.mark.asyncio
async def test_condition_check_matched():
    """True condition should follow on_true branch."""

@pytest.mark.asyncio
async def test_condition_check_unmatched():
    """False condition should follow on_false branch."""

@pytest.mark.asyncio
async def test_condition_unknown_entity():
    """Missing entity should use continue_on_unknown."""

@pytest.mark.asyncio
async def test_condition_in_complex_chain():
    """Conditions + dependencies + parallel should work together."""
```

---

### Task 3: Webhook Integration (6–8 hrs)

#### 3.1 Add WEBHOOK ActionType (1 hr)

**File:** `events/event_chain.py`

```python
class ChainActionType(str, Enum):
    # ... existing ...
    WEBHOOK = "webhook"  # NEW
```

#### 3.2 Webhook Handler (3 hrs)

**File:** `events/webhooks.py` (NEW)

```python
import aiohttp

async def handle_webhook_action(
    step: ChainStep,
    hass: HomeAssistant,
) -> dict[str, Any]:
    """Execute HTTP webhook call."""
    url = step.target
    params = step.parameters
    
    method = params.get("method", "POST")
    timeout_sec = params.get("timeout", 5)
    headers = params.get("headers", {})
    body = params.get("body", {})
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method,
                url=url,
                json=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout_sec),
            ) as response:
                response_data = await response.json()
                
                return {
                    "success": response.status in (200, 201, 202),
                    "status_code": response.status,
                    "response": response_data,
                }
    
    except asyncio.TimeoutError:
        if params.get("on_timeout") == "fail":
            raise
        return {"success": True, "warning": "Webhook timeout"}
    
    except Exception as err:
        raise
```

#### 3.3 Chain Callbacks (2 hrs)

**File:** `events/event_chain.py` (modify EventChainManager)

```python
class EventChainManager:
    def __init__(self, hass: HomeAssistant):
        # ... existing ...
        self.chain_callbacks: dict[str, dict[str, Callable]] = {}
    
    def register_chain_callback(
        self,
        chain_id: str,
        on_success: Optional[Callable] = None,
        on_failure: Optional[Callable] = None,
    ) -> None:
        """Register callbacks for chain completion."""
        self.chain_callbacks[chain_id] = {
            "on_success": on_success,
            "on_failure": on_failure,
        }
    
    async def execute_chain(self, chain_id: str) -> ChainExecution:
        # ... execute chain ...
        
        # Call appropriate callback
        callbacks = self.chain_callbacks.get(chain_id, {})
        if len(execution.failed_steps) == 0 and callbacks["on_success"]:
            await callbacks["on_success"](chain_id, execution)
        elif callbacks["on_failure"]:
            await callbacks["on_failure"](chain_id, execution)
        
        return execution
```

#### 3.4 Webhook Tests (2 hrs)

**File:** `tests/components/house_voice/test_webhooks.py`

```python
@pytest.mark.asyncio
async def test_webhook_success():
    """Successful webhook call returns response."""

@pytest.mark.asyncio
async def test_webhook_timeout():
    """Timeout handling uses on_timeout parameter."""

@pytest.mark.asyncio
async def test_webhook_auth_failure():
    """401/403 responses handled correctly."""

@pytest.mark.asyncio
async def test_chain_callback_on_success():
    """On-success callback triggered when chain completes."""

@pytest.mark.asyncio
async def test_chain_callback_on_failure():
    """On-failure callback triggered when steps fail."""
```

---

### Task 4: Advanced Retry Strategies (3–4 hrs)

#### 4.1 RetryConfig Dataclass (1 hr)

**File:** `events/event_chain.py`

```python
@dataclass
class RetryConfig:
    """Per-step retry configuration."""
    max_attempts: int = 3
    backoff_mode: str = "exponential"  # exponential | linear | constant
    base_delay_ms: int = 100
    max_delay_ms: int = 5000
    
    circuit_breaker_threshold: int = 5  # Fail count before circuit breaks
    circuit_breaker_reset_after_seconds: int = 60

@dataclass
class ChainStep:
    # ... existing fields ...
    retry_config: RetryConfig = field(default_factory=RetryConfig)
```

#### 4.2 Calculate Backoff Delay (1 hr)

**File:** `events/event_chain.py`

```python
def _calculate_backoff_delay_ms(
    attempt: int,
    config: RetryConfig,
) -> int:
    """Calculate delay based on backoff mode."""
    if config.backoff_mode == "exponential":
        delay = config.base_delay_ms * (2 ** attempt)
    elif config.backoff_mode == "linear":
        delay = config.base_delay_ms * (attempt + 1)
    else:  # constant
        delay = config.base_delay_ms
    
    return min(delay, config.max_delay_ms)
```

#### 4.3 Circuit Breaker (1 hr)

**File:** `events/event_chain.py` (in EventChainManager)

```python
class EventChainManager:
    def __init__(self, hass: HomeAssistant):
        # ... existing ...
        self.circuit_breakers: dict[str, dict] = {}  # {step_id: {failure_count, last_reset}}
    
    def _is_circuit_open(self, step_id: str, config: RetryConfig) -> bool:
        """Check if circuit breaker is open for this step."""
        cb = self.circuit_breakers.get(step_id, {"failure_count": 0, "last_reset": 0})
        
        # Check if reset period has passed
        now = time.time()
        if now - cb["last_reset"] > config.circuit_breaker_reset_after_seconds:
            self.circuit_breakers[step_id] = {"failure_count": 0, "last_reset": now}
            cb = self.circuit_breakers[step_id]
        
        return cb["failure_count"] >= config.circuit_breaker_threshold
    
    def _record_failure(self, step_id: str) -> None:
        """Record a failure for circuit breaker."""
        if step_id not in self.circuit_breakers:
            self.circuit_breakers[step_id] = {"failure_count": 0, "last_reset": time.time()}
        self.circuit_breakers[step_id]["failure_count"] += 1
```

#### 4.4 Retry Tests (1 hr)

**File:** `tests/components/house_voice/test_retry_strategies.py`

```python
@pytest.mark.asyncio
async def test_exponential_backoff():
    """Exponential: 100ms, 200ms, 400ms."""

@pytest.mark.asyncio
async def test_linear_backoff():
    """Linear: 100ms, 200ms, 300ms."""

@pytest.mark.asyncio
async def test_constant_backoff():
    """Constant: 100ms, 100ms, 100ms."""

@pytest.mark.asyncio
async def test_circuit_breaker_opens():
    """Circuit opens after threshold failures."""

@pytest.mark.asyncio
async def test_circuit_breaker_resets():
    """Circuit resets after timeout."""
```

---

## File Summary

### Modified Files
- `custom_components/house_voice/events/event_chain.py` (+~400 lines)
  - Parallel execution engine
  - Condition check handler
  - Webhook callback registration
  - Circuit breaker logic
  - Backoff calculation

### New Files
- `custom_components/house_voice/events/webhooks.py` (new, ~100 lines)
  - Webhook execution handler
  - HTTP client logic

- `tests/components/house_voice/test_chain_performance.py` (new, ~50 lines)
- `tests/components/house_voice/test_conditional_steps.py` (new, ~100 lines)
- `tests/components/house_voice/test_webhooks.py` (new, ~120 lines)
- `tests/components/house_voice/test_retry_strategies.py` (new, ~80 lines)

### Docs
- Update `ANNOUNCEMENT_CHAIN_API.md` with new features
- Create `SPRINT_3_FEATURES.md` (user-facing guide)

---

## Version Updates Needed

When Sprint 3 is complete:

```
Files to update to v3.5.0:
├── manifest.json                      (version: "3.5.0")
├── custom_components/house_voice/__init__.py
├── custom_components/house_voice/const.py
├── custom_components/house_voice/events/event_chain.py
└── All modified .py files (add # VERSION = "3.5.0")

Create:
├── CHANGELOG.md entry for v3.5.0
└── Update SPRINT_3_FEATURES.md
```

---

## Success Checklist

- [ ] All 15+ new tests pass (4 features × ~4 tests each)
- [ ] No regressions in existing tests (v3.4.0 test suite still passes)
- [ ] Parallel execution reduces chain time by 30%+ (benchmark verified)
- [ ] Documentation complete (ANNOUNCEMENT_CHAIN_API.md updated)
- [ ] Code review passes (clean, well-commented)
- [ ] CI passes (hassfest, pytest, linting)
- [ ] Tag v3.5.0 and push to GitHub

---

## Estimated Timeline

| Feature | Hours | Start | End |
|---------|-------|-------|-----|
| 1. Parallel | 6–8 | Day 1 | Day 1–2 |
| 2. Conditionals | 6–8 | Day 2 | Day 2–3 |
| 3. Webhooks | 6–8 | Day 3 | Day 3–4 |
| 4. Retry | 3–4 | Day 4 | Day 4 |
| Testing + CI | 2–3 | Throughout | Day 4–5 |
| **Total** | **23–31** | **Day 1** | **Day 5** |

---

**Ready to kick off Task 1 (Parallel Execution)?** 🚀
