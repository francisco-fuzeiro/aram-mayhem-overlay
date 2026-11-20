"""A4 v3: independently proven captures inside one serialized OCR tick.

All pixels, titles, and clocks are synthetic. These tests never open League.
"""
from __future__ import annotations

from collections import Counter

from PIL import Image

from backend.collectors import screen_ocr, slot_title_ocr
from backend.collectors.league_window import LeagueWindow
from backend.collectors.window_capture import CaptureProof

GAME = LeagueWindow(77, -1200, 40, -240, 580, False)
TITLES = {
    "left": {10: ("a", "Synthetic A", 98), 40: ("b", "Synthetic B", 99)},
    "centre": {20: ("c", "Synthetic C", 97)},
    "right": {30: ("d", "Synthetic D", 96)},
}


def verified(codes=(10, 20, 30), timestamp=10.0, *, proof=True,
             reason="ok", window=GAME):
    if reason != "ok":
        return screen_ocr.RegionCapture(None, None, reason)
    image = Image.new("RGB", (4, 4), codes)
    token = (
        CaptureProof("wgc", window.hwnd, window.rect, timestamp, "other")
        if proof else None
    )
    return screen_ocr.RegionCapture(image, token, "ok")


def setup(monkeypatch, frames, *, independent_observer=None, calibration=None):
    """Record every capture/slot/OCR/sleep without using an actual device."""
    queue = list(frames)
    captures = []
    delays = []
    reads = Counter()

    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: GAME)

    def capture(*_args, **_kwargs):
        captures.append(len(captures) + 1)
        assert queue, "Unexpected third read in one tick"
        return queue.pop(0)

    monkeypatch.setattr(screen_ocr, "capture_augment_region", capture)
    monkeypatch.setattr(screen_ocr, "crop_title_slots", lambda image, *_: {
        slot: Image.new("RGB", (340, 90), (value, value, value))
        for slot, value in zip(("left", "centre", "right"),
                               image.getpixel((0, 0)))
    })
    monkeypatch.setattr(screen_ocr, "_perceptual_hash",
                        lambda image: str(image.getpixel((0, 0))[0]))
    monkeypatch.setattr(screen_ocr, "_hamming_distance",
                        lambda a, b: abs(int(a) - int(b)))

    def read(slot, image, _names):
        reads[slot] += 1
        return TITLES[slot].get(image.getpixel((0, 0))[0])

    monkeypatch.setattr(slot_title_ocr, "recognize_title_slot", read)
    watcher = screen_ocr.ScreenWatcher(
        sleep_fn=delays.append,
        independent_observer=independent_observer,
        approved_calibration=calibration,
    )
    return watcher, captures, delays, reads


def ids(matches):
    assert isinstance(matches, slot_title_ocr.SlotMatches)
    return [matches.slots[slot][0] if matches.slots[slot] else None
            for slot in ("left", "centre", "right")]


def test_two_valid_independent_reads_publish_all_three_slots_in_first_tick(monkeypatch):
    watcher, captures, delays, reads = setup(
        monkeypatch, [verified(timestamp=10.0), verified(timestamp=10.6)]
    )
    action, result = watcher.check({})
    assert action == "detected"
    assert ids(result) == ["a", "c", "d"]
    assert captures == [1, 2]
    assert delays == [screen_ocr.BURST_SECOND_READ_DELAY_S]
    assert delays == [0.5]
    assert reads == Counter({"left": 2, "centre": 2, "right": 2})
    assert not watcher._temporal.has_pending


def test_second_capture_occlusion_suspends_and_clears_pending(monkeypatch):
    watcher, captures, delays, _reads = setup(
        monkeypatch, [
            verified(timestamp=10.0), verified(reason="occluded"),
            verified(timestamp=11.0), verified(timestamp=11.6),
        ]
    )
    assert watcher.check({}) == ("occluded", None)
    assert watcher.last_scan_stage == "game_occluded"
    assert not watcher._temporal.has_pending
    # First frame of next tick must NOT be accepted against the old pending A.
    # Only two NEW verified readings of the three slots may publish.
    action, result = watcher.check({})
    assert action == "detected"
    assert ids(result) == ["a", "c", "d"]
    assert captures == [1, 2, 3, 4]
    assert delays == [0.5, 0.5]


