# VERSION = "3.2.0"
# File: const.py
# Description: Constants for House Voice Manager

DOMAIN   = "house_voice"
VERSION  = "3.2.0"

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

# Defaults
DEFAULT_QUIET_START = 22
DEFAULT_QUIET_END   = 7
DEFAULT_VOLUME      = 0.35
DEFAULT_PRIORITY    = "normal"

# Valid priorities
PRIORITIES = ("info", "normal", "critical")
