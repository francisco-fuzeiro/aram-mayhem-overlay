"""M4/B2: League-window-only crop and focus/stale OCR regression tests."""
from unittest.mock import Mock
from itertools import count

from backend.collectors import screen_ocr
from backend.collectors.league_window import LeagueWindow
from backend.api.server import poll_tick, _OcrWatcherObservation
from tests.test_poll_tick_m1 import make_harness, make_snapshot
import pytest


def league(*, focused=True):
    return LeagueWindow(
        hwnd=17, left=-1920, top=100, right=0, bottom=1180, focused=focused,
    )


_PROOF_TIMES = count(10)


def _verified_client(*, foreground="other"):
    from PIL import Image
    from backend.collectors.window_capture import CaptureProof, CaptureResult
    game = league(focused=False)
    return CaptureResult(
        Image.new("RGB", (1920, 1080), (21, 37, 99)),
        CaptureProof("wgc", game.hwnd, game.rect, float(next(_PROOF_TIMES)), foreground), "ok",
    )


def test_verified_window_source_crops_game_roi_not_monitor(monkeypatch):
    monkeypatch.setattr(screen_ocr, "OCR_AVAILABLE", True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: league(focused=False))
    monkeypatch.setattr(screen_ocr, "capture_league_client", lambda *a, **kw: _verified_client())
    region = screen_ocr.capture_augment_region()
    assert region.reason == "ok"
    assert region.proof.backend == "wgc"
    assert region.image.size == (1344, 302)


def test_unverified_image_is_not_returned_from_capture(monkeypatch):
    monkeypatch.setattr(screen_ocr, "OCR_AVAILABLE", True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: league(focused=False))
    from backend.collectors.window_capture import CaptureResult
    monkeypatch.setattr(screen_ocr, "capture_league_client",
                        lambda *a, **kw: CaptureResult(None, None, "invalid_frame"))
    result = screen_ocr.capture_augment_region()
    assert result.image is None and result.proof is None


def test_watcher_occlusion_suspends_pending_without_reading_ocr(monkeypatch):
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: league(focused=False))
    from backend.collectors.window_capture import CaptureResult
    monkeypatch.setattr(screen_ocr, "capture_league_client",
                        lambda *a, **kw: CaptureResult(None, None, "occluded", "other"))
    from backend.collectors import slot_title_ocr
    monkeypatch.setattr(slot_title_ocr, "recognize_title_slot",
                        lambda *args: pytest.fail("unsafe OCR"))
    watcher = screen_ocr.ScreenWatcher()
    watcher._temporal._pending = {"left": "old"}
    assert watcher.check({"known": "Known"}) == ("occluded", None)
    assert watcher.last_scan_stage == "game_occluded"
    assert not watcher._temporal.has_unverified_changes


def test_foreground_loss_does_not_block_verified_wgc_ocr(monkeypatch):
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: league(focused=False))
    monkeypatch.setattr(screen_ocr, "capture_league_client", lambda *a, **kw: _verified_client())
    monkeypatch.setattr(screen_ocr, "_perceptual_hash", lambda img: "0" * 64)
    monkeypatch.setattr(screen_ocr, "crop_title_slots", lambda *_args: {
        slot: "synthetic" for slot in ("left", "centre", "right")
    })
    reads = []
    from backend.collectors import slot_title_ocr
    def read(slot, _crop, _names):
        reads.append(slot)
        return ("new", "New", 95) if slot == "left" else None
    monkeypatch.setattr(slot_title_ocr, "recognize_title_slot", read)
    watcher = screen_ocr.ScreenWatcher(sleep_fn=lambda _: None)
    action, matches = watcher.check({})
    assert action == "detected"
    assert watcher.check({}) == ("unchanged", None)
    assert matches.slots["left"][0] == "new"
    assert reads == ["left", "centre", "right"] * 2


def test_manual_scan_rejects_unverified_frame(monkeypatch):
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: league(focused=False))
    from backend.collectors.window_capture import CaptureResult
    monkeypatch.setattr(screen_ocr, "capture_league_client",
                        lambda *a, **kw: CaptureResult(None, None, "invalid_frame"))
    monkeypatch.setattr(screen_ocr, "extract_text", lambda *args: pytest.fail("unsafe OCR"))
    assert screen_ocr.detect_augments({"one": "One"}, save=False) == []


@pytest.mark.asyncio
async def test_poll_occluded_window_preserves_old_slots_and_latches_stale():
    state, deps, events = make_harness(
        [{"tick": 1}], [make_snapshot()], ocr=True,
        watcher_result=("occluded", [], None),
    )
    state.scan_window_open = True
    state.last_known_level = 3
    state.augment_choices = ["previous"]
    state.ocr_last_detected = ["previous"]
    state.set_ocr_phase("detected")
    await poll_tick(state, deps, 10.0)
    assert state.augment_choices == ["previous"]
    assert state.ocr_last_detected == ["previous"]
    assert state.ocr_stale
    assert any(e.get("status") == "occluded" and e.get("stale") is True
               for e in events)
    assert not any(e.get("detected") for e in events)


@pytest.mark.asyncio
async def test_poll_recovers_only_after_fresh_observed_cards():
    state, deps, events = make_harness(
        [{"tick": 1}], [make_snapshot()], ocr=True,
        watcher_result=_OcrWatcherObservation("detected", ["current"], [
            {"id": "current", "name": "Current", "confidence": 95},
        ], reverified=True),
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
