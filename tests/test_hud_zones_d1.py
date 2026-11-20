"""D1 v3: versioned HUD exclusions and conservative, DPI-aware overlay placement."""

import json
from pathlib import Path

import pytest

from backend import preferences
from backend.overlay.hud_zones import (
    COMPACT_H,
    PANEL_MIN_H,
    HudScales,
    forbidden_rects,
    load_hud_zones,
    physical_to_logical_rect,
    place_panel,
)
from backend.overlay.layout import calculate_overlay_placement
from backend.overlay.league_config import read_hud_scales


RESOLUTIONS = (
    (1280, 720), (1600, 900), (1920, 1080), (2560, 1080),
    (2560, 1440), (3440, 1440), (3840, 2160), (1920, 1200),
)
SCALES = ((0.0, 0.0), (1.0, 1.0), (0.5, 3.0))
ANCHORS = ("top_left", "top_right", "bottom_left", "bottom_right")


def intersects(a, b):
    return max(a[0], b[0]) < min(a[0] + a[2], b[0] + b[2]) and (
        max(a[1], b[1]) < min(a[1] + a[3], b[1] + b[3])
    )


def bounded(rect, client):
    x, y, w, h = rect
    cx, cy, cw, ch = client
    return w >= 0 and h >= 0 and cx <= x and cy <= y and x + w <= cx + cw and y + h <= cy + ch


def test_versioned_coverage_and_provisional_status():
    zones = load_hud_zones()
    assert zones["version"] == "hud_zones_v1"
    assert zones["reference_height"] == 1080
    assert zones["status"] == "unvalidated_until_N1"
    assert set(zones["zones"]) == {
        "top_right_stats", "top_center_score", "kill_feed", "minimap",
        "bottom_hud", "chat", "augment_cards",
    }
    for name, zone in zones["zones"].items():
        assert set(zone) == {"anchor", "x", "y", "w", "h", "scale_with"}, name
        assert zone["anchor"] in {
            "top_left", "top_center", "top_right", "bottom_left",
            "bottom_center", "bottom_right", "center",
        }
        assert zone["scale_with"] in {"hud", "minimap", "none"}


@pytest.mark.parametrize("width,height", RESOLUTIONS)
@pytest.mark.parametrize("origin", (0, -2560))
@pytest.mark.parametrize("dpr", (1.0, 1.25, 1.5))
@pytest.mark.parametrize("hud,minimap", SCALES)
@pytest.mark.parametrize("anchor", ANCHORS)
@pytest.mark.parametrize("offset", (0, 500))
def test_d1_full_placement_matrix(width, height, origin, dpr, hud, minimap, anchor, offset):
    physical = (origin, 0, width, height)
    client = physical_to_logical_rect(physical, dpr)
    zones = forbidden_rects(client, HudScales(hud, minimap), load_hud_zones())
    prefs = {**preferences.DEFAULT_OVERLAY, "anchor": anchor, "offset_x": offset, "offset_y": offset}
    choice = place_panel(client, 320, max(180, client[3] - 120), PANEL_MIN_H, zones, prefs)
    assert choice == place_panel(client, 320, max(180, client[3] - 120), PANEL_MIN_H, zones, prefs)
    x, y, w, h, mode = choice
    assert bounded((x, y, w, h), client)
    assert mode in {"full", "compact", "hidden"}
    if mode != "hidden":
        assert h >= COMPACT_H
        for zone in zones.values():
            assert not intersects((x, y, w, h), zone), (physical, dpr, hud, minimap, prefs, choice, zone)
    if mode == "full":
        assert h >= PANEL_MIN_H
    elif mode == "compact":
        assert h == COMPACT_H
    else:
        assert h == 0


