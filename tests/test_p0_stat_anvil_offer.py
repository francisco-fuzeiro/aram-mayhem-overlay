"""P0-C/P0-D: verified Stat Anvil offer from OCR titles + own 0-10 scores.

Uses the REAL 16.23 catalogue (data/anvils/stat_anvils_16.23.json). Card ids
stand for what the dedicated title watcher returns (one id per distinct
title). Nothing here simulates a screen; the live gate is server-side.
"""
from pathlib import Path

import pytest

from backend.collectors.anvil_voucher import (
    STAT_ANVIL_VOUCHER_IDS, count_anvil_vouchers, voucher_tier,
)
from backend.engine.anvil_priorities import rate_stat_anvil_offer
from backend.engine.stat_anvil_offer import resolve_offer, title_catalog
from backend.engine.team_context import EnemyThreatProfile
from backend.static_data.stat_anvil_catalog import load_catalog

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def catalog():
    return {s.id: s for s in load_catalog(ROOT, "16.23")}


@pytest.fixture(scope="module")
def champions():
    from backend.static_data.loader import _load_champions
    return _load_champions()


def _ocr_ids(catalog, *titles):
    """Map titles to the single OCR id the watcher would emit for them."""
    names = title_catalog(catalog.values())
    by_title = {v: k for k, v in names.items()}
    return [by_title[t] for t in titles]


def test_title_catalog_has_one_entry_per_distinct_title(catalog):
    names = title_catalog(catalog.values())
    assert len(names) == len(set(names.values()))
    assert "Attack Speed Shard" in names.values()
    assert "Critical Strike Shard" in names.values() and "Critical Shard" in names.values()


def test_unique_prismatic_titles_resolve_without_voucher(catalog):
    ids = _ocr_ids(catalog, "Omnivamp Shard", "Tenacity Shard", "Move Speed Shard")
    res = resolve_offer(ids, catalog)
    assert (res.status, res.reason, res.tier, res.tier_source) == (
        "ok", "verified_offer", "prismatic", "titles")


def test_silver_gold_shared_titles_are_ambiguous_without_more_evidence(catalog):
    ids = _ocr_ids(catalog, "Attack Speed Shard", "Armor Shard", "Might Shard")
    res = resolve_offer(ids, catalog)
    assert (res.status, res.reason) == ("skipped", "tier_ambiguous")


def test_one_tier_specific_title_resolves_the_whole_offer(catalog):
    ids = _ocr_ids(catalog, "Attack Speed Shard", "Critical Strike Shard", "Armor Shard")
    res = resolve_offer(ids, catalog)
    assert res.tier == "gold" and [s.id for s in res.shards] == [
        "ARAM_GoldStatAnvil_AS", "ARAM_GoldStatAnvil_CritChance", "ARAM_GoldStatAnvil_AR"]


def test_ocr_values_resolve_tier_and_contradictions_abstain(catalog):
    ids = _ocr_ids(catalog, "Attack Speed Shard", "Armor Shard", "Might Shard")
    res = resolve_offer(ids, catalog, card_values=[[35], [45], [25, 25]])
    assert (res.tier, res.tier_source) == ("gold", "values")
    bad = resolve_offer(ids, catalog, card_values=[[11], [45], [25, 25]])
    assert (bad.status, bad.reason) == ("skipped", "mixed_tiers")


def test_voucher_only_narrows_an_already_visual_offer(catalog):
    ids = _ocr_ids(catalog, "Attack Speed Shard", "Armor Shard", "Might Shard")
    res = resolve_offer(ids, catalog, voucher_tier="silver")
    assert (res.tier, res.tier_source) == ("silver", "voucher")
    # A voucher tier that the titles exclude can never be forced.
    prism = _ocr_ids(catalog, "Omnivamp Shard", "Tenacity Shard", "Move Speed Shard")
    assert resolve_offer(prism, catalog, voucher_tier="gold").tier == "prismatic"
    # No titles -> no offer, whatever the voucher says.
    assert resolve_offer([], catalog, voucher_tier="gold").reason == "incomplete_offer"


def test_incomplete_duplicate_unknown_or_mixed_offers_abstain(catalog):
    a, b, c = _ocr_ids(catalog, "Omnivamp Shard", "Tenacity Shard", "Move Speed Shard")
    assert resolve_offer([a, b], catalog).reason == "incomplete_offer"
    assert resolve_offer([a, b, None], catalog).reason == "incomplete_offer"
    assert resolve_offer([a, a, b], catalog).reason == "incomplete_offer"
    assert resolve_offer([a, b, "1205"], catalog).reason == "incomplete_offer"
    mixed = _ocr_ids(catalog, "Omnivamp Shard", "Critical Shard", "Tenacity Shard")
    assert resolve_offer(mixed, catalog).reason == "mixed_tiers"


