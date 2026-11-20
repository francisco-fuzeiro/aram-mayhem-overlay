"""
ARAM Oracle — Click-through transparent overlay window.

Uses PyQt6 + QWebEngineView to render the companion web UI as a
transparent, always-on-top, click-through window. This works over
League of Legends in borderless windowed mode without causing tab-outs
because the window never captures mouse input.

Win32 flags:
  WS_EX_TRANSPARENT — mouse events pass through to the game (Alt+O to toggle)
  WS_EX_LAYERED     — required for per-pixel transparency
  HWND_TOPMOST      — stays on top of all windows

Usage:
  python -m backend.overlay
"""

from __future__ import annotations

import ctypes
import sys
import logging
import threading
import urllib.request
import webbrowser
from urllib.parse import urlsplit, parse_qs

from backend import preferences
from backend.overlay.layout import calculate_overlay_geometry

logger = logging.getLogger("aram-oracle.overlay")

try:
    from PyQt6.QtCore import Qt, QUrl, QTimer
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QMenu, QSystemTrayIcon, QStyle,
    )
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings

    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    logger.warning("PyQt6 not installed — overlay window unavailable")


# Win32 constants for click-through
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000

# Overlay dimensions
OVERLAY_WIDTH = 320
OVERLAY_MARGIN_RIGHT = 10
OVERLAY_MARGIN_TOP = 60
VK_MENU = 0x12
VK_O = 0x4F
VK_H = 0x48
VK_S = 0x53
# PG: never monitor global click positions without a separate policy/consent gate.
PICK_CLICK_HINTS_ENABLED = False


def _window_action_for_url(value: str) -> str | None:
    """Accept only deliberate control fragments on our local overlay page."""
    url = urlsplit(value)
    try:
        trusted_origin = (
            url.scheme == "http"
            and url.hostname in {"localhost", "127.0.0.1"}
            and url.port == 8765
        )
    except ValueError:
        return None
    if (
        not trusted_origin
        or url.path != "/overlay"
        or parse_qs(url.query).get("mode") != ["overlay"]
    ):
        return None
    return {"qt-hide": "hide", "qt-quit": "quit"}.get(url.fragment)


