import time
import random
import threading
from pynput import keyboard
from pynput.keyboard import Key
from pynput.mouse import (
    Controller as MouseController,
    Button,
    Listener as MouseListener,
)
import importlib
import sys
import shutil
from dataclasses import dataclass

from . import hyprland, linux_input

try:
    importlib.import_module("Quartz")
    _HAS_QUARTZ = True
except Exception:
    _HAS_QUARTZ = False

# Click engines available on this platform, in toggle/fallback order
_HAS_HYPRLAND = linux_input.is_wayland_session() and hyprland.available()
_ENGINES = (
    ["hyprland"]
    if _HAS_HYPRLAND
    else ["pynput", "quartz"]
    if _HAS_QUARTZ
    else ["pynput"]
)

# Runtime state
running = False
delay = 0.5  # base delay in seconds (default)
min_delay = 0.05
max_delay = 5.0
hold_time = 0.1  # how long to hold the button down per click
# Randomization multipliers for per-click delay
MIN_DELAY_MULTIPLIER = 0.5
MAX_DELAY_MULTIPLIER = 1.5
# Preferred click method: "pynput" or "quartz" (macOS)
# Default to Quartz if available for best macOS compatibility
click_method = "hyprland" if _HAS_HYPRLAND else "quartz" if _HAS_QUARTZ else "pynput"
debug = False
jitter_enabled = False  # default jitter disabled (enable with 'j' if needed)
jitter_px = 1
local_keys_enabled = True  # when False, only the global hotkey works
cursor_lock_enabled = False  # Lock cursor position when running
locked_position = None  # (x, y) tuple
_last_lock_alert = 0.0  # track last alert time for throttling
_pressed_keys = set()  # track currently pressed keys for combo detection
_cursor_lock_thread = None
_cursor_lock_active = threading.Event()
_cursor_lock_shutdown = threading.Event()


# ---------------- Status line support -----------------
@dataclass
class Status:
    start_time: float
    running: bool
    delay: float
    hold_time: float
    click_method: str
    jitter_enabled: bool
    debug: bool
    local_keys_enabled: bool
    cursor_lock_enabled: bool
    click_count: int = 0
    last_click_ts: float | None = None
    next_delay: float | None = None
    fallbacks: int = 0
    message: str | None = None
    message_ts: float | None = None


