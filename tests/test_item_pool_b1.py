"""B1 versioned two-source Mayhem item pool: offline tests-first contract."""
import copy
import json
from collections import Counter
from pathlib import Path

import pytest
import requests

from backend.static_data.item_policy import (
    ITEM_POLICY_VERSION, POOL_CLASSES, RECOMMENDABLE_CLASSES, classify_item,
    cdragon_matches, load_item_overrides, patch_of,
)
from backend.static_data.loader import StaticData, _load_items


FIXTURES = Path(__file__).parent / "fixtures" / "items"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def dd_from_compact(c):
    return {
        "name": c["n"], "maps": {str(m): True for m in c["m"]},
        "gold": {"purchasable": bool(c["p"]), "total": c["g"]},
        "into": ["x"] * c["i"], "from": ["x"] * c["f"],
        "tags": c["t"], "inStore": c["s"] == 1,
        "hideFromAll": bool(c["h"]), "requiredChampion": c["rc"],
        "stats": {}, "description": "",
    }


def sources():
    compact = fixture("ddragon_items_16.23.1_compact.json")["items"]
    dd = {ident: dd_from_compact(row) for ident, row in compact.items()}
    details = fixture("ddragon_items_16.23.1_details.json")["items"]
    for ident, details_row in details.items():
        dd[ident].update(
            {"from": details_row["from"], "into": details_row["into"],
             "stats": details_row["stats"]}
        )
    cd_json = fixture("cdragon_items_2026-11-20.json")
    fields = cd_json["fields"]
    cd = {str(row[0]): dict(zip(fields, row)) for row in cd_json["rows"]}
    return dd, cd, cd_json


def test_full_480_classification_matches_versioned_expected_fixture():
    dd, cd, _ = sources()
    expected = fixture("expected_item_pool_16.23.1.json")
    classified = {ident: classify_item(ident, row, cd.get(ident), {"force_class": {}})
                  for ident, row in dd.items()}
    assert ITEM_POLICY_VERSION == "item_pool_v6"
    assert classified == expected["classes"]
    assert Counter(classified.values()) == {
        "final": 104, "boots_tier2": 7, "boots_tier1": 1,
        "component": 69, "augment_reward": 5, "conditional": 12,
        "mode_variant": 152, "not_on_aram_map": 76,
        "not_purchasable": 42, "consumable_trinket": 12,
    }
    assert sorted(k for k, c in classified.items() if c in POOL_CLASSES) == sorted(expected["pool_ids"])
    assert sorted(k for k, c in classified.items() if c in RECOMMENDABLE_CLASSES) == sorted(expected["final_ids"])


@pytest.mark.parametrize("item_id,category", [
    ("226668", "augment_reward"), ("223069", "augment_reward"),
    ("228002", "augment_reward"), ("223084", "augment_reward"),
    ("773074", "mode_variant"), ("771036", "mode_variant"),
    ("323003", "not_on_aram_map"), ("663060", "not_on_aram_map"),
    ("124011", "not_purchasable"), ("3039", "not_purchasable"),
    ("4003", "not_purchasable"), ("4004", "not_purchasable"),
    ("3040", "conditional"), ("3042", "conditional"),
    ("2421", "conditional"), ("2003", "consumable_trinket"),
    ("3340", "not_on_aram_map"),  # Map 12 check precedes tag exclusion.
])
def test_known_exclusions_never_enter_recommendable_pool(item_id, category):
    dd, cd, _ = sources()
    assert classify_item(item_id, dd[item_id], cd.get(item_id), {"force_class": {}}) == category


@pytest.mark.parametrize("item_id", ["3074", "126697", "123430", "1036", "1001", "3006"])
def test_known_normal_shop_ids_are_in_the_pool(item_id):
    dd, cd, _ = sources()
    assert classify_item(item_id, dd[item_id], cd.get(item_id), {"force_class": {}}) in POOL_CLASSES


