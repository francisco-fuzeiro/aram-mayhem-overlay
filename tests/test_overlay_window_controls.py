"""Guard local Qt window commands and expose discoverable UI affordances."""

from pathlib import Path

import pytest

from backend.overlay.window import _window_action_for_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://localhost:8765/overlay?mode=overlay#qt-hide", "hide"),
        ("http://127.0.0.1:8765/overlay?mode=overlay#qt-quit", "quit"),
        ("http://localhost:8765/overlay?mode=overlay", None),
        ("http://localhost:8765/overlay?mode=overlay#qt-other", None),
        ("http://localhost:8765/overlay#qt-hide", None),
        ("http://localhost:8766/overlay?mode=overlay#qt-quit", None),
        ("http://example.org:8765/overlay?mode=overlay#qt-quit", None),
        ("https://localhost:8765/overlay?mode=overlay#qt-quit", None),
        ("http://localhost:8765/health?mode=overlay#qt-hide", None),
        ("http://localhost:malformed/overlay?mode=overlay#qt-hide", None),
        ("http://evil.test@other.invalid:8765/overlay?mode=overlay#qt-quit", None),
    ],
)
def test_window_action_validates_local_origin_and_explicit_fragment(url, expected):
    assert _window_action_for_url(url) == expected


def test_window_control_buttons_are_present_only_for_native_qt():
    root = Path(__file__).resolve().parent.parent
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    css = (root / "frontend" / "style.css").read_text(encoding="utf-8")
    script = (root / "frontend" / "app.js").read_text(encoding="utf-8")

    assert 'id="btn-hide-overlay"' in html
    assert 'id="btn-quit-overlay"' in html
    assert ".qt-window-controls {" in css
    assert "display: none;" in css.split(".qt-window-controls {", 1)[1].split("}", 1)[0]
    assert ".qt-native-overlay .qt-window-controls" in css
    assert 'location.hash = "qt-hide"' in script
    assert 'location.hash = "qt-quit"' in script


def test_qt_lifecycle_includes_global_visibility_hotkey_and_tray():
    root = Path(__file__).resolve().parent.parent
    source = (root / "backend" / "overlay" / "window.py").read_text(encoding="utf-8")
    assert "VK_H = 0x48" in source
    assert "QSystemTrayIcon.isSystemTrayAvailable()" in source
    assert "app.setQuitOnLastWindowClosed(False)" in source
    assert "self._hotkey_timer.timeout.connect(self._poll_interaction_hotkey)" in source
    assert 'self._tray_toggle = menu.addAction("Hide overlay (Alt+H)")' in source


def test_a5_scan_hotkey_uses_edge_triggered_local_post_without_focus_or_game_keys():
    root = Path(__file__).resolve().parent.parent
    source = (root / "backend" / "overlay" / "window.py").read_text(encoding="utf-8")
    assert "VK_S = 0x53" in source
    assert "GetAsyncKeyState(VK_S)" in source
    assert "if scan_down and not self._scan_hotkey_was_down:" in source
    assert "self._scan_hotkey_was_down = scan_down" in source
    assert "def _request_manual_scan(self)" in source
    assert "/api/ocr/scan" in source
    assert 'method="POST"' in source
    assert "threading.Thread(" in source
    assert "daemon=True" in source
    hotkey_method = source.split("def _request_manual_scan(self):", 1)[1].split(
        "def _toggle_click_through(self):", 1,
    )[0]
    assert "SetForegroundWindow" not in hotkey_method
    assert "SendInput" not in hotkey_method
    assert "keybd_event" not in hotkey_method


def test_a6_nonactivating_qt_defaults_are_declared():
    source = (Path(__file__).resolve().parent.parent / "backend" / "overlay" / "window.py").read_text(encoding="utf-8")
    assert "WS_EX_NOACTIVATE = 0x08000000" in source
    constructor = source.split("def __init__(self, url:", 1)[1].split("def _screens_changed(", 1)[0]
    assert "Qt.WindowType.WindowDoesNotAcceptFocus" in constructor
    assert "self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)" in constructor


def test_a6_click_through_and_interactive_restore_native_and_qt_focus_flags():
    source = (Path(__file__).resolve().parent.parent / "backend" / "overlay" / "window.py").read_text(encoding="utf-8")
    toggle = source.split("def _toggle_click_through(self):", 1)[1].split("def _set_click_through(self):", 1)[0]
    passive = source.split("def _set_click_through(self):", 1)[1].split("\ndef is_available()", 1)[0]
    assert "style & ~(WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)" in toggle
    assert "self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, False)" in toggle
    assert "self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)" in toggle
    assert toggle.count("self.show()") >= 2
    assert "QTimer.singleShot(0, self._set_click_through)" in toggle
    assert "WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE" in passive
    assert "if not self._is_click_through:" in passive


def test_a6_capture_exclusion_is_verified_after_native_creation_and_qt_flag_changes():
    source = (Path(__file__).resolve().parent.parent / "backend" / "overlay" / "window.py").read_text(encoding="utf-8")
    assert "WDA_EXCLUDEFROMCAPTURE = 0x11" in source
    assert "SetWindowDisplayAffinity" in source
    assert "GetWindowDisplayAffinity" in source
    show_event = source.split("def showEvent(self, event):", 1)[1].split("def resizeEvent(", 1)[0]
    assert "self._apply_capture_exclusion()" in show_event
    toggle = source.split("def _toggle_click_through(self):", 1)[1].split("def _set_click_through(self):", 1)[0]
    assert toggle.count("self._apply_capture_exclusion()") >= 2


def test_a6_visibility_restoration_never_activates_the_overlay():
    source = (Path(__file__).resolve().parent.parent / "backend" / "overlay" / "window.py").read_text(encoding="utf-8")
    visibility = source.split("def _toggle_visibility(self):", 1)[1].split("def _quit_overlay(self):", 1)[0]
    assert "self.show()" in visibility
    assert "activateWindow(" not in visibility
    assert "SetForegroundWindow" not in visibility


def test_a6_capture_exclusion_failure_is_an_enumerated_diagnostic():
    from backend.diagnostic_events import SCHEMA, _clean

    assert SCHEMA["overlay_capture_exclusion"]["status"] == frozenset({"unsupported"})
    assert _clean("overlay_capture_exclusion", {"status": "unsupported"}) == {"status": "unsupported"}
    assert _clean("overlay_capture_exclusion", {"status": "ok", "username": "secret"}) == {}
