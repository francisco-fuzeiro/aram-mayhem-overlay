"""M5/C4 RED: conservative offer visibility; synthetic evidence only.

Unreadable titles are never proof that the offer vanished or that a player chose
a card. There are no native League screenshots or invented UI anchors here.
"""
from backend.collectors.offer_lifecycle import OfferLifecycle


def test_level_due_is_pending_not_visible():
    life = OfferLifecycle()
    assert life.state == "inactive"
    life.open()
    assert life.state == "pending"
    life.observe("no_augments")
    assert life.state == "pending"


def test_only_temporally_confirmed_named_cards_make_offer_present():
    life = OfferLifecycle()
    life.open()
    life.observe("detected", identified=2)
    assert life.state == "present"


def test_all_unknown_after_valid_cards_is_uncertain_never_gone():
    life = OfferLifecycle()
    life.open()
    life.observe("detected", identified=3)
    life.observe("detected", identified=0)
    assert life.state == "uncertain"
    life.observe("unchanged")
    assert life.state == "uncertain"


def test_dialogue_or_animation_does_not_count_as_verified_disappearance():
    life = OfferLifecycle()
    life.open()
    life.observe("detected", identified=3)
    life.observe("disappeared", verified_absence=False)
    assert life.state == "uncertain"
    life.observe("detected", identified=1)
    assert life.state == "present"


def test_focus_loss_suspends_and_only_fresh_confirmed_read_restores_present():
    life = OfferLifecycle()
    life.open()
    life.observe("detected", identified=3)
    life.observe("not_focused")
    assert life.state == "suspended"
    life.observe("unchanged")
    assert life.state == "suspended"
    life.observe("detected", identified=2)
    assert life.state == "present"


def test_capture_failure_and_unknown_frame_do_not_erase_confirmed_card_identity():
    life = OfferLifecycle()
    life.open()
    life.observe("detected", identified=1)
    life.observe("unavailable")
    assert life.state == "suspended"
    life.observe("no_augments")
    assert life.state == "suspended"


def test_verified_absence_is_explicit_and_cannot_choose_a_card():
    life = OfferLifecycle()
    life.open()
    life.observe("detected", identified=3)
    life.observe("disappeared", verified_absence=True)
    assert life.state == "gone"
    life.observe("detected", identified=3)
    assert life.state == "gone"


def test_new_offer_after_close_starts_pending_with_no_old_visibility():
    life = OfferLifecycle()
    life.open()
    life.observe("detected", identified=3)
    life.close()
    assert life.state == "inactive"
    life.open()
    assert life.state == "pending"


def test_inactive_state_rejects_unrelated_ocr_events():
    life = OfferLifecycle()
    life.observe("detected", identified=3)
    life.observe("disappeared", verified_absence=True)
    assert life.state == "inactive"
