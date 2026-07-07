# House Voice – Project Status

**Version:** 3.2.0
**Date:** 2026-07-07
**Status:** Stabil

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
| v3.0.1 – HEOS queue fix | ✅ Complete |
| v3.0.2 – Panel reload crash fix | ✅ Complete |
| v3.1.1 – Volume + HEOS kø fix | ✅ Complete |
| v3.2.0 – Condition Library | ✅ Complete |
| Gold tier compliance | 🔄 `test_full_coverage` – Condition Library + UltraTTS v3.2.0 tests added 2026-07-07, `hass.data`→`runtime_data` migration still pending |

---

## Files – Current State

| File | Version | Notes |
|------|---------|-------|
| `__init__.py` | 3.2.0 | +`say_text` service, groups + conditions init, engine lifecycle |
| `manifest.json` | 3.2.0 | version bumped |
| `const.py` | 3.2.0 | +`SERVICE_SAY_TEXT`, `CONF_QUIET_*`, `CONF_TTS_ENTITY`, `PRIORITIES`, `STORAGE_GROUPS_KEY`, `STORAGE_CONDITIONS_KEY` |
| `config_flow.py` | 3.2.0 | Options Flow for quiet hours start/end + TTS entity |
| `voice_engine.py` | 3.2.0 | `_execute_tts` → `UltraTTS` (now with configurable `tts_entity`), queue worker supervision, Condition Library evaluation (`_eval_conditions`) |
| `ultra_tts.py` | 3.2.0 | Native duck/speak/restore, HEOS sibling detection, MA app_id check, configurable `tts_entity` |
| `panel.py` | 3.2.0 | Session-level static path guard — reload crash fix |
| `groups.py` | 3.2.0 | Speaker group storage + `resolve_speakers()` |
| `storage.py` | 3.2.0 | +`HouseVoiceConditions` – condition library storage |
| `websocket.py` | 3.2.0 | 12 commands (+`get/save/delete_condition`) |
| `sensor.py` | 2.0.0 | Unchanged |
| `system_health.py` | 2.2.0 | +`groups_count`, `queue_size` |
| `diagnostics.py` | 2.2.0 | +`groups_count`, `group_ids`, `history_count`, quiet hours config |
| `repairs.py` | 2.0.0 | Unchanged |
| `services.yaml` | 3.2.0 | Rewritten — added `say_text`, added `priority`/`volume`/`conditions` to `add_event`, proper selectors throughout |
| `strings.json` | 3.2.0 | `conditions` field renamed to match service schema — was `condition` (Jinja2 string), now `conditions` (list) |
| `quality_scale.yaml` | 2.0.0 | Unchanged |
| `house-voice-panel.js` | 3.2.0 | 3-tab layout + Condition Library section + fixed reload-knap |
| `translations/en.json` | 3.2.0 | `conditions` field renamed to match service schema |
| `translations/da.json` | 3.2.0 | `conditions` field renamed to match service schema |
| `hacs.json` | 2.0.0 | Unchanged |
| `.github/workflows/tests.yml` | 2.0.0 | Unchanged |
| `requirements-test.txt` | 2.0.0 | Unchanged |
| `blueprints/house_voice_say.yaml` | 2.2.0 | Automation blueprint |

---

## Services

| Service | Registreret | Valideret | Notes |
|---------|-------------|-----------|-------|
| `house_voice.say` | ✅ | ✅ | Afspiller gemt event |
| `house_voice.say_text` | ✅ | ✅ | Ad-hoc tekst, gruppe-refs, Jinja2 |
| `house_voice.add_event` | ✅ | ✅ | +`condition` felt |
| `house_voice.delete_event` | ✅ | ✅ | |
| `house_voice.test_event` | ✅ | ✅ | `bypass_spam=True` |

---

## WebSocket API — 9 commands

| Command | Type | Notes |
|---------|------|-------|
| `house_voice/get_events` | sync | Alle gemte events |
| `house_voice/get_media_players` | sync | Alle `media_player` entities |
| `house_voice/save_event` | async | +`condition` felt |
| `house_voice/delete_event` | async | |
| `house_voice/test_event` | async | `bypass_spam=True` |
| `house_voice/get_groups` | sync | Alle højttalergrupper |
| `house_voice/save_group` | async | Opret/opdater gruppe |
| `house_voice/delete_group` | async | Slet gruppe |
| `house_voice/get_history` | sync | In-memory historik (50 entries, nyeste først) |
| `house_voice/get_conditions` | sync | Alle gemte betingelser i biblioteket |
| `house_voice/save_condition` | async | Opret/opdater betingelse |
| `house_voice/delete_condition` | async | Slet betingelse |

---

## UI Panel (house-voice-panel.js)

| Feature | Status | Notes |
|---------|--------|-------|
| Events tab | ✅ | Cards med condition badge, gruppe-speaker visning |
| Groups tab | ✅ | Opret/rediger/slet højttalergrupper |
| History tab | ✅ | Sidste 50 TTS-kald med farvekoded status |
| Condition felt i formular | ✅ | Jinja2 input med hint |
| Gruppe-picker i event-formular | ✅ | Grupper over individuelle højttalere |
| Søgning (events) | ✅ | |
| Import/Export events | ✅ | |
| Stats bar | ✅ | Events + grupper + today + quiet hours |
| Reload-knap | ✅ | Genindlæser integration fra panelet |
| Indeklima Designer design | ✅ | Teal `#14b8a6` / Emerald `#34d399` |

