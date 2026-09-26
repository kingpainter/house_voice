# House Voice v3.13.0 — Production Test Plan

**Date:** 2026-09-26  
**Version:** 3.13.0  
**Tester:** Flemming

---

## 📋 Test Overview

This document guides systematic testing of House Voice integration in a live Home Assistant environment. All tests should be run against the current v3.13.0 code.

### Goals
- Verify core TTS functionality is stable
- Test speaker groups and volume control
- Validate conditions, quiet hours, priority levels
- Confirm UI/panel responsiveness
- Identify edge cases and error handling

### Duration Estimate
- Full test suite: ~45 minutes
- Quick validation: ~15 minutes

---

## 1️⃣ Core TTS Functionality

### 1.1: Basic Event Playback
**Test:** Call `house_voice.say` with a simple stored event
```yaml
service: house_voice.say
data:
  event_id: "test_basic"
```
**Expected:** Speaker plays "Test message" immediately  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 1.2: Ad-hoc Text Playback
**Test:** Call `house_voice.say_text` with inline message
```yaml
service: house_voice.say_text
data:
  message: "This is a test message"
  speakers:
    - media_player.kitchen
  volume: 0.5
  priority: normal
```
**Expected:** Kitchen speaker plays message at 50% volume  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 1.3: Volume Levels
**Test:** Send same message at different volumes (0.2, 0.5, 0.8)
```yaml
- message: "Volume test twenty percent"
  volume: 0.2
- message: "Volume test fifty percent"
  volume: 0.5
- message: "Volume test eighty percent"
  volume: 0.8
```
**Expected:** Clear volume differences; 0.2 quiet, 0.8 loud  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 1.4: Multiple Speakers Simultaneously
**Test:** Send message to 2+ speakers at once
```yaml
service: house_voice.say_text
data:
  message: "Testing multiple speakers"
  speakers:
    - media_player.kitchen
    - media_player.bedroom
    - group:downstairs
  priority: normal
```
**Expected:** All speakers play message (may queue if concurrent)  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

---

## 2️⃣ Speaker Groups

### 2.1: Group Resolution
**Test:** Create group `test_group` with 2+ speakers, then use it
```yaml
service: house_voice.say_text
data:
  message: "Testing group resolution"
  speakers:
    - group:test_group
```
**Expected:** All speakers in group play message  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 2.2: Mixed Speakers + Groups
**Test:** Call with both individual speakers and a group
```yaml
speakers:
  - media_player.kitchen
  - group:bedroom
  - media_player.office
```
**Expected:** All 4+ speakers play (no duplicates)  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 2.3: Non-existent Group
**Test:** Call with a group that doesn't exist
```yaml
speakers:
  - group:nonexistent_group
```
**Expected:** Error in history, no crash; service handles gracefully  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

---

## 3️⃣ Advanced Features

### 3.1: Quiet Hours — Blocking
**Test:** Trigger message during configured quiet hours (e.g., 22:00-07:00)
```yaml
service: house_voice.say_text
data:
  message: "Should be blocked by quiet hours"
  speakers: [media_player.kitchen]
  priority: normal  # NOT critical
```
**Expected:** Message blocked, history shows `blocked_quiet_hours`  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 3.2: Quiet Hours — Critical Bypass
**Test:** Trigger CRITICAL message during quiet hours
```yaml
service: house_voice.say_text
data:
  message: "Critical alarm should bypass quiet hours"
  speakers: [media_player.kitchen]
  priority: critical
```
**Expected:** Message plays despite quiet hours  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 3.3: Spam Filter
**Test:** Send same message twice within 10 seconds
```yaml
# Message 1
service: house_voice.say_text
data:
  message: "Spam test message"
  speakers: [media_player.kitchen]
# Wait 3 seconds
# Message 2 (identical)
service: house_voice.say_text
data:
  message: "Spam test message"
  speakers: [media_player.kitchen]
```
**Expected:** First plays, second blocked (status: `blocked_spam`)  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 3.4: Condition Library — AND Logic
**Test:** Create conditions `someone_home` + `not_sleeping`, apply both to event
```yaml
service: house_voice.add_event
data:
  event_id: "conditional_message"
  message: "This plays only if someone is home AND not sleeping"
  speakers: [media_player.kitchen]
  conditions:
    - someone_home
    - not_sleeping
```
**Test cases:**
- someone_home=ON, not_sleeping=ON → ☐ Plays
- someone_home=ON, not_sleeping=OFF → ☐ Blocked
- someone_home=OFF, not_sleeping=ON → ☐ Blocked

