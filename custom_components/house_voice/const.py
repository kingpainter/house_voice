# VERSION = "3.4.0"
# File: const.py
# Description: Constants for House Voice Manager

DOMAIN   = "house_voice"
VERSION  = "3.4.0"

# Storage
STORAGE_KEY             = "house_voice_events"
STORAGE_VERSION         = 1
STORAGE_GROUPS_KEY      = "house_voice_groups"
STORAGE_CONDITIONS_KEY  = "house_voice_conditions"

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
