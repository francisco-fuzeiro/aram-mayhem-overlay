"""M4/B3 screenshot privacy: explicit opt-in, card crops and retention."""
import os
import time
from pathlib import Path
from unittest.mock import Mock

from PIL import Image
import pytest

from backend.collectors import screen_ocr
from backend.collectors.league_window import LeagueWindow
from backend.collectors.window_capture import CaptureProof, CaptureResult
from backend.config import DEFAULTS, Config, config
from backend.api import server
from backend.diagnostic_events import default_log_dir


def league(focused=True):
    return LeagueWindow(
        hwnd=3, left=0, top=0, right=1920, bottom=1080, focused=focused,
    )


def image_of_augment_region():
    return Image.new("RGB", (1344, 302), (21, 37, 99))


def verified_proof(game=None):
    game = game or league()
    return CaptureProof("wgc", game.hwnd, game.rect, 10.0, "other")


@pytest.fixture
def debug_env(monkeypatch, tmp_path):
    monkeypatch.setattr(screen_ocr, "OCR_AVAILABLE", True)
    monkeypatch.setattr(screen_ocr, "SCREENSHOT_DIR", tmp_path)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: league())
    monkeypatch.setattr(screen_ocr, "screenshot_opted_in", lambda: True, raising=False)
    return tmp_path


def test_default_off_and_only_boolean_explicit_toml_opt_in(tmp_path):
    assert DEFAULTS["ocr_debug_screenshots"] is False
    assert config.get("ocr_debug_screenshots") is False
    path = tmp_path / "config.toml"
    path.write_text("[ocr]\nocr_debug_screenshots = true\n", encoding="utf-8")
    store = Config()
    store.load(path)
    assert store.get("ocr_debug_screenshots") is True


def test_no_image_saved_by_default_even_if_save_requested(monkeypatch, tmp_path):
    monkeypatch.setattr(screen_ocr, "OCR_AVAILABLE", True)
    monkeypatch.setattr(screen_ocr, "SCREENSHOT_DIR", tmp_path / "screenshots")
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: league())
    assert screen_ocr.screenshot_opted_in() is False
    assert screen_ocr.save_screenshot(image_of_augment_region(), label="ocr", proof=verified_proof()) is None
    assert not (tmp_path / "screenshots").exists()


def test_explicit_optin_cannot_save_unverified_image_even_without_focus(debug_env, monkeypatch):
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: league(False))
    assert screen_ocr.save_screenshot(image_of_augment_region(), label="ocr") is None
    assert not list(debug_env.glob("*.png"))


def test_opted_in_images_are_three_narrow_card_title_crops_only(debug_env):
    image = image_of_augment_region()
    first = screen_ocr.save_screenshot(
        image, label="ocr", ocr_texts=["PRIVATE SCREEN TEXT"],
        matches=[("internal", "PRIVATE AUGMENT", 92)], proof=verified_proof(),
    )
    paths = list(debug_env.glob("*.png"))
    assert first is not None and first in paths
    assert len(paths) == 3
    assert {p.name.split("_")[1] for p in paths} == {"left", "centre", "right"}
    for path in paths:
        with Image.open(path) as crop:
            assert crop.width < image.width // 2
            assert 0 < crop.height < image.height // 2
            # No arbitrary text or OCR annotation may be burnt into images.
            assert crop.tobytes() == Image.new("RGB", crop.size, (21, 37, 99)).tobytes()


def test_even_opted_in_rejects_full_monitor_and_other_untrusted_input(debug_env):
    assert screen_ocr.save_screenshot(Image.new("RGB", (1920, 1080)), label="full") is None
    assert screen_ocr.save_screenshot(Image.new("RGB", (1000, 600)), label="window") is None
    assert list(debug_env.glob("*.png")) == []


def test_user_data_directory_and_retention_count_and_age(debug_env):
    assert screen_ocr.default_screenshot_dir() == default_log_dir().parent / "screenshots"
    old = debug_env / "card_left_legacy.png"
    old.write_bytes(b"old")
    old_time = time.time() - 9 * 86400
    os.utime(old, (old_time, old_time))
    for i in range(12):
        assert screen_ocr.save_screenshot(image_of_augment_region(), label="ocr")
    paths = list(debug_env.glob("*.png"))
    assert not old.exists()
    assert 0 < len(paths) <= screen_ocr.MAX_SCREENSHOTS
    assert all(p.name.startswith("card_") for p in paths)


def test_removed_fullscreen_capture_api_cannot_be_called():
    assert not hasattr(screen_ocr, "capture_full_screen")


@pytest.mark.asyncio
async def test_manual_rest_and_ws_ocr_obey_explicit_debug_switch(monkeypatch):
    seen = []
    state = server.GameState()
    state.scan_window_open = True
    state.offer_lifecycle.open()
    monkeypatch.setattr(server, "game_state", state)
    monkeypatch.setattr(server, "ocr_available", lambda: True)
    monkeypatch.setitem(config._data, "ocr_debug_screenshots", True)
    monkeypatch.setattr(server, "detect_augments",
                        lambda names, *, save: seen.append(save) or [])
    await server.ocr_scan()
    server._run_ocr_scan_manual()
    assert seen == [True, True]


def test_auto_watcher_debug_flag_is_injected_from_config(monkeypatch):
    seen = []
    monkeypatch.setitem(config._data, "ocr_debug_screenshots", True)
    class FakeWatcher:
        def check(self, names, *, save):
            seen.append(save)
            return "no_augments", None
    monkeypatch.setattr(server, "screen_watcher", FakeWatcher())
    server._run_watcher_check()
    assert seen == [True]


def test_screenshot_routes_only_serve_active_user_data_directory(debug_env, monkeypatch):
    monkeypatch.setitem(config._data, "ocr_debug_screenshots", True)
    (debug_env / "card_left_test.png").write_bytes(b"fake")
    result = server.list_screenshots()
    assert result == [{
        "name": "card_left_test.png",
        "url": "/api/ocr/screenshots/card_left_test.png",
    }]
    monkeypatch.setitem(config._data, "ocr_debug_screenshots", False)
    assert server.list_screenshots() == []
    assert server.get_screenshot("card_left_test.png") == {"error": "not found"}


def test_custom_ocr_region_cannot_escape_game_or_request_full_window(monkeypatch):
    invalid = [
        [-0.5, 0.22, 1.4, 0.5],
        [0, 0, 1, 1],
        ["invalid", 0.22, 0.85, 0.5],
        [float("nan"), 0.22, 0.85, 0.5],
    ]
    for override in invalid:
        monkeypatch.setitem(config._data, "ocr_region", override)
        assert screen_ocr.get_augment_region(1920, 1080) == screen_ocr.AUGMENT_REGION_16_9
    monkeypatch.setitem(config._data, "ocr_region", [0.1, 0.2, 0.9, 0.45])
    assert screen_ocr.get_augment_region(1920, 1080) == (0.1, 0.2, 0.9, 0.45)


def test_cached_game_handle_rejects_unverified_window_mismatch(monkeypatch):
    monkeypatch.setattr(screen_ocr, "OCR_AVAILABLE", True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: league(False))
    wrong = LeagueWindow(99, 0, 0, 1920, 1080, False)
    monkeypatch.setattr(screen_ocr, "capture_league_client", lambda *a, **kw:
                        CaptureResult(
                            Image.new("RGB", (1920, 1080)),
                            verified_proof(wrong), "ok",
                        ))
    result = screen_ocr.capture_augment_region(league_window=league(True))
    assert result.reason == "window_changed" and result.image is None