def test_unknown_and_valid_override_are_conservative(tmp_path):
    dd, cd, _ = sources()
    assert classify_item("3074", dd["3074"], None, {"force_class": {}}) == "unknown"
    override = {"version": "test.1", "force_class": {
        "3074": {"class": "not_purchasable", "reason": "tested", "source": "fixture"},
    }}
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps(override), encoding="utf-8")
    assert classify_item("3074", dd["3074"], cd["3074"], load_item_overrides(path)) == "not_purchasable"
    for invalid in ({"class": "not_purchasable", "source": "fixture"},
                    {"class": "not_purchasable", "reason": "tested"},
                    {"class": "not_a_class", "reason": "tested", "source": "fixture"}):
        override["force_class"]["3074"] = invalid
        path.write_text(json.dumps(override), encoding="utf-8")
        with pytest.raises(ValueError):
            load_item_overrides(path)


def test_patch_match_is_strict_not_prefix_guess():
    assert patch_of("16.23.1") == "16.23"
    assert cdragon_matches("16.23.1", "16.23.8406595+branch.releases-16-23.content.release")
    assert not cdragon_matches("16.23.1", "16.2.999")
    assert not cdragon_matches("16.23.1", "16.24.1")
    assert not cdragon_matches("16.23.1", "latest")


class Response:
    def __init__(self, value):
        self.value = value
        self.content = json.dumps(value).encode("utf-8")

    def json(self):
        return copy.deepcopy(self.value)

    def raise_for_status(self):
        return None


def offline_loader(monkeypatch, tmp_path, *, cdragon=True, patch="16.23.8406595+branch.test", conflict=False):
    from backend.static_data import loader
    dd, cd, raw_cd = sources()
    if conflict:
        raw_cd = copy.deepcopy(raw_cd)
        idx = raw_cd["fields"].index("priceTotal")
        for row in raw_cd["rows"]:
            if row[0] == 3074:
                row[idx] += 1
    monkeypatch.setattr(loader, "_get_dd_version", lambda: "16.23.1")
    monkeypatch.setattr(loader, "CACHE_DIR", tmp_path)
    def get(url, timeout=15):
        if "content-metadata.json" in url:
            if not cdragon:
                raise requests.ConnectionError("offline")
            return Response({"version": patch})
        if "plugins/rcp-be-lol-game-data/global/default/v1/items.json" in url:
            if not cdragon:
                raise requests.ConnectionError("offline")
            return Response(raw_cd["rows"])
        if url.endswith("/item.json"):
            return Response({"data": dd})
        raise AssertionError(f"unexpected network request: {url}")
    monkeypatch.setattr(loader.requests, "get", get)


def test_verified_two_source_pool_and_versioned_cache(monkeypatch, tmp_path):
    offline_loader(monkeypatch, tmp_path)
    catalog = _load_items()
    assert catalog.meta.availability == "verified_two_source"
    assert catalog.meta.ddragon_version == "16.23.1"
    assert catalog.meta.cdragon_patch.startswith("16.23.")
    assert len(catalog.meta.cdragon_sha256) == 64
    assert catalog.data_source == "network"
    data = StaticData()
    data._items = catalog
    assert len(data.recommendable_items()) == 112
    assert len(catalog.pool_ids) == 181
    assert {i.id for i in data.recommendable_items()} == set(fixture("expected_item_pool_16.23.1.json")["final_ids"]) | {"2526"}  # Whispering Circlet: Tear item, transform unbuyable (24/11)
    assert all(item.item_class in RECOMMENDABLE_CLASSES for item in data.recommendable_items())
    assert "226668" not in catalog.pool_ids
    assert "3040" not in catalog.pool_ids
    assert data.get_item("3074").name == "Ravenous Hydra"
    assert list(tmp_path.glob("items_v5_16.23.1*.json"))


