"""Tests for House Voice Manager panel registration."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from custom_components.house_voice.const import DOMAIN
from custom_components.house_voice.panel import _SESSION_KEY_STATIC
from custom_components.house_voice import HouseVoiceRuntimeData
from types import SimpleNamespace



def _get_entry(hass):
    """Helper to get the House Voice entry from hass."""
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


@pytest.fixture
def hass_with_panel_data(mock_hass, mock_entry):
    """Return hass with panel domain data initialized (fresh HA session)."""
    # Wire up mock_entry into hass so panel.py can find it via hass.config_entries.async_entries()
    mock_hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])
    # Initialize runtime_data with panel_registered=False
    mock_entry.runtime_data = HouseVoiceRuntimeData(
        storage=MagicMock(),
        groups=MagicMock(),
        conditions=MagicMock(),
        engine=MagicMock(),
        sensor=None,
        panel_registered=False,
    )
    mock_hass.config = MagicMock()
    mock_hass.config.path = MagicMock(return_value="/config/custom_components")
    mock_hass.http = MagicMock()
    mock_hass.http.async_register_static_paths = AsyncMock()
    return mock_hass


@pytest.mark.asyncio
async def test_register_panel_sets_flag(hass_with_panel_data, mock_entry):
    """Panel registration sets _panel_registered flag to True."""
    hass = hass_with_panel_data

    with patch("custom_components.house_voice.panel.panel_custom.async_register_panel", new=AsyncMock()), \
         patch("os.path.getmtime", return_value=1234567890.0):

        from custom_components.house_voice.panel import async_register_panel
        await async_register_panel(hass)

    assert mock_entry.runtime_data.panel_registered is True


@pytest.mark.asyncio
async def test_static_path_registered_once_per_session(hass_with_panel_data, mock_entry):
    """Static HTTP path is only registered once even after unload/reload."""
    hass = hass_with_panel_data

    from custom_components.house_voice.panel import async_register_panel, async_unregister_panel
    from custom_components.house_voice import panel as panel_module

    with patch("custom_components.house_voice.panel.panel_custom.async_register_panel", new=AsyncMock()), \
         patch.object(panel_module, "_HAS_STATIC_PATH_CONFIG", False), \
         patch("os.path.getmtime", return_value=1234567890.0):

        # First setup
        await async_register_panel(hass)
        assert hass.data.get(_SESSION_KEY_STATIC) is True
        assert hass.http.async_register_static_paths.call_count == 1

        # Simulate reload: unload clears _panel_registered but NOT _SESSION_KEY_STATIC
        async_unregister_panel(hass)
        mock_entry.runtime_data.panel_registered = False

        # Second setup after reload
        await async_register_panel(hass)

    # Static path must still only have been registered once
    assert hass.http.async_register_static_paths.call_count == 1
    assert mock_entry.runtime_data.panel_registered is True


@pytest.mark.asyncio
async def test_register_panel_skips_if_already_registered(hass_with_panel_data, mock_entry):
    """Panel registration is skipped if already registered."""
    hass = hass_with_panel_data
    mock_entry.runtime_data.panel_registered = True

    with patch("custom_components.house_voice.panel.panel_custom.async_register_panel", new=AsyncMock()) as mock_reg:
        from custom_components.house_voice.panel import async_register_panel
        await async_register_panel(hass)

    mock_reg.assert_not_called()


@pytest.mark.asyncio
async def test_register_panel_handles_missing_js_file(hass_with_panel_data, mock_entry):
    """Panel registration continues even if JS file is missing (cache_bust=0)."""
    hass = hass_with_panel_data

    with patch("custom_components.house_voice.panel.panel_custom.async_register_panel", new=AsyncMock()), \
         patch("os.path.getmtime", side_effect=OSError("file not found")):

        from custom_components.house_voice.panel import async_register_panel
        await async_register_panel(hass)

    assert mock_entry.runtime_data.panel_registered is True


@pytest.mark.asyncio
async def test_unregister_does_not_clear_session_key(hass_with_panel_data, mock_entry):
    """unregister_panel clears _panel_registered but leaves _SESSION_KEY_STATIC intact."""
    hass = hass_with_panel_data
    hass.data[_SESSION_KEY_STATIC] = True
    mock_entry.runtime_data.panel_registered = True

    with patch("custom_components.house_voice.panel.frontend.async_remove_panel"):
        from custom_components.house_voice.panel import async_unregister_panel
        async_unregister_panel(hass)

    assert mock_entry.runtime_data.panel_registered is False
    assert hass.data[_SESSION_KEY_STATIC] is True  # must survive unload


def test_unregister_panel_clears_flag(mock_hass, mock_entry):
    """Unregistering panel clears _panel_registered flag."""
    mock_hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])
    mock_entry.runtime_data = HouseVoiceRuntimeData(
        storage=MagicMock(),
        groups=MagicMock(),
        conditions=MagicMock(),
        engine=MagicMock(),
        sensor=None,
        panel_registered=True,
    )

    with patch("custom_components.house_voice.panel.frontend.async_remove_panel") as mock_remove:
        from custom_components.house_voice.panel import async_unregister_panel
        async_unregister_panel(mock_hass)

    mock_remove.assert_called_once_with(mock_hass, DOMAIN)
    assert mock_entry.runtime_data.panel_registered is False


def test_unregister_panel_skips_if_not_registered(mock_hass, mock_entry):
    """Unregistering panel does not call remove if not registered."""
    mock_hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])
    mock_entry.runtime_data = HouseVoiceRuntimeData(
        storage=MagicMock(),
        groups=MagicMock(),
        conditions=MagicMock(),
        engine=MagicMock(),
        sensor=None,
        panel_registered=False,
    )

    with patch("custom_components.house_voice.panel.frontend.async_remove_panel") as mock_remove:
        from custom_components.house_voice.panel import async_unregister_panel
        async_unregister_panel(mock_hass)

    mock_remove.assert_not_called()
