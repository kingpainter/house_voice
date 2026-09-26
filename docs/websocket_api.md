# House Voice — WebSocket API Documentation

**Version:** 3.13.0  
**Last Updated:** 2026-09-26  
**Scope:** All 19 core WebSocket commands for the House Voice sidebar panel

---

## 1. Overview

The House Voice integration exposes a RESTful WebSocket API for the sidebar panel UI. All commands follow the Home Assistant WebSocket pattern:

```javascript
hass.connection.subscribeMessage(
  (response) => { /* handle response */ },
  { type: "house_voice/command_name", ...params }
)
```

### Command Categories

- **Events Management** (5 commands) — Create, read, test, delete voice events
- **Groups Management** (3 commands) — Manage speaker groups
- **Conditions Library** (3 commands) — Manage conditional playback rules
- **History Viewer** (2 commands) — Query and filter execution history
- **Analytics Dashboard** (4 commands) — Aggregated statistics and performance metrics
- **Media Players** (1 command) — List available speakers
- **Execution History** (1 command) — List execution records

---

## 2. Events Management

### 2.1 `house_voice/get_events`

Retrieve all stored voice events.

**Type:** Query (no parameters required)

**Parameters:** None

**Response:**
```json
{
  "events": {
    "event_id_1": {
      "message": "Guten Morgen",
      "speakers": ["media_player.kitchen", "group:bedroom"],
      "priority": "normal",
      "volume": 0.35,
      "conditions": ["someone_home", "not_sleeping"]
    }
  }
}
```

**Error Codes:**
- `not_ready` — Storage not initialized
- `invalid_data` — Corrupted event data

---

### 2.2 `house_voice/save_event`

Create or update a voice event.

**Type:** Async command

**Parameters:**
| Parameter | Type | Required | Default | Notes |
|-----------|------|----------|---------|-------|
| `event_id` | string | Yes | — | Unique identifier, must be non-empty |
| `message` | string | Yes | — | TTS text (Jinja2 supported) |
| `speakers` | list | Yes | — | At least one speaker required |
| `priority` | string | No | "normal" | One of: `info`, `normal`, `critical` |
| `volume` | float | No | 0.35 | Range: 0.05–1.0 |
| `conditions` | list | No | [] | Condition Library IDs (AND logic) |

---

### 2.3 `house_voice/test_event`

Test-play a voice event (bypasses spam filter and quiet hours).

**Type:** Async command

**Parameters:** `event_id` (string, required)

---

### 2.4 `house_voice/delete_event`

Delete a voice event.

**Type:** Async command

**Parameters:** `event_id` (string, required)

---

## 3. Groups Management

### 3.1 `house_voice/get_groups`

Retrieve all speaker groups.

**Type:** Query (no parameters required)

---

### 3.2 `house_voice/save_group`

Create or update a speaker group.

**Type:** Async command

**Parameters:**
| Parameter | Type | Required |
|-----------|------|----------|
| `group_id` | string | Yes |
| `name` | string | Yes |
| `speakers` | list | Yes |

---

### 3.3 `house_voice/delete_group`

Delete a speaker group.

**Type:** Async command

**Parameters:** `group_id` (string, required)

---

## 4. Conditions Library

### 4.1 `house_voice/get_conditions`

Retrieve all saved conditions.

**Type:** Query (no parameters required)

---

### 4.2 `house_voice/save_condition`

Create or update a condition.

**Type:** Async command

**Parameters:**
| Parameter | Type | Required |
|-----------|------|----------|
| `condition_id` | string | Yes |
| `label` | string | Yes |
| `entity_id` | string | Yes |
| `state` | string | Yes |

---

### 4.3 `house_voice/delete_condition`

Delete a condition.

**Type:** Async command

**Parameters:** `condition_id` (string, required)

---

## 5. History & Execution Records

### 5.1 `house_voice/get_history`

Retrieve the last 50 TTS execution records.

**Type:** Query (no parameters required)

---

### 5.2 `house_voice/query_executions`

Query persistent execution history with advanced filtering.

**Type:** Async command

**Parameters:**
| Parameter | Type | Required |
|-----------|------|----------|
| `chain_id` | string | No |
| `status` | string | No |
| `start_date` | string | No |
| `end_date` | string | No |
| `search_text` | string | No |

---

### 5.3 `house_voice/get_execution_detail`

Retrieve full details of a single execution record.

**Type:** Query

**Parameters:** `exec_id` (string, required)

---

## 6. Analytics Dashboard

### 6.1 `house_voice/get_analytics_statistics`

Retrieve aggregated performance statistics.

**Type:** Query

**Parameters:** `start_date`, `end_date`, `chain_id` (optional, string)

---

### 6.2 `house_voice/get_chain_performance`

List chains ranked by execution performance.

**Type:** Query

**Parameters:** `start_date`, `end_date`, `limit` (optional, int, default 10)

---

### 6.3 `house_voice/get_step_analytics`

Retrieve top-10 analytics for individual steps.

**Type:** Query

**Parameters:** `start_date`, `end_date` (optional, string)

---

### 6.4 `house_voice/get_execution_timeline`

Retrieve execution records for visualization.

**Type:** Query

**Parameters:**
| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `chain_id` | string | Yes | — |
| `limit` | int | No | 50 |

---

## 7. Media Players

### 7.1 `house_voice/get_media_players`

Retrieve all available media_player entities.

**Type:** Query (no parameters required)

---

## 8. Execution History

### 8.1 `house_voice/list_execution_history`

List execution history records.

**Type:** Query (no parameters required)

---

## 9. Error Handling

All commands return errors in this format:

```json
{
  "type": "result",
  "id": 1,
  "error": {
    "code": "error_code_name",
    "message": "Human-readable error message"
  }
}
```

**Common Error Codes:**
- `not_ready` — Service not initialized
- `invalid_input` — Validation failed
- `not_found` — Resource doesn't exist
- `invalid_data` — Data corruption
- `unknown_error` — Unexpected error

---

## 10. Best Practices

1. Always validate responses — Check `error` property before accessing data
2. Handle async commands — They may take longer than queries
3. Use filters efficiently — Filter at backend with `query_executions`
4. Cache results — Call `get_events` once per session
5. Implement retry logic — For `unknown_error`, implement exponential backoff

---

**Version History:**
- 3.13.0 (2026-09-26) — Phase 9 analytics commands added
- 3.11.0 (2026-09-25) — Phase 8 execution history viewer
- 3.7.0 (2026-09-24) — Phase 7 parallel execution
- 3.3.1 (2026-09-20) — Core commands