def test_disagreeing_second_read_replaces_pending_without_publishing(monkeypatch):
    watcher, captures, delays, reads = setup(
        monkeypatch, [verified(timestamp=10.0), verified((40, 20, 30), 10.6)]
    )
    # Stable neighbours can be verified internally, but a changed left
    # slot stays pending and the complete offer cannot be published.
    assert watcher.check({}) == ("transition", None)
    assert watcher.current_slots.slots["left"] is None
    assert watcher._temporal.has_pending
    assert reads == Counter({"left": 2, "centre": 2, "right": 2})
    assert captures == [1, 2]
    assert delays == [0.5]


def test_no_pending_after_first_read_means_no_second_capture_or_sleep(monkeypatch):
    watcher, captures, delays, reads = setup(
        monkeypatch, [
            verified(timestamp=10.0), verified(timestamp=10.6),
            verified(timestamp=11.2),
        ]
    )
    assert watcher.check({})[0] == "detected"
    assert watcher.check({}) == ("unchanged", None)
    assert captures == [1, 2, 3]
    assert delays == [0.5]
    assert reads == Counter({"left": 2, "centre": 2, "right": 2})


def test_invalid_second_capture_fails_closed_no_old_snapshot(monkeypatch):
    watcher, captures, delays, reads = setup(
        monkeypatch, [verified(timestamp=10.0), verified(reason="invalid_frame")]
    )
    assert watcher.check({}) == ("capture_unavailable", None)
    assert watcher.last_scan_stage == "capture_invalid"
    assert not watcher._temporal.has_pending
    assert watcher.current_slots is None
    assert reads == Counter({"left": 1, "centre": 1, "right": 1})
    assert captures == [1, 2]
    assert delays == [0.5]


def test_second_capture_without_proof_is_rejected_before_any_ocr(monkeypatch):
    watcher, captures, _delays, reads = setup(
        monkeypatch, [verified(timestamp=10.0), verified(timestamp=10.6, proof=False)]
    )
    assert watcher.check({}) == ("capture_unavailable", None)
    assert not watcher._temporal.has_pending
    assert reads == Counter({"left": 1, "centre": 1, "right": 1})
    assert captures == [1, 2]


def test_reused_capture_timestamp_is_not_a_fresh_second_frame(monkeypatch):
    watcher, captures, _delays, reads = setup(
        monkeypatch, [verified(timestamp=10.0), verified(timestamp=10.0)]
    )
    assert watcher.check({}) == ("capture_unavailable", None)
    assert not watcher._temporal.has_pending
    assert reads == Counter({"left": 1, "centre": 1, "right": 1})
    assert captures == [1, 2]


def test_other_window_proof_cannot_confirm_pending_slots(monkeypatch):
    other = LeagueWindow(78, -1200, 40, -240, 580, False)
    watcher, _captures, _delays, reads = setup(
        monkeypatch, [verified(timestamp=10.0),
                      verified(timestamp=10.6, window=other)]
    )
    assert watcher.check({}) == ("capture_unavailable", None)
    assert not watcher._temporal.has_pending
    assert reads == Counter({"left": 1, "centre": 1, "right": 1})


def test_direct_temporal_pending_is_read_only():
    from backend.collectors.slot_temporal import SlotTemporalTracker
    tracker = SlotTemporalTracker()
    assert tracker.has_pending is False
    assert tracker.has_pending == tracker.has_unverified_changes


def test_second_capture_window_change_discards_pending(monkeypatch):
    watcher, captures, delays, reads = setup(
        monkeypatch, [verified(timestamp=10.0), verified(reason="window_changed")]
    )
    assert watcher.check({}) == ("capture_unavailable", None)
    assert not watcher._temporal.has_pending
    assert watcher.current_slots is None
    assert reads == Counter({"left": 1, "centre": 1, "right": 1})
    assert captures == [1, 2]
    assert delays == [0.5]


def test_calibrated_first_frame_occlusion_blocks_even_a_proven_burst(monkeypatch):
    from backend.collectors.offer_visibility import IndependentCue

    key = (GAME.hwnd, GAME.rect)
    def observer(_image, _window):
        return IndependentCue("occluded", "a4-synthetic", key)

    watcher, captures, delays, reads = setup(
        monkeypatch, [verified(timestamp=10.0), verified(timestamp=10.6)],
        independent_observer=observer, calibration="a4-synthetic",
    )
    assert watcher.check({}) == ("transition", None)
    assert watcher.last_scan_stage == "titles_transition"
    assert watcher.current_slots is None
    assert not watcher._temporal.has_pending
    assert captures == [1]
    assert delays == []
    assert reads == Counter()
