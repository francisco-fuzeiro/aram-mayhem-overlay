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
