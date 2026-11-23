"""F2/#85: injected, independently calibrated layout proof precedes title OCR.

All frames, card counts and identities below are synthetic. This suite does
not enable a visual producer or claim native three/four-card recognition.
"""
from itertools import count

from PIL import Image

from backend.collectors import screen_ocr
from backend.collectors.league_window import LeagueWindow
from backend.collectors.offer_card_count import CardCountEvidence
from backend.collectors.window_capture import CaptureProof


RECT = (8, 31, 2552, 1384)
MATCH_ID = "synthetic-match"
NAMES = {"one": "One", "two": "Two", "three": "Three"}
WINDOW = LeagueWindow(7, *RECT, True)


def setup(monkeypatch, *, card_counts, times=None, calibration="test-reviewed"):
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: WINDOW)
    img = Image.new("RGB", (int(2544 * .70), int(1353 * .28)), (12, 12, 12))
    ids = iter(times if times is not None else count(10))
    observed = []
    def capture(*_args, **_kwargs):
        t = next(ids)
        observed.append(t)
        return screen_ocr.RegionCapture(
            img, CaptureProof("wgc", WINDOW.hwnd, RECT, float(t), "league"), "ok",
        )
    monkeypatch.setattr(screen_ocr, "capture_augment_region", capture)
    calls = []
    from backend.collectors import slot_title_ocr

    def read(slot, _image, _names):
        calls.append(slot)
        ids = {"left": "one", "centre": "two", "right": "three"}
        return ids[slot], ids[slot].title(), 99
    monkeypatch.setattr(slot_title_ocr, "recognize_title_slot", read)
    monkeypatch.setattr(screen_ocr, "_perceptual_hash", lambda _: "0" * 256)
    values = iter(card_counts)

    def visual_observer(_img, game, proof, match_id, offer_epoch):
        c = next(values)
        return CardCountEvidence(
            match_id=match_id, offer_epoch=offer_epoch,
            window_key=(game.hwnd, game.rect), captured_at=proof.captured_at,
            frame_id=f"fresh-{proof.captured_at:g}", card_count=c,
            source="calibrated_client_visual", calibration_id=calibration,
            verified=True,
        )
    watcher = screen_ocr.ScreenWatcher(
        card_count_observer=visual_observer,
        approved_card_count_calibration=calibration,
        sleep_fn=lambda _: None,
    )
    return watcher, calls, observed


def check(watcher, **kwargs):
    return watcher.check(NAMES, match_id=MATCH_ID, offer_epoch=4, **kwargs)


def test_verified_four_card_source_blocks_all_legacy_three_title_reads(monkeypatch):
    watcher, reads, captures = setup(monkeypatch, card_counts=[4])
    assert check(watcher) == ("transition", None)
    assert watcher.last_scan_stage == "layout_four_unsupported"
    assert watcher.last_detected == []
    assert reads == []
    assert len(captures) == 1


def test_three_card_count_requires_two_distinct_frames_before_title_reader(monkeypatch):
    watcher, reads, captures = setup(monkeypatch, card_counts=[3, 3, 3])
    assert check(watcher) == ("transition", None)
    assert reads == []
    action, names = check(watcher)
    assert action == "detected"
    assert names is not None
    assert [m[0] for m in names] == ["one", "two", "three"]
    assert len(captures) == 3
    assert reads == ["left", "centre", "right"] * 2


def test_second_burst_frame_four_card_rejects_first_frame_ocr(monkeypatch):
    watcher, reads, captures = setup(monkeypatch, card_counts=[3, 3, 4])
    assert check(watcher) == ("transition", None)
    assert check(watcher) == ("transition", None)
    assert watcher.last_scan_stage == "layout_four_unsupported"
    assert watcher.last_detected == []
    assert watcher.current_slots is None
    assert reads == ["left", "centre", "right"]
    assert len(captures) == 3


def test_unknown_layout_must_abstain_and_never_attempt_recognition(monkeypatch):
    watcher, reads, _ = setup(monkeypatch, card_counts=[None, 5, 4])
    for stage in ("layout_unverified", "layout_unverified",
                  "layout_four_unsupported"):
        assert check(watcher) == ("transition", None)
        assert watcher.last_scan_stage == stage
    assert reads == []


def test_no_match_epoch_scope_cannot_promote_count_evidence(monkeypatch):
    watcher, reads, _ = setup(monkeypatch, card_counts=[3])
    assert watcher.check(NAMES) == ("transition", None)
    assert watcher.last_scan_stage == "layout_unverified"
    assert not reads


def test_duplicate_capture_restarts_layout_proof_not_temporal_ocr(monkeypatch):
    watcher, reads, _ = setup(
        monkeypatch, card_counts=[3, 3, 3], times=[10, 10, 11],
    )
    assert check(watcher) == ("transition", None)
    assert check(watcher) == ("transition", None)
    assert check(watcher) == ("transition", None)
    assert reads == []


def test_unapproved_calibration_does_not_accept_three_cards(monkeypatch):
    watcher, reads, _ = setup(monkeypatch, card_counts=[3, 3])
    watcher._card_count_gate._approved = None
    assert check(watcher) == ("transition", None)
    assert check(watcher) == ("transition", None)
    assert reads == []