class StatusRenderer:
    def __init__(self, use_color: bool = True, interval: float = 0.1):
        self.interval = interval
        self.last_render = 0.0
        self.dirty = True
        self.use_color = use_color and sys.stdout.isatty()
        self._cached_line = ""
        self._spinners = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._spinner_idx = 0
        self._last_spinner_tick = 0.0

    def mark(self):
        self.dirty = True

    def _color(self, text: str, code: str):
        if not self.use_color:
            return text
        return f"\x1b[{code}m{text}\x1b[0m"

    def build_line(self, st: Status) -> str:
        now = time.time()
        # Spinner only when running
        spinner = ""
        if st.running and now - self._last_spinner_tick > 0.15:
            self._spinner_idx = (self._spinner_idx + 1) % len(self._spinners)
            self._last_spinner_tick = now
        if st.running:
            spinner = self._spinners[self._spinner_idx] + " "
        state_sym = "▶" if st.running else "⏸"
        # lock shows yes/no for compatibility (yes = locked)
        lock_val = "no" if st.local_keys_enabled else "yes"
        clock_val = "yes" if st.cursor_lock_enabled else "no"
        jitter_sym = "J" if st.jitter_enabled else "-"
        debug_sym = "D" if st.debug else "-"
        method_map = {"quartz": "QTZ", "pynput": "PNP", "hyprland": "HYP"}
        method_disp = method_map.get(st.click_method, st.click_method)
        # Fixed width numeric fields to avoid jitter
        delay_val = f"{st.delay:5.2f}s"
        rng_lo = f"{st.delay * MIN_DELAY_MULTIPLIER:5.2f}"
        rng_hi = f"{st.delay * MAX_DELAY_MULTIPLIER:5.2f}"
        rng_val = f"{rng_lo}–{rng_hi}"
        hold_val = f"{st.hold_time:5.2f}s"
        last_age = (now - st.last_click_ts) if st.last_click_ts else None
        if last_age is not None:
            last_val = f"{last_age:5.2f}s"
        else:
            last_val = "  --  "
        if st.next_delay is not None:
            next_val = f"{st.next_delay:5.2f}s"
        else:
            next_val = "  --  "
        elapsed = now - st.start_time
        cps = (st.click_count / elapsed) if st.click_count and elapsed > 0 else 0.0
        cps_val = f"{cps:4.1f}" if st.click_count else " 0.0"
        clicks_val = f"{st.click_count:6d}"
        line_parts = [
            f"{spinner}{state_sym}",
            f"delay:{delay_val}",
            f"rng:{rng_val}",
            f"hold:{hold_val}",
            f"meth:{method_disp}",
            f"jitter:{jitter_sym}",
            f"debug:{debug_sym}",
            f"lock:{lock_val}",
            f"clock:{clock_val}",
            f"clicks:{clicks_val}",
            f"last:{last_val}",
            f"next:{next_val}",
            f"cps:{cps_val}",
        ]
        if st.fallbacks:
            line_parts.append(f"fb:{st.fallbacks}")
        if st.message and st.message_ts and (now - st.message_ts) < 2.5:
            line_parts.append(st.message)
        line = " | ".join(line_parts)
        # Color minimal elements
        if self.use_color:
            if st.running:
                line = line.replace(state_sym, self._color(state_sym, "32"))
            else:
                line = line.replace(state_sym, self._color(state_sym, "33"))
            if not st.local_keys_enabled:
                line = line.replace("lock:yes", self._color("lock:yes", "31"))
            if st.cursor_lock_enabled:
                line = line.replace("clock:yes", self._color("clock:yes", "36"))
        width = shutil.get_terminal_size(fallback=(120, 20)).columns
        if len(line) > width:
            line = line[: max(0, width - 1)] + "…"
        return line

    def maybe_render(self, st: Status, force: bool = False):
        now = time.time()
        if not self.dirty and not force and (now - self.last_render) < self.interval:
            return
        line = self.build_line(st)
        if line != self._cached_line or force:
            sys.stdout.write("\r" + line + "\x1b[K")
            sys.stdout.flush()
            self._cached_line = line
        self.dirty = False
        self.last_render = now

    def finalize(self, st: Status):
        # Clear line then print summary
        elapsed = time.time() - st.start_time
        summary = (
            f"Stopped after {st.click_count} clicks in {elapsed:.1f}s "
            f"(avg {(st.click_count / elapsed) if elapsed > 0 else 0:.2f} cps)"
        )
        sys.stdout.write("\r" + " " * max(len(self._cached_line), len(summary)) + "\r")
        print(summary)


status = Status(
    start_time=time.time(),
    running=running,
    delay=delay,
    hold_time=hold_time,
    click_method=click_method,
    jitter_enabled=jitter_enabled,
    debug=debug,
    local_keys_enabled=local_keys_enabled,
    cursor_lock_enabled=cursor_lock_enabled,
)
status_renderer = StatusRenderer()


def _refresh_status(mark: bool = True):
    # Sync global vars into status object
    status.running = running
    status.delay = delay
    status.hold_time = hold_time
    status.click_method = click_method
    status.jitter_enabled = jitter_enabled
    status.debug = debug
    status.local_keys_enabled = local_keys_enabled
    status.cursor_lock_enabled = cursor_lock_enabled
    if mark:
        status_renderer.mark()


def _set_message(msg: str):
    status.message = msg
    status.message_ts = time.time()
    status_renderer.mark()


# Shared controller for clicks, cursor position, jitter, and cursor lock.
_mouse = hyprland.MouseController() if _HAS_HYPRLAND else MouseController()


def _click_with_pynput():
    # Click at current pointer location using Quartz events via pynput
    _mouse.press(Button.left)
    if hold_time > 0:
        time.sleep(hold_time)
    _mouse.release(Button.left)


def _click_with_quartz():
    if not _HAS_QUARTZ:
        raise RuntimeError("Quartz not available")
    Quartz = importlib.import_module("Quartz")
    CG = Quartz.CoreGraphics
    # Use current Quartz cursor location directly to avoid multi-display
    # conversion issues
    evt = CG.CGEventCreate(None)
    qpt = CG.CGEventGetLocation(evt)
    down = CG.CGEventCreateMouseEvent(
        None, CG.kCGEventLeftMouseDown, qpt, CG.kCGMouseButtonLeft
    )
    up = CG.CGEventCreateMouseEvent(
        None, CG.kCGEventLeftMouseUp, qpt, CG.kCGMouseButtonLeft
    )
    CG.CGEventPost(CG.kCGHIDEventTap, down)
    if hold_time > 0:
        time.sleep(hold_time)
    CG.CGEventPost(CG.kCGHIDEventTap, up)
    # tiny yield to ensure event dispatch
    time.sleep(0.001)


