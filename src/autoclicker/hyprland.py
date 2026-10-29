"""Mouse control through Hyprland IPC, including native Wayland windows."""

import json
import os
import socket
import threading
import time


def _socket_path():
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not runtime or not signature:
        return None
    return os.path.join(runtime, "hypr", signature, ".socket.sock")


def available():
    path = _socket_path()
    return path is not None and os.path.exists(path)


def _request(*args):
    # Speak hyprctl's wire format directly instead of spawning hyprctl:
    # "<flags>/<command> <args>", e.g. "j/cursorpos" for `hyprctl -j cursorpos`.
    flags = "".join(arg[1:] for arg in args if arg.startswith("-"))
    command = " ".join(arg for arg in args if not arg.startswith("-"))
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            sock.connect(_socket_path())
            sock.sendall(f"{flags}/{command}".encode())
            # Hyprland closes the connection after writing the reply.
            chunks = []
            while chunk := sock.recv(8192):
                chunks.append(chunk)
    except (OSError, TypeError) as exc:
        raise RuntimeError(f"Hyprland: {exc}") from exc
    output = b"".join(chunks).decode(errors="replace").strip()
    if args[0] == "dispatch" and output != "ok":
        raise RuntimeError(f"Hyprland: {output}")
    return output


class MouseController:
    def __init__(self):
        self._click_lock = threading.Lock()
        # Lua-configured Hyprland parses dispatch arguments as Lua expressions.
        # Probe with a no-op, never with a click that could execute twice.
        try:
            _request("dispatch", "hl.dsp.no_op()")
        except RuntimeError:
            self._lua = False
        else:
            self._lua = True

    def _button(self, state):
        if self._lua:
            _request(
                "dispatch",
                'hl.dsp.send_key_state({mods="",key="mouse:272",state="'
                + state
                + '"})',
            )
        else:
            _request("dispatch", "sendkeystate", f",mouse:272,{state},")
        # send_key_state does not emit wl_pointer.frame on some Hyprland
        # versions. A warp to the current position flushes the event without
        # jitter, so clients receive down/up immediately and honor hold time.
        self.position = self.position

    @property
    def position(self):
        pos = json.loads(_request("-j", "cursorpos"))
        return pos["x"], pos["y"]

    @position.setter
    def position(self, pos):
        x, y = int(pos[0]), int(pos[1])
        if self._lua:
            _request("dispatch", f"hl.dsp.cursor.move({{x={x},y={y}}})")
        else:
            _request("dispatch", "movecursor", f"{x} {y}")

    def click(self, hold_time):
        # Serialize test clicks and automatic clicks to keep down/up paired.
        with self._click_lock:
            try:
                self._button("down")
                if hold_time > 0:
                    time.sleep(hold_time)
            except BaseException:
                # Try to release even after a timeout, but preserve the original
                # error if release also fails.
                try:
                    self._button("up")
                except Exception:
                    pass
                raise
            else:
                self._button("up")
