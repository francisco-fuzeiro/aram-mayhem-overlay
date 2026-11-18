"""Launch native ARAM Oracle Settings without launching an in-game overlay.

Usage:
    python -m backend.desktop
"""

from __future__ import annotations

import logging
import sys

from backend.desktop.runtime import DesktopStartupError
from backend.desktop.lifecycle import run_application
from backend.desktop.window import is_available

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("aram-oracle.desktop")


def main(argv: list[str] | None = None, *, initial_view: str = "settings") -> int:
    """Run the Settings UI, returning a nonzero status for startup failures."""
    import argparse
    parser = argparse.ArgumentParser(description="ARAM Oracle desktop Settings")
    parser.parse_args(argv)

    if not is_available():
        logger.error(
            'PyQt6 WebEngine is required. Install: python -m pip install -e ".[overlay]"'
        )
        return 2

    try:
        from backend.config import config
        config.load()
        return run_application(initial_view)
    except DesktopStartupError as error:
        logger.error("%s", error)
        return 1
    except Exception:
        logger.exception("Desktop Settings failed to start")
        return 1


if __name__ == "__main__":
    sys.exit(main())
