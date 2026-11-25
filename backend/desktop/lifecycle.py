"""Unified startup for the Qt Settings and overlay surfaces."""
from __future__ import annotations

import logging

from backend.desktop.instance import InstanceGate
from backend.desktop.runtime import DesktopStartupError
from backend.desktop.service import ManagedApi

logger = logging.getLogger("aram-oracle.desktop")


def _wait_acquire(gate, timeout: float) -> bool:
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if gate.acquire():
            return True
        time.sleep(0.2)
    return False


def run_application(initial_view: str = "settings", directory=None) -> int:
    """One process, one tray and at most one owned API for both launchers."""
    if initial_view not in {"settings", "overlay"}:
        raise ValueError("Unknown initial view")
    with InstanceGate(directory) as gate:
        if not gate.acquire():
            from backend.feature_diagnostics import code_version
            mine = code_version()
            if mine is not None and gate.owner_code() != mine:
                # Field 23/11: launching an updated version only re-showed the
                # old process. Ask it to quit, then take over.
                gate.forward("quit", timeout=3.0)
                if not _wait_acquire(gate, 10.0):
                    raise DesktopStartupError(
                        "An older ARAM Oracle is still running. Quit it (tray icon > "
                        "Quit ARAM Oracle, or close its terminal) and start again.")
            elif gate.forward(initial_view):
                logger.info("Activated existing ARAM Oracle %s window", initial_view)
                return 0
            else:
                raise DesktopStartupError(
                "Another ARAM Oracle instance is starting or not responding. "
                "Try launching it again, or close the unresponsive process."
            )

        service = ManagedApi()
        try:
            service.start()
            gate.listen()
            from backend.desktop.window import run_managed_ui
            return run_managed_ui(gate, service, initial_view)
        finally:
            # Releases the listener+instance lock and shuts down owned uvicorn.
            # Externally started, compatible API servers remain untouched.
            gate.close()
            service.stop()
