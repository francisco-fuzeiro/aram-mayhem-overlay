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
