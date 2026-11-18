"""Pure, DPI-independent overlay placement within a Qt screen's available geometry.

Coordinates are logical Qt pixels, not physical desktop pixels. The caller supplies
the selected monitor's availableGeometry() (with its possibly negative origin).
No Qt import is needed, so positioning is covered by headless CI regressions.
"""
from __future__ import annotations

from backend.preferences import validate_overlay


def calculate_overlay_geometry(
    available: tuple[int, int, int, int],
    overlay: dict,
    *,
    base_width: int = 320,
    vertical_inset: int = 60,
) -> tuple[int, int, int, int]:
    """Return a bounded x/y/width/height for any corner and signed offsets."""
    prefs = validate_overlay(overlay)
    left, top, width, height = available
    if width <= 0 or height <= 0 or base_width <= 0 or vertical_inset < 0:
        raise ValueError("invalid available screen geometry")
    scale = prefs["scale"]
    panel_width = min(width, max(1, round(base_width * scale)))
    content_height = max(180, height - 2 * vertical_inset)
    panel_height = min(height, max(1, round(content_height * scale)))
    x = (left + prefs["offset_x"] if prefs["anchor"].endswith("left")
         else left + width - panel_width - prefs["offset_x"])
    y = (top + prefs["offset_y"] if prefs["anchor"].startswith("top")
         else top + height - panel_height - prefs["offset_y"])
    x = min(max(x, left), left + width - panel_width)
    y = min(max(y, top), top + height - panel_height)
    return int(x), int(y), int(panel_width), int(panel_height)
