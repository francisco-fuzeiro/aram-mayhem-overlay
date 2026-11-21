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
import json
from ctypes import wintypes
import sys
import logging
import threading
import urllib.request
import webbrowser
from urllib.parse import urlsplit, parse_qs

from backend import preferences
from backend.diagnostic_events import events
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
WS_EX_NOACTIVATE = 0x08000000
WDA_EXCLUDEFROMCAPTURE = 0x11

# Overlay dimensions
OVERLAY_WIDTH = 320
OVERLAY_MARGIN_RIGHT = 10
OVERLAY_MARGIN_TOP = 60
VK_MENU = 0x12
VK_O = 0x4F
VK_H = 0x48
VK_S = 0x53
VK_B = 0x42
VK_1 = 0x31
VK_2 = 0x32
VK_3 = 0x33
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
            if level.value >= QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel.value:
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
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool  # hidden from taskbar
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )

            # D4b: screen-relative geometry is applied once WebEngine is ready.
            self._overlay_preferences = dict(preferences.DEFAULT_OVERLAY)
            self._layout_in_progress = False
            self._watched_screens = set()
            self._screen_signal_connected = False
            self._capture_exclusion_warning_emitted = False

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
            self._build_hotkey_was_down = False
            self._pick_hotkeys_down = {"left": False, "centre": False, "right": False}
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
            # The native HWND may be recreated when Qt window flags change.
            self._apply_capture_exclusion()

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
            """D1: place Qt logical geometry only inside verified HUD-free bands."""
            if self._layout_in_progress or not hasattr(self, "_view"):
                return
            from backend.collectors.league_window import find_league_window
            from backend.overlay.hud_zones import (
                HudScales, forbidden_rects, load_hud_zones,
                physical_to_logical_rect,
            )
            from backend.overlay.league_config import (
                executable_path_for_hwnd, read_hud_scales,
            )
            from backend.overlay.layout import calculate_overlay_placement

            screens = QApplication.screens()
            screen = self.screen()
            if screen not in screens:
                screen = QApplication.primaryScreen()
            if screen is None:
                return

            game = find_league_window()
            if game is not None:
                # LeagueWindow.rect is already DPI-aware *physical* client pixels.
                physical_client = (
                    game.left, game.top, game.right - game.left,
                    game.bottom - game.top,
                )
                centre_x = game.left + physical_client[2] / 2
                centre_y = game.top + physical_client[3] / 2

                def monitor_distance(candidate):
                    # On Windows Qt screen origins are native desktop positions,
                    # whereas width/height are device-independent.
                    geometry = candidate.geometry()
                    ratio = candidate.devicePixelRatio()
                    if ratio <= 0:
                        ratio = 1.0
                    l, t = geometry.x(), geometry.y()
                    r = l + geometry.width() * ratio
                    b = t + geometry.height() * ratio
                    dx = max(l - centre_x, 0, centre_x - r)
                    dy = max(t - centre_y, 0, centre_y - b)
                    return dx * dx + dy * dy

                screen = min(screens, key=monitor_distance)
                # Convert exactly once before invoking the pure layout solver.
                dpr = screen.devicePixelRatio()
                client = physical_to_logical_rect(
                    physical_client, dpr if dpr > 0 else 1.0,
                )
                scales = read_hud_scales(executable_path_for_hwnd(game.hwnd))
            else:
                # No verified game window: remain in the screen work area with
                # conservative defaults. Do not infer game state from Qt focus.
                area = screen.availableGeometry()
                client = (area.x(), area.y(), area.width(), area.height())
                scales = HudScales()
            area = screen.availableGeometry()  # taskbar-safe and screen-origin-aware
            try:
                zones = forbidden_rects(client, scales, load_hud_zones())
                x, y, w, h, mode = calculate_overlay_placement(
                    client, self._overlay_preferences, base_width=OVERLAY_WIDTH,
                    vertical_inset=OVERLAY_MARGIN_TOP, forbidden=zones,
                )
                self._layout_in_progress = True
                # A hidden layout must never leave a sizeable transparent Qt
                # surface above the game. Keep native shortcuts/tray intact.
                self._view.setVisible(mode != "hidden")
                qt_height = h if mode != "hidden" else 1
                if (self.x(), self.y(), self.width(), self.height()) != (x, y, w, qt_height):
                    self.setGeometry(x, y, w, qt_height)
                self._view.setZoomFactor(self._overlay_preferences["scale"])
                self.setWindowOpacity(self._overlay_preferences["opacity"])
            except (ValueError, RuntimeError, OSError) as exc:
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
            """Read deliberate local hotkeys, never send keys or clicks to League."""
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
            build_down = alt_down and bool(
                user32.GetAsyncKeyState(VK_B) & 0x8000
            )
            if interaction_down and not self._hotkey_was_down:
                self._toggle_click_through()
            if visibility_down and not self._visibility_hotkey_was_down:
                self._toggle_visibility()
            if scan_down and not self._scan_hotkey_was_down:
                self._request_manual_scan()
            if build_down and not self._build_hotkey_was_down:
                self._view.page().runJavaScript(
                    "window.postMessage({type:'toggle_build'}, '*')"
                )
            for slot, key in (("left", VK_1), ("centre", VK_2), ("right", VK_3)):
                down = alt_down and bool(user32.GetAsyncKeyState(key) & 0x8000)
                if down and not self._pick_hotkeys_down[slot]:
                    self._request_confirm_slot(slot)
                self._pick_hotkeys_down[slot] = down
            self._hotkey_was_down = interaction_down
            self._visibility_hotkey_was_down = visibility_down
            self._scan_hotkey_was_down = scan_down
            self._build_hotkey_was_down = build_down

        def _request_manual_scan(self):
            """Alt+S: explicitly recover a due offer if needed, then request OCR."""
            try:
                port = urlsplit(self._view.url().toString()).port or 8765
            except ValueError:
                port = 8765
            origin = f"http://127.0.0.1:{port}"

            def request_scan():
                try:
                    status_request = urllib.request.Request(
                        origin + "/api/ocr/status", method="GET",
                    )
                    with urllib.request.urlopen(status_request, timeout=5) as response:
                        status = json.load(response)
                    offers = status.get("offers", [])
                    verified = any(
                        o.get("state") == "awaiting_confirm" or
                        (o.get("state") == "visible" and any(
                            slot.get("source") == "ocr" and slot.get("augment_id")
                            for slot in o.get("slots", {}).values()
                        ))
                        for o in offers if isinstance(o, dict)
                    )
                    due = [o for o in offers
                           if isinstance(o, dict) and o.get("state") == "due"
                           and type(o.get("offer_id")) is int]
                    if not verified and due:
                        target = max(due, key=lambda o: o["offer_id"])
                        recovery = urllib.request.Request(
                            origin + "/api/offers/recover",
                            data=json.dumps(
                                {"offer_id": target["offer_id"]}
                            ).encode("utf-8"),
                            method="POST",
                            headers={"Content-Type": "application/json"},
                        )
                        with urllib.request.urlopen(recovery, timeout=5) as response:
                            response.read()
                    request = urllib.request.Request(
                        origin + "/api/ocr/scan", data=b"", method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=5) as response:
                        response.read()
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    logger.debug("Manual OCR request unavailable: %s",
                                 type(exc).__name__)

            threading.Thread(
                target=request_scan, daemon=True, name="aram-ocr-manual",
            ).start()

        def _request_confirm_slot(self, slot: str):
            """Confirm only through the local ledger API, off the Qt thread."""
            if slot not in ("left", "centre", "right"):
                return
            try:
                port = urlsplit(self._view.url().toString()).port or 8765
            except ValueError:
                port = 8765
            endpoint = f"http://127.0.0.1:{port}/api/offers/confirm-slot"
            body = json.dumps({"slot": slot}).encode("utf-8")

            def send_confirmation():
                request = urllib.request.Request(
                    endpoint, data=body, method="POST",
                    headers={"Content-Type": "application/json"},
                )
                try:
                    with urllib.request.urlopen(request, timeout=5) as response:
                        response.read()
                except (OSError, ValueError) as exc:
                    logger.debug("Manual pick confirmation unavailable: %s",
                                 type(exc).__name__)

            threading.Thread(
                target=send_confirmation, daemon=True,
                name="aram-pick-confirm",
            ).start()

        def _toggle_click_through(self):
            """Alt+O temporarily permits interaction, then restores non-activation."""
            if sys.platform != "win32":
                return
            if self._is_click_through:
                self._is_click_through = False
                self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, False)
                self.show()
                self._apply_capture_exclusion()
                hwnd = int(self.winId())
                user32 = ctypes.windll.user32
                style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE,
                    style & ~(WS_EX_TRANSPARENT | WS_EX_NOACTIVATE),
                )
                self._view.page().runJavaScript(
                    "document.body.classList.add('interactive-mode');"
                    "window.dispatchEvent(new Event('aram-interaction-changed'))"
                )
            else:
                self._is_click_through = True
                self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
                self.show()
                self._apply_capture_exclusion()
                self._view.page().runJavaScript(
                    "document.body.classList.remove('interactive-mode');"
                    "window.dispatchEvent(new Event('aram-interaction-changed'))"
                )
                # Qt may recreate its HWND during the flag change.
                QTimer.singleShot(0, self._set_click_through)
            logger.info(
                "Qt click-through %s", "ON" if self._is_click_through else "OFF"
            )

        def _set_click_through(self):
            """Restore click-through and no-activation on the current native HWND."""
            # A previously queued timer must never undo a newer Alt+O toggle.
            if not self._is_click_through:
                return
            if sys.platform != "win32":
                logger.warning("Click-through only works on Windows")
                return

            try:
                hwnd = int(self.winId())
                user32 = ctypes.windll.user32
                current_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE,
                    current_style | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE,
                )
                self._apply_capture_exclusion()
                logger.info("Click-through enabled (HWND=%d)", hwnd)
            except Exception as exc:
                logger.error("Failed to set click-through: %s", exc)

        def _apply_capture_exclusion(self):
            """Best-effort screenshot hygiene; never evidence for A3 window capture."""
            if sys.platform != "win32":
                return
            try:
                user32 = ctypes.windll.user32
                set_affinity = user32.SetWindowDisplayAffinity
                get_affinity = user32.GetWindowDisplayAffinity
                # Explicit HWND types avoid truncating 64-bit native handles.
                set_affinity.argtypes = (wintypes.HWND, wintypes.DWORD)
                set_affinity.restype = wintypes.BOOL
                get_affinity.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
                get_affinity.restype = wintypes.BOOL
                hwnd = int(self.winId())
                applied = bool(set_affinity(hwnd, WDA_EXCLUDEFROMCAPTURE))
                actual = wintypes.DWORD()
                if (
                    applied
                    and bool(get_affinity(hwnd, ctypes.byref(actual)))
                    and actual.value == WDA_EXCLUDEFROMCAPTURE
                ):
                    return
            except (AttributeError, OSError, TypeError, ValueError):
                pass

            if not self._capture_exclusion_warning_emitted:
                logger.warning(
                    "Overlay capture exclusion unsupported; A3 occlusion safeguards remain active"
                )
                self._capture_exclusion_warning_emitted = True
            events.transition("overlay_capture_exclusion", status="unsupported")


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
