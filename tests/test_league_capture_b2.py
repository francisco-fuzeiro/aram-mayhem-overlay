"""M4/B2: League-window-only crop and focus/stale OCR regression tests."""
from unittest.mock import Mock

from backend.collectors import screen_ocr
from backend.collectors.league_window import LeagueWindow
from backend.api.server import poll_tick
from tests.test_poll_tick_m1 import make_harness, make_snapshot
import pytest


def league(*, focused=True):
    return LeagueWindow(
        hwnd=17, left=-1920, top=100, right=0, bottom=1180, focused=focused,
    )


def test_mss_crop_uses_game_client_rect_not_selected_monitor(monkeypatch):
    monkeypatch.setattr(screen_ocr, "OCR_AVAILABLE", True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: league())
    grabbed = []
    class FakeMSS:
        @property
        def monitors(self):
            raise AssertionError("monitor fallback must never be used")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def grab(self, rect):
            grabbed.append(rect)
            return type("Shot", (), {"size": (rect["width"], rect["height"]), "bgra": b""})()
    monkeypatch.setattr(screen_ocr.mss, "mss", lambda: FakeMSS())
    monkeypatch.setattr(screen_ocr.Image, "frombytes", lambda *args: "cropped")
    assert screen_ocr.capture_augment_region() == "cropped"
    assert grabbed == [{
        "left": -1632, "top": 337, "width": 1344, "height": 302,
    }]


def test_alt_tab_blocks_capture_without_opening_mss(monkeypatch):
    monkeypatch.setattr(screen_ocr, "OCR_AVAILABLE", True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: league(focused=False))
    monkeypatch.setattr(screen_ocr.mss, "mss", lambda: pytest.fail("captured desktop"))
    assert screen_ocr.capture_augment_region() is None


def test_watcher_blur_returns_not_focused_without_capture_ocr_or_forgetting_slots(monkeypatch):
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: league(focused=False))
    monkeypatch.setattr(screen_ocr, "capture_augment_region", lambda *args, **kw: pytest.fail("captured"))
    monkeypatch.setattr(screen_ocr, "extract_text", lambda *args: pytest.fail("OCR invoked"))
    watcher = screen_ocr.ScreenWatcher()
    watcher._last_detected = [("known", "Known", 95)]
    watcher._frozen_hash = "old"
    assert watcher.check({"known": "Known"}) == ("not_focused", None)
    assert watcher.last_detected == [("known", "Known", 95)]


def test_refocus_forces_fresh_ocr_even_if_hash_would_match_previous_frame(monkeypatch):
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    state = {"focused": False}
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: league(focused=state["focused"]))
    monkeypatch.setattr(screen_ocr, "capture_augment_region", lambda *args, **kw: "frame")
    monkeypatch.setattr(screen_ocr, "_perceptual_hash", lambda img: "0" * 64)
    monkeypatch.setattr(screen_ocr, "crop_title_slots", lambda *_args: {
        slot: "synthetic" for slot in ("left", "centre", "right")
    })
    reads = []
    def read(slot, _crop, _names):
        reads.append(slot)
        return ("new", "New", 95) if slot == "left" else None
    from backend.collectors import slot_title_ocr
    monkeypatch.setattr(slot_title_ocr, "recognize_title_slot", read)
    watcher = screen_ocr.ScreenWatcher()
    watcher._last_detected = [("old", "Old", 90)]
    assert watcher.check({})[0] == "not_focused"
    state["focused"] = True
    # Refocus does not reuse the previous hash or accept one frame.
    assert watcher.check({})[0] == "no_augments"
    action, matches = watcher.check({})
    assert action == "detected"
    assert matches.slots["left"][0] == "new"
    assert reads == ["left", "centre", "right"] * 2


def test_manual_scan_cannot_ocr_an_unfocused_window(monkeypatch):
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: league(focused=False))
    monkeypatch.setattr(screen_ocr, "extract_text", lambda *args: pytest.fail("OCR invoked"))
    assert screen_ocr.detect_augments({"one": "One"}, save=False) == []


@pytest.mark.asyncio
async def test_poll_alt_tab_preserves_old_slots_and_emits_stale_not_focused():
    state, deps, events = make_harness(
        [{"tick": 1}], [make_snapshot()], ocr=True,
        watcher_result=("not_focused", [], None),
    )
    state.scan_window_open = True
    state.last_known_level = 3
    state.augment_choices = ["previous"]
    state.ocr_last_detected = ["previous"]
    await poll_tick(state, deps, 10.0)
    assert state.augment_choices == ["previous"]
    assert state.ocr_last_detected == ["previous"]
    assert state.ocr_stale
    assert any(e.get("status") == "not_focused" and e.get("stale") is True
               for e in events)
    assert not any(e.get("detected") for e in events)


@pytest.mark.asyncio
async def test_poll_recovers_only_after_fresh_observed_cards():
    state, deps, events = make_harness(
        [{"tick": 1}], [make_snapshot()], ocr=True,
        watcher_result=("detected", ["current"], [
            {"id": "current", "name": "Current", "confidence": 95},
        ]),
    )
    state.scan_window_open = True
    state.last_known_level = 3
    state.augment_choices = ["previous"]
    state.ocr_stale = True
    await poll_tick(state, deps, 12.0)
    assert not state.ocr_stale
    assert state.augment_choices == ["current"]
    assert any(e["type"] == "ocr_result" and e["detected"][0]["id"] == "current"
               for e in events)
