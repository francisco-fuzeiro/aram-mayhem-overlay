"""Regular Settings host and unified Qt tray owner for ARAM Oracle."""
from __future__ import annotations

import logging
import sys

from backend.desktop.runtime import SETTINGS_URL, DesktopStartupError

logger = logging.getLogger("aram-oracle.desktop")

try:
    from PyQt6.QtCore import QUrl, QTimer
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QMessageBox, QMenu, QSystemTrayIcon, QStyle,
    )
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


if PYQT_AVAILABLE:

    class SettingsWindow(QMainWindow):
        """A standard taskbar window; no overlay flags or Win32 mouse hooks."""

        def __init__(self, url: str = SETTINGS_URL, on_close=None, on_failure=None):
            super().__init__()
            self._on_close = on_close
            self._on_failure = on_failure
            self.setWindowTitle("ARAM Oracle — Settings")
            self.resize(960, 760)
            self.setMinimumSize(600, 460)

            self._view = QWebEngineView(self)
            self.setCentralWidget(self._view)
            self._view.loadFinished.connect(self._on_page_loaded)
            self._view.setUrl(QUrl(url))

        def closeEvent(self, event):
            if self._on_close is not None and self._on_close():
                event.ignore()
                self.hide()
                return
            super().closeEvent(event)

        def _on_page_loaded(self, success: bool) -> None:
            if success:
                logger.info("Desktop Settings loaded")
                return
            logger.error("Failed to load the local Settings page")
            QMessageBox.critical(
                self,
                "ARAM Oracle — Settings unavailable",
                "The local Settings page could not be loaded. "
                "Check that ARAM Oracle is running, then launch it again.",
            )
            if self._on_failure is not None:
                self._on_failure()
            else:
                self.close()


    class DesktopController:
        """Own exactly one tray and both Qt windows on the GUI event loop."""

        def __init__(self, app, gate, service, initial_view: str):
            from backend.overlay.window import OverlayWindow
            from backend.overlay.__main__ import OVERLAY_URL

            self.app = app
            self.gate = gate
            self.service = service
            self._quitting = False
            self._api_failures = 0
            self.tray = None
            self._tray_toggle = None

            self.settings = SettingsWindow(
                SETTINGS_URL, on_close=self._settings_close, on_failure=self.quit
            )
            self.overlay = OverlayWindow(
                OVERLAY_URL,
                enable_tray=False,
                on_quit=self.quit,
                on_settings=self.show_settings,
                on_visibility=self._sync_tray,
            )
            self._setup_tray()

            self._activation_timer = QTimer(app)
            self._activation_timer.timeout.connect(self._drain_activation)
            self._activation_timer.start(100)
            self._health_timer = QTimer(app)
            self._health_timer.timeout.connect(self._check_api)
            self._health_timer.start(4000)

            if initial_view == "overlay":
                self.show_overlay()
            else:
                self.show_settings()

        def _setup_tray(self) -> None:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                logger.warning("No system tray: closing Settings will quit ARAM Oracle")
                return
            self.tray = QSystemTrayIcon(self.app)
            self.tray.setIcon(
                self.app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            )
            self.tray.setToolTip("ARAM Oracle")
            menu = QMenu()
            menu.addAction("Open Settings").triggered.connect(self.show_settings)
            self._tray_toggle = menu.addAction("Show overlay (Alt+H)")
            self._tray_toggle.triggered.connect(self.toggle_overlay)
            menu.addAction("Toggle overlay interaction (Alt+O)").triggered.connect(
                self.overlay._toggle_click_through
            )
            menu.addSeparator()
            menu.addAction("Quit ARAM Oracle").triggered.connect(self.quit)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(self._tray_activated)
            self.tray.show()

        def _tray_activated(self, reason) -> None:
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
                self.show_settings()

        def show_settings(self) -> None:
            self.settings.showNormal()
            self.settings.raise_()
            self.settings.activateWindow()

        def show_overlay(self) -> None:
            if not self.overlay.isVisible():
                self.overlay._toggle_visibility()
            else:
                self.overlay.raise_()
            self._sync_tray()

        def toggle_overlay(self) -> None:
            self.overlay._toggle_visibility()

        def _sync_tray(self) -> None:
            if self._tray_toggle is not None:
                action = "Hide" if self.overlay.isVisible() else "Show"
                self._tray_toggle.setText(f"{action} overlay (Alt+H)")

        def _settings_close(self) -> bool:
            if self._quitting:
                return False
            if self.tray is not None:
                logger.info("Settings hidden to notification area")
                return True
            self.quit()
            return False

        def _drain_activation(self) -> None:
            for action in self.gate.drain():
                if action == "settings":
                    self.show_settings()
                elif action == "overlay":
                    self.show_overlay()
                elif action == "quit":
                    self.quit()

        def _check_api(self) -> None:
            if self._quitting:
                return
            if self.service.alive():
                self._api_failures = 0
                return
            self._api_failures += 1
            if self._api_failures >= 2:
                logger.error("Local API is unavailable; shutting down safely")
                QMessageBox.warning(
                    self.settings,
                    "ARAM Oracle — Local API unavailable",
                    "The local server stopped responding. ARAM Oracle will close. "
                    "You can restart it when the service is available.",
                )
                self.quit()

        def quit(self) -> None:
            if self._quitting:
                return
            self._quitting = True
            self._activation_timer.stop()
            self._health_timer.stop()
            if self.tray is not None:
                self.tray.hide()
            self.app.quit()


def is_available() -> bool:
    """Require Qt Widgets and WebEngine; no display needed for this check."""
    return PYQT_AVAILABLE


def run_desktop(url: str = SETTINGS_URL) -> int:
    """D1 compatibility host; the CLI uses the managed D2 lifecycle instead."""
    if not PYQT_AVAILABLE:
        raise DesktopStartupError(
            'PyQt6 WebEngine is missing. Install with: '
            'python -m pip install -e ".[overlay]"'
        )
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ARAM Oracle")
    window = SettingsWindow(url)
    window.show()
    logger.info("Desktop Settings window opened at %s", url)
    return app.exec()


def run_managed_ui(gate, service, initial_view: str = "settings") -> int:
    """Create one Qt event loop, one tray, one Settings window and one overlay."""
    if not PYQT_AVAILABLE:
        raise DesktopStartupError("PyQt6 WebEngine is required for the managed Qt app")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ARAM Oracle")
    app.setQuitOnLastWindowClosed(False)
    controller = DesktopController(app, gate, service, initial_view)
    logger.info("Managed ARAM Oracle Qt application opened (%s)", initial_view)
    return app.exec()
