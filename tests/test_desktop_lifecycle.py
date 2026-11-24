"""D2 regressions: process lock, activation, ownership and legacy Qt launcher.

All tests run headlessly, without a real tray, WebEngine or League client.
"""
from __future__ import annotations

import json
from pathlib import Path
import socket
import time

import pytest

from backend.desktop.instance import InstanceGate
from backend.desktop.lifecycle import run_application
from backend.desktop import lifecycle, service
from backend.desktop.runtime import DesktopStartupError


def test_only_one_owner_holds_lock_and_release_allows_restart(tmp_path):
    first = InstanceGate(tmp_path)
    second = InstanceGate(tmp_path)
    assert first.acquire()
    assert second.acquire() is False
    first.close()
    assert second.acquire()
    second.close()


def test_new_process_activation_uses_existing_owner_without_second_listener(tmp_path):
    first = InstanceGate(tmp_path)
    second = InstanceGate(tmp_path)
    try:
        assert first.acquire()
        first.listen()
        assert second.acquire() is False
        assert second.forward("settings", timeout=1.5)
        assert second.forward("overlay", timeout=1.5)
        deadline = time.monotonic() + 1.5
        commands = []
        while time.monotonic() < deadline and len(commands) < 2:
            commands.extend(first.drain())
            time.sleep(0.01)
        assert commands == ["settings", "overlay"]
    finally:
        second.close()
        first.close()
    assert not (tmp_path / "desktop-instance.json").exists()


def test_invalid_activation_is_denied_and_never_queued(tmp_path):
    owner = InstanceGate(tmp_path)
    try:
        assert owner.acquire()
        owner.listen()
        descriptor = json.loads(owner.info_path.read_text(encoding="utf-8"))
        with socket.create_connection(("127.0.0.1", descriptor["port"]), timeout=1) as sock:
            sock.sendall(json.dumps({"action": "overlay", "token": "wrong"}).encode())
            assert sock.recv(64) == b"denied\n"
        assert owner.drain() == []
    finally:
        owner.close()


def test_stale_descriptor_does_not_prevent_lock_recovery(tmp_path):
    path = tmp_path / "desktop-instance.json"
    path.write_text('{"port": 1, "token": "old", "pid": 99999}', encoding="utf-8")
    gate = InstanceGate(tmp_path)
    try:
        assert gate.acquire()
        gate.listen()
        assert json.loads(path.read_text(encoding="utf-8"))["pid"] != 99999
    finally:
        gate.close()


def test_unreachable_owner_is_not_impersonated(tmp_path):
    gate = InstanceGate(tmp_path)
    gate.info_path.write_text(
        json.dumps({"port": 1, "token": "stale"}), encoding="utf-8"
    )
    assert not gate.forward("settings", timeout=0.01)


