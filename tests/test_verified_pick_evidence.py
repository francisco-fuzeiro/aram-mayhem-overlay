"""P0/#86 RED: only genuinely verified source events may confirm Mayhem picks.

Synthetic events only. No Overwolf SDK, League process, network, player
identifiers, user screenshots, real augment titles, or hidden game state.
"""

import pytest

from backend.workflow.offer_ledger import LedgerError, OfferLedger


MATCH = "synthetic-match"
CATALOG = {"101", "102", "103", "201"}
APPROVED = frozenset({"synthetic_fixture"})


def evidence(base_epoch, **changes):
    # Import deliberately deferred to preserve all existing tests in RED CI
    # while the new source-bound contract has not been implemented.
    from backend.workflow.picked_augment import PickedAugmentEvidence

    params = dict(
        match_id=MATCH, offer_id=1, epoch=base_epoch, catalog_id="101",
        source="synthetic_fixture", source_event_id="event-1",
        observed_at=100.0, verified=True,
    )
    params.update(changes)
    return PickedAugmentEvidence(**params)


def expect_error(code, call):
    with pytest.raises(LedgerError) as exc:
        call()
    assert exc.value.code == code


def confirm(ledger, ev, **overrides):
    args = dict(
        current_match_id=MATCH, catalog=CATALOG,
        approved_sources=APPROVED, now=100.5,
    )
    args.update(overrides)
    return ledger.confirm_verified_external(ev, **args)


def test_verified_source_can_confirm_without_ocr_titles_and_is_idempotent():
    ledger = OfferLedger((3, 7, 11, 15))
    offer = ledger.on_level(3)
    ev = evidence(offer.epoch)
    assert offer.state == "due"
    confirmed, applied = confirm(ledger, ev)
    assert confirmed is offer and applied is True
    assert offer.state == "confirmed"
    assert offer.picked_id == "101"
    assert offer.pick_source == "verified_external"
    assert ledger.active_augment_ids() == ["101"]
    again, applied = confirm(ledger, ev)
    assert again is offer and applied is False
    assert ledger.active_augment_ids() == ["101"]
    assert "source_event_id" not in str(ledger.payload())


def test_external_confirmation_requires_actual_approved_verified_fresh_source():
    ledger = OfferLedger((3, 7, 11, 15))
    offer = ledger.on_level(3)
    for ev, code, options in (
        (evidence(offer.epoch), "unapproved_source", {"approved_sources": frozenset()}),
        (evidence(offer.epoch, source="overwolf_gep"), "unapproved_source", {}),
        (evidence(offer.epoch, verified=False), "unverified_source", {}),
        (evidence(offer.epoch, match_id="other"), "match_mismatch", {}),
        (evidence(offer.epoch, epoch=offer.epoch + 1), "stale_epoch", {}),
        (evidence(offer.epoch, catalog_id="missing"), "not_in_catalog", {}),
        (evidence(offer.epoch, observed_at=70.0), "stale_evidence", {}),
        (evidence(offer.epoch, observed_at=101.0), "stale_evidence", {}),
        (evidence(offer.epoch, source_event_id=""), "bad_evidence", {}),
    ):
        expect_error(code, lambda ev=ev, options=options: confirm(ledger, ev, **options))
        assert ledger.active_augment_ids() == []
        assert offer.state == "due"


