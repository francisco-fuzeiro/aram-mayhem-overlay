"""Pure, versioned HUD exclusion zones in League-client coordinates.

All measurements are provisional until the N1 native acceptance. This module
does not inspect screen pixels, game state or user input.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path

Rect = tuple[int, int, int, int]
PANEL_MIN_H = 160
COMPACT_H = 36
_ANCHORS = frozenset({
    "top_left", "top_center", "top_right", "bottom_left",
    "bottom_center", "bottom_right", "center",
})


@dataclass(frozen=True)
class HudScales:
    hud: float = 1.0
    minimap: float = 1.0
    confidence: str = field(default="default", compare=False)


def load_hud_zones() -> dict:
    """Read the bundled, intentionally unvalidated HUD geometry data."""
    with Path(__file__).with_name("hud_zones_v1.json").open(encoding="utf-8") as source:
        return json.load(source)


def physical_to_logical_rect(client: Rect, dpr: float) -> Rect:
    """Convert a DPI-aware physical League client rectangle exactly once."""
    if not math.isfinite(dpr) or dpr <= 0:
        raise ValueError("devicePixelRatio must be a finite positive number")
    x, y, w, h = client
    if w <= 0 or h <= 0:
        raise ValueError("invalid client geometry")
    return tuple(int(round(value / dpr)) for value in client)


def _scale_factor(kind: str, scales: HudScales) -> float:
    if kind == "none":
        return 1.0
    if kind == "hud":
        value = scales.hud
        if not math.isfinite(value):
            value = 1.0
        return 0.75 + 0.25 * max(0.0, min(1.0, value))
    if kind == "minimap":
        value = scales.minimap
        if not math.isfinite(value):
            value = 1.0
        return 0.6 + 0.4 * max(0.0, min(3.0, value)) / 3.0
    raise ValueError("invalid zone scale_with")


def forbidden_rects(client: Rect, scales: HudScales, zones: dict) -> dict[str, Rect]:
    """Anchor and clip forbidden rectangles in the client's coordinate system.

    The reference size is 1080 client pixels high; anchors use the entire
    client, never the desktop or screen's work area.
    """
    cx, cy, cw, ch = client
    if cw <= 0 or ch <= 0:
        raise ValueError("invalid client geometry")
    if zones.get("version") != "hud_zones_v1" or zones.get("reference_height") != 1080:
        raise ValueError("unsupported HUD zone data version")
    result: dict[str, Rect] = {}
    unit = ch / zones["reference_height"]
    right, bottom = cx + cw, cy + ch
    for name, zone in zones["zones"].items():
        anchor = zone["anchor"]
        if anchor not in _ANCHORS:
            raise ValueError("invalid HUD zone anchor")
        factor = _scale_factor(zone["scale_with"], scales)
        ow = max(0, int(round(zone["w"] * unit * factor)))
        oh = max(0, int(round(zone["h"] * unit * factor)))
        dx = zone["x"] * unit * factor
        dy = zone["y"] * unit * factor
        if anchor.endswith("left"):
            x = cx + round(dx)
        elif anchor.endswith("right"):
            x = right - ow - round(dx)
        else:
            x = cx + cw // 2 + round(dx)
        if anchor.startswith("top"):
            y = cy + round(dy)
        elif anchor.startswith("bottom"):
            y = bottom - oh - round(dy)
        else:
            y = cy + ch // 2 + round(dy)
        x1, y1 = max(cx, x), max(cy, y)
        x2, y2 = min(right, x + ow), min(bottom, y + oh)
        if x2 > x1 and y2 > y1:
            result[name] = (x1, y1, x2 - x1, y2 - y1)
    return result


def place_panel(
    client: Rect,
    panel_w: int,
    preferred_h: int,
    min_h: int,
    forbidden: dict[str, Rect],
    prefs: dict,
) -> tuple[int, int, int, int, str]:
    """Place a panel in a free vertical interval of its selected edge column.

    Full-height layouts are preferred. Compact layouts are exactly one line
    high, and a blocked column produces a zero-height hidden result. The
    horizontal and vertical offsets are clamped *inside* the client/free band.
    """
    cx, cy, cw, ch = client
    if cw <= 0 or ch <= 0 or panel_w <= 0 or preferred_h <= 0 or min_h <= 0:
        raise ValueError("invalid panel or client geometry")
    anchor = prefs["anchor"]
    if anchor not in {"top_left", "top_right", "bottom_left", "bottom_right"}:
        raise ValueError("invalid panel anchor")
    width = min(cw, panel_w)
    xoff = prefs["offset_x"]
    x = cx + xoff if anchor.endswith("left") else cx + cw - width - xoff
    x = max(cx, min(cx + cw - width, int(x)))
    column_right = x + width

    # The entire horizontal column must be clear, not just the four corners.
    blocked = []
    for rx, ry, rw, rh in forbidden.values():
        if rw > 0 and rh > 0 and rx < column_right and rx + rw > x:
            start, end = max(cy, ry), min(cy + ch, ry + rh)
            if start < end:
                blocked.append((start, end))
    blocked.sort()

    free: list[tuple[int, int]] = []
    cursor = cy
    for start, end in blocked:
        if start > cursor:
            free.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < cy + ch:
        free.append((cursor, cy + ch))

    from_top = anchor.startswith("top")
    qualifies = [interval for interval in free if interval[1] - interval[0] >= min_h]
    if qualifies:
        start, end = qualifies[0] if from_top else qualifies[-1]
        height = min(max(preferred_h, min_h), end - start)
        mode = "full"
    else:
        long_enough = [interval for interval in free if interval[1] - interval[0] >= COMPACT_H]
        if not long_enough:
            return (x, cy if from_top else cy + ch, width, 0, "hidden")
        best = max(end - start for start, end in long_enough)
        candidates = [interval for interval in long_enough if interval[1] - interval[0] == best]
        start, end = candidates[0] if from_top else candidates[-1]
        height = min(COMPACT_H, end - start)
        mode = "compact"
    offset = max(0, prefs["offset_y"])
    if from_top:
        y = start + min(offset, end - start - height)
    else:
        y = end - height - min(offset, end - start - height)
    return (x, y, width, height, mode)
