# House Voice – Project Status

**Version:** 2.1.0
**Date:** 2026-05-14
**Status:** Active development – v2.1.0 complete, Gold tier in progress

---

## Overall Progress

| Phase | Status |
|-------|--------|
| v1.0 – Core TTS service | ✅ Complete |
| v2.0 – UI Panel + WebSocket API | ✅ Complete |
| v3.0 – Smart features | ✅ Complete |
| v2.1 – Stability + code quality | ✅ Complete |
| Gold tier compliance | 🔄 In progress (`test_full_coverage` remaining) |

---

## Files – Current State

| File | Version | Notes |
|------|---------|-------|
| `__init__.py` | 2.1.0 | Service handler docstrings; log uses `VERSION` from const |
| `manifest.json` | 2.1.0 | Bumped to 2.1.0 |
| `const.py` | 2.1.0 | `VERSION = "2.1.0"` |
| `services.yaml` | 2.0.0 | Unchanged |
| `voice_engine.py` | 2.1.0 | `blocking=False`; `bypass_spam` param; type hints; docstring |
| `storage.py` | 2.1.0 | Full type hints + docstrings; non-dict guard in `async_load` |
| `panel.py` | 2.0.0 | Unchanged |
| `websocket.py` | 2.1.0 | `vol.In` + `vol.Length` in schema; `ServiceValidationError` caught in test |
| `sensor.py` | 2.0.0 | Unchanged |
| `system_health.py` | 2.0.0 | Unchanged |
| `diagnostics.py` | 2.0.0 | Unchanged |
| `repairs.py` | 2.0.0 | Unchanged |
| `strings.json` | 2.0.0 | Unchanged |
| `quality_scale.yaml` | 2.0.0 | Unchanged |
| `house-voice-panel.js` | 2.0.1 | Indeklima Designer language – teal/emerald, DM Sans/Mono, dark tokens |
| `translations/en.json` | 2.0.0 | Unchanged |
| `translations/da.json` | 2.0.0 | Unchanged |
| `hacs.json` | 2.0.0 | Unchanged |
| `.github/workflows/tests.yml` | 2.0.0 | Unchanged |
| `requirements-test.txt` | 2.0.0 | Unchanged |

---

## Services

| Service | Registered | Validated | Notes |
|---------|------------|-----------|-------|
| `house_voice.say` | ✅ | ✅ | `vol.Schema` + `ServiceValidationError` |
| `house_voice.add_event` | ✅ | ✅ | Full `vol.Schema` incl. priority + volume range |
| `house_voice.delete_event` | ✅ | ✅ | `vol.Schema` |
| `house_voice.test_event` | ✅ | ✅ | Calls `say(bypass_spam=True)` – always plays |

---

## WebSocket API (websocket.py)

| Command | Type | Notes |
|---------|------|-------|
| `house_voice/get_events` | sync | Returns all stored events |
| `house_voice/get_media_players` | sync | Returns all `media_player` entities from HA |
| `house_voice/save_event` | async | `vol.In` + `vol.Length(min=1)` in schema |
| `house_voice/delete_event` | async | Validates event exists before deleting |
| `house_voice/test_event` | async | `bypass_spam=True`; `ServiceValidationError` surfaced to panel |

---

## UI Panel (house-voice-panel.js)

| Feature | Status | Notes |
|---------|--------|-------|
| Event list view | ✅ | Cards with ID, message, priority badge, speakers, volume |
| Add event form | ✅ | Modal overlay with all fields |
| Edit event | ✅ | Event ID is read-only when editing |
| Delete event | ✅ | Confirm dialog before delete |
| Test event | ✅ | Triggers playback immediately |
| Refresh button | ✅ | Reloads events + players from backend |
| Speaker selection | ✅ | Checkboxes – supports multiple speakers |
| Volume slider | ✅ | Live % display, 5–100% in 5% steps |
| Priority selector | ✅ | Info / Normal / Critical with emoji labels |
| Notifications | ✅ | Success/error toast, auto-dismisses after 3.5s |
| HA theme support | ✅ | Indeklima Designer tokens with HA CSS variable fallbacks |
| Admin-only access | ✅ | `require_admin: true` in `panel.py` |
| Cache-busting | ✅ | `?v=VERSION&m=mtime` on JS URL |
| Stats bar (header) | ✅ | Events count, today count, quiet hours status |
| Search field | ✅ | Live filter on event ID and message |
| Import events | ✅ | Upload JSON – validates + saves all events |
| Export events | ✅ | Download all events as `house_voice_events.json` |
| Indeklima Designer design | ✅ | Teal `#14b8a6` / Emerald `#34d399`, DM Sans + DM Mono |

---

## Voice Engine (voice_engine.py)

