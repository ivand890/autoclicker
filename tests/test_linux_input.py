import pytest
from pynput.keyboard import Key, KeyCode

from autoclicker import linux_input

pytestmark = pytest.mark.skipif(
    linux_input.ecodes is None, reason="evdev not available"
)


def _recorder():
    events = []
    return (
        events,
        (lambda k: events.append(("press", k))),
        (lambda k: events.append(("release", k))),
    )


def test_evdev_translates_letters_and_modifiers():
    ec = linux_input.ecodes
    events, press, release = _recorder()
    lst = linux_input.EvdevKeyboardListener(press, release)

    lst.handle_event(ec.KEY_LEFTCTRL, 1)
    lst.handle_event(ec.KEY_LEFTALT, 1)
    lst.handle_event(ec.KEY_K, 1)
    lst.handle_event(ec.KEY_K, 0)

    assert events == [
        ("press", Key.ctrl_l),
        ("press", Key.alt_l),
        ("press", KeyCode.from_char("k")),
        ("release", KeyCode.from_char("k")),
    ]


def test_evdev_shift_equal_is_plus_and_release_matches_press():
    ec = linux_input.ecodes
    events, press, release = _recorder()
    lst = linux_input.EvdevKeyboardListener(press, release)

    lst.handle_event(ec.KEY_LEFTSHIFT, 1)
    lst.handle_event(ec.KEY_EQUAL, 1)
    lst.handle_event(ec.KEY_LEFTSHIFT, 0)
    lst.handle_event(ec.KEY_EQUAL, 0)

    assert ("press", KeyCode.from_char("+")) in events
    assert events[-1] == ("release", KeyCode.from_char("+"))


def test_evdev_ignores_unmapped_keys():
    events, press, release = _recorder()
    lst = linux_input.EvdevKeyboardListener(press, release)
    lst.handle_event(linux_input.ecodes.KEY_F5, 1)
    lst.handle_event(linux_input.ecodes.KEY_F5, 0)
    assert events == []


def test_terminal_ctrl_alt_k_sequence():
    events, press, release = _recorder()
    lst = linux_input.TerminalKeyListener.__new__(linux_input.TerminalKeyListener)
    lst.on_press, lst.on_release = press, release

    lst.handle_bytes(b"s\x1b\x0b")

    presses = [k for kind, k in events if kind == "press"]
    assert presses == [
        KeyCode.from_char("s"),
        Key.ctrl_l,
        Key.alt_l,
        KeyCode.from_char("k"),
    ]


def test_evdev_maps_super_as_modifier():
    ec = linux_input.ecodes
    events, press, release = _recorder()
    lst = linux_input.EvdevKeyboardListener(press, release)
    lst.handle_event(ec.KEY_LEFTMETA, 1)
    assert events == [("press", Key.cmd_l)]
