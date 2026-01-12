from unittest.mock import patch, MagicMock
from autoclicker import app


def test_cursor_lock_toggle_hotkey():
    """Test that 'l' triggers the cursor lock toggle."""
    app._pressed_keys.clear()
    app.local_keys_enabled = True

    key = MagicMock()
    key.char = "l"

    with patch("autoclicker.app.toggle_cursor_lock") as mock_toggle:
        app.on_press(key)
        mock_toggle.assert_called_once()


def test_cursor_lock_logic():
    """Test the state change when toggling cursor lock."""
    # Reset state
    app.cursor_lock_enabled = False

    with (
        patch("autoclicker.app._set_message") as mock_msg,
        patch("autoclicker.app._refresh_status") as mock_refresh,
    ):
        app.toggle_cursor_lock()

        assert app.cursor_lock_enabled is True
        mock_msg.assert_called_with("cursor_lock:enabled")
        mock_refresh.assert_called()

        app.toggle_cursor_lock()

        assert app.cursor_lock_enabled is False
        mock_msg.assert_called_with("cursor_lock:disabled")


def test_mouse_move_enforcement():
    """Test that mouse movement is corrected when locked."""
    app.running = True
    app.cursor_lock_enabled = True
    app.locked_position = (100, 100)
    app._last_lock_alert = 0.0

    # Mock the mouse controller
    with (
        patch("autoclicker.app._mouse") as mock_mouse,
        patch("autoclicker.app._set_message") as mock_msg,
    ):
        # Small movement (within threshold) - should do nothing
        # Distance squared: (101-100)^2 + (101-100)^2 = 1 + 1 = 2 < 25
        mock_mouse.position = (101, 101)
        app._enforce_cursor_lock()
        # Ensure position was NOT set back (it remains (101, 101))
        assert mock_mouse.position == (101, 101)

        # Large movement - should reset
        # Distance squared: (120-100)^2 = 400 > 25
        mock_mouse.position = (120, 100)
        app._enforce_cursor_lock()

        # Verify it tried to set position back to locked_position
        assert mock_mouse.position == (100, 100)
        mock_msg.assert_called_with("Cursor locked! Movement detected.")


def test_mouse_move_ignored_when_not_running():
    """Test that mouse movement is ignored when not running."""
    app.running = False
    app.cursor_lock_enabled = True
    app.locked_position = (100, 100)

    with patch("autoclicker.app._mouse") as mock_mouse:
        mock_mouse.position = (200, 200)
        app._enforce_cursor_lock()
        # Should not have touched position
        assert mock_mouse.position == (200, 200)
