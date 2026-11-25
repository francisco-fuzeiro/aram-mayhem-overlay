"""M5/C3 RED: temporal per-slot OCR contract with synthetic, privacy-safe frames.

Only observed League title names documented for C2 are used as examples;
colour-coded frames and changed augment IDs below are synthetic, not game samples.
"""
from collections import Counter

from PIL import Image

from backend.collectors.slot_temporal import SlotTemporalTracker
from backend.collectors.slot_title_ocr import SLOTS, SlotMatches


TITLES = {
    10: ("en", "En Passant", 98),
    11: ("new_left", "Synthetic Left Replacement", 96),
    12: ("next_left", "Synthetic Second Left Replacement", 97),
    20: ("bind", "Ravenous Bind", 99),
    21: ("new_centre", "Synthetic Centre Replacement", 95),
    30: ("kill", "It's Killing Time", 99),
    31: ("new_right", "Synthetic Right Replacement", 97),
}
READS = Counter()


def frame(left=10, centre=20, right=30):
    return {
        slot: Image.new("RGB", (340, 90), (code, code, code))
        for slot, code in zip(SLOTS, (left, centre, right))
    }


def hash_image(crop):
    return str(crop.getpixel((0, 0))[0])


def distance(a, b):
    return 0 if a == b else 256


def read_slot(slot, crop, _names):
    READS[slot] += 1
    return TITLES.get(crop.getpixel((0, 0))[0])


def observe(tracker, left=10, centre=20, right=30):
    return tracker.observe(frame(left, centre, right), {}, read_slot, hash_image, distance)


def assert_ids(matches, ids):
    assert isinstance(matches, SlotMatches)
    assert [matches.slots[slot][0] if matches.slots[slot] else None for slot in SLOTS] == ids


def baseline():
    READS.clear()
    tracker = SlotTemporalTracker()
    assert observe(tracker) is None, "One scan must not publish unconfirmed OCR"
    assert_ids(observe(tracker), ["en", "bind", "kill"])
    assert tracker.snapshot().slots["centre"][0] == "bind"
    return tracker


def test_first_three_cards_need_two_consistent_reads():
    baseline()
    assert READS == Counter({"left": 2, "centre": 2, "right": 2})


def test_single_left_reroll_preserves_centre_right_and_skips_unchanged_ocr():
    t = baseline()
    assert observe(t, left=11) is None
    assert_ids(t.snapshot(), ["en", "bind", "kill"])
    assert_ids(observe(t, left=11), ["new_left", "bind", "kill"])
    assert READS == Counter({"left": 4, "centre": 2, "right": 2})
    assert observe(t, left=11) is None


def test_single_centre_reroll():
    t = baseline()
    assert observe(t, centre=21) is None
    assert_ids(observe(t, centre=21), ["en", "new_centre", "kill"])
    assert READS["left"] == READS["right"] == 2


def test_single_right_reroll():
    t = baseline()
    assert observe(t, right=31) is None
    assert_ids(observe(t, right=31), ["en", "bind", "new_right"])
    assert READS["left"] == READS["centre"] == 2


def test_two_consecutive_rerolls_on_same_left_card():
    t = baseline()
    assert observe(t, left=11) is None
    assert_ids(observe(t, left=11), ["new_left", "bind", "kill"])
    assert observe(t, left=12) is None
    assert_ids(observe(t, left=12), ["next_left", "bind", "kill"])
    assert READS == Counter({"left": 6, "centre": 2, "right": 2})


def test_unreadable_rerolled_slot_becomes_unknown_no_old_id_fallback():
    t = baseline()
    assert observe(t, left=90) is None
    assert_ids(observe(t, left=90), [None, "bind", "kill"])
    assert t.snapshot().slots["left"] is None
    assert observe(t, left=90) is None


def test_single_transition_frame_does_not_replace_stable_card():
    t = baseline()
    assert observe(t, left=90) is None
    assert observe(t) is None
    assert_ids(t.snapshot(), ["en", "bind", "kill"])
    assert READS["centre"] == READS["right"] == 2


