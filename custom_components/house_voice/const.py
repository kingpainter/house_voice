# VERSION  = "3.9.0"
# File: const.py
# Description: Constants for House Voice Manager

DOMAIN   = "house_voice"
VERSION  = "3.9.0"

# Storage
STORAGE_KEY             = "house_voice_events"
STORAGE_VERSION         = 1
STORAGE_GROUPS_KEY      = "house_voice_groups"
STORAGE_CONDITIONS_KEY  = "house_voice_conditions"
STORAGE_ANALYTICS_KEY   = "house_voice_analytics"

# Services
SERVICE_SAY       = "say"
SERVICE_SAY_TEXT  = "say_text"
SERVICE_ADD       = "add_event"
SERVICE_DELETE    = "delete_event"
SERVICE_TEST      = "test_event"

# Panel
PANEL_TITLE    = "House Voice"
PANEL_ICON     = "mdi:microphone-message"
PANEL_NAME     = "house-voice-panel"
PANEL_FOLDER   = "frontend"
PANEL_FILENAME = "house-voice-panel.js"
PANEL_URL      = f"/api/{DOMAIN}-panel"

# Custom components folder name
CUSTOM_COMPONENTS = "custom_components"

# Options / config entry keys
CONF_QUIET_START   = "quiet_hours_start"
CONF_QUIET_END     = "quiet_hours_end"
CONF_TTS_ENTITY    = "tts_entity"

# Defaults
DEFAULT_QUIET_START = 22
DEFAULT_QUIET_END   = 7
DEFAULT_VOLUME      = 0.35
DEFAULT_PRIORITY    = "normal"
DEFAULT_TTS_ENTITY  = "tts.home_assistant_cloud"

# Valid priorities
PRIORITIES = ("info", "normal", "critical")

# TTS Engine (UltraTTS)
TTS_PRE_SPEAK_DELAY = 1.0                       # delay before speaking (speaker warmup)
TTS_MIN_SPEECH_DELAY = 8.0                      # minimum playback wait time
TTS_CHARS_PER_SECOND = 10.0                     # character-per-second estimate for duration
TTS_HEOS_BUFFER = 3.0                           # extra buffer for HEOS/MA network latency
TTS_IDLE_VOLUME_THRESHOLD = 0.25                # volume below which speaker is considered idle

# TTS volume duck factors by priority
TTS_DUCK_FACTOR: dict[str, float] = {
    "critical": 0.0,
    "normal":   0.25,
    "info":     0.40,
}

# Voice Engine queue and history
SPAM_FILTER_SECONDS = 30                        # minimum seconds between repeat events
SPAM_CLEANUP_AGE = 3600                         # cleanup _last_spoken entries older than this
HISTORY_MAX_ENTRIES = 50                        # max in-memory history log size

# REST API (Sprint 1)
REST_API_PORT = 8765
REST_API_HOST = "127.0.0.1"
 
# History Database (Sprint 1)
HISTORY_DB_NAME = "house_voice_history.db"
HISTORY_CLEANUP_DAYS = 30

# Chain Templates — Presets for common workflows (Phase 8)
CHAIN_TEMPLATES = {
    "simple_announcement": {
        "name": "Simple Announcement",
        "description": "Single TTS announcement to selected speakers",
        "steps": [
            {
                "id": "announce",
                "type": "TTS",
                "text": "{{ message }}",
                "speakers": [],
                "priority": "normal",
            }
        ]
    },
    "conditional_announcement": {
        "name": "Conditional Announcement",
        "description": "Check condition before announcing",
        "steps": [
            {
                "id": "check",
                "type": "CONDITION_CHECK",
                "condition": "{{ entity_state == 'on' }}",
                "on_true": "announce",
                "on_false": None,
            },
            {
                "id": "announce",
                "type": "TTS",
                "text": "{{ message }}",
                "speakers": [],
                "priority": "normal",
            }
        ]
    },
    "volume_ducking": {
        "name": "Volume Ducking",
        "description": "Lower volume → announce → restore volume",
        "steps": [
            {
                "id": "lower_volume",
                "type": "VOLUME_SET",
                "speakers": [],
                "volume": 0.3,
            },
            {
                "id": "announce",
                "type": "TTS",
                "text": "{{ message }}",
                "speakers": [],
                "priority": "normal",
            },
            {
                "id": "restore_volume",
                "type": "VOLUME_SET",
                "speakers": [],
                "volume": 0.7,
            }
        ]
    },
    "multi_room_sequence": {
        "name": "Multi-Room Sequence",
        "description": "Announce to multiple rooms with delays between",
        "steps": [
            {
                "id": "announce_kitchen",
                "type": "TTS",
                "text": "{{ message }}",
                "speakers": ["media_player.kokken"],
                "priority": "normal",
            },
            {
                "id": "delay_1",
                "type": "DELAY",
                "duration": 2,
            },
            {
                "id": "announce_living_room",
                "type": "TTS",
                "text": "{{ message }}",
                "speakers": ["media_player.stue"],
                "priority": "normal",
            }
        ]
    },
    "critical_alert": {
        "name": "Critical Alert (Parallel)",
        "description": "Announce to all rooms simultaneously",
        "steps": [
            {
                "id": "alert",
                "type": "TTS",
                "text": "{{ message }}",
                "speakers": ["group:alle_rum"],
                "priority": "critical",
            }
        ]
    }
}

# History / Execution constants
DEFAULT_HISTORY_LIMIT = 50
EXECUTION_STATUSES = ("in_progress", "completed", "failed", "blocked_condition")
EXECUTION_STATUS_SUCCESS = "completed"
EXECUTION_STATUS_FAILED = "failed"
EXECUTION_STATUS_BLOCKED = "blocked_condition"
EXECUTION_STATUS_IN_PROGRESS = "in_progress"