**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 3.5: Jinja2 Templates
**Test:** Use Home Assistant entities in message template
```yaml
service: house_voice.say_text
data:
  message: "{{ state_attr('person.flemming', 'friendly_name') }} is {{ states('person.flemming') }}"
  speakers: [media_player.kitchen]
```
**Expected:** Message resolves to actual person state (e.g., "Flemming is home")  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

---

## 4️⃣ UI/Panel Testing

### 4.1: Tab Navigation
**Test:** Open House Voice panel, click each tab
- ☐ Events tab loads and displays event list
- ☐ Groups tab loads and displays groups
- ☐ History tab loads and shows execution records
- ☐ Analytics tab loads and shows stats

**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 4.2: History Tab Display
**Test:** Run 3-5 events, check history tab
**Expected:** 
- Events appear in reverse chronological order
- Status badges visible (✓ Afsluttet, ✕ Fejl, ⟳ I gang)
- Timestamps and durations displayed

**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 4.3: Create/Edit Event
**Test:** 
1. Create new event via UI
2. Edit existing event
3. Delete event

**Expected:** All operations reflect immediately in list  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 4.4: Panel Reload
**Test:** Click "Reload" button in topbar
**Expected:** Panel refreshes without full page reload; no errors  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 4.5: Response Time
**Test:** Click through tabs and buttons, measure response
**Expected:** <500ms response time for UI interactions  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

---

## 5️⃣ Edge Cases & Error Handling

### 5.1: Unavailable Entity
**Test:** Add condition with an entity that doesn't exist or is `unavailable`
```yaml
entity_id: "binary_sensor.does_not_exist"
state: "on"
```
**Expected:** 
- Event STILL plays (fail-open design)
- Warning logged (check HA logs)
- History shows execution (not blocked)

**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 5.2: Empty Speakers List
**Test:** Call say_text with empty speakers list
```yaml
speakers: []
```
**Expected:** Error in history; service handles gracefully  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 5.3: Very Long Message
**Test:** Send 500+ character message
```yaml
message: "Lorem ipsum dolor sit amet... [long text]"
```
**Expected:** Message plays (may take longer); no crashes  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 5.4: Special Characters
**Test:** Send message with special chars: ÆØÅ, 中文, emoji 🔊
```yaml
message: "Test ÆØÅ and emoji 🔊 and numbers 123"
```
**Expected:** Message plays/displays correctly  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

### 5.5: Rapid Sequential Calls
**Test:** Send 5 messages in rapid succession (no delay)
```yaml
# x5 in loop with no delay
service: house_voice.say_text
data:
  message: "Message N"
  speakers: [media_player.kitchen]
```
**Expected:** Queue handles all; no crashes; history shows all  
**Status:** ☐ Pass ☐ Fail  
**Notes:** _________

---

## 📊 Summary

### Passing Tests: ___ / 25
### Failing Tests: ___ / 25
### Critical Issues: ___ 

### Overall Status
- ☐ All Green — Ready for production
- ☐ Minor Issues — Document for future phase
- ☐ Blocking Issues — Requires fixes before production use

### Critical Findings
_[List any bugs, crashes, or unexpected behavior]_

### Recommendations
_[Any improvements or optimizations needed?]_

---

**Tested by:** Flemming  
**Test Date:** 2026-09-26  
**HA Version:** ___  
**House Voice Version:** 3.13.0  