def test_two_distinct_animation_frames_do_not_count_as_consistent():
    t = baseline()
    assert observe(t, left=11) is None
    assert observe(t, left=90) is None
    assert_ids(t.snapshot(), ["en", "bind", "kill"])
    assert_ids(observe(t, left=90), [None, "bind", "kill"])


def test_one_off_ocr_failure_without_hash_change_cannot_erase_identity():
    t = baseline()
    before = READS.copy()
    assert observe(t) is None
    assert t.snapshot().slots["left"][0] == "en"
    assert READS == before


def test_focus_loss_clears_temporal_candidates_but_preserves_stale_observations():
    t = baseline()
    assert observe(t, left=11) is None
    t.suspend()
    assert_ids(t.snapshot(), ["en", "bind", "kill"])
    # Refocus needs two fresh independent reads, even if old frame looks identical.
    assert observe(t, left=11) is None
    assert_ids(observe(t, left=11), ["new_left", "bind", "kill"])


def test_focus_return_same_cards_is_not_falsely_a_reroll():
    t = baseline()
    t.suspend()
    assert observe(t) is None
    # Same identities are republished once as a fresh, non-reroll refocus
    # verification so the backend can clear its stale-focus flag.
    assert_ids(observe(t), ["en", "bind", "kill"])
    assert_ids(t.snapshot(), ["en", "bind", "kill"])
    assert READS == Counter({"left": 4, "centre": 4, "right": 4})


def test_duplicate_candidate_cannot_overwrite_stable_other_slot():
    t = baseline()
    assert observe(t, left=20) is None
    assert_ids(observe(t, left=20), [None, "bind", "kill"])


def test_initial_all_unknown_does_not_claim_offer_detected():
    t = SlotTemporalTracker()
    assert observe(t, 90, 90, 90) is None
    assert observe(t, 90, 90, 90) is None
    assert t.snapshot() is None
    assert observe(t, 10, 20, 30) is None
    assert_ids(observe(t, 10, 20, 30), ["en", "bind", "kill"])


def test_reset_makes_next_offer_require_two_new_readings():
    t = baseline()
    t.reset()
    assert t.snapshot() is None
    assert observe(t) is None
    assert_ids(observe(t), ["en", "bind", "kill"])


def test_manual_and_automatic_scans_share_timeline_without_single_read_bypass(monkeypatch):
    from backend.collectors import screen_ocr
    from backend.collectors.league_window import LeagueWindow
    from backend.api import server

    window = LeagueWindow(7, 8, 31, 2552, 1384, True)
    state = {"left": 10}
    tracker = screen_ocr.ScreenWatcher(sleep_fn=lambda _: None)
    monkeypatch.setattr(screen_ocr, "watcher", tracker)
    monkeypatch.setattr(server, "screen_watcher", tracker)
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: window)
    from backend.collectors.window_capture import CaptureProof
    from itertools import count
    times = count(10)
    monkeypatch.setattr(screen_ocr, "capture_augment_region", lambda *_a, **_k:
                        screen_ocr.RegionCapture(
                            "focused synthetic", CaptureProof(
                                "wgc", window.hwnd, window.rect, float(next(times)), "league",
                            ), "ok"))
    monkeypatch.setattr(screen_ocr, "crop_title_slots",
                        lambda *_a: frame(state["left"]))
    monkeypatch.setattr(screen_ocr, "_perceptual_hash", hash_image)
    monkeypatch.setattr(screen_ocr, "_hamming_distance", distance)
    from backend.collectors import slot_title_ocr
    monkeypatch.setattr(slot_title_ocr, "recognize_title_slot", read_slot)
    READS.clear()

    # Manual and automatic calls share the same serialized temporal gate.
    # Each may complete two independently proven readings within one tick.
    assert [m[0] for m in screen_ocr.detect_augments({})] == ["en", "bind", "kill"]
    action, ids, rows = server._run_watcher_check()
    assert action == "unchanged"
    assert ids == [] and rows is None

    state["left"] = 11
    action, ids, rows = server._run_watcher_check()
    assert action == "detected"
    assert ids == ["new_left", "bind", "kill"]
    assert [row["id"] for row in rows] == ids
    assert [m[0] for m in screen_ocr.detect_augments({})] == [
        "new_left", "bind", "kill",
    ]
    assert READS == Counter({"left": 4, "centre": 2, "right": 2})


