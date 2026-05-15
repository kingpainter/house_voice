# House Voice – Project Status

**Version:** 2.2.0
**Date:** 2026-05-14
**Status:** Active development – v2.2.0 complete, Gold tier in progress

---

## Overall Progress

| Phase | Status |
|-------|--------|
| v1.0 – Core TTS service | ✅ Complete |
| v2.0 – UI Panel + WebSocket API | ✅ Complete |
| v2.1 – Stability + code quality | ✅ Complete |
| v2.2 – Speaker groups, queue, conditions, history | ✅ Complete |
| Gold tier compliance | 🔄 In progress (`test_full_coverage` remaining) |

---

## Files – Current State

| File | Version | Notes |
|------|---------|-------|
| `__init__.py` | 2.2.0 | +`say_text` service, groups init, engine lifecycle, `say_text` handler |
| `manifest.json` | 2.2.0 | Bumped |
| `const.py` | 2.2.0 | +`SERVICE_SAY_TEXT`, `CONF_QUIET_*`, `PRIORITIES`, `STORAGE_GROUPS_KEY` |
| `config_flow.py` | 2.2.0 | +Options Flow for quiet hours start/end |
| `voice_engine.py` | 2.2.0 | +queue, groups, conditions, history, `say_text`, configurable quiet hours |
| `groups.py` | 2.2.0 | NEW – speaker group storage + `resolve_speakers()` |
| `storage.py` | 2.1.0 | Unchanged |
| `panel.py` | 2.0.0 | Unchanged |
| `websocket.py` | 2.2.0 | 9 commands: +`get_groups`, `save_group`, `delete_group`, `get_history` |
| `sensor.py` | 2.0.0 | Unchanged |
| `system_health.py` | 2.2.0 | +`groups_count`, `queue_size` |
| `diagnostics.py` | 2.2.0 | +`groups_count`, `group_ids`, `history_count`, quiet hours config |
| `repairs.py` | 2.0.0 | Unchanged |
| `strings.json` | 2.2.0 | +Options Flow, `say_text` service, `condition` field |
| `quality_scale.yaml` | 2.0.0 | Unchanged |
| `house-voice-panel.js` | 2.2.0 | 3-tab layout: Events / Groups / History; condition badge; group picker |
| `translations/en.json` | 2.2.0 | +Options Flow, `say_text`, `condition` |
| `translations/da.json` | 2.2.0 | +Options Flow, `say_text`, `condition` |
| `hacs.json` | 2.0.0 | Unchanged |
| `.github/workflows/tests.yml` | 2.0.0 | Unchanged |
| `requirements-test.txt` | 2.0.0 | Unchanged |
| `blueprints/house_voice_say.yaml` | 2.2.0 | NEW – automation blueprint |

---

## Services

| Service | Registered | Schema validated | Notes |
|---------|------------|-----------------|-------|
| `house_voice.say` | ✅ | ✅ | Speaks stored event |
| `house_voice.say_text` | ✅ | ✅ | Ad-hoc text, group refs, Jinja2 |
| `house_voice.add_event` | ✅ | ✅ | +`condition` field |
| `house_voice.delete_event` | ✅ | ✅ | |
| `house_voice.test_event` | ✅ | ✅ | `bypass_spam=True` |

---

## WebSocket API (websocket.py) — 9 commands

| Command | Type | Notes |
|---------|------|-------|
| `house_voice/get_events` | sync | All stored events |
| `house_voice/get_media_players` | sync | All `media_player` entities |
| `house_voice/save_event` | async | +`condition` field |
| `house_voice/delete_event` | async | |
| `house_voice/test_event` | async | `bypass_spam=True`, `ServiceValidationError` surfaced |
| `house_voice/get_groups` | sync | All speaker groups |
| `house_voice/save_group` | async | Create/update group |
| `house_voice/delete_group` | async | Delete group |
| `house_voice/get_history` | sync | In-memory history (50 entries, newest first) |

---

## UI Panel (house-voice-panel.js)

| Feature | Status | Notes |
|---------|--------|-------|
| Events tab | ✅ | Cards with condition badge, group speaker display |
| Groups tab | ✅ | Create/edit/delete speaker groups |
| History tab | ✅ | Last 50 TTS events with status colours |
| Condition field in form | ✅ | Jinja2 input with hint |
| Group picker in event form | ✅ | Groups above individual speakers |
| Search (events) | ✅ | |
| Import/Export events | ✅ | |
| Stats bar | ✅ | Events + groups count + today + quiet hours |
| Indeklima Designer design | ✅ | Teal `#14b8a6` / Emerald `#34d399` |

---

## Voice Engine (voice_engine.py)

| Feature | Status | Notes |
|---------|--------|-------|
| Spam filter | ✅ | 30 sec same event |
| Spam bypass | ✅ | `bypass_spam=True` for test calls |
| Quiet hours (configurable) | ✅ | Read from `entry.options` at call time |
| Jinja2 templates | ✅ | Message rendering with fallback |
| Conditional playback | ✅ | Jinja2 condition field, fail-open on error |
| Speaker group resolution | ✅ | `group:id` prefix resolved via `HouseVoiceGroups` |
| Async TTS queue | ✅ | `asyncio.Queue`, critical jumps queue |
| Event history log | ✅ | In-memory deque, 50 entries |
| `say_text` method | ✅ | Ad-hoc TTS without stored event |
| `ultra_tts` non-blocking | ✅ | `blocking=False` |
| Repair issue on failure | ✅ | |
| Sensor increment | ✅ | Safely wrapped |
| Type hints + docstrings | ✅ | Full coverage |

---

## Known Issues / Technical Debt

| Item | Priority | Note |
|------|----------|------|
| Tests need updating | Medium | New features not yet covered: groups, history, conditions, `say_text`, queue |
| `hass.data[DOMAIN]` → `entry.runtime_data` | Low | Deferred to v3 |
| Native `ultra_tts.py` | V3 | Replaces YAML script with Python |
| Blueprint folder must be created manually | One-time | `blueprints/` directory doesn't auto-create |

---

## Quality Scale

| Tier | Status |
|------|--------|
| 🥉 Bronze | ✅ Complete |
| 🥈 Silver | ✅ Complete |
| 🥇 Gold | 🔄 `test_full_coverage` remaining |

---

## Next Recommended Actions

1. Create `blueprints/` folder in repo root, place `house_voice_say.yaml` inside
2. Push to GitHub → verify CI passes
3. HA restart → test: groups, conditions, history tab, quiet hours Options Flow
4. Update tests for v2.2.0 (groups, history, conditions, say_text, queue)
5. Native `ultra_tts.py` (v3)
