## [3.5.1] - 2026-09-24

### Fixed
- **Frontend**: Corrected syntax error in panel `_load()` finally block (indentation + method call placement)
- **Frontend**: Resolved optional chaining with assignment operators in tab visibility updates (lines 782-784)
  - Optional chaining (`?.`) operator does not support assignment in JavaScript
  - Replaced with traditional null-check pattern for proper DOM manipulation

### Details
- Bug fix commit f5d8aae: Fixed indentation error where `this._render()` was placed in comment
- Bug fix commit 50db63e: Resolved invalid optional chaining assignment pattern on tab display properties
- All 218/220 tests passing (2 pre-existing mock assertion issues unrelated to these fixes)
- Panel now loads without syntax errors in Home Assistant browser console

## [3.4.0] – 2026-09-24

### Added
- **Event Chain Manager** (`events/event_chain.py` – `EventChainManager`) – DAG-based execution engine for multi-step event sequences. Supports dependency resolution, retry logic with exponential backoff (0.5s → 1s → 2s), and per-step error handling (continue/retry/fail). Enables complex announcement workflows like "volume up → announce → delay → volume down".
- `ChainStep` dataclass for defining event chain steps with action type, target, parameters, delays, retry configuration, and dependencies.
- `ChainActionType` enum supporting: ANNOUNCEMENT, GROUP_VOLUME_UP, GROUP_VOLUME_DOWN, DELAY, CONDITION_CHECK, WEBHOOK.
- Built-in action handlers: `handle_announcement_action`, `handle_group_volume_action`, `handle_delay_action`.
- `create_announcement_chain()` factory function for standard announcement chains.
- **VolumeControllerV2** (`speaker_control/volume_controller.py`) – robust volume adjustment with 3-attempt exponential backoff (0.5s, 1s, 2s delays) and fallback strategy execution. Includes cache for speaker group volumes, bounds checking (0.0–1.0), and detailed execution tracking via `VolumeAdjustmentResult`.
- **Fallback Strategies** (`speaker_control/fallback_strategies.py`) – 5 pluggable strategies for graceful degradation when volume adjustment fails:
  - `NoOpFallback`: Log error, allow announcement to proceed (speaker may recover).
  - `ManualAdjustmentFallback`: Queue persistent notification for user to manually adjust volume.
  - `RetryWithIncreasingDelayFallback`: Wait 5 seconds and retry later.
  - `SkipVolumeAdjustmentFallback`: Skip adjustment, proceed with announcement at current volume.
  - `LogAndAlertFallback`: Log error and send system alert via persistent_notification.
- `FallbackStrategy` ABC for implementing custom fallback strategies.

### Changed
- All Sprint 2 files (`events/`, `speaker_control/`) now part of house_voice integration.
- Version bumped to 3.4.0 across all core files: `manifest.json`, `__init__.py`, `const.py`.

### Technical Details
- `EventChainManager` maintains chain registry, execution state, and action handler registry.
- Volume controller uses asyncio locks for thread-safe speaker volume caching.
- Fallback strategies return standardized `dict[str, Any]` with `success`, `strategy`, and `message`/`error` keys.
- All async/await patterns follow HA Core 2026 best practices.
- Strict type hints throughout new modules.

### Next Steps (v3.5.0 planning)
- Integrate EventChainManager into `voice_engine.py` for standard announcement chains.
- Wire up VolumeControllerV2 into existing volume control flow.
- Test event chains end-to-end with real speaker groups.
- Add test suite for event chain execution and fallback strategies.


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
