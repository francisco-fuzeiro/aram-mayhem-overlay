"""Lifecycle ownership for the existing FastAPI application (not a second API)."""
from __future__ import annotations

import logging
import threading
import time

from backend.desktop.runtime import (
    DesktopStartupError, companion_code, port_in_use, probe_companion,
)

logger = logging.getLogger("aram-oracle.desktop")


class ManagedApi:
    """Start one in-process uvicorn server or reuse a pre-existing compatible API."""

    def __init__(self):
        self._server = None
        self._thread = None
        self._errors: list[BaseException] = []
        self.mode: str | None = None

    def start(self, timeout: float = 120.0) -> str:
        if probe_companion():
            # Field 23/11: an old API kept serving after "updates", so every
            # report came from stale code. Reuse only the same code version.
            from backend.feature_diagnostics import code_version
            mine, theirs = code_version(), companion_code()
            if mine is not None and theirs != mine:
                raise DesktopStartupError(
                    f"An older ARAM Oracle ({theirs or 'unknown version'}) is still "
                    f"running. Quit it (tray icon > Quit ARAM Oracle, or close its "
                    f"terminal) and start this version ({mine}) again.")
            self.mode = "reused"
            return self.mode
        if port_in_use():
            raise DesktopStartupError(
                "Port 8765 is occupied by an incompatible service. "
                "Close that service before launching ARAM Oracle."
            )

        # Reuse the existing ASGI app, preferences, collectors and pipeline.
        import uvicorn
        from backend.api.server import app

        self._server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=8765, log_level="warning"
        ))

        def runner() -> None:
            try:
                self._server.run()
            except BaseException as error:
                self._errors.append(error)
                logger.exception("ARAM Oracle API stopped unexpectedly")

        self._thread = threading.Thread(
            target=runner, name="aram-oracle-api", daemon=True
        )
        self._thread.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # Check ownership before accepting a responding API: another process
            # may have won a simultaneous port bind after the initial probe.
            if self._errors or not self._thread.is_alive():
                self.stop()
                raise DesktopStartupError(
                    f"ARAM Oracle API could not start: {self._errors[0] if self._errors else 'server exited'}"
                )
            if self._server.started and probe_companion():
                self.mode = "started"
                return self.mode
            time.sleep(0.1)

        self.stop()
        raise DesktopStartupError(
            "ARAM Oracle API did not become ready in time. "
            "Check port 8765 and the server logs."
        )

    def alive(self) -> bool:
        return (self._thread is not None and self._thread.is_alive()
                if self.mode == "started" else probe_companion())

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=6)
            if self._thread.is_alive():
                logger.error("API thread did not exit within six seconds")
            self._thread = None
        self._server = None
        self.mode = None
