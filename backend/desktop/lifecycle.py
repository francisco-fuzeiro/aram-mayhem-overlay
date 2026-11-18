"""Unified startup for the Qt Settings and overlay surfaces."""
from __future__ import annotations

import logging

from backend.desktop.instance import InstanceGate
from backend.desktop.runtime import DesktopStartupError
from backend.desktop.service import ManagedApi

logger = logging.getLogger("aram-oracle.desktop")


def run_application(initial_view: str = "settings", directory=None) -> int:
    """One process, one tray and at most one owned API for both launchers."""
    if initial_view not in {"settings", "overlay"}:
        raise ValueError("Unknown initial view")
    with InstanceGate(directory) as gate:
        if not gate.acquire():
            if gate.forward(initial_view):
                logger.info("Activated existing ARAM Oracle %s window", initial_view)
                return 0
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