# Guard class definitions behind PYQT_AVAILABLE so they don't reference
# undefined names (QWebEnginePage, QMainWindow) when PyQt6 is missing or
# when PyInstaller freezes the module.
if PYQT_AVAILABLE:

    class OverlayPage(QWebEnginePage):
        """Custom page that suppresses console noise and link navigation."""

        def javaScriptConsoleMessage(self, level, message, line, source):
            if level >= QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
                logger.error("JS [%s:%d]: %s", source, line, message)

        def acceptNavigationRequest(self, url, nav_type, is_main_frame):
            # Block all navigation except the initial page load
            if nav_type == QWebEnginePage.NavigationType.NavigationTypeTyped:
                return True
            if nav_type == QWebEnginePage.NavigationType.NavigationTypeOther:
                return True
            return False

    class OverlayWindow(QMainWindow):
        """Transparent, click-through, always-on-top overlay."""

        def __init__(self, url: str = "http://localhost:8765/overlay?mode=overlay", *,
                     enable_tray: bool = True, on_quit=None,
                     on_settings=None, on_visibility=None):
            super().__init__()

            self.setWindowTitle("ARAM Oracle Overlay")
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool  # hidden from taskbar
            )

            # D4b: screen-relative geometry is applied once WebEngine is ready.
            self._overlay_preferences = dict(preferences.DEFAULT_OVERLAY)
            self._layout_in_progress = False
            self._watched_screens = set()
            self._screen_signal_connected = False

            # Web view
            self._view = QWebEngineView(self)
            page = OverlayPage(self._view)
            self._view.setPage(page)

            # Transparent background for the web view
            self._view.page().setBackgroundColor(Qt.GlobalColor.transparent)
            self._view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self._view.setStyleSheet("background: transparent;")

            self.setCentralWidget(self._view)
            self._view.loadFinished.connect(self._on_page_loaded)
            self._view.urlChanged.connect(self._on_url_changed)

            # Read the same atomic preferences file owned by the existing API.
            # This avoids blocking the GUI event loop with synchronous HTTP.
            self._reload_overlay_preferences(force=True)
            self._watch_screens()
            QApplication.instance().screenAdded.connect(self._screens_changed)
            QApplication.instance().screenRemoved.connect(self._screens_changed)
            QApplication.instance().primaryScreenChanged.connect(self._screens_changed)
            self._preferences_timer = QTimer(self)
            self._preferences_timer.timeout.connect(self._reload_overlay_preferences)
            self._preferences_timer.start(800)

            # Load the overlay URL only after the transparent window is configured.
            self._view.setUrl(QUrl(url))

            # Keep an interaction toggle available while the game has focus.
            self._is_click_through = True
            self._hotkey_was_down = False
            self._visibility_hotkey_was_down = False
            self._scan_hotkey_was_down = False
            self._tray = None
            self._tray_toggle = None
            self._on_quit = on_quit
            self._on_settings = on_settings
            self._on_visibility = on_visibility
            if enable_tray:
                self._setup_tray()
            QTimer.singleShot(100, self._set_click_through)
            self._hotkey_timer = QTimer(self)
            self._hotkey_timer.timeout.connect(self._poll_interaction_hotkey)
            self._hotkey_timer.start(60)

        def _screens_changed(self, *_args):
            """Reconcile Qt logical-coordinate screens after hotplug / DPI changes."""
            self._watch_screens()
            self._apply_overlay_layout()

        def _watch_screens(self):
            screens = set(QApplication.screens())
            self._watched_screens.intersection_update(screens)
            for screen in screens - self._watched_screens:
                screen.availableGeometryChanged.connect(self._apply_overlay_layout)
                screen.geometryChanged.connect(self._apply_overlay_layout)
                screen.logicalDotsPerInchChanged.connect(self._apply_overlay_layout)
                self._watched_screens.add(screen)

        def showEvent(self, event):
            super().showEvent(event)
            handle = self.windowHandle()
            if handle is not None and not self._screen_signal_connected:
                handle.screenChanged.connect(self._screens_changed)
                self._screen_signal_connected = True
            self._apply_overlay_layout()

        def resizeEvent(self, event):
            super().resizeEvent(event)
            if not self._layout_in_progress and hasattr(self, "_preferences_timer"):
                QTimer.singleShot(0, self._apply_overlay_layout)

        def _reload_overlay_preferences(self, force=False):
            """Apply only changed, sanitized settings; never change interaction mode."""
            loaded = preferences.load_preferences()["overlay"]
            if force or loaded != self._overlay_preferences:
                self._overlay_preferences = loaded
                self._apply_overlay_layout()

        def _apply_overlay_layout(self, *_args):
            """Qt returns device-independent screen coordinates, including DPI scales."""
            if self._layout_in_progress or not hasattr(self, "_view"):
                return
            screens = QApplication.screens()
            screen = self.screen()
            if screen not in screens:
                screen = QApplication.primaryScreen()
            if screen is None:
                return
            area = screen.availableGeometry()  # taskbar-safe and screen-origin-aware
            try:
                x, y, w, h = calculate_overlay_geometry(
                    (area.x(), area.y(), area.width(), area.height()),
                    self._overlay_preferences, base_width=OVERLAY_WIDTH,
                    vertical_inset=OVERLAY_MARGIN_TOP,
                )
                self._layout_in_progress = True
                if (self.x(), self.y(), self.width(), self.height()) != (x, y, w, h):
                    self.setGeometry(x, y, w, h)
                self._view.setZoomFactor(self._overlay_preferences["scale"])
                self.setWindowOpacity(self._overlay_preferences["opacity"])
            except (ValueError, RuntimeError) as exc:
                logger.warning("Unable to apply Qt overlay preferences: %s", exc)
            finally:
                self._layout_in_progress = False
            # Opacity may recreate a layered HWND on Windows; never turn off Alt+O.
            if getattr(self, "_is_click_through", False) and self.isVisible():
                QTimer.singleShot(0, self._set_click_through)

        def _on_page_loaded(self, success: bool):
            """Expose native-only controls after the local HTML page loads."""
            if success:
                self._view.page().runJavaScript(
                    "document.documentElement.classList.add('qt-native-overlay')"
                )

        def _on_url_changed(self, url: QUrl):
            """Route local hash actions without a privileged web API endpoint."""
            action = _window_action_for_url(url.toString())
            if action is None:
                return
            # Clear the fragment so the same action can be clicked repeatedly.
            self._view.page().runJavaScript(
                "history.replaceState(null, '', location.pathname + location.search)"
            )
            if action == "hide":
                self._toggle_visibility()
            elif action == "quit":
                self._quit_overlay()

        def _setup_tray(self):
            """Keep a visible restore/quit route after hiding a frameless window."""
            if not QSystemTrayIcon.isSystemTrayAvailable():
                logger.info("System tray unavailable; Alt+H can still restore the overlay")
                return
            self._tray = QSystemTrayIcon(self)
            self._tray.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            )
            self._tray.setToolTip("ARAM Oracle Overlay (Alt+H to show/hide)")
            menu = QMenu()
            open_settings = menu.addAction("Open Settings")
            open_settings.triggered.connect(self._open_settings)
            menu.addSeparator()
            self._tray_toggle = menu.addAction("Hide overlay (Alt+H)")
            self._tray_toggle.triggered.connect(self._toggle_visibility)
            interaction = menu.addAction("Toggle interaction (Alt+O)")
            interaction.triggered.connect(self._toggle_click_through)
            menu.addSeparator()
            quit_action = menu.addAction("Quit overlay")
            quit_action.triggered.connect(self._quit_overlay)
            self._tray.setContextMenu(menu)
            self._tray.activated.connect(self._on_tray_activated)
            self._tray.show()

        def _open_settings(self):
            """Open Settings using the managed Qt host or legacy browser fallback."""
            if self._on_settings is not None:
                self._on_settings()
                return
            url = "http://127.0.0.1:8765/settings"
            try:
                if not webbrowser.open(url, new=2):
                    logger.warning("Could not open Settings automatically: %s", url)
            except Exception:
                logger.exception("Failed to open Settings in the default browser")

        def _on_tray_activated(self, reason):
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
                self._toggle_visibility()

        def _toggle_visibility(self):
            """Hide the native window without stopping the poller or WebSocket."""
            if self.isVisible():
                self.hide()
                logger.info("Qt overlay hidden (Alt+H or tray to restore)")
            else:
                self.show()
                self.raise_()
                # The managed desktop may create the overlay while hidden.
                # Reapply its existing Win32 transparency flags after first show.
                if self._is_click_through:
                    QTimer.singleShot(0, self._set_click_through)
                logger.info("Qt overlay shown")
            if self._tray_toggle is not None:
                action = "Hide" if self.isVisible() else "Show"
                self._tray_toggle.setText(f"{action} overlay (Alt+H)")
            if self._on_visibility is not None:
                self._on_visibility()

        def _quit_overlay(self):
            """Delegate quit to the lifecycle owner when using the managed app."""
            if self._on_quit is not None:
                self._on_quit()
                return
            logger.info("Closing Qt overlay")
            app = QApplication.instance()
            if app is not None:
                app.quit()

        def _poll_interaction_hotkey(self):
            """Observe Alt+O, Alt+H and edge-triggered Alt+S without game input."""
            if sys.platform != "win32":
                return
            user32 = ctypes.windll.user32
            alt_down = bool(user32.GetAsyncKeyState(VK_MENU) & 0x8000)
            interaction_down = alt_down and bool(
                user32.GetAsyncKeyState(VK_O) & 0x8000
            )
            visibility_down = alt_down and bool(
                user32.GetAsyncKeyState(VK_H) & 0x8000
            )
            scan_down = alt_down and bool(
                user32.GetAsyncKeyState(VK_S) & 0x8000
            )
            if interaction_down and not self._hotkey_was_down:
                self._toggle_click_through()
            if visibility_down and not self._visibility_hotkey_was_down:
                self._toggle_visibility()
            if scan_down and not self._scan_hotkey_was_down:
                self._request_manual_scan()
            self._hotkey_was_down = interaction_down
            self._visibility_hotkey_was_down = visibility_down
            self._scan_hotkey_was_down = scan_down

        def _request_manual_scan(self):
            """POST to the existing local API off the GUI thread; never send game keys."""
            try:
                port = urlsplit(self._view.url().toString()).port or 8765
            except ValueError:
                port = 8765
            endpoint = f"http://127.0.0.1:{port}/api/ocr/scan"

            def request_scan():
                request = urllib.request.Request(endpoint, data=b"", method="POST")
                try:
                    with urllib.request.urlopen(request, timeout=5) as response:
                        response.read()
                except (OSError, ValueError) as exc:
                    logger.debug("Manual OCR request unavailable: %s", type(exc).__name__)

            threading.Thread(
                target=request_scan, daemon=True, name="aram-ocr-manual",
            ).start()

        def _toggle_click_through(self):
            """Enable controls temporarily without affecting transparency."""
            if sys.platform != "win32":
                return
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if self._is_click_through:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_TRANSPARENT)
                self._view.page().runJavaScript(
                    "document.body.classList.add('interactive-mode')"
                )
            else:
                user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED
                )
                self._view.page().runJavaScript(
                    "document.body.classList.remove('interactive-mode')"
                )
            self._is_click_through = not self._is_click_through
            logger.info(
                "Qt click-through %s", "ON" if self._is_click_through else "OFF"
            )

        def _set_click_through(self):
            """Set Win32 extended styles so mouse events pass through."""
            if sys.platform != "win32":
                logger.warning("Click-through only works on Windows")
                return

            try:
                hwnd = int(self.winId())
                user32 = ctypes.windll.user32
                current_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE,
                    current_style | WS_EX_TRANSPARENT | WS_EX_LAYERED,
                )
                logger.info("Click-through enabled (HWND=%d)", hwnd)
            except Exception as e:
                logger.error("Failed to set click-through: %s", e)


def is_available() -> bool:
    """Check if PyQt6 dependencies are installed."""
    return PYQT_AVAILABLE


def run_overlay(url: str = "http://localhost:8765/overlay?mode=overlay"):
    """Launch the overlay window (blocking — runs the Qt event loop)."""
    if not PYQT_AVAILABLE:
        print("ERROR: PyQt6 and PyQt6-WebEngine are required.")
        print("Install with: pip install PyQt6 PyQt6-WebEngine")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("ARAM Oracle")
    # Keep the event loop alive while the frameless window is hidden.
    app.setQuitOnLastWindowClosed(False)

    window = OverlayWindow(url)
    window.show()

    logger.info("Overlay window started at %s", url)
    sys.exit(app.exec())
