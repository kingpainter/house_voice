# House Voice Announcement Chain API

**Version:** 3.4.0  
**Last Updated:** 2026-09-24  
**Status:** ✅ Complete

---

## Overview

Announcement chains provide a powerful DAG-based orchestration system for multi-step speaker control. Instead of simple point-to-point TTS, chains coordinate:

- **Volume adjustments** before/after announcements (3-retry backoff with fallback)
- **Timed delays** between steps
- **Parallel step execution** with dependency resolution
- **Automatic fallback strategies** when services fail
- **Detailed execution tracking** for debugging and automation

This documentation covers how to use announcement chains in automations and via the REST API.

---

## Quick Start

### Basic Announcement Chain (Automatic)

The simplest way to use announcement chains is via `execute_announcement_chain()` in **VoiceEngine**:

```python
# Python/HA internal usage
await engine.execute_announcement_chain(
    event_id="doorbell",
    speakers=["media_player.living_room"],  # or "group:kokken"
    volume_increase=0.15,  # +15% volume before announcement
)
```

This creates and executes a standard 4-step chain:
1. **GROUP_VOLUME_UP** (+0.15) → with 3-retry fallback
2. **ANNOUNCEMENT** (doorbell event) → fail if blocked
3. **DELAY** (2000ms) → let audio finish
4. **GROUP_VOLUME_DOWN** (-0.15) → restore original volume

Each step has automatic retry logic (exponential backoff: 500ms, 1s, 2s).

---

## Advanced: Custom Announcement Chains

For finer control, construct chains manually:

### 1. Import the Chain Builder

```python
from custom_components.house_voice.events.event_chain import (
    EventChainManager,
    ChainActionType,
    ChainStep,
    create_announcement_chain,
)
```

### 2. Create a Custom Chain

```python
# Example: Volume UP → Announce → LONG delay → Volume DOWN
chain_steps = [
    ChainStep(
        action=ChainActionType.GROUP_VOLUME_UP,
        target="living_room",
        parameters={"volume_step": 0.2},  # +20%
        on_error="continue",  # Skip if fails
        max_retries=3,
    ),
    ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="alarm_event",
        on_error="fail",  # Stop chain if announcement fails
        max_retries=1,
    ),
    ChainStep(
        action=ChainActionType.DELAY,
        parameters={"duration_ms": 5000},  # 5 second delay
        on_error="continue",
    ),
    ChainStep(
        action=ChainActionType.GROUP_VOLUME_DOWN,
        target="living_room",
        parameters={"volume_step": 0.2},
        on_error="continue",
    ),
]

# Register and execute
await event_chain_manager.register_chain("custom_alarm", chain_steps)
execution = await event_chain_manager.execute_chain("custom_alarm")
```

### 3. Check Execution Results

```python
if execution.is_complete:
    print(f"✅ Chain complete: {len(execution.completed_steps)} succeeded")
    for failed in execution.failed_steps:
        print(f"❌ Failed step: {failed}")
        error = execution.step_errors.get(failed)
        print(f"   Error: {error}")
else:
    print("Chain still executing...")
```

---

## ChainStep Reference

### ChainStep Constructor

```python
ChainStep(
    action: ChainActionType,           # Required: what to do
    target: Optional[str] = None,      # Required for most actions
    parameters: dict[str, Any] = {},   # Action-specific params
    delay_ms: Optional[int] = None,    # Delay before step
    on_error: str = "continue",        # "continue" | "retry" | "fail"
    max_retries: int = 3,              # Attempts before fallback
    depends_on: list[str] = [],        # Step IDs this depends on
)
```

### Action Types

| ChainActionType | Target | Parameters | Purpose |
|---|---|---|---|
| `ANNOUNCEMENT` | Event ID (str) | (none) | Play stored voice event |
| `GROUP_VOLUME_UP` | Group ID (str) | `{"volume_step": float}` | Increase group volume (0.0–1.0) |
| `GROUP_VOLUME_DOWN` | Group ID (str) | `{"volume_step": float}` | Decrease group volume |
| `DELAY` | (ignored) | `{"duration_ms": int}` | Wait before next step |
| `CONDITION_CHECK` | Condition ID | (varies) | Check if condition matches |
| `WEBHOOK` | URL (str) | `{"method": "GET\|POST"}` | Call external webhook |

### Error Handling Modes

