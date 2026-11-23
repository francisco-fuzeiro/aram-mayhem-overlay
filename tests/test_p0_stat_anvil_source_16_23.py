"""P0-A/B: the REAL patch 16.23 Stat Anvil source, pinned and loaded.

Fixture ``tests/fixtures/anvils/statanvils.16.23.bin.json`` is the unmodified
public CommunityDragon file
https://raw.communitydragon.org/16.23/game/maps/modespecificdata/statanvils.bin.json
(fetched 2026-11-23, Last-Modified 2026-11-23 18:11:48 GMT, sha256 below).
The string fixture is an allowlisted 60-key extract of the same patch's
``game/en_us/data/menu/en_us/lol.stringtable.json``. These are real data, not
synthetic shapes; they guard future patch changes (rename, new shard, value).
"""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from backend.static_data.anvil_public_catalog import AnvilCatalogError, parse_public_bins
from backend.static_data.stat_anvil_catalog import (
    SOURCE_PATH, build_catalog, canonical_stats, load_catalog, validate_catalog,
)

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "anvils"
BIN_SHA256 = "494f603dffc677341a9531e5e71d5ad260d99280943b2993b18de1dcfeb694c2"
SOURCE = {
    "url": "https://raw.communitydragon.org/16.23/" + SOURCE_PATH,
    "path": SOURCE_PATH, "sha256": BIN_SHA256,
    "last_modified": "Mon, 23 Nov 2026 18:11:48 GMT",
    "strings": "game/en_us/data/menu/en_us/lol.stringtable.json",
}


def _bin_text():
    return (FIX / "statanvils.16.23.bin.json").read_text(encoding="utf-8")


def _strings():
    return json.loads((FIX / "stringtable.anvils.16.23.en_us.json").read_text(
        encoding="utf-8"))["entries"]


def _catalog(doc=None):
    return build_catalog(doc or json.loads(_bin_text()), _strings(),
                         patch="16.23", source=SOURCE)


def test_fixture_is_the_unmodified_public_16_23_file():
    assert hashlib.sha256(_bin_text().encode("utf-8")).hexdigest() == BIN_SHA256


def test_real_16_23_counts_raw_and_offerable():
    cat = _catalog()
    assert cat["raw_anvil_data"] == 37
    assert cat["raw_tiers"] == {"silver": 14, "gold": 14, "prismatic": 8}
    assert cat["total"] == 34
    assert cat["tiers"] == {"silver": 13, "gold": 13, "prismatic": 8}
    assert {(r["id"], r["reason"]) for r in cat["rejected"]} == {
        ("ARAM_StatAnvil_Random", "disabled_in_game_bin"),
        ("ARAM_GoldStatAnvil_Random", "disabled_in_game_bin"),
        ("ARAM_StatAnvil_Pristine", "disabled_in_game_bin"),
    }


def test_root_spell_data_values_become_exact_stats():
    by_id = {e["id"]: e for e in _catalog()["entries"]}
    assert by_id["ARAM_StatAnvil_AS"]["stats"] == {"as": 11.0}
    assert by_id["ARAM_GoldStatAnvil_AS"]["stats"] == {"as": 35.0}
    assert by_id["ARAM_StatAnvil_HP"]["stats"] == {"hp": 110.0}
    assert by_id["ARAM_GoldStatAnvil_HP"]["stats"] == {"hp": 375.0}
    assert by_id["ARAM_PrisStatAnvil_HP"]["stats"] == {"hp_pct": 15.0, "size": 10.0}
    assert by_id["ARAM_PrisStatAnvil_Lethality"]["stats"] == {"armor_pen_pct": 17.5}
    assert by_id["ARAM_GoldStatAnvil_Hybrid3"]["stats"] == {"armor": 30.0, "mr": 30.0}
    assert by_id["ARAM_StatAnvil_Omnivamp"]["stats"] == {
        "omnivamp": 20.0, "omnivamp_ranged": 10.0}
    assert by_id["ARAM_GoldStatAnvil_AS"]["title"] == "Attack Speed Shard"
    assert by_id["ARAM_PrisStatAnvil_Lethality"]["title"] == "Armor Penetration Shard"
    assert by_id["ARAM_StatAnvil_CritChance"]["title"] == "Critical Shard"
    assert by_id["ARAM_GoldStatAnvil_CritChance"]["title"] == "Critical Strike Shard"


