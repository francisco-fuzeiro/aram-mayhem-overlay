"""M5/C4c RED: focus-safe offer epoch, OCR outage and manual-scan fencing.

All tests use synthetic metadata and fake watchers. No game/screenshot needed.
"""
import pytest
from unittest.mock import Mock

from backend.api.server import GameState, poll_tick
from tests.test_poll_tick_m1 import make_harness, make_snapshot


def _visible(state):
    state.scan_window_open = True
    state.offer_lifecycle.open()
    state.offer_lifecycle.observe("detected", identified=3)
    state.augment_choices[:] = ["en", "bind", "kill"]
    state.ocr_slot_choices = {"left": "en", "centre": "bind", "right": "kill"}


def _rows():
    return [
        {"slot": "left", "id": "en", "name": "En Passant", "confidence": 99},
        {"slot": "centre", "id": "bind", "name": "Ravenous Bind", "confidence": 98},
        {"slot": "right", "id": "kill", "name": "It's Killing Time", "confidence": 97},
    ]


def test_c4c_disabling_and_reenabling_ocr_requires_new_verified_reads():
    state = GameState()
    state.offer_epoch = 4
    _visible(state)
    watcher = Mock()
    state.set_ocr_enabled(False, watcher=watcher)
    assert state.offer_state == "suspended"
    assert state.ocr_stale is True
    assert state.augment_choices == ["en", "bind", "kill"]  # historical only
    assert state.offer_epoch == 5
    watcher.reset.assert_called_once()

    state.set_ocr_enabled(True, watcher=watcher)
    assert state.offer_state == "suspended"
    assert state.offer_epoch == 6
    assert state.ocr_enabled is True
    assert watcher.reset.call_count == 2
    assert not state.chosen_augments


def test_c4c_manual_scan_refuses_a_closed_or_changed_offer_epoch():
    state = GameState()
    state.match_id = "lcu:202"
    state.offer_epoch = 7
    ids = ["en", "bind", "kill"]
    assert state.accept_manual_ocr(ids, _rows(), match_id="lcu:202", offer_epoch=7) is False
    _visible(state)
    before = list(state.augment_choices)
    for match_id, epoch in (("lcu:201", 7), ("lcu:202", 6)):
        assert state.accept_manual_ocr(ids, _rows(), match_id=match_id, offer_epoch=epoch) is False
        assert state.augment_choices == before
    state.scan_window_open = False
    assert state.accept_manual_ocr(ids, _rows(), match_id="lcu:202", offer_epoch=7) is False


def test_c4c_current_manual_scan_accepts_only_slot_verified_triple():
    state = GameState()
    state.match_id = "lcu:123"
    state.offer_epoch = 9
    state.scan_window_open = True
    state.offer_lifecycle.open()
    assert state.accept_manual_ocr(["en", "bind", "kill"], _rows(),
                                   match_id="lcu:123", offer_epoch=9)
    assert state.offer_state == "present"
    assert state.ocr_slot_choices == {"left": "en", "centre": "bind", "right": "kill"}
    assert state.chosen_augments == []


def test_c4c_manual_scan_rejects_disabled_ocr_and_already_confirmed_pick():
    state = GameState()
    state.match_id = "lcu:9"
    state.offer_epoch = 1
    _visible(state)
    state.ocr_enabled = False
    assert not state.accept_manual_ocr(["en"], _rows(), match_id="lcu:9", offer_epoch=1)
    state.ocr_enabled = True
    state.confirmation_pending = True
    assert not state.accept_manual_ocr(["en"], _rows(), match_id="lcu:9", offer_epoch=1)


@pytest.mark.asyncio
async def test_c4c_ocr_unavailable_during_open_offer_suspends_instead_of_freezing_present():
    state, deps, events = make_harness([{"tick": 1}], [make_snapshot()], ocr=False)
    _visible(state)
    await poll_tick(state, deps, 91.0)
    assert state.offer_state == "suspended"
    assert state.ocr_stale is True
    assert state.scan_window_open is True
    assert state.chosen_augments == []
    assert any(e.get("type") == "ocr_result" and e.get("status") == "unavailable"
               and e.get("offer_state") == "suspended" for e in events)


@pytest.mark.asyncio
async def test_c4c_closed_offer_never_reopens_on_late_ocr_result():
    state = GameState()
    state.match_id = "lcu:99"
    state.offer_epoch = 3
    _visible(state)
    state.scan_window_open = False
    state.offer_lifecycle.close()
    assert not state.accept_manual_ocr(["en", "bind", "kill"], _rows(),
                                        match_id="lcu:99", offer_epoch=3)
    assert state.offer_state == "inactive"
    assert state.chosen_augments == []


def test_c4c_reset_advances_epoch_and_clears_old_offer():
    state = GameState()
    state.offer_epoch = 12
    _visible(state)
    state.reset()
    assert state.offer_epoch == 13
    assert state.offer_state == "inactive"
    assert state.ocr_slot_choices is None
    assert not state.chosen_augments
