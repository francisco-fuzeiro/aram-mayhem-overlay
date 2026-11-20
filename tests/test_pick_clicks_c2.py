"""C2 offline click-hint geometry is pure and never monitors the OS mouse."""

from pathlib import Path

from backend.collectors.pick_clicks import (
    PICK_CLICK_HINTS_ENABLED, card_body_rects, first_card_click,
)


def test_click_monitoring_is_disabled_and_overlay_does_not_poll_mouse():
    assert PICK_CLICK_HINTS_ENABLED is False
    window = Path("backend/overlay/window.py").read_text(encoding="utf-8")
    assert "VK_LBUTTON" not in window
    assert "first_card_click(" not in window


def test_card_body_geometry_is_anchored_to_client_and_title():
    bands = {
        "left": (520, 465, 340, 90),
        "centre": (1110, 465, 340, 90),
        "right": (1690, 465, 340, 90),
    }
    rects = card_body_rects((0, 0, 2560, 1440), bands)
    middle = rects["centre"]
    assert (middle[0] + middle[2]) // 2 == 1280
    assert middle[2] - middle[0] == 490
    assert middle[1] < 510 < middle[3]


def test_first_click_and_reroll_area_safety():
    bands = {
        "left": (520, 465, 340, 90),
        "centre": (1110, 465, 340, 90),
        "right": (1690, 465, 340, 90),
    }
    rects = card_body_rects((0, 0, 2560, 1440), bands)
    assert first_card_click([(1280, 510, 3.0), (700, 510, 4.0)], rects, 2.0) == "centre"
    assert first_card_click([(700, 510, 1.0), (1280, 510, 3.0)], rects, 2.0) == "centre"
    assert first_card_click([(1280, 1000, 3.0)], rects, 2.0) is None
    assert first_card_click([(1280, 510, 1.0)], rects, 2.0) is None
