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

logger = logging.getLogger("aram-oracle.overlay")

try:
    from PyQt6.QtCore import Qt, QUrl, QTimer
    from PyQt6.QtWidgets import QApplication, QMainWindow
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

        def __init__(self, url: str = "http://localhost:8765/overlay?mode=overlay"):
            super().__init__()

            self.setWindowTitle("ARAM Oracle Overlay")
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool  # hidden from taskbar
            )

            # Position: right edge, offset from top
            screen = QApplication.primaryScreen().geometry()
            x = screen.width() - OVERLAY_WIDTH - OVERLAY_MARGIN_RIGHT
            y = OVERLAY_MARGIN_TOP
            h = screen.height() - OVERLAY_MARGIN_TOP * 2
            self.setGeometry(x, y, OVERLAY_WIDTH, h)

            # Web view
            self._view = QWebEngineView(self)
            page = OverlayPage(self._view)
            self._view.setPage(page)

            # Transparent background for the web view
            self._view.page().setBackgroundColor(Qt.GlobalColor.transparent)
            self._view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self._view.setStyleSheet("background: transparent;")

            self.setCentralWidget(self._view)

            # Load the overlay URL
            self._view.setUrl(QUrl(url))

            # Keep an interaction toggle available while the game has focus.
            self._is_click_through = True
            self._hotkey_was_down = False
            QTimer.singleShot(100, self._set_click_through)
            self._hotkey_timer = QTimer(self)
            self._hotkey_timer.timeout.connect(self._poll_interaction_hotkey)
            self._hotkey_timer.start(60)

        def _poll_interaction_hotkey(self):
            """Toggle passthrough on a fresh Alt+O key chord globally."""
            if sys.platform != "win32":
                return
            user32 = ctypes.windll.user32
            down = bool(
                user32.GetAsyncKeyState(VK_MENU) & 0x8000
                and user32.GetAsyncKeyState(VK_O) & 0x8000
            )
            if down and not self._hotkey_was_down:
                self._toggle_click_through()
            self._hotkey_was_down = down

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

    window = OverlayWindow(url)
    window.show()

    logger.info("Overlay window started at %s", url)
    sys.exit(app.exec())