def _jitter_move():
    if not jitter_enabled or jitter_px <= 0:
        return
    try:
        x, y = _mouse.position
        _mouse.position = (x + jitter_px, y)
        _mouse.position = (x, y)
    except Exception:
        # ignore jitter failures
        pass


def _click_with(method: str):
    if method == "hyprland":
        _mouse.click(hold_time)
    elif method == "quartz":
        _click_with_quartz()
    else:
        _click_with_pynput()


def perform_click(with_jitter: bool = True):
    global click_method
    try:
        if with_jitter:
            _jitter_move()
        _click_with(click_method)
        status.click_count += 1
        status.last_click_ts = time.time()
        status_renderer.mark()
    except Exception as e:
        # Fallback to the other method once if one fails
        try:
            idx = _ENGINES.index(click_method)
        except ValueError:
            idx = -1
        other = _ENGINES[(idx + 1) % len(_ENGINES)]
        if other == click_method:
            # No alternative engine on this platform
            raise
        if debug:
            print(f"Click via {click_method} failed: {e} -> trying {other}")
        click_method = other
        status.fallbacks += 1
        status_renderer.mark()
        _set_message(f"fallback->{other}")
        _click_with(other)
        status.click_count += 1
        status.last_click_ts = time.time()
        status_renderer.mark()


def _try_perform_click(with_jitter=True):
    global running
    try:
        perform_click(with_jitter=with_jitter)
    except Exception as exc:
        running = False
        _sync_cursor_lock_worker_state()
        _refresh_status()
        _set_message(f"Click failed: {exc}")
        print(f"\nClick failed; paused: {exc}", file=sys.stderr)
        return False
    return True


def toggle_running():
    global running, locked_position
    running = not running
    if running:
        locked_position = _mouse.position
    _sync_cursor_lock_worker_state()
    _set_message("started" if running else "paused")
    _refresh_status()


def global_toggle_keys():
    """Toggle local keys on/off via Ctrl+Alt+K (doesn't affect autoclicker)"""
    global local_keys_enabled
    local_keys_enabled = not local_keys_enabled

    _set_message("keys:unlocked" if local_keys_enabled else "keys:locked")
    _refresh_status()


def toggle_cursor_lock():
    global cursor_lock_enabled, locked_position
    cursor_lock_enabled = not cursor_lock_enabled
    if cursor_lock_enabled:
        locked_position = _mouse.position
    _sync_cursor_lock_worker_state()
    state = "enabled" if cursor_lock_enabled else "disabled"
    _set_message(f"cursor_lock:{state}")
    _refresh_status()


def increase_speed():
    global delay
    delay = max(min_delay, round(delay - 0.1, 3))
    _set_message(f"delay {delay:.2f}s")
    _refresh_status()


def decrease_speed():
    global delay
    delay = min(max_delay, round(delay + 0.1, 3))
    _set_message(f"delay {delay:.2f}s")
    _refresh_status()


def increase_hold():
    global hold_time
    hold_time = min(0.25, round(hold_time + 0.005, 3))
    _set_message(f"hold {hold_time:.3f}s")
    _refresh_status()


def decrease_hold():
    global hold_time
    hold_time = max(0.0, round(hold_time - 0.005, 3))
    _set_message(f"hold {hold_time:.3f}s")
    _refresh_status()


def toggle_method():
    global click_method
    try:
        idx = _ENGINES.index(click_method)
    except ValueError:
        idx = 0
    click_method = _ENGINES[(idx + 1) % len(_ENGINES)]
    _set_message(f"method {click_method}")
    _refresh_status()


def single_test_click():
    x, y = _mouse.position
    _set_message(f"test {int(x)},{int(y)}")
    _try_perform_click(with_jitter=False)
    _refresh_status()


def toggle_debug():
    global debug
    debug = not debug
    _set_message("debug:on" if debug else "debug:off")
    _refresh_status()


