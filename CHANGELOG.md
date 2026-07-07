# Changelog

All notable changes to House Voice Manager are documented here.

---

## [3.2.0] – 2026-07-07

### Added
- **Condition Library** (`storage.py` – `HouseVoiceConditions`) – named, reusable conditions replace raw Jinja2 template conditions on events. Each condition maps an ID to a label, `entity_id` and expected state (e.g. `nogen_hjemme` → `binary_sensor.nogen_hjemme` == `on`).
- `voice_engine._eval_conditions()` evaluates a list of condition IDs with **AND logic** before playback. Fail-open behaviour: an unknown condition ID or an unavailable entity does not block playback (logged as a warning instead).
- Events now store `conditions: list[str]` (condition IDs) instead of a single raw Jinja2 `condition` string.
- 3 new WebSocket commands: `get_conditions`, `save_condition`, `delete_condition` (12 commands total, up from 9).
- Panel: new Condition Library section on the Events tab with its own add/edit/delete flyout form, plus a condition checkbox list and badge (⚡) on the event form/cards.

### Changed
- `ws_save_event` schema: `conditions` (list) replaces the old free-text `condition` field.
- `strings.json` / `translations/en.json` / `translations/da.json`: `add_event` service field renamed from `condition` (singular, described a raw Jinja2 template) to `conditions` (plural, list of Condition Library IDs) — the old strings no longer matched the actual `conditions` field in the `add_event` service schema.
- `services.yaml` fully rewritten to match the actual service schemas in `__init__.py`: added the missing `say_text` service entirely, and added `priority`/`volume`/`conditions` fields to `add_event` (previously only `event`/`message`/`speakers` were listed). All fields now use proper HA selectors (`text`, `select`, `number` with slider) instead of bare `example` values, so the Developer Tools → Services UI now renders correct input controls.
- `house-voice-panel.js` reload button no longer falls back to the incorrect `reload_custom_templates` service call when the config entry ID can't be resolved. It now fails loudly with a clear notification instructing manual reload via Settings → Devices & Services, instead of silently calling a service that reloads Jinja2 templates rather than this integration.

### Fixed
- Version numbers in `groups.py`, `ultra_tts.py`, `__init__.py`, `panel.py` and `manifest.json` were out of sync with `const.py`/`voice_engine.py`/`websocket.py`/`storage.py`/`config_flow.py` after the Condition Library was implemented. All files now consistently report 3.2.0.

### Added (continued)
- `tests/test_conditions.py` – full coverage of `HouseVoiceConditions` storage (load/add/delete/get) and the `get_conditions`/`save_condition`/`delete_condition` WebSocket commands. The AND-logic evaluation itself (`_eval_conditions`) was already covered in `test_voice_engine_v22.py`.
- `tests/test_ultra_tts_v32.py` – duck-threshold coverage (idle vs. playing-above/below-0.25 volume), `_find_heos_sibling` (device_id strategy, unique_id fallback, no-match, missing-entry), `_needs_queue_clear` via `app_id`, and the new configurable `tts_entity`.
- **`TTS_ENTITY` configurable via Options Flow** – new `CONF_TTS_ENTITY`/`DEFAULT_TTS_ENTITY` in `const.py`. `UltraTTS.__init__` now accepts an optional `tts_entity` parameter (defaults to `tts.home_assistant_cloud`). `voice_engine._execute_tts` reads the configured entity from `entry.options` on every call. Options Flow form extended with a text field for the TTS entity ID.

### Deferred
- `hass.data[DOMAIN]` → `entry.runtime_data` migration is intentionally **not** included in this release. It touches ~10 files plus the entire test suite's mocking pattern, and cannot be verified locally (no Python execution available in this environment) — it needs an explicit go-ahead and manual `pytest` verification by the maintainer before being attempted.

---

## [3.1.1] – 2026-05-23

### Fixed
- **Volume falder under TTS** (`ultra_tts.py`): Duck-logikken brugte `original_volume`
  som base i stedet for den konfigurerede `volume`. Idle MA-speaker rapporterer
  `volume_level: 0.11–0.16` — over den gamle `0.05`-grænse — så TTS spillede ved
  `0.45 * 0.25 = 0.11` i stedet for `0.45`. Duck aktiveres nu kun hvis
  `state == 'playing'` OG `volume > 0.25`. Ellers sættes TTS direkte til konfigureret volumen.
- **HEOS kø ryddes på forkert entity**: `clear_playlist` blev kaldt på
  `media_player.kokken_2` (Music Assistant), men den interne kø sidder på
  `media_player.kokken` (HEOS direkte). Ny `_find_heos_sibling()` finder HEOS-entityen
  via to strategier: (1) samme `device_id`, (2) matching `unique_id` — MA bruger
  HEOS player_id som `unique_id`. Virker automatisk uden manuel konfiguration.
