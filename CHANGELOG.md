# Changelog

All notable changes to House Voice Manager are documented here.

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
