"""Heuristic Stat Anvil ranking on the real pinned 16.23 catalogue (#107).

Shards carry canonical ``stats`` from the catalogue; ranking must use them
instead of guessing from the kind or the raw DataValues names.
"""
from pathlib import Path

from backend.static_data.stat_anvil_catalog import load_catalog
from backend.tierdb.anvil_stats import anvil_stat_for_kind, rank_anvil_options, stat_demand

ROOT = Path(__file__).resolve().parents[1]


def _catalog_shards():
    return [{"id": a.id, "tier": a.tier, "kind": a.kind, "stats": a.stat_map()}
            for a in load_catalog(ROOT, "16.23")]


def test_every_real_16_23_shard_is_modelled():
    shards = _catalog_shards()
    assert len(shards) == 34
    out = rank_anvil_options(shards, stat_demand("mage", [], {}))
    unmodelled = [r["id"] for r in out if r["level"] == "unmodelled"]
    assert unmodelled == []
    assert all(r["tier"] in ("A", "B", "C", "D", "E") for r in out)


def test_raw_datavalue_names_with_min_prefix_map_to_stats():
    assert anvil_stat_for_kind("MinAD") == "ad"
    assert anvil_stat_for_kind("MinAP") == "ap"
    assert anvil_stat_for_kind("MinAR") == "armor"
    assert anvil_stat_for_kind("MinMR") == "mr"
    assert anvil_stat_for_kind("MinHP") == "hp"
    assert anvil_stat_for_kind("hp_pct") == "hp"
    assert anvil_stat_for_kind("MinAS+MinAH") is None  # hybrids come via stats


def test_hybrid_uses_both_stats_weighted_by_catalogue_values():
    shards = {s["id"]: s for s in _catalog_shards()}
    demand = stat_demand("mage", [], {})
    pick = [shards["ARAM_StatAnvil_AP"], shards["ARAM_StatAnvil_AD"],
            shards["ARAM_StatAnvil_Hybrid2"]]
    by_id = {r["id"]: r for r in rank_anvil_options(pick, demand)}
    # AD+AP hybrid gives 12 AP (pure AP shard 15): below pure AP, above pure AD for a mage.
    assert by_id["ARAM_StatAnvil_AP"]["score"] > by_id["ARAM_StatAnvil_Hybrid2"]["score"]
    assert by_id["ARAM_StatAnvil_Hybrid2"]["score"] > by_id["ARAM_StatAnvil_AD"]["score"]
    assert by_id["ARAM_StatAnvil_Hybrid2"]["stat"] == "ap"  # dominant stat shown


def test_side_effects_do_not_score():
    shards = {s["id"]: s for s in _catalog_shards()}
    demand = stat_demand("tank", [], {})
    row = rank_anvil_options([shards["ARAM_PrisStatAnvil_HP"]], demand)[0]
    assert row["stat"] == "hp" and row["score"] is not None
