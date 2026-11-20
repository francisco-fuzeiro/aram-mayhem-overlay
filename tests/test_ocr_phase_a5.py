"""A5 v3: honest OCR phases, evidence-gated stale recovery and safe manual scans.

Synthetic observations only. No game process, desktop screen or real keyboard.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from PIL import Image

from backend.api import server
from backend.collectors.slot_temporal import SlotTemporalTracker
from backend.collectors.slot_title_ocr import SLOTS


VALID_IDS = ["a", "b", "c"]
ROWS = [
    {"slot": slot, "id": aid, "name": f"Synthetic {aid}", "confidence": 98}
    for slot, aid in zip(SLOTS, VALID_IDS)
]


def test_a5_exact_phase_vocabulary_and_defaults():
    state = server.GameState()
    assert state.ocr_phase == "no_offer"
    assert state.ocr_stale is False
    assert state.ocr_stale_since_epoch is None
    assert set(server.OCR_PHASES) == {
        "disabled", "ocr_missing", "no_game", "capture_unavailable",
        "occluded", "no_offer", "verifying", "detected", "unreadable",
    }


def test_detected_to_occlusion_latches_stale_until_positive_reverification():
    state = server.GameState()
    state.scan_window_open = True
    state.offer_epoch = 14
    state.set_ocr_phase("detected")
    state.set_ocr_phase("occluded")
    assert state.ocr_stale is True
    assert state.ocr_stale_since_epoch == 14
    for _ in range(3):
        state.set_ocr_phase("no_offer")
    assert state.ocr_stale is True
    state.set_ocr_phase("detected", reverified=False)
    assert state.ocr_stale is True
    state.set_ocr_phase("detected", reverified=True)
    assert state.ocr_stale is False
    assert state.ocr_stale_since_epoch is None


def test_verifying_and_unreadable_to_capture_failure_are_stale():
    for initial in ("verifying", "unreadable"):
        state = server.GameState()
        state.scan_window_open = True
        state.set_ocr_phase(initial)
        state.set_ocr_phase("capture_unavailable")
        assert state.ocr_stale is True
        state.set_ocr_phase("no_game")
        assert state.ocr_stale is True
        state.set_ocr_phase("no_offer", offer_closed=True)
        assert state.ocr_stale is False


def test_no_offer_without_independent_closed_offer_proof_never_clears_stale():
    state = server.GameState()
    state.scan_window_open = True
    state.set_ocr_phase("detected")
    state.set_ocr_phase("no_game")
    state.set_ocr_phase("no_offer")
    assert state.ocr_stale
    state.set_ocr_phase("verifying")
    assert state.ocr_stale


def test_tracker_reverified_requires_two_fresh_reads_for_all_three_slots():
    tracker = SlotTemporalTracker()
    crops = {slot: Image.new("RGB", (4, 4), i) for i, slot in enumerate(SLOTS, 1)}
    def read(slot, _crop, _names):
        i = SLOTS.index(slot)
        return VALID_IDS[i], f"Synthetic {i}", 98
    def digest(img):
        return str(img.getpixel((0, 0))[0])
    def distance(left, right):
        return 0 if left == right else 256
    def observe():
        return tracker.observe(crops, {}, read, digest, distance)

    assert observe() is None
    assert tracker.last_emit_reverified is False
    assert observe() is not None
    assert tracker.last_emit_reverified is False
    tracker.suspend()
    assert observe() is None
    assert tracker.last_emit_reverified is False
    assert observe() is not None
    assert tracker.last_emit_reverified is True
    assert observe() is None
    assert tracker.last_emit_reverified is False


def test_manual_scan_with_pending_confirmation_can_run_but_requires_proven_result(monkeypatch):
    state = server.GameState()
    state.scan_window_open = True
    state.confirmation_pending = True
    state.awaiting_stat_delta = True
    monkeypatch.setattr(server, "game_state", state)
    monkeypatch.setattr(server, "ocr_available", lambda: True)
    monkeypatch.setattr(server, "_run_ocr_scan_manual",
                        lambda: (VALID_IDS, ROWS, True))
    result = asyncio.run(server.ocr_scan())
    assert result["status"] == "detected"
    assert state.ocr_slot_choices == dict(zip(SLOTS, VALID_IDS))


def test_manual_scan_without_verified_capture_never_publishes(monkeypatch):
    state = server.GameState()
    state.scan_window_open = True
    state.ocr_stale = True
    state.confirmation_pending = True
    monkeypatch.setattr(server, "game_state", state)
    monkeypatch.setattr(server, "ocr_available", lambda: True)
    monkeypatch.setattr(server, "_run_ocr_scan_manual",
                        lambda: (VALID_IDS, ROWS, False))
    result = asyncio.run(server.ocr_scan())
    assert result["status"] != "detected"
    assert state.ocr_stale is True
    assert state.ocr_slot_choices is None


def test_alt_s_local_ocr_request_uses_background_thread_without_game_input():
    source = (Path(__file__).resolve().parents[1] / "backend" / "overlay" / "window.py"
              ).read_text(encoding="utf-8")
    assert "VK_S = 0x53" in source
    assert "def _request_manual_scan(self)" in source
    assert '"http://127.0.0.1:' in source
    assert "/api/ocr/scan" in source
    assert "threading.Thread" in source
    assert "GetAsyncKeyState(VK_S)" in source
