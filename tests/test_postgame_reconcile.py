"""Plan v2 layer 3: live picks are checked against the post-game history."""
import asyncio

from backend.workflow.offer_ledger import OfferLedger


def _ledger(levels=(1, 7)):
    ledger = OfferLedger(levels)
    ledger.on_level(7)
    return ledger


def _show(ledger, offer, ids):
    for slot, aid in zip(("left", "centre", "right"), ids):
        offer.slots[slot].augment_id = aid
        offer.slots[slot].source = "ocr"


def test_reconcile_agrees_corrects_and_counts():
    ledger = _ledger()
    a, b = ledger.offers
    _show(ledger, a, ["1", "2", "3"])
    _show(ledger, b, ["4", "5", "6"])
    a.picked_id, a.state = "2", "confirmed"
    b.picked_id, b.state = "4", "confirmed"        # wrong cursor guess
    counts = ledger.reconcile(["2", "6"])
    assert counts == {"agreed": 1, "corrected": 1, "unmatched": 0}
    assert [o.picked_id for o in ledger.offers] == ["2", "6"]
    assert all(o.state == "reconciled" and o.pick_source == "postgame" for o in ledger.offers)
    assert ledger.active_augment_ids() == ["2", "6"]


def test_four_card_offer_reconciles_by_pick_or_position():
    ledger = _ledger()
    a, b = ledger.offers
    a.picked_id, a.state = "9", "confirmed"        # four-card pick, no slot titles
    counts = ledger.reconcile(["9", "11"])
    assert counts["agreed"] == 1 and b.picked_id == "11" and counts["corrected"] == 1


def test_unmatched_offer_is_left_alone():
    ledger = _ledger((1,))
    _show(ledger, ledger.offers[0], ["1", "2", "3"])
    assert ledger.reconcile(["8"]) == {"agreed": 0, "corrected": 0, "unmatched": 1}
    assert ledger.offers[0].state != "reconciled"


def test_server_reconciles_only_with_history_on(monkeypatch):
    from backend.api import server
    from backend.storage import history_import
    seen = []
    monkeypatch.setattr(server.feature_diagnostics, "record",
                        lambda *a, **k: seen.append(a[:3]))
    ledger = _ledger((1,))
    _show(ledger, ledger.offers[0], ["1", "2", "3"])
    monkeypatch.setattr(server, "_history_import_allowed", lambda: False)
    asyncio.run(server._postgame_reconcile(ledger, "garen", delays=(0,)))
    assert seen[-1] == ("augment.postgame_reconcile", "skipped", "history_off")

    monkeypatch.setattr(server, "_history_import_allowed", lambda: True)
    monkeypatch.setattr(history_import, "fetch_latest_own_augments", lambda c: ["3"])
    synced = []
    monkeypatch.setattr(history_import, "sync_recent_mayhem_games",
                        lambda n: synced.append(n) or {"status": "ok"})
    monkeypatch.setattr(server.impact_gate, "_rows_source", lambda: [])
    asyncio.run(server._postgame_reconcile(ledger, "garen", delays=(0,)))
    assert ("augment.postgame_reconcile", "ok", "corrected") in seen
    assert ledger.offers[0].picked_id == "3" and synced == [5]
