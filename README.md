# House Voice Manager

A Home Assistant custom integration that centralizes all text-to-speech (TTS) output in your home. Instead of calling media players directly in automations, you define named voice events and trigger them with a single service call.

**Version:** 3.1.1 | **Platform:** Home Assistant | **Setup:** UI only (no YAML) | **Quality:** 🥈 Silver

---

## Features

- 🎙️ **Single service entry point** – automations call only `house_voice.say` or `house_voice.say_text`
- 🖥️ **Sidebar panel** – 3-tab UI for managing events, speaker groups and history
- 🔇 **Spam filter** – same event blocked if triggered within 30 seconds
- 🌙 **Quiet hours** – configurable via Options Flow (default 22:00–07:00), only `critical` priority passes through
- 🧩 **Jinja2 templates** – dynamic messages using HA state values
- ⚡ **Conditional playback** – optional Jinja2 condition on events; only plays if condition evaluates to true
- 🔊 **Speaker groups** – define named groups (e.g. `alle_rum`, `stueetage`) and reference them in events
- 📋 **TTS queue** – async queue ensures announcements never overlap; `critical` jumps to front
- 📊 **Statistics sensor** – `sensor.house_voice_today` counts daily TTS output
- 🔍 **Search** – filter events by ID or message
- 📥📤 **Import/Export** – backup and restore all events as JSON
- 📜 **History** – last 50 TTS calls with status (`spoken`, `blocked_spam`, `blocked_quiet_hours`, `blocked_condition`)
- 🩺 **System Health** – integration status visible in HA System Health panel
- 🔬 **Diagnostics** – downloadable diagnostics from HA UI
- 🛠️ **Repairs** – HA UI alert if TTS fails
- 🌍 **Translations** – full English and Danish support

---

## Installation

### Via HACS (recommended)
1. Open HACS in Home Assistant
2. Go to **Integrations → Custom repositories**
3. Add your GitHub repo URL and select **Integration**
4. Search for **House Voice Manager** and install
5. Restart Home Assistant

### Manual
1. Copy the `house_voice` folder to your `custom_components/` directory:
   ```
   config/
     custom_components/
       house_voice/
         __init__.py
         manifest.json
         const.py
         services.yaml
         config_flow.py
         voice_engine.py
         ultra_tts.py
         groups.py
         storage.py
         panel.py
         websocket.py
         sensor.py
         system_health.py
         diagnostics.py
         repairs.py
         strings.json
         quality_scale.yaml
         translations/
           en.json
           da.json
         blueprints/
           house_voice_say.yaml
         frontend/
           house-voice-panel.js
   ```
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration** and search for **House Voice Manager**
4. Click **Submit** – no configuration required

---

## Configuration

Quiet hours are configurable via **Settings → Devices & Services → House Voice → Configure**:

| Setting | Default |
|---------|----------|
| Quiet hours start | 22:00 |
| Quiet hours end | 07:00 |

No restart required – changes take effect immediately.

---

## Services

### `house_voice.say`
Speak a stored voice event by ID.

```yaml
service: house_voice.say
data:
  event: dishwasher_done
```

### `house_voice.say_text`
Ad-hoc TTS without a stored event. Supports Jinja2, group references, priority and volume. Subject to quiet hours but no spam filter.

```yaml
service: house_voice.say_text
data:
  message: "Temperaturen ude er {{ states('sensor.outdoor_temp') }} grader"
  speakers:
    - group:alle_rum
  priority: normal
  volume: 0.4
```

### `house_voice.add_event`
Add or update a voice event.

```yaml
service: house_voice.add_event
data:
  event: dishwasher_done
  message: "Opvaskeren er færdig"
  speakers:
    - media_player.kokken
    - group:stueetage
  priority: normal
  volume: 0.4
  condition: "{{ is_state('person.flemming', 'home') }}"
```

### `house_voice.delete_event`
Delete a voice event.

```yaml
service: house_voice.delete_event
data:
  event: dishwasher_done
```

### `house_voice.test_event`
Test-speak a stored voice event immediately (bypasses spam filter).

```yaml
service: house_voice.test_event
data:
  event: dishwasher_done
```

---

## Event Data Structure

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `message` | `str` | ✅ | – | TTS message text. Supports Jinja2 templates. |
| `speakers` | `list` | ✅ | – | `media_player` entity IDs and/or `group:<id>` references |
| `priority` | `str` | ❌ | `normal` | `info` / `normal` / `critical` |
| `volume` | `float` | ❌ | `0.35` | Volume level 0.05–1.0 |
| `condition` | `str` | ❌ | `""` | Jinja2 expression – event only plays if it evaluates to true |