def test_four_card_offer_is_supported_structurally(catalog):
    ids = _ocr_ids(catalog, "Omnivamp Shard", "Tenacity Shard", "Move Speed Shard",
                   "Critical Damage Shard")
    res = resolve_offer(ids, catalog)
    assert res.status == "ok" and len(res.shards) == 4


def test_prismatic_voucher_is_a_real_stat_anvil_voucher():
    # RED before P0: 220010 "Prismatic Stat Voucher" was not observed.
    assert "220010" in STAT_ANVIL_VOUCHER_IDS
    assert count_anvil_vouchers([{"itemID": 220010, "count": 1}]) == {"220010": 1}
    assert voucher_tier(("220009",)) == "gold"
    assert voucher_tier(("220008", "220009")) is None
    assert voucher_tier(()) is None


def _offer(catalog, *ids):
    return [catalog[i] for i in ids]


def test_scores_follow_champion_stats(catalog, champions):
    shards = list(catalog.values())
    offer = _offer(catalog, "ARAM_GoldStatAnvil_AS", "ARAM_GoldStatAnvil_AP",
                   "ARAM_GoldStatAnvil_MR")
    jinx = rate_stat_anvil_offer(champions["jinx"], offer, shards, [], [], None)
    assert jinx[0]["anvil_id"] == "ARAM_GoldStatAnvil_AS"
    ahri = rate_stat_anvil_offer(champions["ahri"], offer, shards, [], [], None)
    assert ahri[0]["anvil_id"] == "ARAM_GoldStatAnvil_AP"
    assert all(0.0 <= r["score"] <= 10.0 for r in jinx + ahri)
    assert all("win" not in r["reason"].lower() for r in jinx + ahri)


def test_enemy_damage_type_moves_defensive_choice(catalog, champions):
    shards = list(catalog.values())
    offer = _offer(catalog, "ARAM_GoldStatAnvil_AR", "ARAM_GoldStatAnvil_MR",
                   "ARAM_GoldStatAnvil_AD")
    ad_heavy = EnemyThreatProfile(enemies_visible=5, enemies_analyzed=5,
                                  physical_pressure=0.9, magic_pressure=0.1)
    ap_heavy = EnemyThreatProfile(enemies_visible=5, enemies_analyzed=5,
                                  physical_pressure=0.1, magic_pressure=0.9)
    vs_ad = rate_stat_anvil_offer(champions["malphite"], offer, shards, [], [], ad_heavy)
    vs_ap = rate_stat_anvil_offer(champions["malphite"], offer, shards, [], [], ap_heavy)
    assert vs_ad[0]["anvil_id"] == "ARAM_GoldStatAnvil_AR"
    assert vs_ap[0]["anvil_id"] == "ARAM_GoldStatAnvil_MR"
    assert vs_ad[0]["reason"] == "enemies deal mostly physical damage"
    assert vs_ad[0]["confidence"] == "medium"


def test_unmodelled_champion_or_mixed_offer_abstains(catalog, champions):
    shards = list(catalog.values())
    assert rate_stat_anvil_offer(None, _offer(catalog, "ARAM_GoldStatAnvil_AS"),
                                 shards, [], [], None) == []
    mixed = _offer(catalog, "ARAM_GoldStatAnvil_AS", "ARAM_StatAnvil_AS")
    assert rate_stat_anvil_offer(champions["jinx"], mixed, shards, [], [], None) == []


def test_pipeline_rates_only_server_verified_offer_ids(catalog):
    from backend.models import ChampionMeta, GamePhase, GameSnapshot, StatVector
    from backend.static_data.loader import StaticData
    from backend.workflow.pipeline import Pipeline
    sd = StaticData()
    sd._champions = {"lux": ChampionMeta(id="lux", name="Lux", role="mage",
                                         stats=StatVector(ap=0.9, pen=0.6, cdr=0.7))}
    sd._stat_anvil_catalog = dict(catalog)
    snap = GameSnapshot(game_id="t", phase=GamePhase.AUG_PICK_1, champion_id="lux",
                        augment_choices=[], chosen_augments=[], purchased_items=[],
                        current_gold=0, game_time=300.0, enemy_champion_ids=[])
    assert Pipeline(sd).run(snap).anvil_offer_ratings == []
    snap.anvil_offer_ids = ["ARAM_GoldStatAnvil_AP", "ARAM_GoldStatAnvil_AS",
                            "ARAM_GoldStatAnvil_AR"]
    rows = Pipeline(sd).run(snap).anvil_offer_ratings
    assert [r["anvil_id"] for r in rows][0] == "ARAM_GoldStatAnvil_AP"
    snap.anvil_offer_ids = ["ARAM_GoldStatAnvil_AP", "not-a-shard", "ARAM_GoldStatAnvil_AR"]
    assert Pipeline(sd).run(snap).anvil_offer_ratings == []
