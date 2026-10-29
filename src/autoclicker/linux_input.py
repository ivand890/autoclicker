"""Keyboard listeners for Linux sessions where pynput's X11 backend is blind.

On Wayland, pynput's Xlib listener only sees keys delivered to XWayland
windows, so hotkeys pressed in native Wayland apps (including the terminal)
never arrive. These listeners feed the same ``on_press``/``on_release``
callbacks with pynput ``Key``/``KeyCode`` objects (or look-alikes when pynput
can't load because there is no X server):

- ``EvdevKeyboardListener`` reads physical keyboards from ``/dev/input``
  (global, requires read access, e.g. membership in the ``input`` group).
- ``TerminalKeyListener`` reads keys typed into the controlling terminal
  (works without extra permissions, but only while the terminal is focused).
"""

import enum
import glob
import os
import select
import sys
import threading
import time
from dataclasses import dataclass

try:
    from pynput.keyboard import Key, KeyCode
except ImportError:
    # pynput's Linux backend needs an X server. Hyprland without Xwayland
    # still works through IPC and evdev, which only need distinct key objects.
    Key = enum.Enum(
        "Key",
        "alt alt_l alt_r alt_gr cmd cmd_l cmd_r ctrl ctrl_l ctrl_r "
        "shift shift_l shift_r",
    )

    @dataclass(frozen=True)
    class KeyCode:
        char: str | None = None
        vk: int | None = None

        @classmethod
        def from_char(cls, char):
            return cls(char=char)


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

# How often to look for keyboards plugged in after startup
_RESCAN_INTERVAL = 2.0


class EvdevKeyboardListener:
    """Global keyboard listener reading every keyboard device via evdev."""

    def __init__(self, on_press, on_release):
        self.on_press = on_press
        self.on_release = on_release
        self._devices = {}  # path -> InputDevice
        self._probed = set()  # paths already tried, keyboards or not
        self._last_scan = 0.0
        self._down = {}  # evdev code -> key object emitted on press
        self._stop_r, self._stop_w = os.pipe()
        self._thread = None

    @staticmethod
    def _is_keyboard(dev) -> bool:
        keys = dev.capabilities().get(ecodes.EV_KEY, [])
        return ecodes.KEY_S in keys and ecodes.KEY_K in keys

    def _scan(self):
        """Open keyboards that appeared since the last scan."""
        self._last_scan = time.monotonic()
        # evdev.list_devices() skips devices that aren't also writable, but
        # reading is all we need, so let InputDevice try each node.
        paths = set(glob.glob("/dev/input/event*"))
        self._probed &= paths  # re-probe event nodes reused by new devices
        for path in sorted(paths - self._probed):
            self._probed.add(path)
            try:
                dev = evdev.InputDevice(path)
            except OSError:
                continue
            if self._is_keyboard(dev):
                self._devices[path] = dev
            else:
                dev.close()

    def open_devices(self) -> int:
        """Open readable keyboard devices; return how many were opened."""
        if evdev is None:
            return 0
        self._scan()
        return len(self._devices)

    def _disconnect(self, path):
        dev = self._devices.pop(path)
        self._probed.discard(path)
        try:
            dev.close()
        except Exception:
            pass
        # Its keys will never report a release; don't leave modifiers stuck.
        for code in list(self._down):
            self.on_release(self._down.pop(code))

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
        while True:
            fds = {dev.fd: path for path, dev in self._devices.items()}
            readable, _, _ = select.select(
                [*fds, self._stop_r], [], [], _RESCAN_INTERVAL
            )
            if self._stop_r in readable:
                return
            if time.monotonic() - self._last_scan >= _RESCAN_INTERVAL:
                self._scan()
            for fd in readable:
                path = fds[fd]
                try:
                    events = list(self._devices[path].read())
                except BlockingIOError:
                    continue
                except OSError:
                    # Device unplugged; a later scan picks it up if it returns
                    self._disconnect(path)
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
        for dev in self._devices.values():
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
        self._pending = b""  # start of an escape sequence split across reads
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
        data = self._pending + data
        self._pending = b""
        i = 0
        while i < len(data):
            if data[i] == 0x1B:
                end = self._escape_end(data, i)
                if end is None:
                    # Incomplete sequence; wait for the rest
                    self._pending = data[i:]
                    return
                # Ctrl+Alt+K arrives as ESC followed by Ctrl+K (0x0b). Every
                # other sequence (arrows, F-keys, Alt+key) is not a hotkey.
                if data[i : i + 2] == b"\x1b\x0b":
                    self._tap(KeyCode.from_char("k"), Key.ctrl_l, Key.alt_l)
                i = end
                continue
            ch = chr(data[i])
            if ch.isprintable():
                self._tap(KeyCode.from_char(ch))
            i += 1

    @staticmethod
    def _escape_end(data: bytes, i: int):
        """Index just past the escape sequence at data[i], or None if cut off."""
        if i + 1 >= len(data):
            return None
        if data[i + 1] == ord("O"):  # SS3, e.g. ESC O P for F1
            return i + 3 if i + 2 < len(data) else None
        if data[i + 1] == ord("["):  # CSI, e.g. ESC [ D or ESC [ 1 ; 5 C
            for j in range(i + 2, len(data)):
                if 0x40 <= data[j] <= 0x7E:  # final byte
                    return j + 1
            return None
        return i + 2  # ESC + key is Alt+key

    def flush_pending(self):
        """Treat a lone ESC that nothing followed as a plain Esc press."""
        self._pending = b""

    def _run(self):
        while True:
            # A real escape sequence arrives at once; a lone ESC is just Esc.
            timeout = 0.05 if self._pending else None
            readable, _, _ = select.select([self._fd, self._stop_r], [], [], timeout)
            if self._stop_r in readable:
                return
            if not readable:
                self.flush_pending()
                continue
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
