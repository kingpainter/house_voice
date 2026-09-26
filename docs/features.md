# House Voice — Features & User Guide

**Version:** 3.13.0  
**Last Updated:** 2026-09-26

---

## 1. Overview

House Voice is a centralized TTS (Text-to-Speech) management system for Home Assistant. Instead of configuring TTS in every automation:

- **Define Events** — Store reusable voice messages with speaker preferences
- **Create Groups** — Bundle speakers into zones (bedroom, downstairs, etc.)
- **Set Conditions** — Add rules for playback (only if home, not sleeping, etc.)
- **Manage History** — View all TTS executions with logs and analytics

---

## 2. Events Management

### What is an Event?

An event is a stored voice message with predefined settings.

### Creating an Event

1. Open House Voice panel → **Events** tab
2. Click **New Event**
3. Enter details:
   - **Event ID** — unique name (e.g., `doorbell_alert`)
   - **Message** — TTS text (Jinja2 templates supported)
   - **Speakers** — which speakers to use
   - **Priority** — urgency level (info/normal/critical)
   - **Volume** — playback level (0.05–1.0)
   - **Conditions** (optional) — rules for playback
4. Click **Save**

### Testing Events

Click **Test** to preview with current settings:
- Bypasses spam filter
- Bypasses quiet hours
- Uses configured speakers and volume

---

## 3. Speaker Groups

### Why Use Groups?

Group multiple speakers to avoid listing them repeatedly:

```yaml
# Without groups
speakers:
  - media_player.kitchen
  - media_player.living_room
  - media_player.hallway

# With groups
speakers:
  - group:downstairs
```

### Creating a Group

1. Go to **Groups** tab
2. Click **New Group**
3. Enter:
   - **Group ID** — name (e.g., `bedroom`)
   - **Group Name** — display name (e.g., `Bedroom Speakers`)
   - **Speakers** — select speakers in this group
4. Click **Save**

---

## 4. Conditions Library

### What are Conditions?

Conditions are rules that determine when events should play. Use to avoid:
- Announcements during sleep
- Alerts when nobody is home
- Notifications during work

### Creating a Condition

1. Go to **Conditions** tab
2. Click **New Condition**
3. Enter:
   - **Condition ID** — name (e.g., `someone_home`)
   - **Label** — display name (e.g., `Someone is home`)
   - **Entity** — HA entity to monitor
   - **State** — expected state for playback
4. Click **Save**

### Using Conditions

When editing an event:
- Check conditions that must be true
- Uses AND logic (all conditions must match)
- Fail-open: event plays if condition can't be checked

---

## 5. Priority Levels

Control queue order of voice messages:

| Level | Behavior | Use |
|-------|----------|-----|
| `info` | Lowest priority | Weather, reminders |
| `normal` | Default | Announcements, events |
| `critical` | Plays immediately | Alarms, security alerts |

---

## 6. Quiet Hours

Prevent notifications during sleeping times.

### Configuration

1. Go to **Settings** → **Options**
2. Set **Overnight quiet hours** (e.g., 22:00–07:00)
3. Optionally set **Same-day quiet hours** (e.g., 13:00–15:00)
4. Save

### Behavior

| Priority | During Quiet Hours |
|----------|-------------------|
| info | Blocked |
| normal | Blocked |
| critical | **Plays anyway** |

Critical events always play (for alarms, emergencies).

---

## 7. Execution History

### Viewing History

1. Open **History** tab
2. View recent 50 executions
3. Click expand row for details

### Filtering

Use filter panel to find executions:
- **Chain ID** — Filter by automation
- **Status** — completed, failed, in_progress, blocked
- **Date Range** — select dates
- **Search** — search event names and errors

### Exporting

Click download icon on any execution to get JSON export.

---

## 8. Analytics Dashboard

### Available Metrics

**Overall Statistics:**
- Total executions
- Success rate
- Average duration

**Chain Performance:**
- Ranked by speed/failures
- Execution counts

**Step Analytics:**
- Top-10 failing steps
- Slowest steps
- Most-used steps

**Timeline:**
- Gantt chart visualization
- Execution history

---

## 9. Getting Started

### Step 1: Create Your First Event

1. Go to **Events** tab
2. Click **New Event**
3. Fill:
   - ID: `test_event`
   - Message: `Hello from House Voice`
   - Speaker: Select one
   - Priority: `normal`
   - Volume: `0.35`
4. Save

### Step 2: Use in Automation

```yaml
automation:
  - alias: Morning Greeting
    trigger:
      platform: time
      at: "07:00:00"
    action:
      - service: house_voice.say
        data:
          event_id: test_event
```

### Step 3: Monitor

Check **History** tab to see if event played or if blocked.

---

## 10. Services

### `house_voice.say`

Play a stored event.

```yaml
service: house_voice.say
data:
  event_id: "good_morning"
```

### `house_voice.say_text`

Play ad-hoc text.

```yaml
service: house_voice.say_text
data:
  message: "{{ trigger.entity_id }} triggered"
  speakers:
    - media_player.kitchen
    - group:bedroom
  priority: normal
  volume: 0.5
```

---

## 11. Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Event blocked | Quiet hours | Check History for `blocked_quiet_hours` |
| Event blocked | Condition failed | Check if entity exists in HA |
| No sound | Volume too low | Increase volume (0.05–1.0) |
| Event plays twice | Spam filter | Wait 10 seconds before re-triggering |
| Speaker offline | Device issue | Check Media Player in HA |

---

**Version:** 3.13.0 | **Last Updated:** 2026-09-26
