"""M5/C1: measured, ordered title bands for opt-in diagnostic screenshots.

The 2544x1353 client is a real Windows League viewport, desktop origin (8,31).
These are observed positioning checks, not OCR accuracy or 1080p acceptance.
"""
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from backend.collectors import screen_ocr
from backend.collectors.card_title_geometry import title_bands_from_client_rect
from backend.collectors.league_window import LeagueWindow
from backend.collectors.window_capture import CaptureProof


OBSERVED_RECT = (8, 31, 2552, 1384)
OBSERVED = {
    "left": (643, 490, 340, 90),
    "centre": (1100, 490, 340, 90),
    "right": (1567, 490, 340, 90),
}


def test_real_windowed_client_three_padded_title_bands():
    # Real user-reviewed Mayhem offer: long wrapped left title, centre and right.
    # The earlier 496..574 strip was too tightly bounded at the glyph edge.
    assert title_bands_from_client_rect(OBSERVED_RECT) == OBSERVED


def test_negative_monitor_origin_and_desktop_offset_do_not_move_local_titles():
    assert title_bands_from_client_rect((-1920, -70, 624, 1283)) == OBSERVED
    assert title_bands_from_client_rect((100, 200, 2644, 1553)) == OBSERVED


def test_borderless_1440p_and_synthetic_1080p_scale_without_slot_overlap():
    for rect in ((0, 0, 2560, 1440), (0, 0, 1920, 1080)):
        bands = title_bands_from_client_rect(rect)
        assert bands is not None
        assert list(bands) == ["left", "centre", "right"]
        width, height = rect[2], rect[3]
        for x, y, w, h in bands.values():
            assert 0 <= x < x + w <= width
            assert 0 <= y < y + h <= height
            assert w >= 80 and h >= 20
        assert bands["left"][0] + bands["left"][2] < bands["centre"][0]
        assert bands["centre"][0] + bands["centre"][2] < bands["right"][0]
    # 1080p boxes here are *extrapolations*, pending a real 1080p playtest.
    # League's UI scales with the height (audit P1-10): offsets from the
    # centre and the box size follow 1080/1353, not 1920/2544.
    assert title_bands_from_client_rect((0, 0, 1920, 1080)) == {
        "left": (458, 391, 271, 72),
        "centre": (823, 391, 271, 72),
        "right": (1195, 391, 271, 72),
    }
    centre = title_bands_from_client_rect((0, 0, 1920, 1080))["centre"]
    assert abs(centre[0] + centre[2] / 2 - 960) <= 3  # observed box is 2 px off-centre


@pytest.mark.parametrize("rect", [
    (0, 0, 1920, 1200),  # 16:10 unsupported
    (0, 0, 2560, 1080),  # 21:9 unsupported
    (0, 0, 1280, 960),   # 4:3 unsupported
    (0, 0, 0, 1080), (0, 0, 1920, 0), (3, 4, 2, 5),
    (0, 0, 500, 260),    # too small for a reliable title-band diagnostic
])
def test_unsupported_client_geometry_fails_closed(rect):
    assert title_bands_from_client_rect(rect) is None


@pytest.fixture
def diagnostic(monkeypatch, tmp_path):
    monkeypatch.setattr(screen_ocr, "OCR_AVAILABLE", True)
    monkeypatch.setattr(screen_ocr, "screenshot_opted_in", lambda: True)
    monkeypatch.setattr(screen_ocr, "SCREENSHOT_DIR", tmp_path / "saved")
    monkeypatch.setattr(
        screen_ocr, "find_league_window",
        lambda: LeagueWindow(23, 8, 31, 2552, 1384, True),
    )
    return tmp_path / "saved"


def observed_region_image():
    width, height = 2544, 1353
    left, top, right, bottom = screen_ocr.get_augment_region(width, height)
    region_width = int(width * (right - left))
    region_height = int(height * (bottom - top))
    strip = Image.new("RGB", (region_width, region_height), (12, 12, 12))
    draw = ImageDraw.Draw(strip)
    colors = {"left": (255, 20, 20), "centre": (20, 255, 20), "right": (20, 20, 255)}
    for slot, (x, y, w, h) in OBSERVED.items():
        rx, ry = x - int(width * left), y - int(height * top)
        draw.rectangle((rx, ry, rx + w - 1, ry + h - 1), fill=colors[slot])
    return strip, colors


def test_save_screenshot_extracts_correct_ordered_bands_without_icons_or_hud(diagnostic):
    strip, colors = observed_region_image()
    first = screen_ocr.save_screenshot(strip, label="PRIVATE-ignored",
                                        ocr_texts=["PRIVATE-ignored"],
                                        proof=CaptureProof("wgc", 23, OBSERVED_RECT, 10.0, "other"))
    paths = {slot: next(diagnostic.glob(f"card_{slot}_*.png")) for slot in OBSERVED}
    assert first == paths["left"]
    assert len(list(diagnostic.glob("*.png"))) == 3
    for slot in OBSERVED:
        with Image.open(paths[slot]) as img:
            assert img.size == (340, 90)
            assert img.mode == "RGB"
            assert img.getpixel((10, 10)) == colors[slot]
            assert img.getpixel((170, 45)) == colors[slot]
    assert not list(diagnostic.glob("*PRIVATE*"))


def test_rejects_region_override_that_does_not_contain_all_title_bands(
    diagnostic, monkeypatch,
):
    strip, _ = observed_region_image()
    # Same shape as a permitted custom region, but excludes the right title.
    monkeypatch.setattr(screen_ocr, "get_augment_region", lambda *args: (0.15, 0.22, 0.50, 0.50))
    shorter = strip.crop((0, 0, int(2544 * 0.35), strip.height))
    assert screen_ocr.save_screenshot(shorter) is None
    assert not diagnostic.exists()


def test_unverified_blurred_window_never_saves_even_with_opt_in(diagnostic, monkeypatch):
    monkeypatch.setattr(
        screen_ocr, "find_league_window",
        lambda: LeagueWindow(23, 8, 31, 2552, 1384, False),
    )
    strip, _ = observed_region_image()
    assert screen_ocr.save_screenshot(strip) is None
    assert not diagnostic.exists()
