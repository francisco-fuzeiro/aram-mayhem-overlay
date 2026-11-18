"""Launch native ARAM Oracle Settings without launching an in-game overlay.

Usage:
    python -m backend.desktop
"""

from __future__ import annotations

import logging
import sys

from backend.desktop.runtime import (
    SETTINGS_URL,
    DesktopStartupError,
    ensure_api_available,
)
from backend.desktop.window import is_available, run_desktop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("aram-oracle.desktop")


def main(argv: list[str] | None = None) -> int:
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
        mode = ensure_api_available()
        logger.info("Local ARAM Oracle API %s", mode)
        return run_desktop(SETTINGS_URL)
    except DesktopStartupError as error:
        logger.error("%s", error)
        return 1
    except Exception:
        logger.exception("Desktop Settings failed to start")
        return 1


if __name__ == "__main__":
    sys.exit(main())