def test_watcher_occlusion_resets_pending_and_refocus_requires_fresh_confirmation(monkeypatch):
    from backend.collectors import screen_ocr
    from backend.collectors.league_window import LeagueWindow
    from backend.collectors.window_capture import CaptureProof

    blocked = {"value": False}
    window = LeagueWindow(7, 8, 31, 2552, 1384, False)
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: window)
    captures = []
    def capture(*_a, **_kw):
        captures.append("attempt")
        if blocked["value"]:
            return screen_ocr.RegionCapture(None, None, "occluded", "other")
        return screen_ocr.RegionCapture(
            "synthetic", CaptureProof(
                "wgc", window.hwnd, window.rect, float(10 + len(captures)), "other",
            ), "ok",
        )
    monkeypatch.setattr(screen_ocr, "capture_augment_region", capture)
    monkeypatch.setattr(screen_ocr, "crop_title_slots", lambda *_a: frame())
    monkeypatch.setattr(screen_ocr, "_perceptual_hash", hash_image)
    monkeypatch.setattr(screen_ocr, "_hamming_distance", distance)
    from backend.collectors import slot_title_ocr
    monkeypatch.setattr(slot_title_ocr, "recognize_title_slot", read_slot)

    t = screen_ocr.ScreenWatcher(sleep_fn=lambda _: None)
    assert t.check({})[0] == "detected"
    blocked["value"] = True
    assert t.check({}) == ("occluded", None)
    assert t.current_slots.slots["centre"][0] == "bind"
    blocked["value"] = False
    action, result = t.check({})
    assert action == "detected"
    assert_ids(result, ["en", "bind", "kill"])
    assert len(captures) == 5



def test_stable_visual_change_with_identical_title_is_not_a_false_reroll():
    t = baseline()
    TITLES[13] = ("en", "En Passant", 98)
    try:
        assert observe(t, left=13) is None
        assert observe(t, left=13) is None
        reads = READS.copy()
        assert observe(t, left=13) is None
        assert READS == reads, "revalidated same-title image must become new hash baseline"
        assert_ids(t.snapshot(), ["en", "bind", "kill"])
    finally:
        del TITLES[13]


def test_interleaved_ocr_failure_and_new_title_needs_two_matching_readings():
    t = baseline()
    calls = 0
    def flickering(slot, crop, names):
        nonlocal calls
        if slot == "left":
            calls += 1
            if calls == 1:
                return None
        return read_slot(slot, crop, names)

    for tick in range(2):
        assert t.observe(frame(11), {}, flickering, hash_image, distance) is None
        assert_ids(t.snapshot(), ["en", "bind", "kill"])
    assert_ids(t.observe(frame(11), {}, flickering, hash_image, distance),
               ["new_left", "bind", "kill"])
    assert calls == 3


def test_unreadable_confirmed_slot_is_retried_without_other_slot_ocr():
    t = baseline()
    assert observe(t, left=90) is None
    assert_ids(observe(t, left=90), [None, "bind", "kill"])
    previous = READS.copy()
    # Tesseract may recover on identical pixels after a temporary failure.
    TITLES[90] = ("recovered", "Synthetic Recovered Title", 95)
    try:
        eventual = None
        for _ in range(10):
            eventual = observe(t, left=90)
            if eventual is not None:
                break
        assert_ids(eventual, ["recovered", "bind", "kill"])
        assert READS["left"] > previous["left"]
        assert READS["centre"] == READS["right"] == 2
    finally:
        del TITLES[90]


def test_actual_slot_hash_sees_glyph_sized_changes_without_whole_strip():
    from PIL import ImageDraw
    from backend.collectors.screen_ocr import _perceptual_hash, _hamming_distance
    from backend.collectors.slot_temporal import CHANGE_THRESHOLD

    def synthetic_title(shift):
        band = Image.new("RGB", (340, 90), (35, 36, 62))
        draw = ImageDraw.Draw(band)
        draw.rectangle((30, 30, 300, 62), fill=(50, 45, 69))
        for x in (42, 81, 133, 184, 236):
            dx = shift if x == 133 else 0
            draw.rectangle((x+dx, 38, x+dx+9, 57), fill=(230, 230, 210))
        return band

    before = _perceptual_hash(synthetic_title(0))
    after = _perceptual_hash(synthetic_title(10))
    assert _hamming_distance(before, after) > CHANGE_THRESHOLD
    assert _hamming_distance(before, before) == 0


