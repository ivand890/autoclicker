"""Keyboard listeners for Linux sessions where pynput's X11 backend is blind.

On Wayland, pynput's Xlib listener only sees keys delivered to XWayland
windows, so hotkeys pressed in native Wayland apps (including the terminal)
never arrive. These listeners feed the same ``on_press``/``on_release``
callbacks with pynput ``Key``/``KeyCode`` objects:

- ``EvdevKeyboardListener`` reads physical keyboards from ``/dev/input``
  (global, requires read access, e.g. membership in the ``input`` group).
- ``TerminalKeyListener`` reads keys typed into the controlling terminal
  (works without extra permissions, but only while the terminal is focused).
"""

import os
import select
import sys
import threading

from pynput.keyboard import Key, KeyCode

try:
    import evdev
    from evdev import ecodes
except Exception:  # pragma: no cover - evdev ships with pynput on Linux
    evdev = None
    ecodes = None


def is_wayland_session() -> bool:
    return sys.platform.startswith("linux") and (
        bool(os.environ.get("WAYLAND_DISPLAY"))
        or os.environ.get("XDG_SESSION_TYPE") == "wayland"
    )


def _build_keymaps():
    if ecodes is None:
        return {}, {}
    special = {
        ecodes.KEY_LEFTCTRL: Key.ctrl_l,
        ecodes.KEY_RIGHTCTRL: Key.ctrl_r,
        ecodes.KEY_LEFTALT: Key.alt_l,
        ecodes.KEY_RIGHTALT: Key.alt_r,
        ecodes.KEY_LEFTSHIFT: Key.shift_l,
        ecodes.KEY_RIGHTSHIFT: Key.shift_r,
        ecodes.KEY_LEFTMETA: Key.cmd_l,
        ecodes.KEY_RIGHTMETA: Key.cmd_r,
    }
    # US layout: code -> (plain, shifted)
    chars = {
        getattr(ecodes, f"KEY_{c.upper()}"): (c, c.upper())
        for c in "abcdefghijklmnopqrstuvwxyz"
    }
    chars.update(
        {
            ecodes.KEY_MINUS: ("-", "_"),
            ecodes.KEY_EQUAL: ("=", "+"),
            ecodes.KEY_LEFTBRACE: ("[", "{"),
            ecodes.KEY_RIGHTBRACE: ("]", "}"),
            ecodes.KEY_KPPLUS: ("+", "+"),
            ecodes.KEY_KPMINUS: ("-", "-"),
        }
    )
    return special, chars


_SPECIAL_KEYS, _CHAR_KEYS = _build_keymaps()


class EvdevKeyboardListener:
    """Global keyboard listener reading every keyboard device via evdev."""

    def __init__(self, on_press, on_release):
        self.on_press = on_press
        self.on_release = on_release
        self._devices = []
        self._down = {}  # evdev code -> key object emitted on press
        self._stop_r, self._stop_w = os.pipe()
        self._thread = None

    @staticmethod
    def _is_keyboard(dev) -> bool:
        keys = dev.capabilities().get(ecodes.EV_KEY, [])
        return ecodes.KEY_S in keys and ecodes.KEY_K in keys

    def open_devices(self) -> int:
        """Open readable keyboard devices; return how many were opened."""
        if evdev is None:
            return 0
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
            except OSError:
                continue
            if self._is_keyboard(dev):
                self._devices.append(dev)
            else:
                dev.close()
        return len(self._devices)

    def _shift_down(self) -> bool:
        return ecodes.KEY_LEFTSHIFT in self._down or ecodes.KEY_RIGHTSHIFT in self._down

    def _key_for(self, code):
        if code in _SPECIAL_KEYS:
            return _SPECIAL_KEYS[code]
        if code in _CHAR_KEYS:
            plain, shifted = _CHAR_KEYS[code]
            return KeyCode.from_char(shifted if self._shift_down() else plain)
        return None

    def handle_event(self, code: int, value: int):
        # value: 0 = up, 1 = down, 2 = autorepeat (treated as press, like X11)
        if value in (1, 2):
            key = self._down.get(code) if value == 2 else None
            key = key or self._key_for(code)
            if key is None:
                return
            self._down[code] = key
            self.on_press(key)
        elif value == 0:
            key = self._down.pop(code, None)
            if key is not None:
                self.on_release(key)

    def _run(self):
        fds = {dev.fd: dev for dev in self._devices}
        while fds:
            readable, _, _ = select.select([*fds, self._stop_r], [], [])
            if self._stop_r in readable:
                return
            for fd in readable:
                dev = fds[fd]
                try:
                    events = list(dev.read())
                except OSError:
                    # Device unplugged
                    del fds[fd]
                    continue
                for ev in events:
                    if ev.type == ecodes.EV_KEY:
                        try:
                            self.handle_event(ev.code, ev.value)
                        except Exception:
                            pass

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        os.write(self._stop_w, b"x")
        if self._thread:
            self._thread.join(timeout=0.5)
        for dev in self._devices:
            try:
                dev.close()
            except Exception:
                pass
        os.close(self._stop_r)
        os.close(self._stop_w)


class TerminalKeyListener:
    """Fallback listener reading keys typed into the controlling terminal."""

    def __init__(self, on_press, on_release):
        self.on_press = on_press
        self.on_release = on_release
        self._fd = sys.stdin.fileno()
        self._saved_attrs = None
        self._stop_r, self._stop_w = os.pipe()
        self._thread = None

    @staticmethod
    def available() -> bool:
        return sys.stdin.isatty()

    def _tap(self, key, *modifiers):
        for m in modifiers:
            self.on_press(m)
        self.on_press(key)
        self.on_release(key)
        for m in reversed(modifiers):
            self.on_release(m)

    def handle_bytes(self, data: bytes):
        i = 0
        while i < len(data):
            ch = chr(data[i])
            # Ctrl+Alt+K arrives as ESC followed by Ctrl+K (0x0b)
            if ch == "\x1b" and data[i + 1 : i + 2] == b"\x0b":
                self._tap(KeyCode.from_char("k"), Key.ctrl_l, Key.alt_l)
                i += 2
                continue
            if ch.isprintable():
                self._tap(KeyCode.from_char(ch))
            i += 1

    def _run(self):
        while True:
            readable, _, _ = select.select([self._fd, self._stop_r], [], [])
            if self._stop_r in readable:
                return
            try:
                data = os.read(self._fd, 64)
            except OSError:
                return
            if not data:
                return
            try:
                self.handle_bytes(data)
            except Exception:
                pass

    def start(self):
        import termios
        import tty

        self._saved_attrs = termios.tcgetattr(self._fd)
        # cbreak keeps Ctrl+C working and output processing intact
        tty.setcbreak(self._fd)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        import termios

        os.write(self._stop_w, b"x")
        if self._thread:
            self._thread.join(timeout=0.5)
        if self._saved_attrs is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved_attrs)
        os.close(self._stop_r)
        os.close(self._stop_w)
