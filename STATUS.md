# House Voice – Project Status

**Version:** 2.0.0
**Date:** 2026-03-11
**Status:** Active development – v2.0.0 complete, v3 features complete, Gold tier in progress

---

## Overall Progress

| Phase | Status |
|-------|--------|
| v1.0 – Core TTS service | ✅ Complete |
| v2.0 – UI Panel + WebSocket API | ✅ Complete |
| v3.0 – Smart features | ✅ Complete |
| Gold tier compliance | 🔄 In progress (`test_full_coverage` remaining) |

---

## Files – Current State

| File | Version | Notes |
|------|---------|-------|
| `__init__.py` | 2.0.0 | Setup, services, WebSocket, panel, sensor platform, `ConfigEntryNotReady` |
| `manifest.json` | 2.0.0 | `config_flow: true`, `iot_class: local_push`, `quality_scale: silver` |
| `const.py` | 2.0.0 | All constants defined incl. panel + storage |
| `services.yaml` | 2.0.0 | 4 services defined |
| `voice_engine.py` | 2.0.0 | Speakers fix + spam filter + quiet hours + Jinja2 + sensor + HA exceptions |
| `storage.py` | 2.0.0 | HA Storage API wrapper |
| `panel.py` | 2.0.0 | Sidebar panel registration with cache-busting + admin guard |
| `websocket.py` | 2.0.0 | 5 WebSocket commands registered |
| `sensor.py` | 2.0.0 | `sensor.house_voice_today` daily TTS counter |
| `system_health.py` | 2.0.0 | System Health info – fixed: `async_register` is now synchronous |
| `diagnostics.py` | 2.0.0 | HA diagnostics download support |
| `repairs.py` | 2.0.0 | NEW – Repair issue if `script.ultra_tts` is missing |
| `strings.json` | 2.0.0 | NEW – Master translation strings (config flow, services, exceptions, repairs) |
| `quality_scale.yaml` | 2.0.0 | NEW – Bronze + Silver done, Gold in progress |
| `house-voice-panel.js` | 2.0.0 | Stats bar, search field, import/export |
| `translations/en.json` | 2.0.0 | Full English translations |
| `translations/da.json` | 2.0.0 | Full Danish translations |
| `hacs.json` | 2.0.0 | NEW – HACS support |
| `.github/workflows/tests.yml` | 2.0.0 | NEW – GitHub Actions CI |
| `requirements-test.txt` | 2.0.0 | NEW – Test dependencies |

---

## Services

| Service | Registered | Validated | Notes |
|---------|------------|-----------|-------|
| `house_voice.say` | ✅ | ✅ | `vol.Schema` + `ServiceValidationError` |
| `house_voice.add_event` | ✅ | ✅ | Full `vol.Schema` incl. priority + volume range |
| `house_voice.delete_event` | ✅ | ✅ | `vol.Schema` added |
| `house_voice.test_event` | ✅ | ✅ | Identical to `say` – intentional |

---

## WebSocket API (websocket.py)

| Command | Type | Notes |
|---------|------|-------|
| `house_voice/get_events` | sync | Returns all stored events |
| `house_voice/get_media_players` | sync | Returns all `media_player` entities from HA |
| `house_voice/save_event` | async | Full input validation |
| `house_voice/delete_event` | async | Validates event exists before deleting |
| `house_voice/test_event` | async | Triggers `engine.say()` directly |

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
| HA theme support | ✅ | Uses HA CSS variables throughout |
| Admin-only access | ✅ | `require_admin: true` in `panel.py` |
| Cache-busting | ✅ | `?v=VERSION&m=mtime` on JS URL |
| Stats bar (header) | ✅ | Events count, today count, quiet hours status |
| Search field | ✅ | Live filter on event ID and message |
| Import events | ✅ | Upload JSON – validates + saves all events |
| Export events | ✅ | Download all events as `house_voice_events.json` |

---

## Voice Engine (voice_engine.py)

| Feature | Status | Notes |
|---------|--------|-------|
| Speakers list → string fix | ✅ | `isinstance` check before `ultra_tts` call |
| Spam filter | ✅ | Same event blocked within 30 sec |
| Quiet hours | ✅ | 22:00–07:00 – only `critical` passes through |
| Jinja2 templates | ✅ | `Template().async_render()` with fallback |
| Sensor increment | ✅ | Increments `sensor.house_voice_today` after TTS |
| Empty speakers guard | ✅ | `ServiceValidationError` if speakers is empty |
| `ultra_tts` error handling | ✅ | `HomeAssistantError` + Repair issue raised |
| `_last_spoken` cleanup | ✅ | Entries older than 1 hour removed automatically |
| HA exception types | ✅ | `ServiceValidationError` / `HomeAssistantError` with translation keys |

---

## HA Compliance

| Feature | Status | Notes |
|---------|--------|-------|
| `ConfigEntryNotReady` | ✅ | Raised if storage fails to load |
| `ServiceValidationError` | ✅ | User errors (unknown event, no speakers) |
| `HomeAssistantError` | ✅ | Communication errors (ultra_tts failure) |
| Localized exceptions | ✅ | `translation_domain` + `translation_key` + placeholders |
| Repairs | ✅ | `repairs.py` – UI issue if `ultra_tts` missing |
| System Health | ✅ | `system_health.py` – sync `async_register` |
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
| **Total** | **55** | |

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

None. 🟢

---

## V3 Features – Status

| Feature | Status | File |
|---------|--------|------|
| Speakers list fix | ✅ Done | `voice_engine.py` |
| Spam filter (30 sec) | ✅ Done | `voice_engine.py` |
| Quiet hours (22:00–07:00) | ✅ Done | `voice_engine.py` |
| Dynamic messages (Jinja2) | ✅ Done | `voice_engine.py` |
| Statistics sensor | ✅ Done | `sensor.py` |
| System health | ✅ Done | `system_health.py` |
| Diagnostics | ✅ Done | `diagnostics.py` |
| Stats bar in panel | ✅ Done | `house-voice-panel.js` |
| Search + Import/Export | ✅ Done | `house-voice-panel.js` |
| HA exception compliance | ✅ Done | `voice_engine.py` |
| Repairs | ✅ Done | `repairs.py` |
| Translations (EN + DA) | ✅ Done | `strings.json`, `en.json`, `da.json` |
| HACS support | ✅ Done | `hacs.json` |
| GitHub Actions CI | ✅ Done | `.github/workflows/tests.yml` |
| Morning briefing | ⬜ Not started | Weather + calendar + temperature |

---

## Next Recommended Actions

1. Push to GitHub → verify CI passes (GitHub Actions)
2. Update `quality_scale.yaml` `test_full_coverage` → `done` once CI is green
3. **Morning briefing** – when ready to build
