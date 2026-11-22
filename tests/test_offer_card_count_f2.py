"""F2/4C-01: card count must be proven independently of three title crops.

Synthetic source-contract tests only. No League capture, OCR text, game input
or private screenshots are used. Native visual calibration remains open.
"""
from dataclasses import replace

import pytest

from backend.collectors.offer_card_count import CardCountEvidence, OfferCardCountGate
from backend.collectors.window_capture import CaptureProof


MATCH = "synthetic-match"
RECT = (0, 0, 1920, 1080)
KEY = (19, RECT)


def proof(t=10.0, *, foreground="league", hwnd=19, rect=RECT):
    return CaptureProof("wgc", hwnd, rect, t, foreground)


def evidence(t=10.0, *, count=3, frame_id="frame-a", epoch=4,
             calibration="reviewed-v1", source="calibrated_client_visual",
             match=MATCH, verified=True):
    return CardCountEvidence(
        match_id=match, offer_epoch=epoch, window_key=KEY,
        captured_at=t, frame_id=frame_id, card_count=count,
        source=source, calibration_id=calibration, verified=verified,
    )


def observe(gate, item, p=None, *, match=MATCH, epoch=4):
    return gate.observe(item, proof(item.captured_at) if p is None else p,
                        match_id=match, offer_epoch=epoch)


def test_no_reviewed_visual_source_means_unknown_not_three():
    gate = OfferCardCountGate()
    assert observe(gate, evidence()) == "unknown"
    assert observe(gate, evidence(11, frame_id="frame-b")) == "unknown"


def test_only_two_independent_three_card_frames_can_enable_three_slot_ocr():
    gate = OfferCardCountGate(approved_calibration="reviewed-v1")
    assert observe(gate, evidence()) == "unknown"
    # Replaying the first capture clears the count streak; it must not
    # count toward the two distinct post-replay observations.
    assert observe(gate, evidence(10.0, frame_id="frame-a")) == "unknown"
    assert observe(gate, evidence(10.5, frame_id="frame-b")) == "unknown"
    assert observe(gate, evidence(10.6, frame_id="frame-c")) == "three_verified"


def test_any_verified_four_card_observation_immediately_blocks_three_slot_mapping():
    gate = OfferCardCountGate(approved_calibration="reviewed-v1")
    assert observe(gate, evidence()) == "unknown"
    assert observe(gate, evidence(10.5, frame_id="frame-b")) == "three_verified"
    assert observe(gate, evidence(11, count=4, frame_id="frame-c")) == "four_unsupported"
    assert observe(gate, evidence(11.5, frame_id="frame-d")) == "unknown"
    assert observe(gate, evidence(12, frame_id="frame-e")) == "three_verified"


@pytest.mark.parametrize("count", [None, 0, 1, 2, 5, -1, True, "3", 3.0])
def test_unknown_and_malformed_card_counts_always_abstain(count):
    gate = OfferCardCountGate(approved_calibration="reviewed-v1")
    assert observe(gate, evidence(count=count)) == "unknown"
    assert observe(gate, evidence(10.5, frame_id="frame-b")) == "unknown"


@pytest.mark.parametrize("changes", [
    {"verified": False},
    {"source": "title_ocr"},
    {"source": "three_title_crops"},
    {"calibration": "unapproved"},
    {"frame_id": ""},
    {"frame_id": "../private/capture"},
    {"epoch": 5},
    {"match": "other-match"},
])
def test_unapproved_stale_or_non_independent_evidence_rejected(changes):
    gate = OfferCardCountGate(approved_calibration="reviewed-v1")
    assert observe(gate, evidence(**changes)) == "unknown"


def test_invalid_capture_or_focus_cannot_reuse_prior_three_card_verdict():
    gate = OfferCardCountGate(approved_calibration="reviewed-v1")
    assert observe(gate, evidence()) == "unknown"
    assert observe(gate, evidence(10.5, frame_id="frame-b")) == "three_verified"
    assert observe(gate, evidence(11, frame_id="frame-c"),
                   proof(11, foreground="other")) == "unknown"
    assert observe(gate, evidence(11.5, frame_id="frame-d")) == "unknown"
    assert observe(gate, evidence(12, frame_id="frame-e")) == "three_verified"
    assert observe(gate, evidence(12.5, frame_id="frame-f"),
                   proof(12.5, hwnd=99)) == "unknown"


def test_stale_capture_time_replay_and_epoch_transition_clear_count_proof():
    gate = OfferCardCountGate(approved_calibration="reviewed-v1")
    assert observe(gate, evidence()) == "unknown"
    assert observe(gate, evidence(10.5, frame_id="frame-b")) == "three_verified"
    assert observe(gate, evidence(11, frame_id="frame-c"),
                   proof(11.1)) == "unknown"
    assert observe(gate, evidence(11.5, frame_id="frame-d")) == "unknown"
    assert observe(gate, evidence(12, frame_id="frame-e")) == "three_verified"
    assert observe(gate, evidence(12.5, frame_id="frame-f", epoch=5),
                   epoch=5) == "unknown"
    assert observe(gate, evidence(13, frame_id="frame-g", epoch=5),
                   epoch=5) == "three_verified"
    assert observe(gate, evidence(13, frame_id="frame-g", epoch=5),
                   epoch=5) == "unknown"


def test_ambiguous_occluded_transition_breaks_existing_three_card_count():
    gate = OfferCardCountGate(approved_calibration="reviewed-v1")
    assert observe(gate, evidence()) == "unknown"
    assert observe(gate, evidence(10.5, frame_id="frame-b")) == "three_verified"
    assert observe(gate, evidence(11, frame_id="frame-c", count=None)) == "unknown"
    assert observe(gate, evidence(11.5, frame_id="frame-d")) == "unknown"