def _is_ctrl(key):
    return key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r)


def _is_alt(key):
    return key in (Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr)


def _is_cmd(key):
    return key in (Key.cmd, Key.cmd_l, Key.cmd_r)


def on_press(key):
    # Record key
    _pressed_keys.add(key)

    # Detect global combo Ctrl+Alt+K (works always)
    try:
        if any(_is_ctrl(k) for k in _pressed_keys) and any(
            _is_alt(k) for k in _pressed_keys
        ):
            # On Windows, Ctrl+K often results in '\x0b' (ASCII 11)
            # And Ctrl+Alt+K might result in vk=75 with char=None
            char = getattr(key, "char", None)
            vk = getattr(key, "vk", None)
            if char in ("k", "\x0b") or vk == 75:
                global_toggle_keys()
                return
    except Exception:
        pass

    # If local keys locked, ignore all other keys
    if not local_keys_enabled:
        return

    # Listeners are global, so Ctrl+C, Ctrl+S, Super+L, etc. meant for other
    # apps would otherwise fire the bare-letter hotkeys. On Hyprland, the
    # resulting injected click also drops Ctrl, breaking Ctrl+C in the terminal.
    if any(_is_ctrl(k) or _is_alt(k) or _is_cmd(k) for k in _pressed_keys):
        return

    try:
        ch = getattr(key, "char", None)
        if ch == "s":
            toggle_running()
        elif ch == "+":  # shift + '=' on most keyboards
            increase_speed()
        elif ch == "-":
            decrease_speed()
        elif ch == "]":  # increase hold/"pressure"
            increase_hold()
        elif ch == "[":  # decrease hold/"pressure"
            decrease_hold()
        elif ch == "m":  # toggle click method
            toggle_method()
        elif ch == "c":  # single test click
            single_test_click()
        elif ch == "d":  # toggle debug logs
            toggle_debug()
        elif ch == "j":  # toggle jitter move
            global jitter_enabled
            jitter_enabled = not jitter_enabled
            state = "enabled" if jitter_enabled else "disabled"
            _set_message(f"jitter:{state}")
            _refresh_status()
        elif ch == "l":  # toggle cursor lock
            toggle_cursor_lock()
    except Exception:
        pass


def on_release(key):
    # Safely remove released key
    try:
        _pressed_keys.discard(key)
    except Exception:
        pass


def on_mouse_move(x, y):
    # We now use a dedicated thread for more aggressive locking on Windows,
    # but we keep the listener for potential future use or other platforms.
    pass


def _enforce_cursor_lock():
    """Logic to enforce cursor lock. Returns True if alert was triggered."""
    global _last_lock_alert
    if running and cursor_lock_enabled and locked_position:
        curr = _mouse.position
        # Check distance (squared)
        dx = curr[0] - locked_position[0]
        dy = curr[1] - locked_position[1]
        if (dx * dx + dy * dy) > 25:  # > 5 pixels
            _mouse.position = locked_position
            now = time.time()
            if now - _last_lock_alert > 2.0:
                _set_message("Cursor locked! Movement detected.")
                _last_lock_alert = now
                return True
    return False


def _ensure_cursor_lock_worker():
    global _cursor_lock_thread
    if _cursor_lock_thread and _cursor_lock_thread.is_alive():
        return
    _cursor_lock_shutdown.clear()
    _cursor_lock_thread = threading.Thread(
        target=_cursor_lock_worker,
        daemon=True,
    )
    _cursor_lock_thread.start()


def _sync_cursor_lock_worker_state():
    if running and cursor_lock_enabled:
        _ensure_cursor_lock_worker()
        _cursor_lock_active.set()
    else:
        _cursor_lock_active.clear()


def _stop_cursor_lock_worker():
    global _cursor_lock_thread
    thread = _cursor_lock_thread
    _cursor_lock_shutdown.set()
    _cursor_lock_active.set()
    if thread and thread.is_alive():
        thread.join(timeout=0.1)
    _cursor_lock_active.clear()
    _cursor_lock_thread = None


def _cursor_lock_worker():
    """Dedicated thread to enforce cursor lock with high frequency."""
    while not _cursor_lock_shutdown.is_set():
        _cursor_lock_active.wait()
        if _cursor_lock_shutdown.is_set():
            break
        while _cursor_lock_active.is_set() and not _cursor_lock_shutdown.is_set():
            try:
                _enforce_cursor_lock()
            except Exception:
                pass
            time.sleep(1 / 60)  # ~60Hz; each check is a compositor round trip


