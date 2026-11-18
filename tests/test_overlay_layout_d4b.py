"""D4b headless overlay geometry/Qt integration regression tests."""
from pathlib import Path

import pytest

from backend import preferences
from backend.overlay.layout import calculate_overlay_geometry as geometry


def config(**values):
    return {**preferences.DEFAULT_OVERLAY, **values}


def test_1080p_default_top_right_is_inside_available_screen():
    assert geometry((0, 0, 1920, 1080), config()) == (1576, 24, 320, 960)


@pytest.mark.parametrize("anchor,expected", [
    ("top_left", (-2510, 80)),
    ("top_right", (-370, 80)),
    ("bottom_left", (-2510, 40)),
    ("bottom_right", (-370, 40)),
])
def test_four_corners_on_negative_origin_second_display(anchor, expected):
    assert geometry((-2560, 0, 2560, 1440),
                    config(anchor=anchor, offset_x=50, offset_y=80))[:2] == expected


def test_scaled_logical_coordinates_and_taskbar_inset_125_percent():
    # A 2560x1440 physical display at 125% appears as logical 2048x1152.
    x, y, w, h = geometry((0, 0, 2048, 1112),
                          config(anchor="bottom_right", scale=1.25))
    assert (w, h) == (400, 1112)
    assert 0 <= x <= 2048 - w and 0 <= y <= 1112 - h


def test_150_percent_scale_and_oversized_offsets_clamp_inside_display():
    assert geometry((1920, -100, 1280, 680),
                    config(anchor="top_left", offset_x=-500, offset_y=-500,
                           opacity=0.45, scale=1.5)) == (1920, -100, 480, 680)


def test_bottom_right_negative_offsets_are_safe():
    x, y, w, h = geometry((0, 0, 1920, 1080),
                          config(anchor="bottom_right", offset_x=-500, offset_y=-500))
    assert x == 1920 - w and y == 1080 - h


def test_tiny_monitor_bounds_and_invalid_geometry():
    assert geometry((100, 200, 180, 100), config(scale=1.5)) == (100, 200, 180, 100)
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