---

## Voice Engine (voice_engine.py)

| Feature | Status | Notes |
|---------|--------|-------|
| Spam filter | ✅ | 30 sek samme event |
| Spam bypass | ✅ | `bypass_spam=True` til test-kald |
| Quiet hours (konfigurerbar) | ✅ | Læses fra `entry.options` ved hvert kald |
| Jinja2 templates | ✅ | Besked-rendering med fallback |
| Betinget afspilning | ✅ | Jinja2 condition felt, fail-open ved fejl |
| Gruppe-opløsning | ✅ | `group:id` prefix via `HouseVoiceGroups` |
| Async TTS kø | ✅ | `asyncio.Queue`, critical springer fremad |
| Queue worker supervision | ✅ | `_restart_worker_if_dead()` ved hvert enqueue |
| Event historik log | ✅ | In-memory deque, 50 entries |
| `say_text` metode | ✅ | Ad-hoc TTS uden gemt event |
| Repair issue ved fejl | ✅ | |
| Sensor increment | ✅ | Wrapped i try/except |

---

## UltraTTS (ultra_tts.py)

| Feature | Status | Notes |
|---------|--------|-------|
| Volume set før TTS | ✅ | Sættes til konfigureret volume |
| Duck ved aktiv afspilning | ✅ | Kun hvis `state == playing` AND `volume > 0.25` |
| Volume restore | ✅ | `finally`-blok — garanteret selv ved fejl |
| MA platform-detection | ✅ | Via `state.attributes["app_id"] == "music_assistant"` |
| HEOS sibling-detection | ✅ | Strategi 1: device_id. Strategi 2: matching unique_id |
| HEOS kø pre-clear | ✅ | `clear_playlist` på HEOS-entity før TTS |
| Speech delay | ✅ | `ceil(len/10) + 3s HEOS buffer`, min 8s |
| Multi-speaker | ✅ | Komma-separeret string splittes |
| Volume set på sibling | ✅ | Sætter volumen på både MA og HEOS entity |

---

## Tests

| Fil | Tests | Dækker |
|-----|-------|--------|
| `test_init.py` | 3 | Setup, unload, service registrering |
| `test_storage.py` | 7 | Add, get, delete, overwrite |
| `test_voice_engine.py` | 9 | Spam, quiet hours, Jinja2, speakers (v2.0 baseline) |
| `test_voice_engine_v22.py` | 22 | Queue, bypass_spam, conditions, say_text, groups, historik, lifecycle |
| `test_groups.py` | 12 | async_load, add, delete, get, resolve_speakers |
| `test_sensor.py` | 6 | Increment, midnight reset, attributter |
| `test_config_flow.py` | 3 | Form, submit, duplicate abort |
| `test_websocket.py` | 24 | Alle 9 WS commands + validering |
| `test_panel.py` | 7 | Register, reload safety, session key, unregister |
| `test_diagnostics.py` | 4 | Fields, quiet hours, missing data |
| `test_system_health.py` | 4 | Fields, no storage, register |
| `test_repairs.py` | 4 | Create issue, delete issue, fix flow |
| `test_ultra_tts.py` | 22 | duck/speak/restore, HEOS detection, queue clear, sibling |
| `test_conditions.py` | 20 | HouseVoiceConditions storage + 3 condition WS commands (NEW 2026-07-07) |
| `test_ultra_tts_v32.py` | 10 | Duck threshold, HEOS sibling detection, app_id platform check, configurable tts_entity (NEW 2026-07-07) |
| **Total** | **159** | |

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

1. Push til GitHub → verificer CI er grøn (149 nye/eksisterende tests, kør selv `pytest` for at bekræfte – kan ikke køres herfra)
2. **`hass.data[DOMAIN]` → `entry.runtime_data` migration** – stor omskrivning, afventer eksplicit godkendelse (se "Deferred" i CHANGELOG)
3. `test_ultra_tts.py` (den oprindelige, v3.0.0-fil) kunne konsolideres med `test_ultra_tts_v32.py` på sigt – ikke nødvendigt nu

## Known Issues (fundet 2026-07-07)

- Panel reload-knap kaldte tidligere `reload_custom_templates` som fallback når `config_entry_id` ikke kunne findes – rettet, viser nu klar fejlbesked i stedet.
- `strings.json`/`en.json`/`da.json` dokumenterede et forkert felt (`condition` som Jinja2-streng) på `add_event` – rettet til `conditions` (liste af Condition Library-IDs), som matcher det faktiske service-schema.
- `services.yaml` var stadig fra v2.0.0 – manglede `say_text` og flere felter på `add_event`. **Rettet 2026-07-07** — alle 5 services har nu korrekte felter og selectors.
- Condition Library tests manglede – **rettet 2026-07-07** via `test_conditions.py` (20 tests).
- `TTS_ENTITY` var hardcoded – **rettet 2026-07-07**, nu konfigurerbar via Options Flow.
- `hass.data[DOMAIN]` → `entry.runtime_data` migration er **IKKE** udført – stor omskrivning af ~10 filer + hele testsuiten, kan ikke verificeres uden at køre pytest lokalt. Afventer eksplicit go-ahead.
