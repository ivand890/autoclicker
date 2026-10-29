from unittest.mock import Mock, PropertyMock

import pytest

from autoclicker import app, hyprland


def test_click_releases_button_if_interrupted(monkeypatch):
    monkeypatch.setattr(
        hyprland.MouseController, "position", PropertyMock(return_value=(0, 0))
    )
    request = Mock()
    monkeypatch.setattr(hyprland, "_request", request)
    monkeypatch.setattr(hyprland.time, "sleep", Mock(side_effect=KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        hyprland.MouseController().click(0.1)
    assert [call.args for call in request.call_args_list] == [
        ("dispatch", "hl.dsp.no_op()"),
        ("dispatch", 'hl.dsp.send_key_state({mods="",key="mouse:272",state="down"})'),
        ("dispatch", 'hl.dsp.send_key_state({mods="",key="mouse:272",state="up"})'),
    ]


class FakeSocket:
    def __init__(self, reply):
        self.reply = reply
        self.sent = b""
        self.path = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def settimeout(self, timeout):
        pass

    def connect(self, path):
        self.path = path

    def sendall(self, data):
        self.sent += data

    def recv(self, size):
        reply, self.reply = self.reply, b""
        return reply


@pytest.fixture
def fake_socket(monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "sig")

    def install(reply):
        sock = FakeSocket(reply)
        monkeypatch.setattr(hyprland.socket, "socket", Mock(return_value=sock))
        return sock

    return install


def test_request_uses_hyprctl_wire_format(fake_socket):
    sock = fake_socket(b'{"x": 1, "y": 2}\n')
    assert hyprland._request("-j", "cursorpos") == '{"x": 1, "y": 2}'
    assert sock.path == "/run/user/1000/hypr/sig/.socket.sock"
    assert sock.sent == b"j/cursorpos"

    sock = fake_socket(b"ok")
    hyprland._request("dispatch", "sendkeystate", ",mouse:272,down,")
    assert sock.sent == b"/dispatch sendkeystate ,mouse:272,down,"


def test_socket_failure_raises_runtime_error(fake_socket, monkeypatch):
    sock = fake_socket(b"")
    monkeypatch.setattr(sock, "connect", Mock(side_effect=ConnectionRefusedError()))
    with pytest.raises(RuntimeError, match="Hyprland"):
        hyprland._request("-j", "cursorpos")


def test_cursor_coordinates_include_negative_monitor_origin(monkeypatch):
    request = Mock(return_value='{"x": -1800, "y": 720}')
    monkeypatch.setattr(hyprland, "_request", request)
    mouse = hyprland.MouseController()
    assert mouse.position == (-1800, 720)
    mouse.position = (-1800, 720)
    request.assert_called_with("dispatch", "hl.dsp.cursor.move({x=-1800,y=720})")


def test_hyprland_failure_does_not_count_or_fallback_to_x11(monkeypatch):
    monkeypatch.setattr(app, "click_method", "hyprland")
    monkeypatch.setattr(app, "_ENGINES", ["hyprland"])
    mouse = Mock()
    mouse.click.side_effect = RuntimeError("IPC failed")
    monkeypatch.setattr(app, "_mouse", mouse)
    count = app.status.click_count
    with pytest.raises(RuntimeError, match="IPC failed"):
        app.perform_click(with_jitter=False)
    assert app.status.click_count == count
    mouse.press.assert_not_called()


def test_native_click_uses_configured_hold(monkeypatch):
    mouse = Mock()
    monkeypatch.setattr(app, "_mouse", mouse)
    monkeypatch.setattr(app, "hold_time", 0.15)
    app._click_with("hyprland")
    mouse.click.assert_called_once_with(0.15)


def test_dispatch_error_includes_compositor_message(fake_socket):
    fake_socket(b"Lua syntax error")
    with pytest.raises(RuntimeError, match="Lua syntax error"):
        hyprland._request("dispatch", "bad")


def test_legacy_dispatch_when_lua_unavailable(monkeypatch):
    request = Mock(
        side_effect=[
            RuntimeError("Invalid dispatcher"),
            "ok",
            '{"x":0,"y":0}',
            "ok",
            "ok",
            '{"x":0,"y":0}',
            "ok",
            "ok",
        ]
    )
    monkeypatch.setattr(hyprland, "_request", request)
    mouse = hyprland.MouseController()
    mouse.click(0)
    mouse.position = (10, 20)
    assert [call.args for call in request.call_args_list][1:] == [
        ("dispatch", "sendkeystate", ",mouse:272,down,"),
        ("-j", "cursorpos"),
        ("dispatch", "movecursor", "0 0"),
        ("dispatch", "sendkeystate", ",mouse:272,up,"),
        ("-j", "cursorpos"),
        ("dispatch", "movecursor", "0 0"),
        ("dispatch", "movecursor", "10 20"),
    ]


def test_release_failure_preserves_original_error(monkeypatch):
    monkeypatch.setattr(
        hyprland.MouseController, "position", PropertyMock(return_value=(0, 0))
    )
    monkeypatch.setattr(
        hyprland,
        "_request",
        Mock(
            side_effect=[
                "ok",
                RuntimeError("press failed"),
                RuntimeError("release failed"),
            ]
        ),
    )
    with pytest.raises(RuntimeError, match="press failed"):
        hyprland.MouseController().click(0)


def test_click_failure_pauses_and_reports(monkeypatch, capsys):
    monkeypatch.setattr(app, "running", True)
    monkeypatch.setattr(
        app, "perform_click", Mock(side_effect=RuntimeError("dispatch failed"))
    )
    sync = Mock()
    monkeypatch.setattr(app, "_sync_cursor_lock_worker_state", sync)
    assert app._try_perform_click() is False
    assert app.running is False
    sync.assert_called_once()
    assert "Click failed; paused: dispatch failed" in capsys.readouterr().err