def test_offline_uses_only_verified_same_version_cache(monkeypatch, tmp_path):
    offline_loader(monkeypatch, tmp_path)
    _load_items()
    offline_loader(monkeypatch, tmp_path, cdragon=False)
    reused = _load_items()
    assert reused.meta.availability == "verified_two_source"
    assert reused.data_source == "cache"
    assert len(StaticData().recommendable_items()) == 0  # no implicit globally trusted catalog
    data = StaticData()
    data._items = reused
    assert len(data.recommendable_items()) == 112


def test_no_cache_or_wrong_version_fails_closed_with_names(monkeypatch, tmp_path):
    offline_loader(monkeypatch, tmp_path, cdragon=False)
    catalog = _load_items()
    assert catalog.meta.availability == "unknown"
    data = StaticData()
    data._items = catalog
    assert data.recommendable_items() == []
    assert data.get_item("3074").name == "Ravenous Hydra"
    assert data.get_item("3074").item_class == "unknown"
    assert not catalog.pool_ids
    assert catalog.data_source == "ddragon_unverified"
    (tmp_path / "items_v5_16.22.1.json").write_text(
        json.dumps({"schema": 3, "meta": {"ddragon_version": "16.22.1",
        "availability": "verified_two_source"}, "items": {}}), encoding="utf-8")
    assert _load_items().meta.availability == "unknown"


def test_mismatched_cdragon_patch_and_schema2_cache_are_not_trusted(monkeypatch, tmp_path):
    offline_loader(monkeypatch, tmp_path, patch="16.24.1")
    (tmp_path / "items_v5_16.23.1.json").write_text(
        json.dumps({"schema": 2, "items": {"3074": {}}}), encoding="utf-8")
    catalog = _load_items()
    assert catalog.meta.availability == "unknown"
    assert StaticData().recommendable_items() == []


def test_conflicting_cost_downgrades_only_that_item(monkeypatch, tmp_path):
    from backend.static_data import loader
    observed = []
    monkeypatch.setattr(loader, "_report_item_source_conflict", lambda ident: observed.append(ident))
    offline_loader(monkeypatch, tmp_path, conflict=True)
    catalog = _load_items()
    assert catalog.meta.availability == "verified_two_source"
    assert catalog["3074"].item_class == "unknown"
    assert "3074" not in catalog.pool_ids
    assert len(catalog.pool_ids) == 180
    assert len(catalog.recommendable_ids) == 111
    assert observed == ["3074"]


def test_unverified_sources_hide_builds_and_expose_metadata(monkeypatch, tmp_path):
    """Recognition-only owned items must not leak into a recommended build."""
    from backend.api.server import _serialize_result
    from backend.models import ChampionMeta, GamePhase, GameSnapshot, StatVector
    from backend.workflow.pipeline import Pipeline

    offline_loader(monkeypatch, tmp_path, cdragon=False)
    data = StaticData()
    data._items = _load_items()
    data._champions = {
        "lux": ChampionMeta(id="lux", name="Lux", stats=StatVector(ap=0.9)),
    }
    monkeypatch.setattr(
        "backend.workflow.pipeline.get_all_personal_winrates", lambda _: {},
    )
    snapshot = GameSnapshot(
        game_id="offline", phase=GamePhase.IN_GAME,
        champion_id="lux", augment_choices=[], chosen_augments=[],
        purchased_items=["3074"], current_gold=5000, game_time=10.0,
        enemy_champion_ids=[],
    )
    result = Pipeline(data).run(snapshot)
    assert result is not None
    build = result.build_state
    assert build.full_build == []
    assert build.next_item_id is None
    assert build.boot_replacement is None
    assert build.alternatives == {}
    assert build.build_unavailable_reason == "item_availability_unknown"
    assert build.data_version["availability"] == "unknown"
    assert build.data_version["ddragon_version"] == "16.23.1"
    payload = _serialize_result(result, data)
    assert payload["build_state"]["next_item_id"] is None
    assert payload["build_state"]["build_unavailable_reason"] == "item_availability_unknown"
    assert payload["build_state"]["data_version"]["availability"] == "unknown"


