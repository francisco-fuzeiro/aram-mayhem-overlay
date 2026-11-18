"""
Launch ARAM Oracle with the transparent overlay.

Starts the FastAPI server in a background thread, then opens
the overlay window using the best available backend:

  Default: pywebview > PyQt6 > browser fallback.
  Use --renderer qt to try Qt when WebView2 transparency fails.

Usage:
    python -m backend.overlay
    python -m backend.overlay --renderer qt
"""

import argparse
import sys
import threading
import time
import webbrowser
import logging


def _set_dpi_awareness():
    """Enable per-monitor DPI awareness so screen captures get real pixels."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


_set_dpi_awareness()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("aram-oracle.overlay")

OVERLAY_URL = "http://localhost:8765/overlay?mode=overlay"


def _start_server():
    """Run the FastAPI server in a background thread."""
    import uvicorn
    from backend.api.server import app

    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")


def _launch_overlay(renderer: str = "auto"):
    """Select an embedded window renderer without changing default behavior."""
    from backend.overlay.webview_window import is_available as webview_ok
    from backend.overlay.window import is_available as qt_ok

    if renderer == "qt":
        if not qt_ok():
            raise RuntimeError(
                'Qt renderer unavailable. Install: python -m pip install -e ".[overlay]"'
            )
        logger.info("Using PyQt6 transparent overlay (explicit renderer)")
        from backend.overlay.window import run_overlay
        run_overlay(OVERLAY_URL)
        return

    if renderer == "webview":
        if not webview_ok():
            raise RuntimeError(
                'pywebview unavailable. Install: python -m pip install -e ".[webview-overlay]"'
            )
        logger.info("Using pywebview overlay (explicit renderer)")
        from backend.overlay.webview_window import run_overlay
        run_overlay(OVERLAY_URL)
        return

    if webview_ok():
        logger.info(
            "Using pywebview overlay. For a white transparent background on "
            "Windows, try: python -m backend.overlay --renderer qt"
        )
        from backend.overlay.webview_window import run_overlay
        run_overlay(OVERLAY_URL)
        return

    if qt_ok():
        logger.info("Using PyQt6 overlay")
        from backend.overlay.window import run_overlay
        run_overlay(OVERLAY_URL)
        return

    logger.warning("No overlay backend available — opening in browser")
    webbrowser.open(OVERLAY_URL)


def _wait_for_server(timeout: float = 15.0) -> bool:
    """Poll the health endpoint until the server is ready."""
    import requests as req
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = req.get("http://localhost:8765/health", timeout=0.5)
            if r.status_code == 200:
                logger.info("Server is ready")
                return True
        except req.ConnectionError:
            pass
        time.sleep(0.2)
    logger.warning("Server did not become ready within %.0fs", timeout)
    return False


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="ARAM Oracle companion overlay")
    parser.add_argument(
        "--renderer", choices=("auto", "webview", "qt"), default="auto",
        help="Select the window engine; Qt can avoid WebView2 transparency problems.",
    )
    args = parser.parse_args(argv)
    # Share the same desktop lifecycle for Qt launches and repeated activation.
    # The explicit webview renderer remains a legacy developer fallback.
    if args.renderer == "qt":
        from backend.desktop.__main__ import main as desktop_main
        return desktop_main([], initial_view="overlay")
    if args.renderer == "auto":
        from backend.overlay.window import is_available as qt_ok
        if qt_ok():
            from backend.desktop.__main__ import main as desktop_main
            return desktop_main([], initial_view="overlay")
    from backend.config import config
    config.load()
    logger.info("Starting ARAM Oracle with overlay...")

    # Start the web server in a daemon thread
    server_thread = threading.Thread(target=_start_server, daemon=True)
    server_thread.start()
    logger.info("Server starting on http://localhost:8765")

    # Wait for the server to be ready instead of a fixed sleep
    _wait_for_server()

    # Launch the overlay (blocks until window is closed)
    _launch_overlay(renderer=args.renderer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
