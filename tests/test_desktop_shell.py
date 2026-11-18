"""D1 desktop Settings launch, readiness and overlay compatibility regressions.

These tests do not require a display, installed PyQt6, or a League client.
"""

from pathlib import Path

import pytest

from backend.desktop import runtime, window
from backend.desktop import __main__ as desktop_main


class Response:
    def __init__(self, body=None, text="", code=200):
        self.body = body
        self.text = text
        self.status_code = code

    def json(self):
        return self.body


def test_probe_recognizes_existing_api_and_settings(monkeypatch):
    urls = []

    def get(url, timeout):
        assert timeout == 0.5
        urls.append(url)
        if url.endswith("/health"):
            return Response({
                "status": "ok", "data_loaded": True,
                "champions_loaded": 5, "augments_loaded": 5,
                "items_loaded": 5,
            })
        if url.endswith("/api/preferences"):
            return Response({
                "build_style": "Balanced",
                "available_styles": ["Balanced", "Damage", "Survival", "Utility"],
            })
        if url.endswith("/settings"):
            return Response(text="<title>Settings · ARAM Oracle</title>")
        raise AssertionError("Unexpected URL")

    monkeypatch.setattr(runtime.requests, "get", get)
    assert runtime.probe_companion() is True
    assert urls == [
        "http://127.0.0.1:8765/health",
        "http://127.0.0.1:8765/api/preferences",
        "http://127.0.0.1:8765/settings",
    ]


@pytest.mark.parametrize("broken_path,broken_response", [
    ("/health", Response({"status": "ok"})),
    ("/health", Response({"status": "wrong"}, code=200)),
    ("/api/preferences", Response({"build_style": "Cheat"})),
    ("/api/preferences", Response({"build_style": "Balanced", "available_styles": []})),
    ("/settings", Response(text="<title>Other app</title>")),
    ("/settings", Response(text="Settings · ARAM Oracle", code=404)),
])
def test_probe_rejects_incompatible_service(monkeypatch, broken_path, broken_response):
    good = {
        "/health": Response({
            "status": "ok", "data_loaded": False,
            "champions_loaded": 0, "augments_loaded": 0,
            "items_loaded": 0,
        }),
        "/api/preferences": Response({
            "build_style": "Survival",
            "available_styles": ["Balanced", "Damage", "Survival", "Utility"],
        }),
        "/settings": Response(text="<title>Settings · ARAM Oracle</title>"),
    }
    good[broken_path] = broken_response
    monkeypatch.setattr(
        runtime.requests, "get",
        lambda url, timeout: good[url.removeprefix(runtime.API_BASE)],
    )
    assert runtime.probe_companion() is False


def test_probe_handles_connection_errors(monkeypatch):
    import requests

    def offline(*_args, **_kwargs):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(runtime.requests, "get", offline)
    assert runtime.probe_companion() is False


def test_existing_server_is_reused_without_starting_another(monkeypatch):
    monkeypatch.setattr(runtime, "probe_companion", lambda: True)
    monkeypatch.setattr(
        runtime, "port_in_use",
        lambda: pytest.fail("Port probe must not run for a healthy API"),
    )
    assert runtime.ensure_api_available() == "reused"


def test_foreign_service_on_port_is_reported_without_starting_server(monkeypatch):
    monkeypatch.setattr(runtime, "probe_companion", lambda: False)
    monkeypatch.setattr(runtime, "port_in_use", lambda: True)
    with pytest.raises(runtime.DesktopStartupError, match="Port 8765 is in use"):
        runtime.ensure_api_available()


def test_new_server_uses_existing_overlay_start_path(monkeypatch):
    scans = iter([False, True])
    monkeypatch.setattr(runtime, "probe_companion", lambda: next(scans))
    monkeypatch.setattr(runtime, "port_in_use", lambda: False)
    created = []

    class FakeThread:
        def __init__(self, *, target, name, daemon):
            created.append((target, name, daemon))

        def start(self):
            pass

        def is_alive(self):
            return True

    monkeypatch.setattr(runtime.threading, "Thread", FakeThread)
    assert runtime.ensure_api_available() == "started"
    assert len(created) == 1
    assert created[0][1:] == ("aram-oracle-api", True)


