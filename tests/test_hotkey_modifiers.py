from unittest.mock import patch

import pytest
from pynput.keyboard import Key, KeyCode

from autoclicker import app


@pytest.fixture(autouse=True)
def clean_keys(monkeypatch):
    app._pressed_keys.clear()
    monkeypatch.setattr(app, "local_keys_enabled", True)
    yield
    app._pressed_keys.clear()


def _tap(*keys):
    for key in keys:
        app.on_press(key)
    for key in reversed(keys):
        app.on_release(key)


@pytest.mark.parametrize(
    "modifier, char, handler",
    [
        (Key.ctrl_l, "c", "single_test_click"),
        (Key.ctrl_r, "s", "toggle_running"),
        (Key.alt_l, "l", "toggle_cursor_lock"),
        (Key.cmd_l, "s", "toggle_running"),
    ],
)
def test_modified_letters_do_not_fire_hotkeys(modifier, char, handler):
    with patch.object(app, handler) as mock_handler:
        _tap(modifier, KeyCode.from_char(char))
        mock_handler.assert_not_called()


def test_bare_letter_still_fires_after_modifier_released():
    with patch.object(app, "single_test_click") as click:
        _tap(Key.ctrl_l, KeyCode.from_char("c"))
        _tap(KeyCode.from_char("c"))
        click.assert_called_once()


def test_plus_still_fires():
    # Shift isn't simulated: the dummy pynput backend used in tests makes all
    # Key members equal, so shift would be indistinguishable from ctrl.
    with patch.object(app, "increase_speed") as faster:
        _tap(KeyCode.from_char("+"))
        faster.assert_called_once()


def test_ctrl_alt_k_still_toggles_key_lock():
    with patch.object(app, "global_toggle_keys") as toggle:
        _tap(Key.ctrl_l, Key.alt_l, KeyCode.from_char("k"))
        toggle.assert_called_once()