def test_event_replay_conflict_old_epoch_and_manual_confirmation_are_safe():
    ledger = OfferLedger((3, 7, 11, 15))
    first = ledger.on_level(3)
    ev = evidence(first.epoch)
    confirmed, applied = confirm(ledger, ev)
    assert confirmed is first and applied
    second = ledger.on_level(7)
    assert second.state == "due"
    # A globally unique source event key cannot be reused for another offer.
    replay = evidence(second.epoch, offer_id=2, catalog_id="201")
    expect_error("duplicate_event", lambda: confirm(ledger, replay))
    expect_error("offer_closed", lambda: confirm(
        ledger, evidence(first.epoch, catalog_id="102", source_event_id="event-2"),
    ))
    expect_error("stale_epoch", lambda: confirm(
        ledger, evidence(first.epoch + 1, source_event_id="event-3"),
    ))
    assert second.picked_id is None
    assert ledger.active_augment_ids() == ["101"]

    manual = OfferLedger((3, 7, 11, 15))
    offer = manual.on_level(3)
    manual.on_verified_titles({"left": "102", "centre": None, "right": None}, offer.epoch)
    manual.confirm(1, offer.epoch, "102")
    expect_error("offer_closed", lambda: confirm(manual, evidence(offer.epoch)))
    assert manual.active_augment_ids() == ["102"]


def test_out_of_order_older_offer_can_be_resolved_without_closing_newer_offer():
    ledger = OfferLedger((3, 7, 11, 15))
    first = ledger.on_level(3)
    ledger.on_verified_titles({"left": "101", "centre": "102", "right": "103"}, first.epoch)
    ledger.on_titles_unverified()
    second = ledger.on_level(7)
    before = (second.state, second.epoch, second.picked_id)
    confirmed, applied = confirm(ledger, evidence(first.epoch))
    assert confirmed is first and applied
    assert (second.state, second.epoch, second.picked_id) == before
    assert ledger.active_augment_ids() == ["101"]


@pytest.mark.asyncio
async def test_synthetic_verified_event_flows_to_next_build_pipeline_tick(monkeypatch):
    """The normal polling pipeline consumes only actually confirmed IDs."""
    from types import SimpleNamespace
    from unittest.mock import Mock
    from backend.api import server
    from tests.test_poll_tick_m1 import make_harness, make_snapshot

    state, deps, broadcasts = make_harness(
        [{"tick": 1}], [make_snapshot(level=3)], ocr=False,
    )
    state.match_id = "fallback:1"
    offer = state.offer_ledger.on_level(3)
    state.offer_epoch = offer.epoch
    state.scan_window_open = True
    state.offer_lifecycle.open()
    state.offer_lifecycle.observe("detected", identified=3)
    state.augment_choices[:] = ["101", "102", "103"]
    seen_build_inputs = []
    state.pipeline = SimpleNamespace(
        run=lambda snapshot: (
            seen_build_inputs.append(list(snapshot.chosen_augments)) or object()
        ),
    )
    monkeypatch.setattr(server, "screen_watcher", SimpleNamespace(reset=Mock()))
    deps.serialize_result = lambda *_: {"type": "update"}

    # A synthetic approved provider bypasses missing OCR titles, not proof.
    trusted = evidence(offer.epoch, match_id="fallback:1")
    assert server._apply_approved_pick_evidence(
        state, trusted, catalog=CATALOG,
        approved_sources=APPROVED, now=100.5,
    )
    assert state.chosen_augments == ["101"]
    assert state.scan_window_open is False
    assert state.offer_state == "inactive"
    assert state.augment_choices == []
    accepted_epoch = state.offer_epoch
    assert not server._apply_approved_pick_evidence(
        state, trusted, catalog=CATALOG,
        approved_sources=APPROVED, now=100.5,
    )
    assert state.offer_epoch == accepted_epoch
    await server.poll_tick(state, deps, 101.0)
    assert seen_build_inputs == [["101"]]
    assert any(
        row.get("type") == "update"
        and row.get("offers", [{}])[0].get("pick_source") == "verified_external"
        for row in broadcasts
    )


def test_provider_disabled_by_default_even_for_marked_verified_events():
    from backend.api import server

    state = server.GameState()
    state.match_id = MATCH
    offer = state.offer_ledger.on_level(3)
    event = evidence(offer.epoch)
    expect_error("unapproved_source", lambda: server._apply_approved_pick_evidence(
        state, event, catalog=CATALOG, now=100.5,
    ))
    assert state.offer_ledger.active_augment_ids() == []
    assert state.chosen_augments == []
    assert state.augment_choices == []