@pytest.mark.parametrize("width,height,dpr", ((1920, 1080, 1), (2560, 1440, 1)))
def test_golden_right_column_below_kill_feed_and_above_minimap(width, height, dpr):
    client = physical_to_logical_rect((0, 0, width, height), dpr)
    forbidden = forbidden_rects(client, HudScales(), load_hud_zones())
    x, y, w, h, mode = calculate_overlay_placement(client, preferences.DEFAULT_OVERLAY, forbidden=forbidden)
    assert mode == "full"
    assert y >= forbidden["kill_feed"][1] + forbidden["kill_feed"][3]
    assert y + h <= forbidden["minimap"][1]
    assert all(not intersects((x, y, w, h), z) for z in forbidden.values())


def test_compact_and_hidden_are_explicit_and_never_cover_exclusions():
    client = (0, 0, 200, 250)
    prefs = {**preferences.DEFAULT_OVERLAY, "anchor": "top_left"}
    narrow = {"mid": (0, 0, 200, 190)}
    x, y, w, h, mode = place_panel(client, 120, 220, PANEL_MIN_H, narrow, prefs)
    assert (h, mode) == (COMPACT_H, "compact")
    assert not intersects((x, y, w, h), narrow["mid"])
    fully_blocked = {"all": client}
    x, y, w, h, mode = place_panel(client, 120, 220, PANEL_MIN_H, fully_blocked, prefs)
    assert (h, mode) == (0, "hidden")


def test_physical_coordinates_are_converted_once_including_negative_origin():
    assert physical_to_logical_rect((-2560, 0, 2560, 1440), 1.25) == (-2048, 0, 2048, 1152)
    assert physical_to_logical_rect((0, 0, 1920, 1080), 1.5) == (0, 0, 1280, 720)
    with pytest.raises(ValueError):
        physical_to_logical_rect((0, 0, 1920, 1080), 0)


def test_game_cfg_scales_are_parsed_with_provenance(tmp_path):
    exe = tmp_path / "League" / "Game" / "League of Legends.exe"
    exe.parent.mkdir(parents=True)
    cfg = exe.parent.parent / "Config" / "game.cfg"
    cfg.parent.mkdir()
    cfg.write_text("[HUD]\nGlobalScale=0.5000\nMinimapScale=2.0000\n", encoding="utf-8")
    scales = read_hud_scales(exe)
    assert scales == HudScales(0.5, 2.0)
    assert scales.confidence != "default"
    cfg.write_text("[HUD]\nGlobalScale=nope\nMinimapScale=2.0\n", encoding="utf-8")
    failed = read_hud_scales(exe)
    assert failed == HudScales()
    assert failed.confidence == "default"
    cfg.unlink()
    assert read_hud_scales(exe).confidence == "default"


def test_out_of_range_game_cfg_values_clamp_conservatively(tmp_path):
    exe = tmp_path / "League" / "Game" / "League of Legends.exe"
    exe.parent.mkdir(parents=True)
    cfg = exe.parent.parent / "Config" / "game.cfg"
    cfg.parent.mkdir()
    cfg.write_text("[HUD]\nGlobalScale=-8\nMinimapScale=99\n", encoding="utf-8")
    assert read_hud_scales(exe) == HudScales(0.0, 3.0)


def test_d1_changes_only_qt_layout_and_preserves_no_focus_and_a3_guards():
    source = (Path(__file__).resolve().parents[1] / "backend/overlay/window.py").read_text(encoding="utf-8")
    method = source.split("def _apply_overlay_layout(self, *_args):", 1)[1].split(
        "def _on_page_loaded(self, success:", 1
    )[0]
    assert "find_league_window" in method
    assert "read_hud_scales" in method
    assert "devicePixelRatio" in method
    assert "forbidden_rects" in method
    assert "calculate_overlay_placement" in method
    assert "screen.availableGeometry()" in method
    assert "self._view.setZoomFactor" in method
    assert "self.setWindowOpacity" in method
    assert "WS_EX_NOACTIVATE = 0x08000000" in source
    assert "WDA_EXCLUDEFROMCAPTURE = 0x11" in source