def test_committed_runtime_catalog_is_regenerated_from_the_real_fixture():
    committed = json.loads((ROOT / "data" / "anvils" / "stat_anvils_16.23.json")
                           .read_text(encoding="utf-8"))
    assert committed == _catalog()
    shards = load_catalog(ROOT, "16.23")
    assert len(shards) == 34


def test_catalogue_is_patch_pinned_and_fail_closed():
    cat = _catalog()
    with pytest.raises(AnvilCatalogError):
        validate_catalog(cat, expected_patch="16.24")
    with pytest.raises(AnvilCatalogError):
        load_catalog(ROOT, "16.24")
    no_prismatic = copy.deepcopy(cat)
    no_prismatic["entries"] = [e for e in cat["entries"] if e["tier"] != "prismatic"]
    with pytest.raises(AnvilCatalogError):
        validate_catalog(no_prismatic, expected_patch="16.23")
    wrong_source = copy.deepcopy(cat)
    wrong_source["source"]["path"] = "game/unknown/507cdd64276919f5.bin.json"
    with pytest.raises(AnvilCatalogError):
        validate_catalog(wrong_source, expected_patch="16.23")


def test_new_disabled_entry_is_rejected_generically_not_by_name():
    doc = json.loads(_bin_text())
    key = "Maps/ModeSpecificData/StatAnvils/ARAM_StatAnvil_AD"
    doc[key]["Enabled"] = False
    cat = _catalog(doc)
    assert ("ARAM_StatAnvil_AD", "disabled_in_game_bin") in {
        (r["id"], r["reason"]) for r in cat["rejected"]}
    assert "ARAM_StatAnvil_AD" not in {s.item_id for s in parse_public_bins([doc])}


def test_unmapped_stat_or_missing_title_rejects_entry_with_reason():
    doc = json.loads(_bin_text())
    spell = doc["Maps/ModeSpecificData/StatAnvils/ARAM_StatAnvil_AP/Augment_ARAM_StatAnvil_AP"]
    spell["mSpell"]["DataValues"][0]["name"] = "MinNewStat"
    strings = dict(_strings())
    strings.pop("cherry_statanvil_ah_name")
    cat = build_catalog(doc, strings, patch="16.23", source=SOURCE)
    reasons = {r["id"]: r["reason"] for r in cat["rejected"]}
    assert reasons["ARAM_StatAnvil_AP"].startswith("stats_rejected")
    assert reasons["ARAM_StatAnvil_AH"] == "title_missing"
    assert cat["tiers"]["silver"] == 11


def test_canonical_stats_rejects_unknown_names():
    with pytest.raises(AnvilCatalogError):
        canonical_stats("x", {"Unknown": 1.0})


def test_public_report_tries_the_named_16_23_path_first():
    from scripts.stat_anvil_catalog_report import ANVIL_BIN_PATHS
    assert ANVIL_BIN_PATHS[0] == SOURCE_PATH


def test_static_data_loads_shards_only_for_matching_patch(monkeypatch):
    from backend.models import AugmentTier
    from backend.static_data import loader

    shards, status = loader._load_stat_anvils("16.23.1")
    assert status == {"status": "ok", "reason": "verified_catalog", "patch": "16.23",
                      "total": 34, "tiers": {"silver": 13, "gold": 13, "prismatic": 8}}
    assert all(a.tier == AugmentTier.STAT_ANVIL for a in shards.values())
    gold_as = shards["ARAM_GoldStatAnvil_AS"]
    assert gold_as.name == "Attack Speed Shard" and gold_as.contribution.attack_speed > 0
    empty, status = loader._load_stat_anvils("16.24.1")
    assert empty == {} and status["status"] == "skipped"
    assert status["reason"] == "catalog_patch_mismatch"