def test_two_changed_slots_confirm_independently_without_touching_third():
    t = baseline()
    assert observe(t, left=11, centre=21) is None
    assert_ids(observe(t, left=11, centre=21),
               ["new_left", "new_centre", "kill"])
    assert READS == Counter({"left": 4, "centre": 4, "right": 2})

def _c4b_watcher(monkeypatch, state, *, independent_observer=None, calibration=None):
    """Synthetic focused 2544x1353 window, no actual screen capture."""
    from backend.collectors import screen_ocr, slot_title_ocr
    from backend.collectors.league_window import LeagueWindow

    window = LeagueWindow(7, 8, 31, 2552, 1384, True)
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: window)
    from backend.collectors.window_capture import CaptureProof
    from itertools import count
    times = count(10)
    monkeypatch.setattr(screen_ocr, "capture_augment_region", lambda *_a, **_k:
                        screen_ocr.RegionCapture(
                            "synthetic", CaptureProof(
                                "wgc", window.hwnd, window.rect, float(next(times)), "league",
                            ), "ok",
                        ))
    monkeypatch.setattr(screen_ocr, "crop_title_slots", lambda *_a: frame(
        state["left"], state["centre"], state["right"],
    ))
    monkeypatch.setattr(screen_ocr, "_perceptual_hash", hash_image)
    monkeypatch.setattr(screen_ocr, "_hamming_distance", distance)
    monkeypatch.setattr(slot_title_ocr, "recognize_title_slot", read_slot)
    return screen_ocr.ScreenWatcher(
        independent_observer=independent_observer,
        approved_calibration=calibration,
        sleep_fn=lambda _delay: state.update(state.pop("_after_first", {})),
    )


def test_c4b_first_changed_frame_marks_previous_cards_unverified(monkeypatch):
    state = {"left": 10, "centre": 20, "right": 30}
    watcher = _c4b_watcher(monkeypatch, state)
    assert watcher.check({})[0] == "detected"
    assert watcher.check({}) == ("unchanged", None)
    state["left"] = 11
    state["_after_first"] = {"left": 12}  # unstable new title in second frame
    assert watcher.check({}) == ("transition", None)
    # Historical C3 snapshot remains available, but not publishable as current.
    assert_ids(watcher.current_slots, ["en", "bind", "kill"])
    state["left"] = 11
    status, verified = watcher.check({})
    assert status == "detected"
    assert_ids(verified, ["new_left", "bind", "kill"])


def test_c4b_multiple_pending_slots_must_not_publish_partial_current_offer(monkeypatch):
    state = {"left": 10, "centre": 20, "right": 30}
    watcher = _c4b_watcher(monkeypatch, state)
    assert watcher.check({})[0] == "detected"
    assert watcher.check({}) == ("unchanged", None)
    state["left"], state["centre"] = 11, 21
    state["_after_first"] = {"centre": 90}
    assert watcher.check({})[0] == "transition"  # left verified, centre NOT
    assert_ids(watcher.current_slots, ["new_left", "bind", "kill"])
    state["centre"] = 21
    action, result = watcher.check({})
    assert action == "detected"
    assert_ids(result, ["new_left", "new_centre", "kill"])


def test_c4b_transient_frame_requires_two_fresh_reads_to_restore_visibility(monkeypatch):
    state = {"left": 10, "centre": 20, "right": 30}
    watcher = _c4b_watcher(monkeypatch, state)
    assert watcher.check({})[0] == "detected"
    assert watcher.check({}) == ("unchanged", None)
    state["left"] = 90
    state["_after_first"] = {"left": 10}  # animation reversed within the tick
    assert watcher.check({})[0] == "transition"
    assert watcher._temporal._refresh_required
    action, restored = watcher.check({})
    assert action == "detected"
    assert_ids(restored, ["en", "bind", "kill"])