- **Platform-detection** bruger nu `state.attributes["app_id"] == "music_assistant"`
  som pålidelig første check, med entity registry som fallback.
- Debug-WARNING linjer fjernet fra `ultra_tts.py` og `voice_engine.py`.

---

## [3.0.2] – 2026-05-23

### Fixed
- **Panel reload crash** (`panel.py`): After a reload, `async_register_static_paths`
  threw `RuntimeError: Added route will never be executed, method GET is already registered`
  because aiohttp's HTTP router is permanent across reloads. Fixed by tracking static path
  registration with a session-level key (`house_voice_static_path_registered`) that is
  never cleared on unload. The static path is now only registered once per HA session;
  the sidebar panel entry is still re-registered normally after each reload.
- Added 2 new tests in `test_panel.py`: reload safety (static path called once) and
  session key survives unload. Total: 129 tests.

---

## [3.0.1] – 2026-05-23

### Fixed
- **HEOS queue accumulation** (`ultra_tts.py`): HEOS speakers (Denon/Marantz) accumulate
  TTS mp3 files in their internal queue and replay old messages on subsequent TTS calls.
  `UltraTTS` now calls `media_player.clear_playlist` after every TTS on HEOS speakers.
  The `eid=4` error ("Requested data not available") returned when the queue is already
  empty is silently ignored — this is normal HEOS behaviour since HA 2025.2.
- `_is_heos_speaker()` uses the HA entity registry (`entry.platform == "heos"`) to detect
  HEOS speakers automatically — no manual configuration required.
- Added 5 new tests in `test_ultra_tts.py` covering HEOS detection, queue clear,
  empty-queue error handling, and non-HEOS speaker guard. Total: 125 tests.

---

## [3.0.0] – 2026-05-23

### Added
- **`ultra_tts.py`** – native Python TTS executor replaces the YAML `script.ultra_tts`.
  Implements the full duck → speak → wait → restore cycle directly in Python:
  - Reads current `volume_level` from each speaker's state before ducking
  - Duck factors: `critical` → mute (0.0), `normal` → 25%, `info` → 40% of original
  - 1-second settle delay after duck before speaking
  - Calls `tts.speak` via `tts.home_assistant_cloud`
  - Dynamic post-speech delay: `ceil(len(message) / 12)`, minimum 3 seconds
  - Volume restore runs in `finally` block – guaranteed even if `tts.speak` fails
  - Comma-separated multi-speaker strings are split and handled in parallel
  - Graceful fallback on `volume_set` failure (logged, speech continues)
- `test_ultra_tts.py` – 17 tests covering `_dynamic_delay`, `_get_volumes`,
  `_set_volumes`, `async_speak` full flow (duck/speak/restore), critical mute,
  TTS failure restore, empty speaker guard, multi-speaker comma split.

### Changed
- `voice_engine._execute_tts` now calls `UltraTTS.async_speak` instead of
  `script.ultra_tts`. Error handling and Repair issue creation unchanged.
- `const.py`, `manifest.json`, `voice_engine.py`, `__init__.py` → version 3.0.0.

### Removed
- `script.ultra_tts` is no longer called by House Voice. The YAML file
  (`ultra_tts.yaml`) can be kept as standalone fallback but is not required.

---

## [2.2.1] – 2026-05-23

### Added
- `test_groups.py` – 12 new tests covering `HouseVoiceGroups`: `async_load`, `add_group`,
  `delete_group`, `get_group`, and all `resolve_speakers` cases (plain, group ref, mixed,
  dedup, unknown group, empty list).
- `test_voice_engine_v22.py` – 22 new tests for v2.2.0 `VoiceEngine` features: async queue,
  `bypass_spam`, conditions (true/false/error/fail-open), `say_text` (quiet hours, critical
  bypass, no speakers), group resolution via engine, history log (spoken/spam/quiet hours),
  history ordering and max-50 cap, quiet hours from `entry.options`, queue worker lifecycle.
- `test_websocket.py` – 14 new tests for `get_groups`, `save_group`, `delete_group`,
  `get_history` WebSocket commands.
- Queue worker supervision in `VoiceEngine._restart_worker_if_dead()` – called before
  every enqueue. If the worker task has died unexpectedly, the failure is logged and the
  worker is automatically restarted so queued messages are never silently dropped.

### Changed
- `conftest.py` updated to v2.2.0: new `mock_groups`, `mock_entry` fixtures; `mock_engine`
  uses correct 4-parameter `VoiceEngine` signature; `mock_hass` exposes `hass.loop`.
- `voice_engine._queue_worker`: `asyncio.CancelledError` is now re-raised correctly so
  `stop()` can join the task cleanly; event_id is included in worker error log messages.
- `voice_engine._enqueue`: calls `_restart_worker_if_dead()` before putting a job in the
  queue to guard against silent worker death.
- `sample_event` fixture now includes `condition: ""` field to match v2.2.0 event structure.

