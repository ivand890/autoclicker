import time
import random
import pyautogui
from pynput import keyboard
from pynput.keyboard import Key
from pynput.mouse import Controller as MouseController, Button
import importlib
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
# Preferred click method: "pynput", "pyautogui", or "quartz" (macOS)
# Default to Quartz if available for best macOS compatibility
click_method = "quartz" if _HAS_QUARTZ else "pynput"
debug = False
jitter_enabled = False  # default jitter disabled (enable with 'j' if needed)
jitter_px = 1
local_keys_enabled = True  # when False, only the global hotkey works
_pressed_keys = set()  # track currently pressed keys for combo detection


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
        if other == "pynput":
            _click_with_pynput()
        elif other == "quartz":
            _click_with_quartz()
        else:
            _click_with_pyautogui()


def toggle_running():
    global running
    running = not running
    print("Autoclicker", "started" if running else "paused")


def global_toggle_keys():
    """Toggle local keys on/off via Ctrl+Alt+K (doesn't affect autoclicker)"""
    global local_keys_enabled
    local_keys_enabled = not local_keys_enabled

    if local_keys_enabled:
        print("Local keys enabled")
    else:
        print("Local keys disabled (only Ctrl+Alt+K works)")


def increase_speed():
    global delay
    delay = max(min_delay, round(delay - 0.1, 3))
    print(f"Speed increased, delay: {delay}s")


def decrease_speed():
    global delay
    delay = min(max_delay, round(delay + 0.1, 3))
    print(f"Speed decreased, delay: {delay}s")


def increase_hold():
    global hold_time
    hold_time = min(0.25, round(hold_time + 0.005, 3))
    print(f"Hold time increased to {hold_time}s")


def decrease_hold():
    global hold_time
    hold_time = max(0.0, round(hold_time - 0.005, 3))
    print(f"Hold time decreased to {hold_time}s")


def toggle_method():
    global click_method
    order = ["pynput", "quartz" if _HAS_QUARTZ else None, "pyautogui"]
    order = [m for m in order if m]
    try:
        idx = order.index(click_method)
    except ValueError:
        idx = 0
    click_method = order[(idx + 1) % len(order)]
    print(f"Click method: {click_method}")


def single_test_click():
    pos = pyautogui.position()
    print(f"Test click at {pos} using {click_method} (hold {hold_time}s)")
    perform_click(with_jitter=False)


def toggle_debug():
    global debug
    debug = not debug
    print(f"Debug {'enabled' if debug else 'disabled'}")


def _is_ctrl(key):
    return key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r)


def _is_alt(key):
    return key in (Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr)


def on_press(key):
    # Record key
    _pressed_keys.add(key)

    # Detect global combo Ctrl+Alt+K (works always)
    try:
        if (any(_is_ctrl(k) for k in _pressed_keys)
                and any(_is_alt(k) for k in _pressed_keys)):
            if getattr(key, 'char', None) == 'k':  # final key in combo
                global_toggle_keys()
                return
    except Exception:
        pass

    # If local keys locked, ignore all other keys
    if not local_keys_enabled:
        return

    try:
        ch = getattr(key, 'char', None)
        if ch == 's':
            toggle_running()
        elif ch == '+':  # shift + '=' on most keyboards
            increase_speed()
        elif ch == '-':
            decrease_speed()
        elif ch == ']':  # increase hold/"pressure"
            increase_hold()
        elif ch == '[':  # decrease hold/"pressure"
            decrease_hold()
        elif ch == 'm':  # toggle click method
            toggle_method()
        elif ch == 'c':  # single test click
            single_test_click()
        elif ch == 'd':  # toggle debug logs
            toggle_debug()
        elif ch == 'j':  # toggle jitter move
            global jitter_enabled
            jitter_enabled = not jitter_enabled
            state = 'enabled' if jitter_enabled else 'disabled'
            print(f"Jitter {state} (px={jitter_px})")
    except Exception:
        pass


def on_release(key):
    # Safely remove released key
    try:
        _pressed_keys.discard(key)
    except Exception:
        pass


def main():
    # Single listener handles both local keys and global combo
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    print(
        "Autoclicker ready.\n"
        "Keys: 's' start/pause, '+' faster, '-' slower, '['/']' hold time,\n"
        "      'm' toggle method, 'c' test click, 'd' debug, 'j' jitter.\n"
        "Global: Ctrl+Alt+K lock/unlock local keys (doesn't affect clicking)"
    )

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
                time.sleep(random.uniform(delay * 0.5, delay * 1.5))
            else:
                time.sleep(0.05)
    except KeyboardInterrupt:
        print("Autoclicker stopped.")
    finally:
        try:
            listener.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