def test_c4b_uncalibrated_blank_titles_can_never_emit_gone(monkeypatch):
    state = {"left": 10, "centre": 20, "right": 30}
    watcher = _c4b_watcher(monkeypatch, state)
    assert watcher.check({})[0] == "detected"
    assert watcher.check({}) == ("unchanged", None)
    state.update(left=90, centre=90, right=90)
    state["_after_first"] = {"left": 110, "centre": 110, "right": 110}
    actions = [watcher.check({})[0] for _ in range(8)]
    assert "disappeared" not in actions
    assert "transition" in actions


def test_c4b_explicit_synthetic_cue_triggers_only_after_calibrated_streak(monkeypatch):
    from backend.collectors.offer_visibility import IndependentCue
    state = {"left": 10, "centre": 20, "right": 30}
    decision = {"verdict": "unknown"}
    key = (7, (8, 31, 2552, 1384))

    def observer(_image, _window):
        return IndependentCue(decision["verdict"], "fixture-only", key)

    watcher = _c4b_watcher(
        monkeypatch, state, independent_observer=observer,
        calibration="fixture-only",
    )
    assert watcher.check({})[0] == "detected"
    assert watcher.check({}) == ("unchanged", None)
    state.update(left=90, centre=90, right=90)
    state["_after_first"] = {"left": 110, "centre": 110, "right": 110}
    decision["verdict"] = "absent"
    assert watcher.check({})[0] == "transition"
    assert watcher.check({})[0] != "disappeared"
    assert watcher.check({}) == ("disappeared", None)


def test_c4b_calibrated_occlusion_suspends_old_cards_even_if_pixels_stay_same(monkeypatch):
    """Synthetic independent dialogue cue forces fresh C3 re-verification."""
    from backend.collectors.offer_visibility import IndependentCue

    state = {"left": 10, "centre": 20, "right": 30}
    key = (7, (8, 31, 2552, 1384))
    verdict = {"value": "unknown"}

    def observer(_img, _window):
        return IndependentCue(verdict["value"], "fixture-only", key)

    watcher = _c4b_watcher(
        monkeypatch, state, independent_observer=observer,
        calibration="fixture-only",
    )
    assert watcher.check({})[0] == "detected"
    assert watcher.check({}) == ("unchanged", None)

    verdict["value"] = "occluded"
    assert watcher.check({}) == ("transition", None)
    verdict["value"] = "unknown"
    action, verified = watcher.check({})
    assert action == "detected"
    assert_ids(verified, ["en", "bind", "kill"])


def test_c4b_unapproved_occlusion_cannot_override_verified_cards(monkeypatch):
    """No production calibration: an injected cue is ignored, not authoritative."""
    from backend.collectors.offer_visibility import IndependentCue

    state = {"left": 10, "centre": 20, "right": 30}
    key = (7, (8, 31, 2552, 1384))

    def observer(_img, _window):
        return IndependentCue("occluded", "unapproved", key)

    watcher = _c4b_watcher(monkeypatch, state, independent_observer=observer)
    assert watcher.check({})[0] == "detected"
    assert watcher.check({}) == ("unchanged", None)
    assert watcher.check({}) == ("unchanged", None)


def test_animated_card_verifies_on_two_identical_names_despite_moving_hash():
    # Field 23/11 (latency): shimmering Mayhem cards moved the crop hash every
    # read, so the same title read twice never verified (10-30 s waits).
    tracker = SlotTemporalTracker()
    frames = iter(range(1000))

    def moving_hash(_crop):
        return str(next(frames))

    def read(_slot, crop, _names):
        return TITLES.get(crop.getpixel((0, 0))[0])

    assert tracker.observe(frame(), {}, read, moving_hash, distance) is None
    assert_ids(tracker.observe(frame(), {}, read, moving_hash, distance),
               ["en", "bind", "kill"])


def test_unknown_reads_still_need_a_stable_image():
    tracker = SlotTemporalTracker()
    frames = iter(range(1000))
    blank = {slot: Image.new("RGB", (340, 90), (0, 0, 0)) for slot in SLOTS}
    for _ in range(3):
        assert tracker.observe(blank, {}, read_slot, lambda c: str(next(frames)),
                               distance) is None
