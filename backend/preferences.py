"""Versioned, locally persisted player and overlay preferences.

Preferences are advisory presentation settings, not League client commands.
D4a only stores overlay appearance values; Qt consumes them in D4b.
"""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path

from backend.engine.build_suggester import BUILD_STYLES

logger = logging.getLogger("aram-oracle.preferences")
PREFERENCES_FILE = Path.home() / ".aram-oracle" / "preferences.json"
PREFERENCES_SCHEMA_VERSION = 1
DEFAULT_BUILD_STYLE = "Balanced"
OVERLAY_ANCHORS = frozenset(("top_left", "top_right", "bottom_left", "bottom_right"))
OVERLAY_KEYS = frozenset(("anchor", "offset_x", "offset_y", "opacity", "scale"))
DEFAULT_OVERLAY = {
    "anchor": "top_right",
    "offset_x": 24,
    "offset_y": 24,
    "opacity": 0.92,
    "scale": 1.0,
}
OFFSET_MIN, OFFSET_MAX = -500, 500
OPACITY_MIN, OPACITY_MAX = 0.40, 1.0
SCALE_MIN, SCALE_MAX = 0.75, 1.50


def validate_overlay(overlay: object) -> dict:
    """Strict validation for the full persisted overlay object (no coercion)."""
    if not isinstance(overlay, dict) or set(overlay) != OVERLAY_KEYS:
        raise ValueError("overlay requires anchor, offset_x, offset_y, opacity and scale")
    anchor = overlay["anchor"]
    if not isinstance(anchor, str) or anchor not in OVERLAY_ANCHORS:
        raise ValueError("invalid overlay anchor")
    for name in ("offset_x", "offset_y"):
        value = overlay[name]
        if type(value) is not int or not OFFSET_MIN <= value <= OFFSET_MAX:
            raise ValueError(f"{name} must be an integer between {OFFSET_MIN} and {OFFSET_MAX}")
    for name, lower, upper in (
        ("opacity", OPACITY_MIN, OPACITY_MAX),
        ("scale", SCALE_MIN, SCALE_MAX),
    ):
        value = overlay[name]
        if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError(f"{name} must be a finite number between {lower} and {upper}")
    return {
        "anchor": anchor,
        "offset_x": overlay["offset_x"],
        "offset_y": overlay["offset_y"],
        "opacity": float(overlay["opacity"]),
        "scale": float(overlay["scale"]),
    }


def _read_payload(source: Path) -> dict:
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Unable to read preferences from %s: %s", source, exc)
        return {}
    if not isinstance(payload, dict):
        logger.warning("Invalid preferences document in %s", source)
        return {}
    return payload


def _version_supported(payload: dict) -> bool:
    version = payload.get("schema_version", 0)  # legacy: build_style only
    return type(version) is int and version in (0, PREFERENCES_SCHEMA_VERSION)


def load_preferences(path: Path | None = None) -> dict:
    """Migrate v0 in memory; sanitize invalid saved fields individually.

    A read does not rewrite disk. The next successful save writes schema v1.
    Unknown schema versions use safe defaults; they are never silently rewritten.
    """
    source = path if path is not None else PREFERENCES_FILE
    result = {
        "schema_version": PREFERENCES_SCHEMA_VERSION,
        "build_style": DEFAULT_BUILD_STYLE,
        "overlay": dict(DEFAULT_OVERLAY),
    }
    payload = _read_payload(source)
    if not _version_supported(payload):
        logger.warning("Unsupported preferences schema in %s; using defaults", source)
        return result
    style = payload.get("build_style")
    if type(style) is str and style in BUILD_STYLES:
        result["build_style"] = style
    elif style is not None:
        logger.warning("Invalid saved build style in %s; using default", source)

    if payload.get("schema_version", 0) == PREFERENCES_SCHEMA_VERSION:
        raw_overlay = payload.get("overlay", {})
        if isinstance(raw_overlay, dict):
            for name in OVERLAY_KEYS:
                if name in raw_overlay:
                    candidate = {**result["overlay"], name: raw_overlay[name]}
                    try:
                        result["overlay"] = validate_overlay(candidate)
                    except ValueError:
                        logger.warning("Invalid saved overlay %s in %s; using default", name, source)
        elif raw_overlay is not None:
            logger.warning("Invalid saved overlay object in %s; using defaults", source)
    return result


def _save_document(document: dict, path: Path | None = None) -> None:
    target = path if path is not None else PREFERENCES_FILE
    # Do not destroy a future schema unknown to this client on any write.
    saved = _read_payload(target)
    if not _version_supported(saved):
        raise ValueError("unsupported saved preferences schema")
    style = document.get("build_style")
    if type(style) is not str or style not in BUILD_STYLES:
        raise ValueError("invalid build style")
    overlay = validate_overlay(document.get("overlay"))
    canonical = {
        "schema_version": PREFERENCES_SCHEMA_VERSION,
        "build_style": style,
        "overlay": overlay,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    try:
        temp.write_text(json.dumps(canonical, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, target)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def load_build_style(path: Path | None = None) -> str:
    """Legacy entrypoint remains available for existing callers."""
    return load_preferences(path)["build_style"]


def save_build_style(style: str, path: Path | None = None) -> None:
    """Update only build style without wiping overlay preferences."""
    if type(style) is not str or style not in BUILD_STYLES:
        raise ValueError("invalid build style")
    document = load_preferences(path)
    document["build_style"] = style
    _save_document(document, path)


def save_overlay_preferences(overlay: object, path: Path | None = None) -> None:
    """Update only overlay preferences without wiping legacy build style."""
    validated = validate_overlay(overlay)
    document = load_preferences(path)
    document["overlay"] = validated
    _save_document(document, path)