def test_server_exits_before_readiness(monkeypatch):
    monkeypatch.setattr(runtime, "probe_companion", lambda: False)
    monkeypatch.setattr(runtime, "port_in_use", lambda: False)

    class DeadThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

        def is_alive(self):
            return False

    monkeypatch.setattr(runtime.threading, "Thread", DeadThread)
    with pytest.raises(runtime.DesktopStartupError, match="exited before Settings"):
        runtime.ensure_api_available(timeout=1)


def test_server_failure_surfaces_root_cause(monkeypatch):
    monkeypatch.setattr(runtime, "probe_companion", lambda: False)
    monkeypatch.setattr(runtime, "port_in_use", lambda: False)

    class FailingThread:
        def __init__(self, *, target, **_kwargs):
            self.target = target

        def start(self):
            self.target()

        def is_alive(self):
            return False

    def fail():
        raise RuntimeError("uvicorn could not bind")

    monkeypatch.setattr(runtime, "_run_existing_api", fail)
    monkeypatch.setattr(runtime.threading, "Thread", FailingThread)
    with pytest.raises(runtime.DesktopStartupError, match="uvicorn could not bind"):
        runtime.ensure_api_available(timeout=1)


def test_unready_server_times_out(monkeypatch):
    monkeypatch.setattr(runtime, "probe_companion", lambda: False)
    monkeypatch.setattr(runtime, "port_in_use", lambda: False)

    class IdleThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

        def is_alive(self):
            return True

    monkeypatch.setattr(runtime.threading, "Thread", IdleThread)
    with pytest.raises(runtime.DesktopStartupError, match="did not become ready"):
        runtime.ensure_api_available(timeout=0)


def test_missing_pyqt6_produces_actionable_error(monkeypatch):
    monkeypatch.setattr(window, "PYQT_AVAILABLE", False)
    assert window.is_available() is False
    with pytest.raises(runtime.DesktopStartupError, match="pip install"):
        window.run_desktop()


def test_launcher_does_not_start_server_without_qt(monkeypatch):
    monkeypatch.setattr(desktop_main, "is_available", lambda: False)
    monkeypatch.setattr(
        desktop_main, "run_application",
        lambda _view: pytest.fail("Must check Qt before launching the app"),
    )
    assert desktop_main.main([]) == 2


def test_launcher_passes_settings_view_to_unified_runtime(monkeypatch):
    monkeypatch.setattr(desktop_main, "is_available", lambda: True)
    seen = []
    monkeypatch.setattr(desktop_main, "run_application", lambda view: seen.append(view) or 0)
    assert desktop_main.main([]) == 0
    assert seen == ["settings"]


def test_launcher_fails_cleanly_on_conflict(monkeypatch):
    monkeypatch.setattr(desktop_main, "is_available", lambda: True)

    def fail():
        raise runtime.DesktopStartupError("Port 8765 conflict")

    monkeypatch.setattr(desktop_main, "run_application", lambda _view: fail())
    assert desktop_main.main([]) == 1


def test_native_window_reuses_existing_settings_frontend_without_overlay_flags():
    root = Path(__file__).resolve().parent.parent
    native_source = (root / "backend/desktop/window.py").read_text(encoding="utf-8")
    overlay_source = (root / "backend/overlay/window.py").read_text(encoding="utf-8")
    overlay_launcher = (root / "backend/overlay/__main__.py").read_text(encoding="utf-8")
    settings_html = (root / "frontend/settings.html").read_text(encoding="utf-8")

    assert "class SettingsWindow(QMainWindow)" in native_source
    assert "QWebEngineView(self)" in native_source
    assert "self.setCentralWidget(self._view)" in native_source
    assert "self.setMinimumSize(600, 460)" in native_source
    assert "WA_TranslucentBackground" not in native_source
    assert "WindowStaysOnTopHint" not in native_source
    assert "WS_EX_TRANSPARENT" not in native_source
    assert "FramelessWindowHint" not in native_source
    assert "/settings" in runtime.SETTINGS_URL
    assert '/static/settings.js' in settings_html
    assert '/static/settings.css' in settings_html
    assert 'id="preferred-build"' in settings_html
    assert 'id="feedback-description"' in settings_html

    assert "WS_EX_TRANSPARENT" in overlay_source
    assert "WA_TranslucentBackground" in overlay_source
    assert "VK_O = 0x4F" in overlay_source and "VK_H = 0x48" in overlay_source
    assert 'renderer == "qt"' in overlay_launcher
    assert "run_overlay(OVERLAY_URL)" in overlay_launcher
