# House Voice – Project Status

**Version:** 3.0.0
**Date:** 2026-05-23
**Status:** Active development – v3.0.0 complete

---

## Overall Progress

| Phase | Status |
|-------|--------|
| v1.0 – Core TTS service | ✅ Complete |
| v2.0 – UI Panel + WebSocket API | ✅ Complete |
| v2.1 – Stability + code quality | ✅ Complete |
| v2.2 – Speaker groups, queue, conditions, history | ✅ Complete |
| v2.2.1 – Test coverage + queue supervision | ✅ Complete |
| v3.0 – Native ultra_tts.py | ✅ Complete |
| Gold tier compliance | 🔄 `test_full_coverage` remaining |

---

## Files – Current State

| File | Version | Notes |
|------|---------|-------|
| `__init__.py` | 2.2.0 | +`say_text` service, groups init, engine lifecycle, `say_text` handler |
| `manifest.json` | 2.2.0 | Bumped |
| `const.py` | 2.2.0 | +`SERVICE_SAY_TEXT`, `CONF_QUIET_*`, `PRIORITIES`, `STORAGE_GROUPS_KEY` |
| `config_flow.py` | 2.2.0 | +Options Flow for quiet hours start/end |
| `voice_engine.py` | 3.0.0 | `_execute_tts` kalder nu `UltraTTS` i stedet for `script.ultra_tts` |
| `ultra_tts.py` | 3.0.0 | NY – native duck/speak/restore Python executor |
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

## Tests

| Fil | Tests | Dækker |
|-----|-------|--------|
| `test_init.py` | 3 | Setup, unload, service registrering |
| `test_storage.py` | 7 | Add, get, delete, overwrite |
| `test_voice_engine.py` | 9 | Spam, quiet hours, Jinja2, speakers, TTS (v2.0 baseline) |
| `test_voice_engine_v22.py` | 22 | Queue, bypass_spam, conditions, say_text, groups, historik, lifecycle |
| `test_groups.py` | 12 | async_load, add, delete, get, resolve_speakers (alle cases) |
| `test_sensor.py` | 6 | Increment, midnight reset, attributter |
| `test_config_flow.py` | 3 | Form, submit, duplicate abort |
| `test_websocket.py` | 24 | Alle 9 WS commands + validering |
| `test_panel.py` | 5 | Register, double-guard, unregister |
| `test_diagnostics.py` | 4 | Fields, quiet hours, missing data |
| `test_system_health.py` | 4 | Fields, no storage, register |
| `test_repairs.py` | 4 | Create issue, delete issue, fix flow |
| `test_ultra_tts.py` | 17 | `_dynamic_delay`, `_get_volumes`, `_set_volumes`, `async_speak` full flow |
| **Total** | **120** | |

CI: GitHub Actions kører ved hvert push til `main`/`master`/`dev`.

---

## Known Issues / Technical Debt

Ingen. 🟢

---

## Quality Scale

| Tier | Status |
|------|--------|
| 🥉 Bronze | ✅ Complete |
| 🥈 Silver | ✅ Complete |
| 🥇 Gold | 🔄 `test_full_coverage` remaining |

---

## Next Recommended Actions

1. Push til GitHub → verificer CI er grøn
2. HA genstart → test TTS end-to-end på en rigtig speaker (tjek duck/restore i loggen)
3. `hass.data[DOMAIN]` → `entry.runtime_data` migration
4. `TTS_ENTITY` i `ultra_tts.py` gøres konfigurerbar via Options Flow
