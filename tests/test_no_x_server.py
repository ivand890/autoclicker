import subprocess
import sys
import textwrap


def _run(code, **env):
    # pynput raises ImportError at import time for an unknown backend, the
    # same way it does when there is no X server to connect to.
    env = {"PYNPUT_BACKEND": "missing", "WAYLAND_DISPLAY": "wayland-1", **env}
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_hyprland_starts_without_pynput():
    result = _run(
        """
        from autoclicker import hyprland
        hyprland.available = lambda: True
        hyprland._request = lambda *args: "ok"
        from autoclicker import app
        from autoclicker.linux_input import Key, KeyCode
        assert app._HAS_HYPRLAND and app.keyboard is None
        assert Key.ctrl_l != Key.shift_l
        assert KeyCode.from_char("c") == KeyCode.from_char("c")
        app.local_keys_enabled = True
        app.on_press(Key.ctrl_l)
        assert app._should_defer_click()
        """
    )
    assert result.returncode == 0, result.stderr


def test_without_hyprland_pynput_error_is_raised():
    result = _run(
        """
        from autoclicker import hyprland
        hyprland.available = lambda: False
        from autoclicker import app
        """
    )
    assert result.returncode != 0
    assert "ImportError" in result.stderr