---

## Speaker Groups

Define named groups in the **Groups tab** of the sidebar panel. Groups can be referenced in events and `say_text` using the `group:<id>` prefix.

Example: if `gruppe_stueetage` contains `media_player.stue` and `media_player.kokken`, then:
```yaml
speakers:
  - group:gruppe_stueetage
```
…resolves to both speakers at playback time.

Groups are deduplicated – if the same speaker appears in multiple references, it only receives the announcement once.

---

## Priority System

| Priority | Behavior |
|----------|---------|
| `info` | Duck music to 40% during TTS |
| `normal` | Duck music to 25% during TTS |
| `critical` | Always plays – bypasses quiet hours, mutes music (0%) |

Duck logic only activates if the speaker state is `playing` and `volume_level > 0.25`. Idle speakers receive the configured TTS volume directly.

---

## Quiet Hours

Configurable via Options Flow (default: **22:00–07:00**). Only `critical` priority messages are spoken during quiet hours. All others are silently blocked and logged in the history as `blocked_quiet_hours`.

---

## Jinja2 Templates

Messages support full HA Jinja2 template syntax:

```yaml
message: "Temperaturen ude er {{ states('sensor.outdoor_temp') }} grader"
message: "{{ now().strftime('%H:%M') }} – husk at låse døren"
message: "Luftfugtighed: {{ state_attr('sensor.stue', 'humidity') }}%"
```

If a template fails to render, the raw message is used as fallback and a warning is logged.

---

## Spam Filter

The same voice event cannot be triggered more than once within **30 seconds**. A subsequent call within the window is blocked and logged:

```
House Voice: Spam filter blocked 'dishwasher_done' – try again in 18 seconds
```

`test_event` always bypasses the spam filter.

---

## TTS Queue

All TTS calls are routed through an `asyncio.Queue` worker. This ensures announcements never overlap. `critical` priority messages are inserted at the front of the queue.

The queue worker is automatically restarted if it dies unexpectedly.

---

## Statistics Sensor

`sensor.house_voice_today` counts the number of TTS messages spoken today. The counter resets automatically at midnight. Blocked messages (spam filter, quiet hours, conditions) are not counted.

---

## History

The **History tab** in the sidebar panel shows the last 50 TTS calls with:
- Timestamp
- Event ID (or `say_text`)
- Message
- Status: `spoken`, `blocked_spam`, `blocked_quiet_hours`, `blocked_condition`

History is in-memory and resets on HA restart.

---

## System Health

Visible under **Settings → System → System Health**:

| Field | Description |
|-------|-------------|
| `version` | Integration version |
| `events_count` | Number of stored voice events |
| `groups_count` | Number of speaker groups |
| `queue_size` | Current TTS queue length |
| `storage_loaded` | Storage API status |

---

## Diagnostics

Download a diagnostics JSON from **Settings → Devices & Services → House Voice → Download diagnostics**. Contains version, event IDs, group IDs, today's count, history count and quiet hours status. No message content or speaker names are included.

---

## Repairs

If TTS fails, a **Repair issue** is automatically created in Home Assistant under **Settings → System → Repairs**.

---

## Automation Blueprint

An automation blueprint is included at `blueprints/house_voice_say.yaml`. It triggers a House Voice event when any entity changes state, with optional from/to state and time window restrictions.

Import via **Settings → Automations → Blueprints → Import Blueprint**.

---

## Architecture

```
Automation
    │
    ▼
house_voice.say / house_voice.say_text
    │
    ▼
voice_engine.py
  ├── Condition check (Jinja2)
  ├── Spam filter (30 sec)
  ├── Quiet hours (configurable)
  ├── Group resolution (group:<id> → speaker list)
  ├── asyncio.Queue (critical → front)
  └── ultra_tts.py
        ├── Duck music (if state=playing, volume>0.25)
        ├── HEOS sibling detection (clear_playlist)
        ├── tts.speak → Music Assistant → media_player
        ├── Dynamic delay (ceil(len/10) + 3s buffer, min 8s)
        └── Volume restore (finally block)
```

---

## Running Tests

```bash
pip install -r requirements-test.txt
pytest tests/components/house_voice/ -v
```

Tests run automatically on every push via GitHub Actions.

**Test count:** 129 tests across 13 test files.

---

## Requirements

- Home Assistant 2026+
- Music Assistant (or compatible TTS backend)
- `tts.home_assistant_cloud` configured
- Python 3.12+

---

## License

MIT License – see `LICENSE.md`
