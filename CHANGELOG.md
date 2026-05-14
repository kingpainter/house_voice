# Changelog

All notable changes to House Voice Manager are documented here.

---

## [2.1.0] – 2026-05-14

### Changed
- `voice_engine.py`: `ultra_tts` called with `blocking=False` – prevents stalling HA's
  async event loop during long-running TTS scripts (3–30+ seconds)
- `voice_engine.py`: `say()` now accepts `bypass_spam: bool = False` parameter –
  test calls explicitly skip the spam filter instead of implicitly sharing the same path
- `__init__.py`: `handle_test` uses `bypass_spam=True` – test always plays regardless
  of recent calls to the same event
- `__init__.py`: setup/unload log messages now read `VERSION` from `const.py` instead
  of a hardcoded string
- `__init__.py`: all service handlers have docstrings
- `websocket.py`: `ws_save_event` schema uses `vol.All(list, vol.Length(min=1))` for
  speakers and `vol.In(_VALID_PRIORITIES)` for priority – validation moved into the
  voluptuous schema instead of manual `if/return` guards
- `websocket.py`: `ws_get_media_players` rewritten as a list comprehension
- `websocket.py`: `ws_test_event` catches `ServiceValidationError` separately and
  returns `"invalid_event"` error code so the panel can show a meaningful message
- `websocket.py`: `_get_storage` / `_get_engine` have docstrings
- `storage.py`: full type hints (`dict[str, dict]`, `str | None`) and docstrings on
  all methods; `async_load` guards against non-dict return values
- `house-voice-panel.js`: Indeklima Designer language applied – House Voice accent
  teal `#14b8a6` / emerald `#34d399`, DM Sans + DM Mono typography, gradient header
  icon, dark-theme tokens with HA CSS variable fallbacks, redesigned event cards,
  stats pills, buttons, form overlay and panel-topbar / panel-scroll layout

### Fixed
- `storage.py`: `async_load` now guards against corrupt storage returning a non-dict
  value (e.g. after manual file edits)
- `voice_engine.py`: speakers coerced to `str()` as fallback when not a list, instead
  of passing the raw value to `ultra_tts`

---

## [2.0.0] – 2026-03-11

### Added
- Full UI sidebar panel (`house-voice-panel.js`) with add, edit, delete, test and refresh
- WebSocket API with 5 commands: `get_events`, `get_media_players`, `save_event`, `delete_event`, `test_event`
- Config Flow setup – integration configured entirely via HA UI (no YAML)
- Speaker selection via checkboxes – supports multiple speakers per event
- Volume slider with live % display (5–100% in 5% steps)
- Priority selector: Info / Normal / Critical
- HA theme support via CSS variables
- Admin-only panel access (`require_admin: true`)
- Cache-busting on JS URL (`?v=VERSION&m=mtime`)
- Spam filter – same event blocked within 30 seconds
- Quiet hours enforcement – 22:00–07:00, only `critical` priority passes through
- Jinja2 template rendering in event messages with fallback to raw message on error
- Statistics sensor `sensor.house_voice_today` – daily TTS counter, resets at midnight
- System Health integration – visible under Settings → System → System Health
- Diagnostics support – downloadable JSON from Settings → Devices & Services
- Stats bar in panel header showing events count, today count and quiet hours status
- Search field in panel – live filter on event ID and message
- Import/Export events as JSON
- `vol.Schema` validation on all 4 HA services
- Speakers stored as list are automatically converted to string before `ultra_tts` call
- `ConfigEntryNotReady` raised if storage fails to load on setup
- `ServiceValidationError` for user errors (unknown event ID, no speakers configured)
- `HomeAssistantError` for communication errors (ultra_tts failure)
- Localized exceptions with `translation_domain`, `translation_key` and placeholders
- `repairs.py` – HA Repair issue created in UI if `script.ultra_tts` is missing
- `strings.json` – master translation strings for config flow, services, exceptions and repairs
- `translations/en.json` – full English translations
- `translations/da.json` – full Danish translations
- `quality_scale.yaml` – tracks Bronze ✅ Silver ✅ Gold 🔄
- `hacs.json` – HACS support
- `.github/workflows/tests.yml` – GitHub Actions CI (runs on push/PR)
- `requirements-test.txt` – test dependencies
- 55 automated tests across 10 test files

### Changed
- `voice_engine.py` now handles all TTS logic centrally (spam, quiet hours, templates, sensor, error handling)
- `__init__.py` loads sensor platform via `async_forward_entry_setups`
- `system_health.py` – `async_register` is now correctly synchronous (fixes RuntimeWarning)
- `manifest.json` – added `quality_scale: silver`
- All service handlers re-raise exceptions after logging for proper HA error propagation

### Fixed
- `ultra_tts` receiving a `list` instead of `string` for `speaker` field (caused `unhashable type: 'list'` error)
- `_last_spoken` dict growing unboundedly – entries older than 1 hour are now cleaned up
- Sensor `increment()` wrapped in try/except to prevent TTS failure on sensor crash

---

## [1.0.0] – 2026-01-01

### Added
- Initial release
- Core TTS service `house_voice.say` routing through `script.ultra_tts`
- `add_event`, `delete_event`, `test_event` services
- HA Storage API wrapper (`storage.py`)
- Event data structure: `message`, `speakers`, `priority`, `volume`
