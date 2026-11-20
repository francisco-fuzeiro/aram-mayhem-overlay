"""C2 RED: offer identity, candidate and explicit confirmation must be distinct."""

import pytest

from backend.workflow.offer_ledger import LedgerError, OfferLedger


@pytest.fixture
def ledger():
    return OfferLedger((3, 7, 11, 15))


def expect_error(code, callback):
    with pytest.raises(LedgerError) as caught:
        callback()
    assert caught.value.code == code


def test_level_due_has_no_confirmed_pick_or_visible_cards(ledger):
    assert ledger.on_level(2) is None
    first = ledger.on_level(3)
    assert first.offer_id == 1
    assert first.level == 3
    assert first.state == "due"
    assert all(value.augment_id is None for value in first.slots.values())
    assert ledger.active_augment_ids() == []
    assert ledger.scanning_needed()
    assert ledger.on_level(3) is first


def test_verified_titles_are_identity_not_confirmation(ledger):
    first = ledger.on_level(3)
    ledger.on_verified_titles({"left": "101", "centre": "102", "right": "103"}, first.epoch)
    assert first.state == "visible"
    assert first.slots["left"].source == "ocr"
    assert first.slots["left"].verified_at_epoch == first.epoch
    assert first.picked_id is None
    assert ledger.active_augment_ids() == []
    ledger.on_titles_unverified()
    assert first.state == "awaiting_confirm"
    assert first.picked_id is None
    assert ledger.scanning_needed()


def test_manual_identify_only_updates_identity(ledger):
    first = ledger.on_level(3)
    ledger.open_for_recovery(1)
    epoch = first.epoch
    updated = ledger.identify(1, epoch, "right", "103", {"101", "102", "103"})
    assert updated is first
    assert first.slots["right"].source == "user_identify"
    assert first.state == "visible"
    assert first.candidate_id is None
    assert first.picked_id is None
    assert ledger.active_augment_ids() == []


def test_identify_rejects_stale_conflict_unknown_and_closed(ledger):
    first = ledger.on_level(3)
    ledger.open_for_recovery(1)
    epoch = first.epoch
    expect_error("stale_epoch", lambda: ledger.identify(1, epoch - 1, "left", "101", {"101"}))
    expect_error("bad_slot", lambda: ledger.identify(1, epoch, "fourth", "101", {"101"}))
    expect_error("not_in_catalog", lambda: ledger.identify(1, epoch, "left", "999", {"101"}))
    ledger.identify(1, epoch, "left", "101", {"101"})
    expect_error("identity_conflict", lambda: ledger.identify(1, epoch, "centre", "101", {"101"}))
    ledger.confirm(1, epoch, "101")
    expect_error("offer_closed", lambda: ledger.identify(1, epoch, "right", "102", {"102"}))
    expect_error("unknown_offer", lambda: ledger.identify(9, epoch, "right", "102", {"102"}))


def test_verified_ocr_overrides_only_different_manual_identity(ledger):
    first = ledger.on_level(3)
    ledger.open_for_recovery(1)
    ledger.identify(1, first.epoch, "left", "101", {"101", "102"})
    ledger.on_verified_titles({"left": "101", "centre": None, "right": None}, first.epoch)
    assert first.slots["left"].source == "user_identify"
    ledger.on_verified_titles({"left": "102", "centre": None, "right": None}, first.epoch)
    assert first.slots["left"].source == "ocr"
    assert first.slots["left"].augment_id == "102"


def test_confirm_requires_identity_and_matching_offer_epoch(ledger):
    first = ledger.on_level(3)
    ledger.on_verified_titles({"left": "101", "centre": "102", "right": None}, first.epoch)
    expect_error("not_in_offer", lambda: ledger.confirm(1, first.epoch, "999"))
    expect_error("stale_epoch", lambda: ledger.confirm(1, first.epoch + 1, "101"))
    assert first.picked_id is None
    confirmed = ledger.confirm(1, first.epoch, "102")
    assert confirmed.state == "confirmed"
    assert confirmed.picked_id == "102"
    assert confirmed.pick_source == "user_confirm"
    assert ledger.active_augment_ids() == ["102"]


def test_old_offer_confirmation_does_not_modify_new_offer(ledger):
    first = ledger.on_level(3)
    ledger.on_verified_titles({"left": "101", "centre": "102", "right": "103"}, first.epoch)
    ledger.on_titles_unverified()
    second = ledger.on_level(7)
    ledger.on_verified_titles({"left": "201", "centre": "202", "right": "203"}, second.epoch)
    before = (second.epoch, second.state, second.picked_id, second.slots["centre"].augment_id)
    ledger.confirm(1, first.epoch, "101")
    assert (second.epoch, second.state, second.picked_id, second.slots["centre"].augment_id) == before
    assert ledger.active_augment_ids() == ["101"]


