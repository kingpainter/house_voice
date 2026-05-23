# VERSION = "3.0.1"
# File: panel.py
# Description: Registers the House Voice Manager sidebar panel as a static
#              HTTP path and custom web component in Home Assistant.
#              The static HTTP path survives reloads (aiohttp router is permanent),
#              so it is tracked at session level and only registered once per HA session.

from __future__ import annotations

import logging
import os

from homeassistant.components import frontend, panel_custom
from homeassistant.core import HomeAssistant

from .const import (
    CUSTOM_COMPONENTS,
    DOMAIN,
    PANEL_FILENAME,
    PANEL_FOLDER,
    PANEL_ICON,
    PANEL_NAME,
    PANEL_TITLE,
    PANEL_URL,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)

# Key used to track static path registration at the HA session level.
# Unlike hass.data[DOMAIN], this key is NOT cleared on unload/reload so
# aiohttp's router is never asked to register the same URL twice.
_SESSION_KEY_STATIC = f"{DOMAIN}_static_path_registered"

# StaticPathConfig was introduced in HA 2024.2 – fall back to legacy API if not available
try:
    from homeassistant.components.http import StaticPathConfig
    _HAS_STATIC_PATH_CONFIG = True
except ImportError:
    _HAS_STATIC_PATH_CONFIG = False


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the House Voice sidebar panel."""

    root_dir     = os.path.join(hass.config.path(CUSTOM_COMPONENTS), DOMAIN)
    frontend_dir = os.path.join(root_dir, PANEL_FOLDER)
    panel_file   = os.path.join(frontend_dir, PANEL_FILENAME)

    # Cache busting based on file modification time
    try:
        cache_bust = int(os.path.getmtime(panel_file))
    except OSError:
        _LOGGER.warning("House Voice panel JS not found: %s", panel_file)
        cache_bust = 0

    # Register static HTTP path – once per HA session only.
    # aiohttp's router is permanent: re-registering the same URL after a reload
    # raises RuntimeError. We guard with a session-level key that survives unload.
    if not hass.data.get(_SESSION_KEY_STATIC, False):
        if _HAS_STATIC_PATH_CONFIG:
            await hass.http.async_register_static_paths([
                StaticPathConfig(PANEL_URL, panel_file, cache_headers=False)
            ])
        else:
            hass.http.register_static_path(PANEL_URL, panel_file, cache_headers=False)
        hass.data[_SESSION_KEY_STATIC] = True
        _LOGGER.info("House Voice panel static path registered: %s → %s", PANEL_URL, panel_file)
    else:
        _LOGGER.debug("House Voice panel static path already registered, skipping")

    # Guard against double panel registration within the same HA session
    if hass.data[DOMAIN].get("_panel_registered", False):
        _LOGGER.debug("House Voice panel already registered, skipping")
        return

    # Register the custom sidebar panel
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_NAME,
        frontend_url_path=DOMAIN,
        module_url=f"{PANEL_URL}?v={VERSION}&m={cache_bust}",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=True,
        config={},
    )

    hass.data[DOMAIN]["_panel_registered"] = True
    _LOGGER.info("House Voice panel registered in sidebar at /%s", DOMAIN)


def async_unregister_panel(hass: HomeAssistant) -> None:
    """Remove the House Voice panel from the sidebar."""

    if hass.data.get(DOMAIN, {}).get("_panel_registered", False):
        frontend.async_remove_panel(hass, DOMAIN)
        _LOGGER.debug("House Voice panel removed from sidebar")
    else:
        _LOGGER.debug("House Voice panel was not registered, skipping removal")

    # Clear the panel flag so the next setup re-registers the sidebar entry.
    # Do NOT clear _SESSION_KEY_STATIC – the HTTP route must not be re-added.
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["_panel_registered"] = False