---

## [2.2.0] – 2026-05-14

### Added
- **Speaker Groups** (`groups.py`) – define named groups of media players (e.g. `alle_rum`, `stueetage`).
  Events and `say_text` can reference groups via `group:<id>` prefix. Groups resolve to flat,
  deduplicated speaker lists at playback time.
- **Options Flow** (`config_flow.py`) – quiet hours start/end are now configurable via
  Settings → Devices & Services → House Voice → Configure. Default remains 22:00–07:00.
- **`house_voice.say_text` service** – ad-hoc TTS without a stored event. Supports Jinja2 templates,
  group references, priority and volume. Subject to quiet hours but no spam filter.
- **Automation Blueprint** (`blueprints/house_voice_say.yaml`) – trigger a House Voice event when
  any entity changes state. Optional from/to state and time window restrictions.
- **Event history log** – in-memory ring buffer (50 entries) tracking all TTS calls with timestamp,
  event ID, message and status (`spoken`, `blocked_spam`, `blocked_quiet_hours`, `blocked_condition`).
  Exposed via `house_voice/get_history` WebSocket command and History tab in the panel.
- **Conditional playback** – optional `condition` field on events (Jinja2 expression). Event only
  plays if the condition evaluates to true. Blocked events are logged in history as `blocked_condition`.
- **Async TTS queue** – `VoiceEngine` now routes all TTS through an `asyncio.Queue` worker.
  Ensures announcements never overlap. `critical` priority inserts at queue front.
- **Groups tab** in sidebar panel – create, edit and delete speaker groups with speaker checkboxes.
- **History tab** in sidebar panel – shows the last 50 TTS events with time, event ID, message
  and colour-coded status.
- **Condition field** in event form – Jinja2 input with hint text and condition badge on event card.
- **Group references in event form** – groups appear above individual speakers in the checkbox list.
- Stats bar shows group count alongside event count.
- WebSocket API expanded from 5 to 9 commands: added `get_groups`, `save_group`, `delete_group`,
  `get_history`.
- `strings.json` / `en.json` / `da.json` updated with Options Flow and `say_text` translations.
- `diagnostics.py` extended with `groups_count`, `group_ids`, `history_count`,
  `quiet_hours_start`, `quiet_hours_end`.
- `system_health.py` extended with `groups_count` and `queue_size`.
- `STORAGE_GROUPS_KEY`, `CONF_QUIET_START`, `CONF_QUIET_END`, `DEFAULT_QUIET_START/END`,
  `PRIORITIES`, `SERVICE_SAY_TEXT` added to `const.py`.

### Changed
- `voice_engine.py`: quiet hours now reads from `entry.options` at call time (live, no restart needed).
- `voice_engine.py`: `_is_quiet_hours()` now handles same-day ranges (e.g. 01–06) in addition to
  overnight ranges (e.g. 22–07).
- `voice_engine.py`: `VoiceEngine.__init__` now takes `groups` and `entry` parameters.
- `voice_engine.py`: `VoiceEngine` has `start()` / `stop()` lifecycle methods for queue worker.
- `__init__.py`: registers `HouseVoiceGroups`, starts/stops engine queue worker, adds `say_text` service.
- `__init__.py`: `handle_add` now persists optional `condition` field.
- `__init__.py`: unload now awaits `engine.stop()`.
- Panel: single-page layout replaced by 3-tab layout (Events / Groups / History).
- Panel: speaker selector in event form shows groups section above individual speakers.
- Panel: condition badge (⚡) shown on event cards that have a condition.

---

## [2.1.0] – 2026-05-14

### Changed
- `voice_engine.py`: `ultra_tts` called with `blocking=False`
- `voice_engine.py`: `say()` now accepts `bypass_spam: bool = False` parameter
- `__init__.py`: `handle_test` uses `bypass_spam=True`
- `__init__.py`: log messages use `VERSION` from const
- `websocket.py`: `vol.In` + `vol.Length(min=1)` in WS schema
- `websocket.py`: `ws_test_event` catches `ServiceValidationError` separately
- `storage.py`: full type hints and docstrings; non-dict guard in `async_load`
- `house-voice-panel.js`: Indeklima Designer language (teal #14b8a6 / emerald #34d399)

### Fixed
- `storage.py`: `async_load` guards against corrupt storage returning a non-dict value
- `voice_engine.py`: speakers coerced via `str()` fallback when not a list

---

## [2.0.0] – 2026-03-11

### Added
- Full UI sidebar panel, WebSocket API (5 commands), Config Flow
- Spam filter, quiet hours, Jinja2 templates, statistics sensor
- System Health, Diagnostics, Repairs, Translations (EN + DA)
- HACS support, GitHub Actions CI, 55 automated tests

---

## [1.0.0] – 2026-01-01

### Added
- Initial release – core TTS service routing through `script.ultra_tts`
