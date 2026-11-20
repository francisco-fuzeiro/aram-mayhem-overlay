"""D4b original input matrix, upgraded to D1 HUD-exclusion invariants."""
from pathlib import Path

import pytest

from backend import preferences
from backend.overlay.layout import (
    calculate_overlay_geometry as geometry,
    calculate_overlay_placement,
)
from backend.overlay.hud_zones import HudScales, forbidden_rects, load_hud_zones


def config(**values):
    return {**preferences.DEFAULT_OVERLAY, **values}


def assert_safe(available, overlay):
    result = calculate_overlay_placement(available, overlay)
    assert result == calculate_overlay_placement(available, overlay)
    x, y, w, h, mode = result
    left, top, width, height = available
    assert left <= x <= x + w <= left + width
    assert top <= y <= y + h <= top + height
    assert geometry(available, overlay) == (x, y, w, h)
    zones = forbidden_rects(available, HudScales(), load_hud_zones())
    if mode != "hidden":
        for rx, ry, rw, rh in zones.values():
            assert not (x < rx + rw and x + w > rx and y < ry + rh and y + h > ry)
    else:
        assert h == 0
    return result


def test_1080p_default_top_right_is_inside_available_screen():
    x, y, w, h, mode = assert_safe((0, 0, 1920, 1080), config())
    assert mode == "full"
    assert w == 320


@pytest.mark.parametrize("anchor,expected", [
    ("top_left", (-2510, 80)),
    ("top_right", (-370, 80)),
    ("bottom_left", (-2510, 40)),
    ("bottom_right", (-370, 40)),
])
def test_four_corners_on_negative_origin_second_display(anchor, expected):
    # Preserve the original 2560x1440, negative-origin, offset inputs.
    x, y, w, h, mode = assert_safe(
        (-2560, 0, 2560, 1440), config(anchor=anchor, offset_x=50, offset_y=80)
    )
    assert x == expected[0]
    assert 0 <= y <= 1440 - h


def test_scaled_logical_coordinates_and_taskbar_inset_125_percent():
    # A 2560x1440 physical display at 125% appears as logical 2048x1152.
    available = (0, 0, 2048, 1112)
    prefs = config(anchor="bottom_right", scale=1.25)
    x, y, w, h, mode = assert_safe(available, prefs)
    assert w == 400
    assert 0 <= x <= 2048 - w and 0 <= y <= 1112 - h


def test_150_percent_scale_and_oversized_offsets_clamp_inside_display():
    available = (1920, -100, 1280, 680)
    prefs = config(anchor="top_left", offset_x=-500, offset_y=-500,
                   opacity=0.45, scale=1.5)
    x, y, w, h, mode = assert_safe(available, prefs)
    assert x == 1920 and w == 480


def test_bottom_right_negative_offsets_are_safe():
    available = (0, 0, 1920, 1080)
    prefs = config(anchor="bottom_right", offset_x=-500, offset_y=-500)
    x, y, w, h, mode = assert_safe(available, prefs)
    assert x == 1920 - w
    assert 0 <= y <= 1080 - h


def test_tiny_monitor_bounds_and_invalid_geometry():
    assert_safe((100, 200, 180, 100), config(scale=1.5))
    for bad in ((0, 0, 0, 1080), (0, 0, 1920, -1)):
        with pytest.raises(ValueError, match="invalid available"):
            geometry(bad, config())


def test_invalid_preferences_are_not_silently_applied():
    with pytest.raises(ValueError, match="scale"):
        geometry((0, 0, 1920, 1080), config(scale=float("nan")))


def test_qt_surface_preserves_shortcuts_clickthrough_and_atomic_reload():
    root = Path(__file__).resolve().parents[1]
    source = (root / "backend/overlay/window.py").read_text(encoding="utf-8")
    assert "VK_O = 0x4F" in source and "VK_H = 0x48" in source
    assert "WS_EX_TRANSPARENT | WS_EX_LAYERED" in source
    assert "WA_TranslucentBackground" in source
    assert "enable_tray: bool = True" in source
    assert "preferences.load_preferences()" in source
    assert "self._preferences_timer.start(800)" in source
    assert "screen.availableGeometry()" in source
    assert "self._view.setZoomFactor" in source
    assert "self.setWindowOpacity" in source
    assert 'if getattr(self, "_is_click_through", False)' in source
    assert "self._watch_screens()" in source