- **`"continue"`** (default): Log error, continue to next step. Volume adjustments use this so a failed volume adjustment doesn't block the announcement.
- **`"retry"`**: Attempt again with exponential backoff (500ms, 1s, 2s). After all retries exhaust, apply fallback strategy.
- **`"fail"`**: Stop entire chain if this step fails. Use for critical announcements that must not be silent.

### Dependencies

```python
# Step B depends on Step A
ChainStep(
    action=ChainActionType.ANNOUNCEMENT,
    target="event_b",
    depends_on=["group_volume_up_kokken"],  # Step IDs from previous steps
)
```

If dependency is unmet at execution time, the step is skipped.

---

## Fallback Strategies

When a step with `max_retries > 1` exhausts all attempts, fallback strategies activate automatically.

### Built-in Fallback Strategies

**1. NoOpFallback**
- Logs the error
- Returns success to allow chain to continue
- **Use case:** Temporary service outages (volume adjustment can retry next time)

**2. ManualAdjustmentFallback**
- Sends persistent notification to user
- User manually adjusts speaker volume
- **Use case:** Consistent volume adjustment failures

**3. SkipVolumeAdjustmentFallback**
- Skips the adjustment
- Proceeds with announcement at current volume
- **Use case:** Volume not critical, content delivery is

**4. RetryWithIncreasingDelayFallback**
- Waits 5 seconds
- Service may recover during wait
- **Use case:** Overloaded service, brief restart

**5. LogAndAlertFallback**
- Logs error + system alert
- Notifies user of failure
- **Use case:** Critical errors requiring attention

---

## VolumeControllerV2 Reference

The volume controller handles individual speaker group volume adjustments with built-in retry and fallback.

### Methods

```python
controller = VolumeControllerV2(hass)

# Increase volume
result = await controller.increase_group_volume(
    group_id: str,
    amount: float = 0.1,  # e.g., 0.1 = 10% increase
) -> VolumeAdjustmentResult

# Decrease volume
result = await controller.decrease_group_volume(
    group_id: str,
    amount: float = 0.1,
) -> VolumeAdjustmentResult
```

### VolumeAdjustmentResult

```python
@dataclass
class VolumeAdjustmentResult:
    success: bool                    # True if adjustment succeeded
    group_id: str                    # Speaker group ID
    action: str                      # "increase" | "decrease"
    attempted_count: int             # Number of attempts (1–3)
    final_volume: Optional[float]    # Volume after adjustment
    error_message: Optional[str]     # Last error (if any)
    fallback_applied: bool           # Was fallback strategy used?
    fallback_strategy: Optional[str] # Name of fallback (if applied)
```

### Retry Logic

- **Attempt 1:** Immediate
- **Attempt 2:** After 500ms
- **Attempt 3:** After 1s
- **Fallback:** If all 3 attempts fail, execute fallback strategy

---

## EventChainManager Reference

Central orchestration engine for event chains.

### Methods

```python
manager = EventChainManager(hass)

# Register a handler for a specific action type
manager.register_action_handler(
    action_type: ChainActionType,
    handler: Callable,
)

# Register a chain definition
await manager.register_chain(
    chain_id: str,
    steps: list[ChainStep],
)

# Execute a chain
execution = await manager.execute_chain(
    chain_id: str,
) -> ChainExecution

# Get execution state
state = manager.get_execution(chain_id: str) -> Optional[ChainExecution]
```

### ChainExecution Result

```python
@dataclass
class ChainExecution:
    chain_id: str                           # Chain identifier
    started_at: float                       # Unix timestamp
    step_results: dict[str, Any]            # Result per step
    step_errors: dict[str, Exception]       # Error per failed step
    completed_steps: set[str]               # Successfully executed steps
    failed_steps: set[str]                  # Failed steps (not retried)
    is_complete: bool                       # Execution finished?
```

---

## Built-in Action Handlers

House Voice provides default handlers for common actions:

### `handle_announcement_action()`
Calls `house_voice.say` service with the event ID.

```python
# Registered automatically in VoiceEngine.__init__()
manager.register_action_handler(
    ChainActionType.ANNOUNCEMENT,
    handle_announcement_action,
)
```

### `handle_group_volume_action()`
Calls `VolumeControllerV2.increase_group_volume()` or `.decrease_group_volume()`.

