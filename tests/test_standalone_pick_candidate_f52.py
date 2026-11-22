"""F5.2 RED — passive standalone card-click/visual-closure candidate gate.

No Windows hooks, screenshots, game client, Overwolf bridge, League actions,
real augment names, player IDs or privileged data. Candidate != confirmed pick.
"""
import pytest

from backend.collectors.offer_visibility import IndependentCue
from backend.collectors.standalone_pick_candidate import (
    CalibratedCardLayout, ClickObservation, StandalonePickCandidateGate,
)
from backend.workflow.offer_ledger import OfferLedger, LedgerError


KEY = (123, (0, 0, 320, 180))
ALT = (124, (0, 0, 320, 180))
SLOTS = {"left": "101", "centre": "102", "right": "103"}
LAYOUT = CalibratedCardLayout(
    key=KEY, calibration_id="synthetic-reviewed-v1",
    rects={
        "left": (20, 20, 70, 110),
        "centre": (125, 20, 70, 110),
        "right": (230, 20, 70, 110),
    },
)


def gate(*, calibrated=True, click_source=True):
    return StandalonePickCandidateGate(
        approved_calibration=LAYOUT.calibration_id if calibrated else None,
        approved_click_source="synthetic-mouse" if click_source else None,
    )


def begin(tracker, *, layout=LAYOUT, slots=SLOTS, match="synthetic-match",
          offer_id=1, epoch=7, captured=True):
    return tracker.begin(
        match_id=match, offer_id=offer_id, epoch=epoch, key=KEY,
        layout=layout, verified_slots=slots, capture_proven=captured,
        at=100.0,
    )


def click(tracker, *, point=(160, 70), key=KEY, at=100.25,
          down=True, foreground=True, event_id="click-1", source="synthetic-mouse"):
    return tracker.observe_click(ClickObservation(
        key=key, client_point=point, at=at, source=source,
        event_id=event_id, left_button_down_edge=down,
        league_foreground=foreground,
    ))


def cue(verdict, *, key=KEY, calibration="synthetic-reviewed-v1"):
    return IndependentCue(verdict, calibration, key)


def absent(tracker, stamps=(100.50, 100.80, 101.10)):
    return [tracker.observe_visual(cue("absent"), at=t) for t in stamps]


def test_candidate_needs_c3_offer_click_and_three_independent_absence_reads():
    tracker = gate()
    assert begin(tracker)
    assert click(tracker)
    assert tracker.observe_visual(cue("absent"), at=100.50) is None
    assert tracker.observe_visual(cue("absent"), at=100.80) is None
    candidate = tracker.observe_visual(cue("absent"), at=101.10)
    assert candidate is not None
    assert (candidate.match_id, candidate.offer_id, candidate.epoch) == (
        "synthetic-match", 1, 7,
    )
    assert candidate.catalog_id == "102"
    assert candidate.slot == "centre"
    assert candidate.source == "standalone_visual_candidate"
    assert candidate.verified is False
    assert tracker.observe_visual(cue("absent"), at=101.40) is None

    # Candidate signals must NOT accidentally become selected-augment evidence.
    ledger = OfferLedger((3, 7))
    offer = ledger.on_level(3)
    with pytest.raises(LedgerError) as exc:
        ledger.confirm_verified_external(
            candidate, current_match_id="synthetic-match",
            catalog={"101", "102", "103"},
            approved_sources=frozenset({"standalone_visual_candidate"}),
            now=101.5,
        )
    assert exc.value.code == "bad_evidence"
    assert offer.picked_id is None


def test_no_calibration_or_approved_mouse_source_remains_disabled():
    for tracker in (gate(calibrated=False), gate(click_source=False)):
        assert not begin(tracker) or not click(tracker)
        assert absent(tracker) == [None, None, None]


def test_hover_outside_left_up_unknown_or_cross_window_is_never_a_pick():
    for kw in (
        {"down": False}, {"point": (5, 5)}, {"key": ALT},
        {"foreground": False}, {"source": "unknown"},
    ):
        tracker = gate()
        assert begin(tracker)
        assert not click(tracker, **kw)
        assert absent(tracker) == [None, None, None]


def test_ambiguous_or_incomplete_geometry_or_unverified_ocr_abstains():
    for rects, slots, captured in (
        (
            {"left": (20, 20, 120, 110),
             "centre": (100, 20, 100, 110),
             "right": (230, 20, 70, 110)}, SLOTS, True,
        ),
        ({"left": (20, 20, 70, 110)}, SLOTS, True),
        (LAYOUT.rects, {"left": "101", "centre": None, "right": "103"}, True),
        (LAYOUT.rects, SLOTS, False),
        (LAYOUT.rects, {"left": "101", "centre": "101", "right": "103"}, True),
    ):
        tracker = gate()
        layout = CalibratedCardLayout(KEY, LAYOUT.calibration_id, rects)
        assert not begin(tracker, layout=layout, slots=slots, captured=captured)
        assert not click(tracker)
        assert absent(tracker) == [None, None, None]


def test_two_different_card_clicks_in_one_offer_are_ambiguous_and_fatal():
    tracker = gate()
    assert begin(tracker)
    assert click(tracker, point=(55, 70), event_id="click-1")
    assert not click(tracker, point=(160, 70), event_id="click-2", at=100.32)
    assert absent(tracker) == [None, None, None]
    assert not click(tracker, point=(55, 70), event_id="click-3", at=101.25)


def test_missing_freshness_or_repeated_visual_frame_cannot_fake_three_absences():
    tracker = gate()
    assert begin(tracker)
    assert click(tracker)
    assert tracker.observe_visual(cue("absent"), at=100.50) is None
    assert tracker.observe_visual(cue("absent"), at=100.50) is None
    assert tracker.observe_visual(cue("absent"), at=100.70) is None
    assert tracker.observe_visual(cue("absent"), at=100.90) is None
    assert tracker.observe_visual(cue("absent"), at=111.0) is None
    # The earlier click has expired and cannot be revived by more misses.
    assert tracker.observe_visual(cue("absent"), at=111.25) is None


def test_occlusion_unknown_or_changed_window_invalidates_any_click():
    for negative in (cue("occluded"), cue("unknown"), cue("absent", key=ALT)):
        tracker = gate()
        assert begin(tracker)
        assert click(tracker)
        assert tracker.observe_visual(negative, at=100.5) is None
        assert absent(tracker, stamps=(100.8, 101.1, 101.4)) == [None, None, None]


def test_new_match_epoch_or_offer_discards_previous_click_and_old_absence():
    tracker = gate()
    assert begin(tracker)
    assert click(tracker)
    assert begin(tracker, match="synthetic-match-two", epoch=9, offer_id=2)
    assert absent(tracker) == [None, None, None]
    assert click(tracker, event_id="fresh", at=100.3)
    candidate = absent(tracker)[-1]
    assert candidate is not None
    assert (candidate.match_id, candidate.offer_id, candidate.epoch) == (
        "synthetic-match-two", 2, 9,
    )


def test_four_card_layout_is_not_inferred_from_three_card_calibration():
    tracker = gate()
    slots = dict(SLOTS, fourth="104")
    assert not begin(tracker, slots=slots)
    assert not click(tracker)
    assert absent(tracker) == [None, None, None]
