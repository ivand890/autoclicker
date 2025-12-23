from unittest.mock import patch, MagicMock
from pynput.keyboard import Key
from autoclicker import app


def test_global_lock_combo_standard():
    """Test that Ctrl+Alt+K (standard 'k') triggers the lock toggle."""
    app._pressed_keys.clear()
    app._pressed_keys.add(Key.ctrl_l)
    app._pressed_keys.add(Key.alt_l)

    # Mock the 'k' key press
    key = MagicMock()
    key.char = "k"

    with patch("autoclicker.app.global_toggle_keys") as mock_toggle:
        app.on_press(key)
        mock_toggle.assert_called_once()


def test_global_lock_combo_windows():
    """Test that Ctrl+Alt+K (Windows '\x0b') triggers the lock toggle."""
    app._pressed_keys.clear()
    app._pressed_keys.add(Key.ctrl_l)
    app._pressed_keys.add(Key.alt_l)

    # Mock the Ctrl+K character seen on Windows
    key = MagicMock()
    key.char = "\x0b"

    with patch("autoclicker.app.global_toggle_keys") as mock_toggle:
        app.on_press(key)
        mock_toggle.assert_called_once()


def test_global_lock_combo_windows_vk():
    """Test that Ctrl+Alt+K (Windows vk=75) triggers the lock toggle."""
    app._pressed_keys.clear()
    app._pressed_keys.add(Key.ctrl_l)
    app._pressed_keys.add(Key.alt_l)

    # Mock the KeyCode with vk=75
    key = MagicMock()
    key.char = None
    key.vk = 75

    with patch("autoclicker.app.global_toggle_keys") as mock_toggle:
        app.on_press(key)
        mock_toggle.assert_called_once()


def test_global_lock_combo_missing_modifiers():
    """Test that 'k' alone does not trigger the lock toggle."""
    app._pressed_keys.clear()

    key = MagicMock()
    key.char = "k"

    with patch("autoclicker.app.global_toggle_keys") as mock_toggle:
        app.on_press(key)
        mock_toggle.assert_not_called()
