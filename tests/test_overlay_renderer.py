"""Native overlay selection and HWND discovery regressions.

The actual transparency pipeline is verified only on Windows with a game.
"""

from types import SimpleNamespace

import pytest

import backend.overlay.__main__ as launcher
import backend.overlay.webview_window as native_window
import backend.overlay.window as qt_window


def test_qt_renderer_can_be_selected_with_webview_also_installed(monkeypatch):
    calls = []
    monkeypatch.setattr(qt_window, "is_available", lambda: True)
    monkeypatch.setattr(native_window, "is_available", lambda: True)
    monkeypatch.setattr(qt_window, "run_overlay", lambda url: calls.append(("qt", url)))
    monkeypatch.setattr(native_window, "run_overlay", lambda url: calls.append(("webview", url)))
    launcher._launch_overlay("qt")
    assert calls == [("qt", launcher.OVERLAY_URL)]


def test_auto_renderer_still_uses_existing_pywebview_default(monkeypatch):
    calls = []
    monkeypatch.setattr(qt_window, "is_available", lambda: True)
    monkeypatch.setattr(native_window, "is_available", lambda: True)
    monkeypatch.setattr(qt_window, "run_overlay", lambda url: calls.append("qt"))
    monkeypatch.setattr(native_window, "run_overlay", lambda url: calls.append("webview"))
    launcher._launch_overlay()
    assert calls == ["webview"]


def test_explicit_qt_renderer_reports_missing_dependency(monkeypatch):
    monkeypatch.setattr(qt_window, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="PyQt6|Qt renderer"):
        launcher._launch_overlay("qt")


def test_explicit_webview_renderer_reports_missing_dependency(monkeypatch):
    monkeypatch.setattr(native_window, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="pywebview"):
        launcher._launch_overlay("webview")


def test_native_hwnd_is_preferred_over_window_title(monkeypatch):
    handle = SimpleNamespace(ToInt64=lambda: 98765)
    monkeypatch.setattr(
        native_window, "_window", SimpleNamespace(native=SimpleNamespace(Handle=handle))
    )

    def should_not_use_title(_title):
        raise AssertionError("Title lookup is not reliable for WebView2 windows")

    monkeypatch.setattr(native_window, "_find_hwnd", should_not_use_title)
    assert native_window._get_overlay_hwnd() == 98765


def test_missing_native_hwnd_uses_title_fallback(monkeypatch):
    monkeypatch.setattr(native_window, "_window", SimpleNamespace(native=None))
    monkeypatch.setattr(native_window, "_find_hwnd", lambda title: 123)
    assert native_window._get_overlay_hwnd() == 123


def test_zero_native_hwnd_uses_title_fallback(monkeypatch):
    monkeypatch.setattr(
        native_window, "_window", SimpleNamespace(native=SimpleNamespace(Handle=0))
    )
    monkeypatch.setattr(native_window, "_find_hwnd", lambda title: 456)
    assert native_window._get_overlay_hwnd() == 456
