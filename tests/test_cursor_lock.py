import sys
from unittest.mock import patch, MagicMock
from autoclicker import app


def reset_cursor_lock_state():
    app.running = False
    app.cursor_lock_enabled = False
    app.locked_position = None
    app._last_lock_alert = 0.0
    app._cursor_lock_thread = None
    app._cursor_lock_active.clear()
    app._cursor_lock_shutdown.clear()


def test_cursor_lock_toggle_hotkey():
    """Test that 'l' triggers the cursor lock toggle."""
    reset_cursor_lock_state()
    app._pressed_keys.clear()
    app.local_keys_enabled = True

    key = MagicMock()
    key.char = "l"

    with patch("autoclicker.app.toggle_cursor_lock") as mock_toggle:
        app.on_press(key)
        mock_toggle.assert_called_once()


def test_cursor_lock_logic():
    """Enabling cursor lock mid-run captures the current cursor position."""
    reset_cursor_lock_state()
    app.running = True
    app.locked_position = (10, 10)

    with (
        patch("autoclicker.app._mouse") as mock_mouse,
        patch("autoclicker.app._ensure_cursor_lock_worker") as mock_ensure,
        patch("autoclicker.app._set_message") as mock_msg,
        patch("autoclicker.app._refresh_status") as mock_refresh,
    ):
        mock_mouse.position = (50, 75)
        app.toggle_cursor_lock()

        assert app.cursor_lock_enabled is True
        assert app.locked_position == (50, 75)
        assert app._cursor_lock_active.is_set() is True
        mock_ensure.assert_called_once()
        mock_msg.assert_called_with("cursor_lock:enabled")
        mock_refresh.assert_called()


def test_cursor_lock_disable_keeps_target_and_stops_worker():
    """Disabling cursor lock should stop enforcement without retargeting."""
    reset_cursor_lock_state()
    app.running = True
    app.cursor_lock_enabled = True
    app.locked_position = (100, 100)
    app._cursor_lock_active.set()

    with (
        patch("autoclicker.app._ensure_cursor_lock_worker") as mock_ensure,
        patch("autoclicker.app._set_message") as mock_msg,
        patch("autoclicker.app._refresh_status") as mock_refresh,
    ):
        app.toggle_cursor_lock()

        assert app.cursor_lock_enabled is False
        assert app.locked_position == (100, 100)
        assert app._cursor_lock_active.is_set() is False
        mock_ensure.assert_not_called()
        mock_msg.assert_called_with("cursor_lock:disabled")
        mock_refresh.assert_called()


def test_main_does_not_start_cursor_lock_worker_by_default():
    """Normal startup should not create the cursor-lock worker thread."""
    reset_cursor_lock_state()

    with (
        patch("autoclicker.app.keyboard.Listener") as mock_keyboard_listener,
        patch("autoclicker.app.MouseListener") as mock_mouse_listener,
        patch("autoclicker.app.threading.Thread") as mock_thread,
        patch("autoclicker.app.time.sleep", side_effect=KeyboardInterrupt),
        patch("autoclicker.app.status_renderer.maybe_render"),
        patch("autoclicker.app.status_renderer.finalize"),
        patch.object(sys, "argv", ["autoclicker"]),
    ):
        mock_keyboard_listener.return_value = MagicMock()
        mock_mouse_listener.return_value = MagicMock()

        app.main()

        mock_thread.assert_not_called()


def test_mouse_move_enforcement():
    """Test that mouse movement is corrected when locked."""
    reset_cursor_lock_state()
    app.running = True
    app.cursor_lock_enabled = True
    app.locked_position = (100, 100)

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
    reset_cursor_lock_state()
    app.cursor_lock_enabled = True
    app.locked_position = (100, 100)

    with patch("autoclicker.app._mouse") as mock_mouse:
        mock_mouse.position = (200, 200)
        app._enforce_cursor_lock()
        # Should not have touched position
        assert mock_mouse.position == (200, 200)
