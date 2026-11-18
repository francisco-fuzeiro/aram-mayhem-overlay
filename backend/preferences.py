"""Local player preferences used by the pre-game Settings page.

Preferences are presentation choices, never commands to the League client.
Keep them separate from config.toml and avoid secrets in this file.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from backend.engine.build_suggester import BUILD_STYLES

logger = logging.getLogger("aram-oracle.preferences")
PREFERENCES_FILE = Path.home() / ".aram-oracle" / "preferences.json"
DEFAULT_BUILD_STYLE = "Balanced"


def load_build_style(path: Path | None = None) -> str:
    """Return a validated, safe style from local disk or the default."""
    source = path if path is not None else PREFERENCES_FILE
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("build_style") in BUILD_STYLES:
            return payload["build_style"]
        logger.warning("Invalid saved build style in %s; using default", source)
    except FileNotFoundError:
        pass
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Unable to read saved build style: %s", exc)
    return DEFAULT_BUILD_STYLE


def save_build_style(style: str, path: Path | None = None) -> None:
    """Atomically save a validated build-style preference.

    Callers serialize writes using GameState.lock; this function does not
    change the active match state or make game decisions.
    """
    if style not in BUILD_STYLES:
        raise ValueError("invalid build style")

    target = path if path is not None else PREFERENCES_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    try:
        temp.write_text(
            json.dumps({"build_style": style}, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temp, target)
    finally:
        # A failed atomic replace should not leave misleading temp contents.
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