def _create_keyboard_listener():
    """Return (listener, note). The note explains degraded hotkey support."""
    if not linux_input.is_wayland_session():
        return keyboard.Listener(on_press=on_press, on_release=on_release), None

    # pynput's X11 backend can't see keys sent to Wayland windows
    evdev_listener = linux_input.EvdevKeyboardListener(on_press, on_release)
    if evdev_listener.open_devices():
        return evdev_listener, "Wayland: global hotkeys via /dev/input."
    evdev_listener.stop()

    note = (
        "Wayland: no access to /dev/input, so hotkeys only work while this\n"
        "terminal is focused. For global hotkeys run:\n"
        "  sudo usermod -aG input $USER   (then log out and back in)"
    )
    if linux_input.TerminalKeyListener.available():
        return linux_input.TerminalKeyListener(on_press, on_release), note
    return keyboard.Listener(on_press=on_press, on_release=on_release), note


def main():  # pragma: no cover - interactive app
    # Safety: honor simple flags here too, so that even if the CLI wrapper is
    # bypassed (or an older entry point is used), we don't start the loop.
    try:
        import sys as _sys

        _argv = _sys.argv[1:]
        if any(a in ("-h", "--help") for a in _argv):
            _help_lines = [
                "autoclicker — macOS-friendly Python autoclicker",
                "",
                "Usage:",
                "  autoclicker [--help] [--version]",
                "",
                "Notes:",
                "  - Grant Accessibility and Input Monitoring",
                "    permissions to your terminal app in macOS settings,",
                "    then restart the terminal.",
                "  - Hotkeys:",
                "      s start/pause • +/− speed • ]/[ hold • m method •",
                "      c test",
                "      j jitter • d debug • l lock cursor • Ctrl+Alt+K lock keys",
            ]
            print("\n".join(_help_lines))
            return
        if any(a in ("-V", "--version") for a in _argv):
            from . import __version__ as _ver

            print(_ver)
            return
    except Exception:
        # Never block startup if flag parsing fails; continue normally.
        pass

    # Single listener handles both local keys and global combo
    listener, listener_note = _create_keyboard_listener()
    listener.start()

    # Hyprland supplies pointer position directly; no X11 listener needed.
    mouse_listener = None
    if not _HAS_HYPRLAND:
        mouse_listener = MouseListener(on_move=on_mouse_move)
        mouse_listener.start()

    print("Autoclicker ready (status line below). Press Ctrl+C to exit.")
    print(
        "Keys: 's' start/pause, '+' faster, '-' slower, '['/']' hold time,\n"
        "      'm' method, 'c' test, 'j' jitter, 'd' debug,\n"
        "      Ctrl+Alt+K lock keys, 'l' cursor lock"
    )
    if listener_note:
        print(listener_note)
    if _HAS_HYPRLAND:
        print("Wayland: native clicks via Hyprland (HYP).")
    elif linux_input.is_wayland_session():
        print(
            "Warning: pynput clicks only support XWayland windows on this compositor."
        )
    _refresh_status()

    try:
        while True:
            if running:
                if debug:
                    pos = _mouse.position
                    print(
                        f"Clicking at {pos} via {click_method} "
                        f"(delay {delay}s, hold {hold_time}s)"
                    )
                if not _try_perform_click(with_jitter=True):
                    continue
                nd = random.uniform(
                    delay * MIN_DELAY_MULTIPLIER, delay * MAX_DELAY_MULTIPLIER
                )
                status.next_delay = nd
                status_renderer.mark()
                status_renderer.maybe_render(status)
                time.sleep(nd)
                status.next_delay = None
                status_renderer.mark()
            else:
                time.sleep(0.05)
            status_renderer.maybe_render(status)
    except KeyboardInterrupt:
        print("Autoclicker stopped.")
    finally:
        try:
            listener.stop()
        except Exception:
            pass
        try:
            if mouse_listener is not None:
                mouse_listener.stop()
        except Exception:
            pass
        try:
            _stop_cursor_lock_worker()
        except Exception:
            pass
        try:
            status_renderer.finalize(status)
        except Exception:
            pass
