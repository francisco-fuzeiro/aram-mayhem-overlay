"""Regular resizable Qt WebEngine window for the existing Settings page."""

from __future__ import annotations

import logging
import sys

from backend.desktop.runtime import SETTINGS_URL, DesktopStartupError

logger = logging.getLogger("aram-oracle.desktop")

try:
    from PyQt6.QtCore import QUrl
    from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


if PYQT_AVAILABLE:

    class SettingsWindow(QMainWindow):
        """A standard taskbar window; no overlay flags or Win32 mouse hooks."""

        def __init__(self, url: str = SETTINGS_URL):
            super().__init__()
            self.setWindowTitle("ARAM Oracle — Settings")
            self.resize(960, 760)
            self.setMinimumSize(600, 460)

            self._view = QWebEngineView(self)
            self.setCentralWidget(self._view)
            self._view.loadFinished.connect(self._on_page_loaded)
            self._view.setUrl(QUrl(url))

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
            self.close()


def is_available() -> bool:
    """Require Qt Widgets and WebEngine; no display needed for this check."""
    return PYQT_AVAILABLE


def run_desktop(url: str = SETTINGS_URL) -> int:
    """Open the normal Settings window and block on the Qt event loop."""
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
