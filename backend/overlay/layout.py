"""Pure, DPI-independent placement in Qt logical client coordinates.

The D1 layout computes vertical free bands against versioned HUD exclusions.
Legacy four-value geometry callers keep their return contract; Qt consumes the
five-value placement with an explicit full/compact/hidden presentation mode.
"""
from __future__ import annotations

from backend.preferences import validate_overlay
from backend.overlay.hud_zones import (
    PANEL_MIN_H,
    HudScales,
    forbidden_rects,
    load_hud_zones,
    place_panel,
)


def calculate_overlay_placement(
    available: tuple[int, int, int, int],
    overlay: dict,
    *,
    base_width: int = 320,
    vertical_inset: int = 60,
    forbidden: dict[str, tuple[int, int, int, int]] | None = None,
) -> tuple[int, int, int, int, str]:
    """Find a HUD-safe vertical band, including safe compact/hidden outcomes."""
    prefs = validate_overlay(overlay)
    left, top, width, height = available
    if width <= 0 or height <= 0 or base_width <= 0 or vertical_inset < 0:
        raise ValueError("invalid available screen geometry")
    panel_width = min(width, max(1, round(base_width * prefs["scale"])))
    preferred = max(180, height - 2 * vertical_inset)
    preferred_height = min(height, max(1, round(preferred * prefs["scale"])))
    zones = forbidden if forbidden is not None else forbidden_rects(
        available, HudScales(), load_hud_zones(),
    )
    return place_panel(available, panel_width, preferred_height, PANEL_MIN_H, zones, prefs)


def calculate_overlay_geometry(
    available: tuple[int, int, int, int],
    overlay: dict,
    *,
    base_width: int = 320,
    vertical_inset: int = 60,
) -> tuple[int, int, int, int]:
    """Backward-compatible four-coordinate API; hidden has zero height."""
    return calculate_overlay_placement(
        available, overlay, base_width=base_width, vertical_inset=vertical_inset,
    )[:4]