```python
# Registered automatically for GROUP_VOLUME_UP and GROUP_VOLUME_DOWN
from custom_components.house_voice.events.event_chain import handle_group_volume_action

# For custom chains:
async def volume_up_handler(step, hass):
    return await handle_group_volume_action(step, hass, direction="up")
```

### `handle_delay_action()`
Sleeps for the specified duration (milliseconds).

```python
# Registered automatically for DELAY actions
manager.register_action_handler(ChainActionType.DELAY, handle_delay_action)
```

---

## Example: Advanced Multi-Group Announcement

Announce in three rooms with staggered volume increases:

```python
chain_steps = [
    # Living room: +15%
    ChainStep(
        action=ChainActionType.GROUP_VOLUME_UP,
        target="living_room",
        parameters={"volume_step": 0.15},
        on_error="continue",
    ),
    # Kitchen: +15% (after living room done)
    ChainStep(
        action=ChainActionType.GROUP_VOLUME_UP,
        target="kokken",
        parameters={"volume_step": 0.15},
        delay_ms=500,  # Start 500ms after living room
        on_error="continue",
    ),
    # Bedroom: +15% (after kitchen done)
    ChainStep(
        action=ChainActionType.GROUP_VOLUME_UP,
        target="soveværelse",
        parameters={"volume_step": 0.15},
        delay_ms=500,
        on_error="continue",
    ),
    # Announce (all rooms ready)
    ChainStep(
        action=ChainActionType.ANNOUNCEMENT,
        target="doorbell",
        on_error="fail",
    ),
    # 3 second delay for audio
    ChainStep(
        action=ChainActionType.DELAY,
        parameters={"duration_ms": 3000},
    ),
    # Restore volumes (staggered back down)
    ChainStep(
        action=ChainActionType.GROUP_VOLUME_DOWN,
        target="living_room",
        parameters={"volume_step": 0.15},
        on_error="continue",
    ),
    ChainStep(
        action=ChainActionType.GROUP_VOLUME_DOWN,
        target="kokken",
        parameters={"volume_step": 0.15},
        delay_ms=500,
        on_error="continue",
    ),
    ChainStep(
        action=ChainActionType.GROUP_VOLUME_DOWN,
        target="soveværelse",
        parameters={"volume_step": 0.15},
        delay_ms=500,
        on_error="continue",
    ),
]

await manager.register_chain("multi_doorbell", chain_steps)
execution = await manager.execute_chain("multi_doorbell")
```

---

## Troubleshooting

### Volume adjustments fail silently
- **Cause:** Volume service unavailable, but NoOpFallback allows chain to continue
- **Solution:** Check logs for fallback strategy messages; verify speaker group exists

### Announcement doesn't play at adjusted volume
- **Cause:** Volume adjustment failed, announcement plays at previous volume
- **Solution:** Manually adjust volume in HA, or use `execute_announcement_chain()` which logs all adjustments

### Chain stops unexpectedly
- **Cause:** A step has `on_error="fail"` and encountered an error
- **Solution:** Check `execution.failed_steps` and `execution.step_errors` for details

### Dependency not resolving
- **Cause:** Dependency step ID doesn't match previous step's `step_id` property
- **Solution:** Use `ChainStep.step_id` property directly: `f"{action.value}_{target or 'generic'}"`

---

## Testing

Run the E2E test suite:

```bash
pytest tests/components/house_voice/test_announcement_chain_e2e.py -v
pytest tests/components/house_voice/test_event_chain.py -v
pytest tests/components/house_voice/test_voice_engine.py -k "chain" -v
```

---

## Performance Notes

- **Chain execution:** Sequential by default (each step waits for previous)
- **Retry backoff:** Total max wait per failed step = 3.5 seconds (500ms + 1s + 2s)
- **Fallback overhead:** Minimal (~100ms) for NoOp, ~300ms for ManualAdjustment (notification)
- **Queue behavior:** All chains execute through VoiceEngine's asyncio queue (concurrent with TTS)

---

## Next Steps

- **v3.5.0:** Parallel step execution (DAG-based instead of sequential)
- **v3.5.0:** Conditional steps (CONDITION_CHECK action type)
- **v3.5.0:** Webhook action handler for external integrations
- **Future:** Webhook callbacks on chain completion

---

**Questions?** Check `test_announcement_chain_e2e.py` for usage examples.
