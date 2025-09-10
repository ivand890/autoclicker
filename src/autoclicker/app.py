import time
import random
import pyautogui
from pynput import keyboard
from pynput.keyboard import Key
from pynput.mouse import Controller as MouseController, Button
import importlib
import sys
import shutil
from dataclasses import dataclass

try:
    importlib.import_module("Quartz")
    _HAS_QUARTZ = True
except Exception:
    _HAS_QUARTZ = False


# Runtime state
running = False
delay = 0.5  # base delay in seconds (default)
min_delay = 0.05
max_delay = 5.0
hold_time = 0.1  # how long to hold the button down per click
# Randomization multipliers for per-click delay
MIN_DELAY_MULTIPLIER = 0.5
MAX_DELAY_MULTIPLIER = 1.5
# Preferred click method: "pynput", "pyautogui", or "quartz" (macOS)
# Default to Quartz if available for best macOS compatibility
click_method = "quartz" if _HAS_QUARTZ else "pynput"
debug = False
jitter_enabled = False  # default jitter disabled (enable with 'j' if needed)
jitter_px = 1
local_keys_enabled = True  # when False, only the global hotkey works
_pressed_keys = set()  # track currently pressed keys for combo detection


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
        jitter_sym = "J" if st.jitter_enabled else "-"
        debug_sym = "D" if st.debug else "-"
        method_map = {"quartz": "QTZ", "pynput": "PNP", "pyautogui": "PGA"}
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
    if mark:
        status_renderer.mark()


def _set_message(msg: str):
    status.message = msg
    status.message_ts = time.time()
    status_renderer.mark()


# Configure pyautogui safety
pyautogui.FAILSAFE = False  # disable corner failsafe to avoid unintended stops
pyautogui.PAUSE = 0  # no extra pause added by pyautogui

# Shared mouse controller for pynput method
_mouse = MouseController()


def _click_with_pynput():
    # Click at current pointer location using Quartz events via pynput
    _mouse.press(Button.left)
    if hold_time > 0:
        time.sleep(hold_time)
    _mouse.release(Button.left)


def _click_with_pyautogui():
    # Click at current pointer location via pyautogui
    pyautogui.mouseDown()
    if hold_time > 0:
        time.sleep(hold_time)
    pyautogui.mouseUp()


def _convert_to_quartz_point(pos):
    # Convert top-left origin (pyautogui) to bottom-left origin (Quartz)
    try:
        Quartz = importlib.import_module("Quartz")
        CG = Quartz.CoreGraphics
        bounds = CG.CGDisplayBounds(CG.CGMainDisplayID())
        height = int(bounds.size.height)
        return CG.CGPoint(pos[0], height - pos[1])
    except Exception:
        # Fallback: return as-is (may be wrong on some layouts)
        try:
            CG = Quartz.CoreGraphics  # type: ignore
            return CG.CGPoint(pos[0], pos[1])
        except Exception:
            return pos


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
        if click_method in ("pynput", "quartz"):
            x, y = _mouse.position
            _mouse.position = (x + jitter_px, y)
            _mouse.position = (x, y)
        else:
            pyautogui.moveRel(jitter_px, 0, duration=0)
            pyautogui.moveRel(-jitter_px, 0, duration=0)
    except Exception:
        # ignore jitter failures
        pass


def perform_click(with_jitter: bool = True):
    global click_method
    try:
        if with_jitter:
            _jitter_move()
        if click_method == "pynput":
            _click_with_pynput()
        elif click_method == "quartz":
            _click_with_quartz()
        else:
            _click_with_pyautogui()
        status.click_count += 1
        status.last_click_ts = time.time()
        status_renderer.mark()
    except Exception as e:
        # Fallback to the other method once if one fails
        order = ["pynput", "quartz", "pyautogui"]
        try:
            idx = order.index(click_method)
        except ValueError:
            idx = 0
        other = order[(idx + 1) % len(order)]
        if debug:
            print(f"Click via {click_method} failed: {e} -> trying {other}")
        click_method = other
        status.fallbacks += 1
        status_renderer.mark()
        _set_message(f"fallback->{other}")
        if other == "pynput":
            _click_with_pynput()
        elif other == "quartz":
            _click_with_quartz()
        else:
            _click_with_pyautogui()
        status.click_count += 1
        status.last_click_ts = time.time()
        status_renderer.mark()


def toggle_running():
    global running
    running = not running
    _set_message("started" if running else "paused")
    _refresh_status()


def global_toggle_keys():
    """Toggle local keys on/off via Ctrl+Alt+K (doesn't affect autoclicker)"""
    global local_keys_enabled
    local_keys_enabled = not local_keys_enabled

    _set_message("keys:unlocked" if local_keys_enabled else "keys:locked")
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
    order = ["pynput", "quartz" if _HAS_QUARTZ else None, "pyautogui"]
    order = [m for m in order if m]
    try:
        idx = order.index(click_method)
    except ValueError:
        idx = 0
    click_method = order[(idx + 1) % len(order)]
    _set_message(f"method {click_method}")
    _refresh_status()


def single_test_click():
    pos = pyautogui.position()
    _set_message(f"test {pos[0]},{pos[1]}")
    perform_click(with_jitter=False)
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


def on_press(key):
    # Record key
    _pressed_keys.add(key)

    # Detect global combo Ctrl+Alt+K (works always)
    try:
        if any(_is_ctrl(k) for k in _pressed_keys) and any(
            _is_alt(k) for k in _pressed_keys
        ):
            if getattr(key, "char", None) == "k":  # final key in combo
                global_toggle_keys()
                return
    except Exception:
        pass

    # If local keys locked, ignore all other keys
    if not local_keys_enabled:
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
    except Exception:
        pass


def on_release(key):
    # Safely remove released key
    try:
        _pressed_keys.discard(key)
    except Exception:
        pass


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
                "      j jitter • d debug • Ctrl+Alt+K lock",
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
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    print("Autoclicker ready (status line below). Press Ctrl+C to exit.")
    print(
        "Keys: 's' start/pause, '+' faster, '-' slower, '['/']' hold time,\n"
        "      'm' method, 'c' test, 'j' jitter, 'd' debug,\n"
        "      Ctrl+Alt+K lock keys"
    )
    _refresh_status()

    try:
        while True:
            if running:
                if debug:
                    pos = pyautogui.position()
                    print(
                        f"Clicking at {pos} via {click_method} "
                        f"(delay {delay}s, hold {hold_time}s)"
                    )
                perform_click(with_jitter=True)
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
            status_renderer.finalize(status)
        except Exception:
            pass