def test_hotkey_targets_oldest_awaiting_offer(ledger):
    first = ledger.on_level(3)
    ledger.on_verified_titles({"left": "101", "centre": "102", "right": "103"}, first.epoch)
    ledger.on_titles_unverified()
    second = ledger.on_level(7)
    ledger.on_verified_titles({"left": "201", "centre": "202", "right": "203"}, second.epoch)
    result = ledger.confirm_slot("centre")
    assert result.offer_id == 1
    assert first.picked_id == "102"
    assert second.picked_id is None


def test_candidate_does_not_affect_active_augments(ledger):
    first = ledger.on_level(3)
    ledger.on_verified_titles({"left": "101", "centre": "102", "right": "103"}, first.epoch)
    ledger.set_candidate(1, first.epoch, "right")
    assert first.candidate_id == "103"
    assert first.candidate_source == "click_hint"
    assert first.picked_id is None
    assert ledger.active_augment_ids() == []
    ledger.confirm(1, first.epoch, "101")
    assert first.candidate_id is None


def test_recovery_rejects_old_epoch_and_does_not_confirm(ledger):
    first = ledger.on_level(3)
    old = first.epoch
    ledger.open_for_recovery(1)
    assert first.state == "visible"
    assert first.epoch == old + 1
    assert first.picked_id is None
    expect_error("stale_epoch", lambda: ledger.confirm(1, old, "101"))


def test_closed_offers_stop_scanning(ledger):
    for i, level in enumerate((3, 7, 11, 15)):
        offer = ledger.on_level(level)
        aug_id = str(101 + i)
        ledger.on_verified_titles({"left": aug_id, "centre": None, "right": None}, offer.epoch)
        ledger.confirm(offer.offer_id, offer.epoch, aug_id)
    assert len(ledger.active_augment_ids()) == 4
    assert ledger.scanning_needed() is False


def test_outdated_observation_cannot_overwrite_new_offer(ledger):
    first = ledger.on_level(3)
    ledger.on_verified_titles({"left": "101", "centre": None, "right": None}, first.epoch)
    second = ledger.on_level(7)
    ledger.on_verified_titles({"left": "201", "centre": None, "right": None}, second.epoch)
    prior = second.slots["left"].augment_id
    expect_error("stale_epoch", lambda: ledger.on_verified_titles(
        {"left": "999", "centre": None, "right": None}, first.epoch
    ))
    assert second.slots["left"].augment_id == prior


def test_verified_reroll_identity_cannot_create_unconfirmed_pick(ledger):
    first = ledger.on_level(3)
    ledger.on_verified_titles({"left": "101", "centre": "102", "right": "103"}, first.epoch)
    ledger.on_verified_titles({"left": "104", "centre": "102", "right": "103"}, first.epoch)
    assert first.slots["left"].augment_id == "104"
    assert first.picked_id is None
    expect_error("not_in_offer", lambda: ledger.confirm(1, first.epoch, "101"))
    assert ledger.active_augment_ids() == []


def test_offer_epoch_external_fence_invalidates_stale_confirm(ledger):
    first = ledger.on_level(3)
    ledger.on_verified_titles({"left": "101", "centre": None, "right": None}, first.epoch)
    old_epoch = first.epoch
    ledger.set_current_epoch(old_epoch + 5)
    expect_error("stale_epoch", lambda: ledger.confirm(1, old_epoch, "101"))
    assert first.epoch == old_epoch + 5
    assert ledger.active_augment_ids() == []
    assert ledger.confirm(1, first.epoch, "101").picked_id == "101"


def test_identity_override_event_contains_no_augment_id(monkeypatch, ledger):
    from backend.api import server
    from backend.diagnostic_events import _clean
    events = []
    monkeypatch.setattr(server.event_log, "emit",
                        lambda name, **data: events.append((name, data)))
    offer = ledger.on_level(3)
    ledger.open_for_recovery(1)
    ledger.identify(1, offer.epoch, "left", "101", {"101", "102"})
    server._ledger_verified_titles(
        ledger, {"left": "102", "centre": None, "right": None}, offer.epoch,
    )
    assert events == [("identity_overridden", {
        "slot": "left", "verified_by": "ocr",
    })]
    assert _clean(events[0][0], {**events[0][1], "augment_id": "101"}) == {
        "slot": "left", "verified_by": "ocr",
    }
    assert ledger.active_augment_ids() == []
