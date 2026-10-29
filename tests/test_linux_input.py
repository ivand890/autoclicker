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


def _terminal_listener(press, release):
    lst = linux_input.TerminalKeyListener.__new__(linux_input.TerminalKeyListener)
    lst.on_press, lst.on_release = press, release
    lst._pending = b""
    return lst


def test_terminal_ctrl_alt_k_sequence():
    events, press, release = _recorder()
    lst = _terminal_listener(press, release)

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


def _presses(events):
    return [k for kind, k in events if kind == "press"]


@pytest.mark.parametrize(
    "sequence",
    [
        b"\x1b[D",  # left arrow: "[" must not trigger decrease_hold
        b"\x1b[1;5C",  # Ctrl+Right
        b"\x1bOP",  # F1
        b"\x1bc",  # Alt+C: not the test-click hotkey
    ],
)
def test_terminal_escape_sequences_are_not_hotkeys(sequence):
    events, press, release = _recorder()
    lst = _terminal_listener(press, release)
    lst.handle_bytes(sequence + b"s")
    assert _presses(events) == [KeyCode.from_char("s")]


def test_terminal_sequence_split_across_reads():
    events, press, release = _recorder()
    lst = _terminal_listener(press, release)
    lst.handle_bytes(b"\x1b")
    lst.handle_bytes(b"\x0b")
    lst.handle_bytes(b"\x1b[")
    lst.handle_bytes(b"D")
    assert _presses(events) == [Key.ctrl_l, Key.alt_l, KeyCode.from_char("k")]


def test_terminal_lone_escape_is_dropped():
    events, press, release = _recorder()
    lst = _terminal_listener(press, release)
    lst.handle_bytes(b"\x1b")
    lst.flush_pending()
    lst.handle_bytes(b"s")
    assert _presses(events) == [KeyCode.from_char("s")]


class FakeDevice:
    def __init__(self, path, keyboard=True):
        self.path = path
        self.keyboard = keyboard
        self.closed = False

    def capabilities(self):
        ec = linux_input.ecodes
        keys = [ec.KEY_S, ec.KEY_K] if self.keyboard else [ec.BTN_LEFT]
        return {ec.EV_KEY: keys}

    def close(self):
        self.closed = True


def test_evdev_scan_opens_readable_keyboards_and_picks_up_new_ones(monkeypatch):
    nodes = ["/dev/input/event0", "/dev/input/event1"]
    opened = []

    def open_device(path):
        opened.append(path)
        return FakeDevice(path, keyboard=path != "/dev/input/event1")

    monkeypatch.setattr(linux_input.glob, "glob", lambda pattern: list(nodes))
    monkeypatch.setattr(linux_input.evdev, "InputDevice", open_device)
    lst = linux_input.EvdevKeyboardListener(lambda k: None, lambda k: None)

    # Doesn't depend on evdev.list_devices(), which requires write access
    assert lst.open_devices() == 1
    nodes.append("/dev/input/event2")
    lst._scan()
    assert sorted(lst._devices) == ["/dev/input/event0", "/dev/input/event2"]
    # Already-probed nodes are not reopened
    assert opened.count("/dev/input/event1") == 1


def test_evdev_disconnect_releases_held_keys_and_allows_reconnect(monkeypatch):
    ec = linux_input.ecodes
    monkeypatch.setattr(linux_input.glob, "glob", lambda pattern: ["/dev/input/event0"])
    monkeypatch.setattr(linux_input.evdev, "InputDevice", FakeDevice)
    events, press, release = _recorder()
    lst = linux_input.EvdevKeyboardListener(press, release)
    lst.open_devices()
    dev = lst._devices["/dev/input/event0"]

    lst.handle_event(ec.KEY_LEFTCTRL, 1)
    lst._disconnect("/dev/input/event0")

    assert events[-1] == ("release", Key.ctrl_l)
    assert dev.closed and not lst._devices
    lst._scan()
    assert "/dev/input/event0" in lst._devices
