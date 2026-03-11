# House Voice Manager

A Home Assistant custom integration that centralizes all text-to-speech (TTS) output in your home. Instead of calling media players directly in automations, you define named voice events and trigger them with a single service call.

**Version:** 2.0.0 | **Platform:** Home Assistant | **Setup:** UI only (no YAML) | **Quality:** 🥈 Silver

---

## Features

- 🎙️ **Single service entry point** – automations call only `house_voice.say`
- 🖥️ **Sidebar panel** – manage all voice events from the HA UI
- 🔇 **Spam filter** – same event blocked if triggered within 30 seconds
- 🌙 **Quiet hours** – 22:00–07:00, only `critical` priority passes through
- 🧩 **Jinja2 templates** – dynamic messages using HA state values
- 📊 **Statistics sensor** – `sensor.house_voice_today` counts daily TTS output
- 🔍 **Search** – filter events by ID or message
- 📥📤 **Import/Export** – backup and restore all events as JSON
- 🩺 **System Health** – integration status visible in HA System Health panel
- 🔬 **Diagnostics** – downloadable diagnostics from HA UI
- 🛠️ **Repairs** – HA UI alert if `script.ultra_tts` is missing
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
         voice_engine.py
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
         frontend/
           house-voice-panel.js
   ```
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration** and search for **House Voice Manager**
4. Click **Submit** – no configuration required

---

## Services

### `house_voice.say`
Speak a stored voice event by ID.

```yaml
service: house_voice.say
data:
  event: dishwasher_done
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
  priority: normal
  volume: 0.4
```

### `house_voice.delete_event`
Delete a voice event.

```yaml
service: house_voice.delete_event
data:
  event: dishwasher_done
```

### `house_voice.test_event`
Test-speak a stored voice event immediately.

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
| `speakers` | `list` | ✅ | – | One or more `media_player` entity IDs |
| `priority` | `str` | ❌ | `normal` | `info` / `normal` / `critical` |
| `volume` | `float` | ❌ | `0.35` | Volume level 0.05–1.0 |

---

## Priority System

| Priority | Behavior |
|----------|----------|
| `info` | Duck music during TTS |
| `normal` | Normal playback |
| `critical` | Always plays – bypasses quiet hours and stops music |

---

## Quiet Hours

Between **22:00 and 07:00**, only `critical` priority messages are spoken. All others are silently blocked and logged at `INFO` level.

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

The same voice event cannot be triggered more than once within **30 seconds**. A subsequent call within the window is blocked and logged as a warning:

```
House Voice: Spam filter blocked 'dishwasher_done' – try again in 18 seconds
```

---

## Statistics Sensor

`sensor.house_voice_today` counts the number of TTS messages spoken today. The counter resets automatically at midnight. Blocked messages (spam filter, quiet hours) are not counted.

---

## System Health

Visible under **Settings → System → System Health**:

| Field | Description |
|-------|-------------|
| `version` | Integration version |
| `events_count` | Number of stored voice events |
| `storage_loaded` | Storage API status |

---

## Diagnostics

Download a diagnostics JSON from **Settings → Devices & Services → House Voice → Download diagnostics**. Contains version, event IDs, today's count and quiet hours status. No sensitive data (messages or speaker names) are included.

---

## Repairs

If `script.ultra_tts` is unavailable or fails, a **Repair issue** is automatically created in Home Assistant under **Settings → System → Repairs**. The issue describes the problem and links to the relevant script.

---

## Architecture

```
Automation
    │
    ▼
house_voice.say (event: "dishwasher_done")
    │
    ▼
voice_engine.py
  ├── Spam filter (30 sec)
  ├── Quiet hours (22:00–07:00)
  ├── Jinja2 template render
  ├── script.ultra_tts → Music Assistant → media_player
  └── sensor.house_voice_today increment
```

---

## Running Tests

```bash
pip install -r requirements-test.txt
pytest tests/components/house_voice/ -v
```

Tests run automatically on every push via GitHub Actions.

---

## Requirements

- Home Assistant 2026+
- `script.ultra_tts` configured in your HA instance
- Python 3.11+

---

## License

MIT License – see `LICENSE.md`