| Feature | Status | Notes |
|---------|--------|-------|
| Speakers list → string fix | ✅ | `isinstance` check + `str()` fallback |
| Spam filter | ✅ | Same event blocked within 30 sec |
| Spam filter bypass | ✅ | `bypass_spam=True` for test calls |
| Quiet hours | ✅ | 22:00–07:00 – only `critical` passes through |
| Jinja2 templates | ✅ | `Template().async_render()` with fallback |
| Sensor increment | ✅ | Increments `sensor.house_voice_today` after TTS |
| Empty speakers guard | ✅ | `ServiceValidationError` if speakers is empty |
| `ultra_tts` non-blocking | ✅ | `blocking=False` – avoids stalling HA event loop |
| `ultra_tts` error handling | ✅ | `HomeAssistantError` + Repair issue raised |
| `_last_spoken` cleanup | ✅ | Entries older than 1 hour removed automatically |
| HA exception types | ✅ | `ServiceValidationError` / `HomeAssistantError` with translation keys |
| Type hints + docstrings | ✅ | Full coverage |

---

## HA Compliance

| Feature | Status | Notes |
|---------|--------|-------|
| `ConfigEntryNotReady` | ✅ | Raised if storage fails to load |
| `ServiceValidationError` | ✅ | User errors (unknown event, no speakers) |
| `HomeAssistantError` | ✅ | Communication errors (ultra_tts failure) |
| Localized exceptions | ✅ | `translation_domain` + `translation_key` + placeholders |
| Repairs | ✅ | `repairs.py` – UI issue if `ultra_tts` missing |
| System Health | ✅ | `system_health.py` |
| Diagnostics | ✅ | `diagnostics.py` |
| Translations | ✅ | `strings.json`, `en.json`, `da.json` |
| `quality_scale.yaml` | ✅ | Bronze ✅ Silver ✅ Gold 🔄 |

---

## Tests

| File | Tests | Coverage |
|------|-------|---------|
| `test_init.py` | 3 | Setup, unload, service registration |
| `test_storage.py` | 7 | Add, get, delete, overwrite |
| `test_voice_engine.py` | 9 | Spam, quiet hours, Jinja2, speakers, TTS |
| `test_sensor.py` | 6 | Increment, midnight reset, attributes |
| `test_config_flow.py` | 3 | Form, submit, duplicate abort |
| `test_websocket.py` | 10 | All 5 WS commands + validation |
| `test_panel.py` | 5 | Register, double-guard, unregister |
| `test_diagnostics.py` | 4 | Fields, quiet hours, missing data |
| `test_system_health.py` | 4 | Fields, no storage, register |
| `test_repairs.py` | 4 | Create issue, delete issue, fix flow |
| **Total** | **55** | ⚠️ Tests not yet updated for bypass_spam / vol.In changes |

CI: GitHub Actions runs on every push to `main`/`master`/`dev`.

---

## Quality Scale

| Tier | Status |
|------|--------|
| 🥉 Bronze | ✅ Complete |
| 🥈 Silver | ✅ Complete |
| 🥇 Gold | 🔄 `test_full_coverage` remaining |

---

## Known Issues / Technical Debt

- Tests need updating: `test_voice_engine.py` – add `bypass_spam=True` test case for `test_event`; `test_websocket.py` – `ws_save_event` now validates via voluptuous schema (some manual-validation tests may need adjustment)
- `hass.data[DOMAIN]` bør migreres til `entry.runtime_data` (HA 2026 best practice) – deferred til v3

---

## V3 Features – Status

| Feature | Status | File |
|---------|--------|------|
| Speakers list fix | ✅ Done | `voice_engine.py` |
| Spam filter (30 sec) | ✅ Done | `voice_engine.py` |
| Spam filter bypass for test | ✅ Done | `voice_engine.py` |
| Quiet hours (22:00–07:00) | ✅ Done | `voice_engine.py` |
| Dynamic messages (Jinja2) | ✅ Done | `voice_engine.py` |
| Statistics sensor | ✅ Done | `sensor.py` |
| System health | ✅ Done | `system_health.py` |
| Diagnostics | ✅ Done | `diagnostics.py` |
| Stats bar in panel | ✅ Done | `house-voice-panel.js` |
| Search + Import/Export | ✅ Done | `house-voice-panel.js` |
| Indeklima Designer UI | ✅ Done | `house-voice-panel.js` |
| HA exception compliance | ✅ Done | `voice_engine.py` |
| Repairs | ✅ Done | `repairs.py` |
| Translations (EN + DA) | ✅ Done | `strings.json`, `en.json`, `da.json` |
| HACS support | ✅ Done | `hacs.json` |
| GitHub Actions CI | ✅ Done | `.github/workflows/tests.yml` |
| Morning briefing | ⬜ Not started | Weather + calendar + temperature |
| Native `ultra_tts.py` | ⬜ Deferred to v3 | Replace YAML script with Python |
| `entry.runtime_data` migration | ⬜ Deferred to v3 | HA 2026 best practice |

---

## Next Recommended Actions

1. Push to GitHub → verify CI passes
2. Opdater `test_voice_engine.py` med `bypass_spam=True` test case
3. Opdater `test_websocket.py` for de nye voluptuous-skema regler
4. **Morning briefing** – når klar til at bygge