def test_activation_rejects_unlisted_action(tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        InstanceGate(tmp_path).forward("shutdown")


def test_activation_listener_cannot_start_without_lock(tmp_path):
    with pytest.raises(RuntimeError, match="without owning"):
        InstanceGate(tmp_path).listen()


def test_instance_cleanup_is_idempotent(tmp_path):
    gate = InstanceGate(tmp_path)
    assert gate.acquire()
    gate.listen()
    gate.close()
    gate.close()
    other = InstanceGate(tmp_path)
    assert other.acquire()
    other.close()


def test_second_launch_forwards_without_starting_api_or_qt(monkeypatch):
    from backend import feature_diagnostics
    monkeypatch.setattr(feature_diagnostics, "code_version", lambda: None)
    events = []

    class FakeGate:
        def __init__(self, _directory):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            events.append("close")

        def acquire(self):
            events.append("busy")
            return False

        def forward(self, action):
            events.append(action)
            return True

    monkeypatch.setattr(lifecycle, "InstanceGate", FakeGate)
    monkeypatch.setattr(
        lifecycle, "ManagedApi", lambda: pytest.fail("No API in second instance")
    )
    assert run_application("settings") == 0
    assert events == ["busy", "settings", "close"]


def test_unresponsive_primary_reports_clear_error(monkeypatch):
    from backend import feature_diagnostics
    monkeypatch.setattr(feature_diagnostics, "code_version", lambda: None)
    class Busy:
        def __init__(self, _directory):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def acquire(self):
            return False

        def forward(self, _action):
            return False

    monkeypatch.setattr(lifecycle, "InstanceGate", Busy)
    with pytest.raises(DesktopStartupError, match="not responding"):
        run_application("overlay")


def test_primary_starts_api_before_activation_and_cleans_up(monkeypatch):
    events = []

    class Gate:
        def __init__(self, _directory):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            events.append("unlock")

        def acquire(self):
            events.append("lock")
            return True

        def listen(self):
            events.append("listen")

        def close(self):
            events.append("listener stop")

    class Api:
        def start(self):
            events.append("api start")

        def stop(self):
            events.append("api stop")

    monkeypatch.setattr(lifecycle, "InstanceGate", Gate)
    monkeypatch.setattr(lifecycle, "ManagedApi", Api)
    from backend.desktop import window
    monkeypatch.setattr(
        window, "run_managed_ui",
        lambda _gate, _service, view: events.append(view) or 0
    )
    assert run_application("overlay") == 0
    assert events == [
        "lock", "api start", "listen", "overlay",
        "listener stop", "api stop", "unlock",
    ]


def test_primary_stops_api_on_gui_exception(monkeypatch):
    events = []

    class Gate:
        def __init__(self, _directory):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def acquire(self):
            return True

        def listen(self):
            pass

        def close(self):
            events.append("listener stop")

    class Api:
        def start(self):
            pass

        def stop(self):
            events.append("api stop")

    monkeypatch.setattr(lifecycle, "InstanceGate", Gate)
    monkeypatch.setattr(lifecycle, "ManagedApi", Api)
    from backend.desktop import window

    def broken(*_args):
        raise RuntimeError("UI failed")

    monkeypatch.setattr(window, "run_managed_ui", broken)
    with pytest.raises(RuntimeError, match="UI failed"):
        run_application()
    assert events == ["listener stop", "api stop"]


def test_bad_view_rejected_before_ownership():
    with pytest.raises(ValueError, match="Unknown"):
        run_application("unsafe")


def test_managed_api_reuses_companion_without_binding(monkeypatch):
    from backend import feature_diagnostics
    monkeypatch.setattr(feature_diagnostics, "code_version", lambda: "abc1234")
    monkeypatch.setattr(service, "companion_code", lambda: "abc1234")
    monkeypatch.setattr(service, "probe_companion", lambda: True)
    monkeypatch.setattr(
        service, "port_in_use", lambda: pytest.fail("Must not bind reused API")
    )
    api = service.ManagedApi()
    assert api.start() == "reused"
    api.stop()


def test_managed_api_rejects_foreign_port_without_thread(monkeypatch):
    monkeypatch.setattr(service, "probe_companion", lambda: False)
    monkeypatch.setattr(service, "port_in_use", lambda: True)
    api = service.ManagedApi()
    with pytest.raises(DesktopStartupError, match="incompatible"):
        api.start()
    assert api._thread is None


def test_legacy_qt_launcher_routes_to_unified_app(monkeypatch):
    from backend.overlay import __main__ as launcher
    from backend.desktop import __main__ as desktop_main

    seen = []
    monkeypatch.setattr(
        desktop_main, "main",
        lambda argv, *, initial_view: seen.append((argv, initial_view)) or 0
    )
    assert launcher.main(["--renderer", "qt"]) == 0
    assert seen == [([], "overlay")]


def test_d2_source_keeps_qt_transparency_and_exact_hotkeys():
    root = Path(__file__).resolve().parents[1]
    overlay = (root / "backend/overlay/window.py").read_text(encoding="utf-8")
    desktop = (root / "backend/desktop/window.py").read_text(encoding="utf-8")
    assert "WS_EX_TRANSPARENT" in overlay
    assert "WA_TranslucentBackground" in overlay
    assert "VK_O = 0x4F" in overlay and "VK_H = 0x48" in overlay
    assert "if enable_tray:" in overlay
    assert "enable_tray=False" in desktop
    assert "Quit ARAM Oracle" in desktop
    assert "self.app.quit()" in desktop


def test_owned_uvicorn_server_stops_on_quit(monkeypatch):
    import sys
    import threading
    import types

    class FakeServer:
        def __init__(self, _config):
            self.started = False
            self.should_exit = False
            self.done = threading.Event()

        def run(self):
            self.started = True
            while not self.should_exit:
                time.sleep(0.01)
            self.done.set()

    created = []
    monkeypatch.setitem(sys.modules, "uvicorn", types.SimpleNamespace(
        Config=lambda *_args, **_kwargs: object(),
        Server=lambda config: created.append(FakeServer(config)) or created[-1],
    ))
    monkeypatch.setattr(service, "probe_companion",
                        lambda: bool(created and created[-1].started))
    monkeypatch.setattr(service, "port_in_use", lambda: False)
    api = service.ManagedApi()
    assert api.start(timeout=2) == "started"
    assert api.alive()
    owned = created[-1]
    api.stop()
    assert owned.done.is_set()


def test_uvicorn_binding_failure_releases_owned_thread(monkeypatch):
    import sys
    import types

    class FailingServer:
        started = False
        should_exit = False

        def __init__(self, _config):
            pass

        def run(self):
            raise RuntimeError("simulated port race")

    monkeypatch.setitem(sys.modules, "uvicorn", types.SimpleNamespace(
        Config=lambda *_args, **_kwargs: object(),
        Server=FailingServer,
    ))
    monkeypatch.setattr(service, "probe_companion", lambda: False)
    monkeypatch.setattr(service, "port_in_use", lambda: False)
    api = service.ManagedApi()
    with pytest.raises(DesktopStartupError, match="simulated port race"):
        api.start(timeout=2)
    assert api._thread is None


def test_managed_api_refuses_an_api_running_other_code(monkeypatch):
    # Field 23/11: reports kept coming from an old process after updates.
    from backend import feature_diagnostics
    monkeypatch.setattr(feature_diagnostics, "code_version", lambda: "2ecd870")
    monkeypatch.setattr(service, "companion_code", lambda: None)
    monkeypatch.setattr(service, "probe_companion", lambda: True)
    with pytest.raises(DesktopStartupError, match="older ARAM Oracle"):
        service.ManagedApi().start()


def test_new_version_asks_old_instance_to_quit_and_takes_over(monkeypatch):
    from backend import feature_diagnostics
    monkeypatch.setattr(feature_diagnostics, "code_version", lambda: "2ecd870")
    events = []

    class Old:
        def __init__(self, _directory):
            self.tries = 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            events.append("close")

        def acquire(self):
            self.tries += 1
            return self.tries > 2  # lock frees after the old one quits

        def owner_code(self):
            return "892f379"

        def forward(self, action, timeout=20.0):
            events.append(action)
            return True

        def listen(self):
            events.append("listen")

        def close(self):
            pass

    class Api:
        def start(self):
            events.append("api")

        def stop(self):
            events.append("stop")

    monkeypatch.setattr(lifecycle, "InstanceGate", Old)
    monkeypatch.setattr(lifecycle, "ManagedApi", Api)
    from backend.desktop import window
    monkeypatch.setattr(window, "run_managed_ui", lambda *a: events.append("ui") or 0)
    assert run_application("overlay") == 0
    assert events[:4] == ["quit", "api", "listen", "ui"]
