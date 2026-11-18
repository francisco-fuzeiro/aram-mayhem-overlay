"""Start or reuse the existing local ARAM Oracle API for desktop Settings."""

from __future__ import annotations

import logging
import socket
import threading
import time

import requests

logger = logging.getLogger("aram-oracle.desktop")

API_BASE = "http://127.0.0.1:8765"
SETTINGS_URL = f"{API_BASE}/settings"
_STYLES = {"Balanced", "Damage", "Survival", "Utility"}


class DesktopStartupError(RuntimeError):
    """The desktop UI cannot safely connect to the local companion API."""


def probe_companion() -> bool:
    """Recognize our API, rather than treating any HTTP 200 as our server.

    This is an instance-compatibility check, not authentication. The server
    only binds to loopback; external origins are never used for Settings.
    """
    try:
        health = requests.get(f"{API_BASE}/health", timeout=0.5)
        if health.status_code != 200:
            return False
        status = health.json()
        if not isinstance(status, dict) or status.get("status") != "ok":
            return False
        if not all(
            key in status
            for key in ("data_loaded", "champions_loaded", "augments_loaded", "items_loaded")
        ):
            return False

        prefs = requests.get(f"{API_BASE}/api/preferences", timeout=0.5)
        if prefs.status_code != 200:
            return False
        saved = prefs.json()
        if (
            not isinstance(saved, dict)
            or saved.get("build_style") not in _STYLES
            or not isinstance(saved.get("available_styles"), list)
            or not _STYLES.issubset(set(saved["available_styles"]))
        ):
            return False

        page = requests.get(SETTINGS_URL, timeout=0.5)
        return page.status_code == 200 and "Settings · ARAM Oracle" in page.text
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        return False


def port_in_use() -> bool:
    """Detect an unrelated listener even when its HTTP response is invalid."""
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=0.5):
            return True
    except OSError:
        return False


def _run_existing_api() -> None:
    """Share the exact FastAPI/uvicorn startup path used by the overlay."""
    from backend.overlay.__main__ import _start_server

    _start_server()


def ensure_api_available(timeout: float = 15.0) -> str:
    """Return 'reused' or 'started'; never start a second bound API server.

    The existing overlay process can own the API. A different process on our
    port is a hard failure, not permission to load a possibly foreign page.
    """
    if probe_companion():
        return "reused"
    if port_in_use():
        raise DesktopStartupError(
            "Port 8765 is in use, but the service is not a compatible "
            "ARAM Oracle API. Close the conflicting program and retry."
        )

    failures: list[BaseException] = []

    def server_target() -> None:
        try:
            _run_existing_api()
        except BaseException as error:
            failures.append(error)
            logger.exception("The local API server stopped unexpectedly")

    thread = threading.Thread(
        target=server_target, name="aram-oracle-api", daemon=True
    )
    thread.start()

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if probe_companion():
            return "started"
        if failures:
            raise DesktopStartupError(
                f"ARAM Oracle API failed to start: {failures[0]}"
            ) from failures[0]
        if not thread.is_alive():
            raise DesktopStartupError(
                "ARAM Oracle API exited before Settings became available. "
                "Check the terminal for the server error."
            )
        time.sleep(0.2)

    if port_in_use():
        raise DesktopStartupError(
            "Port 8765 is occupied, but a compatible Settings API never "
            "became ready. Check the terminal or close the conflicting process."
        )
    raise DesktopStartupError(
        "ARAM Oracle API did not become ready within "
        f"{timeout:g} seconds. Check the terminal for startup errors."
    )