def test_visible_outside_pool_items_emit_once_per_match_without_private_fields(monkeypatch, tmp_path):
    from backend.api import server

    offline_loader(monkeypatch, tmp_path)
    data = StaticData()
    data._items = _load_items()
    observed = []
    monkeypatch.setattr(
        server.event_log, "emit",
        lambda event, **fields: observed.append((event, fields)),
    )
    state = server.GameState()
    lcda = {"allPlayers": [{
        "summonerName": "do-not-log",
        "items": [
            {"slot": 0, "itemID": 226668},  # Reward, not a normal shop item.
            {"slot": 1, "itemID": 3074},    # Ordinary pool item.
            {"slot": 6, "itemID": 3340},    # Trinket slot must be ignored.
            {"slot": 2, "itemID": 9999999}, # Reject non-schema numeric length.
        ],
    }]}
    server._record_items_outside_pool(state, lcda, data)
    server._record_items_outside_pool(state, lcda, data)
    assert observed == [(
        "item_outside_pool", {"item_id": "226668", "class": "augment_reward"},
    )]
    assert "do-not-log" not in str(observed)
    state.reset()
    server._record_items_outside_pool(state, lcda, data)
    assert observed == [observed[0], observed[0]]


def test_legacy_offline_cache_recognizes_names_without_promoting_items(monkeypatch, tmp_path):
    from backend.static_data import loader

    offline_loader(monkeypatch, tmp_path, cdragon=False)
    (tmp_path / "items_16.23.1.json").write_text(
        json.dumps({
            "3074": {"name": "Ravenous Hydra", "cost": 3300, "stats": {},
                     "boots": False, "item_class": "final"},
        }), encoding="utf-8",
    )

    def unavailable(url, timeout=15):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(loader.requests, "get", unavailable)
    catalog = _load_items()
    assert catalog.meta.availability == "unknown"
    assert catalog.data_source == "legacy_unverified"
    assert catalog["3074"].name == "Ravenous Hydra"
    assert catalog["3074"].item_class == "unknown"
    data = StaticData()
    data._items = catalog
    assert data.recommendable_items() == []


def test_n1_warm_verified_cache_skips_slow_item_network(monkeypatch, tmp_path):
    """Cold desktop startup must not call a slow source for an exact verified cache."""
    from backend.static_data import loader

    offline_loader(monkeypatch, tmp_path)
    first = _load_items()
    assert first.meta.availability == "verified_two_source"
    assert first.data_source == "network"

    def unexpected_network(url, timeout=15):
        raise AssertionError(f"cached same-patch items triggered network: {url}")

    monkeypatch.setattr(loader.requests, "get", unexpected_network)
    cached = _load_items()
    assert cached.data_source == "cache"
    assert cached.meta.availability == "verified_two_source"
    assert cached.meta.cdragon_sha256 == first.meta.cdragon_sha256
    assert cached.pool_ids == first.pool_ids
    assert cached.recommendable_ids == first.recommendable_ids


def test_n1_corrupt_verified_cache_cannot_enable_shop_when_sources_fail(
    monkeypatch, tmp_path,
):
    """Cache-first still has to reject invalid proof before any shop advice."""
    from backend.static_data import loader

    offline_loader(monkeypatch, tmp_path)
    _load_items()
    cache_file = tmp_path / "items_v5_16.23.1.json"
    cached = json.loads(cache_file.read_text(encoding="utf-8"))
    cached["meta"]["cdragon_sha256"] = "not-a-source-proof"
    cache_file.write_text(json.dumps(cached), encoding="utf-8")

    def unavailable(url, timeout=15):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(loader.requests, "get", unavailable)
    result = _load_items()
    assert result.meta.availability == "unknown"
    assert not result.pool_ids
    assert not result.recommendable_ids
    data = StaticData()
    data._items = result
    assert data.recommendable_items() == []
