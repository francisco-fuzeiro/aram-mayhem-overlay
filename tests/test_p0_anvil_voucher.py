"""P0: voucher purchase is an LCDA inventory delta, never proof of visible cards.

All synthetic observations. No real game state, OCR or League input.
"""
from backend.collectors.anvil_voucher import (
    AnvilVoucherPurchaseObserver, count_anvil_vouchers,
)
from backend.collectors.lcda import parse_game_snapshot
from backend.models import GamePhase


def _item(identifier, count=1, slot=0):
    return {"itemID": identifier, "count": count, "slot": slot}


def test_voucher_presence_and_stacks_count_only_active_inventory():
    raw = {
        "activePlayer": {"riotId": "Synthetic#ONE", "level": 1},
        "allPlayers": [
            {"riotId": "Synthetic#ONE", "championName": "Lux",
             "team": "ORDER", "items": [_item(220008, 2), _item(3006)]},
            {"riotId": "Synthetic#TWO", "championName": "Jinx",
             "team": "CHAOS", "items": [_item(220009, 9)]},
        ],
        "gameData": {"gameId": "synthetic", "gameTime": 5},
    }
    snapshot = parse_game_snapshot(raw, GamePhase.IN_GAME)
    assert snapshot.anvil_vouchers == {"220008": 2}
    # The reward voucher never becomes a regular shop build recommendation.
    assert "220008" in snapshot.purchased_items
    raw["activePlayer"]["riotId"] = "Unknown#PLAYER"
    assert parse_game_snapshot(raw, GamePhase.IN_GAME).anvil_vouchers is None


def test_appearance_and_stack_increment_signal_once_per_observed_change():
    tracker = AnvilVoucherPurchaseObserver()
    assert tracker.observe({}) == ()
    assert tracker.observe({"220008": 1}) == ("220008",)
    assert tracker.observe({"220008": 1}) == ()
    assert tracker.observe({"220008": 3}) == ("220008",)
    assert tracker.observe({}) == ()  # spent, not another purchase
    assert tracker.observe({"220009": 1}) == ("220009",)


def test_no_baseline_no_malformed_or_reconnect_false_purchase():
    tracker = AnvilVoucherPurchaseObserver()
    assert tracker.observe({"220008": 1}) == ()  # attaching mid-match
    assert tracker.observe(None) == ()  # LCDA loss: never fake zero
    assert tracker.observe({"220008": 2}) == ()  # new baseline
    assert tracker.observe({"220008": 3}) == ("220008",)
    assert count_anvil_vouchers([_item(220008, -1)]) is None
    assert count_anvil_vouchers([_item(220008, True)]) is None
    assert count_anvil_vouchers([_item(220008, 2), _item(220008, 1)]) == {"220008": 3}


def test_known_item_id_not_keyword_or_item_catalog():
    assert count_anvil_vouchers([_item(220008), _item(220009), _item(3006)]) == {
        "220008": 1, "220009": 1,
    }
    assert count_anvil_vouchers([_item(999999)]) == {}
    assert count_anvil_vouchers(None) is None


import pytest
from tests.test_poll_tick_m1 import make_harness, make_snapshot
from backend.api.server import poll_tick


@pytest.mark.asyncio
async def test_poll_records_voucher_edge_without_opening_augment_or_ocr_offer():
    frames = [make_snapshot(level=1) for _ in range(4)]
    for frame, vouchers in zip(frames, ({}, {"220008": 1}, {"220008": 1},
                                        {"220008": 2})):
        frame.anvil_vouchers = vouchers
    state, deps, events = make_harness(
        [{"tick": i} for i in range(4)], frames, ocr=True,
    )
    for i in range(4):
        await poll_tick(state, deps, float(i + 10))
    assert state.anvil_voucher_purchase_events == 2
    assert state.anvil_voucher_last_purchase == ("220008",)
    assert state.anvil_voucher_trigger_pending is True
    assert state.scan_window_open is False
    assert state.augment_choices == []
    assert not any(event.get("type") == "ocr_result"
                   and event.get("status") == "detected" for event in events)
    state.reset()
    assert state.anvil_voucher_purchase_events == 0
    assert state.anvil_voucher_trigger_pending is False


@pytest.mark.asyncio
async def test_unknown_voucher_source_never_looks_like_purchase():
    frames = [make_snapshot(level=1) for _ in range(4)]
    for frame, voucher in zip(frames, ({"220008": 1}, None,
                                         {"220008": 2}, {"220008": 3})):
        frame.anvil_vouchers = voucher
    state, deps, _ = make_harness([{"tick": i} for i in range(4)], frames)
    for i in range(4):
        await poll_tick(state, deps, float(i + 10))
    # Two valid observations after the unknown frame are required.
    assert state.anvil_voucher_purchase_events == 1
