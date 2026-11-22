"""Offline F0 contract replay with synthetic data; never inspects League or disk.

Usage: python -m backend.workflow.f0_replay
This report is not a replay of the user's unrecorded N1 game and does not
establish actual native OCR accuracy or item usefulness.
"""
from __future__ import annotations

import json

from backend.engine.champion_select import summarize_champion_select
from backend.models import ChampionMeta, StatVector
from backend.workflow.offer_ledger import OfferLedger
from backend.workflow.f0_trace import (
    classify_champion_identity, classify_offer_slots,
    classify_build_evidence, classify_item_eligibility,
)


def _row(scenario: str, feature: str, outcome: tuple[str, str]) -> dict[str, str]:
    return dict(scenario=scenario, feature=feature,
                status=outcome[0], reason=outcome[1])


def run_synthetic_replay() -> list[dict[str, str]]:
    """Exercise existing champion/offer code plus observational classifiers.

    Rows contain only fixed synthetic scenario identifiers and allowlisted
    status/reason strings: no real game identity, OCR, private paths or pixels.
    """
    catalog = {
        "fixture_self": ChampionMeta(
            "fixture_self", "Synthetic Self", StatVector(ad=0.8), role="marksman"
        ),
        "fixture_bench": ChampionMeta(
            "fixture_bench", "Synthetic Bench", StatVector(ap=0.8), role="mage"
        ),
    }
    ids = {"99": "fixture_self", "222": "fixture_bench"}
    draft = {
        "localPlayerCellId": 4,
        "myTeam": [{"cellId": 4, "championId": 99}],
        "benchChampions": [{"championId": 222}],
    }
    payload = summarize_champion_select(draft, ids, catalog.get)
    # This checks the real summarizer, not only the diagnostic classifier.
    current = [c for c in payload["candidates"] if c["current"]]
    champion_outcome = classify_champion_identity(draft, ids)
    if len(current) != 1 or current[0]["id"] != "fixture_self":
        champion_outcome = ("rejected", "local_cell_ambiguous")

    missing_cell = dict(draft, localPlayerCellId=8)
    rows = [
        _row("champion_self_vs_bench", "champion", champion_outcome),
        _row("champion_missing_cell", "champion",
             classify_champion_identity(missing_cell, ids)),
    ]

    # Lifecycle is real OfferLedger behavior, with only synthetic card IDs.
    ledger = OfferLedger((3, 7, 11, 15))
    offer = ledger.on_level(3)
    assert offer is not None and offer.state == "due"
    rows.append(_row(
        "offer_no_cards", "augment",
        classify_offer_slots(None, stage="titles_unidentified",
                             stale=False, epoch_valid=True),
    ))
    original_epoch = offer.epoch
    first = {"left": "10001", "centre": "10002", "right": "10003"}
    ledger.on_verified_titles(first, original_epoch)
    reroll_epoch = original_epoch + 1
    ledger.set_current_epoch(reroll_epoch)
    rerolled = {"left": "10004", "centre": "10002", "right": "10003"}
    ledger.on_verified_titles(rerolled, reroll_epoch)
    assert offer.slots["left"].augment_id == "10004"
    assert offer.slots["centre"].augment_id == "10002"
    assert ledger.active_augment_ids() == []
    rows.extend([
        _row("offer_one_slot_rerolled", "augment",
             classify_offer_slots(rerolled, stage="titles_detected",
                                  stale=False, epoch_valid=True)),
        _row("offer_previous_epoch", "augment",
             classify_offer_slots(first, stage="titles_detected",
                                  stale=False, epoch_valid=False)),
        _row("offer_unconfirmed_pick", "build",
             classify_build_evidence(champion_known=True, pool_verified=True,
                                     inventory_known=True, augments_confirmed=False)),
    ])
    verified_pool = {"3006", "3046"}
    rows.extend([
        _row("item_reward_excluded", "build", classify_item_eligibility(
            "9999", "augment_reward", verified_pool, True, set(),
        )),
        _row("item_unverified_pool", "build", classify_item_eligibility(
            "3046", "final", verified_pool, False, set(),
        )),
        _row("item_verified_candidate", "build", classify_item_eligibility(
            "3046", "final", verified_pool, True, set(),
        )),
        _row("item_already_owned", "build", classify_item_eligibility(
            "3046", "final", verified_pool, True, {"3046"},
        )),
    ])
    return rows


if __name__ == "__main__":
    print(json.dumps({"kind": "synthetic_f0_contract_replay",
                      "rows": run_synthetic_replay()},
                     sort_keys=True, separators=(",", ":")))
