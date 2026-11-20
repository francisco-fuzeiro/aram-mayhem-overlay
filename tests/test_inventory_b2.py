"""B2 canonical inventory and recursive purchase recipes (offline contract)."""
from collections import Counter
import json
from pathlib import Path

import pytest

from backend.models import ChampionMeta, EnemyState, GamePhase, GameSnapshot, ItemData, StatVector
from backend.engine.build_suggester import suggest_build
from backend.engine.inventory import INVENTORY_SLOTS, Inventory, build_inventory, remaining_cost
from backend.static_data.loader import StaticData, _load_items
from backend.workflow.pipeline import Pipeline
from tests.test_item_pool_b1 import offline_loader


FIXTURES = Path(__file__).parent / "fixtures" / "items"


def _data(monkeypatch, tmp_path):
    offline_loader(monkeypatch, tmp_path)
    data = StaticData()
    data._items = _load_items()
    raw = json.loads((FIXTURES / "ddragon_items_16.23.1_compact.json").read_text(encoding="utf-8"))["items"]
    data._all_item_names = {key: row["n"] for key, row in raw.items()}
    return data


def _price(item_id):
    raw = json.loads((FIXTURES / "ddragon_items_16.23.1_compact.json").read_text(encoding="utf-8"))["items"]
    return raw[item_id]["g"]


def test_item_recipes_preserve_duplicate_components_and_final_class(monkeypatch, tmp_path):
    data = _data(monkeypatch, tmp_path)
    assert data.get_item("3077").from_ids == ("1036", "1036")
    assert data.get_item("3074").from_ids == ("3077", "1053", "3133")
    assert "3074" in data.get_item("3077").into_ids
    assert data.get_item("3074").final
    assert not data.get_item("3077").final
    assert not data.get_item("1001").final
    assert all(item.final for item in data.recommendable_items())
    assert not data.get_item("226668").final


@pytest.mark.parametrize("source,expected", [
    ("773074", "3074"), ("3074", "3074"), ("3040", "3003"),
    ("3042", "3004"), ("3121", "3119"), ("999999", "999999"),
])
def test_canonical_item_ids_use_exact_name_or_verified_special_recipe(
    monkeypatch, tmp_path, source, expected,
):
    data = _data(monkeypatch, tmp_path)
    assert data.canonical_item_id(source) == expected


def test_special_recipes_survive_a_verified_cache_reload(monkeypatch, tmp_path):
    data = _data(monkeypatch, tmp_path)
    assert data.canonical_item_id("3040") == "3003"
    offline_loader(monkeypatch, tmp_path, cdragon=False)
    cached = StaticData()
    cached._items = _load_items()
    assert cached.item_data_source == "cache"
    assert cached.canonical_item_id("3040") == "3003"
    assert cached.canonical_item_id("3042") == "3004"
    assert cached.canonical_item_id("3121") == "3119"
    assert cached.get_item("3077").from_ids == ("1036", "1036")
    assert cached.get_item("3074").from_ids == ("3077", "1053", "3133")
    assert "3074" in cached.get_item("3077").into_ids


def test_name_alias_requires_exact_display_name(monkeypatch, tmp_path):
    data = _data(monkeypatch, tmp_path)
    data._all_item_names["773074"] = "RAVENOUS HYDRA"
    assert data.canonical_item_id("773074") == "773074"
    data._all_item_names["773074"] = "Ravenous Hydra"
    assert data.canonical_item_id("773074") == "3074"


def test_canonical_unknown_or_unverified_ids_never_become_purchase_proof(monkeypatch, tmp_path):
    offline_loader(monkeypatch, tmp_path, cdragon=False)
    data = StaticData()
    data._items = _load_items()
    data._all_item_names = {"773074": "Ravenous Hydra"}
    assert data.canonical_item_id("773074") == "773074"
    assert not data.recommendable_items()


def test_inventory_six_physical_slots_with_separate_build_finals(monkeypatch, tmp_path):
    data = _data(monkeypatch, tmp_path)
    inventory = build_inventory(["1036", "1001", "3074", "226668"], data)
    assert inventory == Inventory(
        finals=("3074",), components=("1036", "1001"), other=("226668",),
    )
    assert inventory.used_slots == 4
    assert inventory.free_slots == 2
    assert INVENTORY_SLOTS == 6
    assert build_inventory(["1036"] * 6, data).free_slots == 0


def test_inventory_canonicalizes_owned_variants_but_rewards_still_occupy_slots(monkeypatch, tmp_path):
    data = _data(monkeypatch, tmp_path)
    inventory = build_inventory(["773074", "3040", "226668", "999999"], data)
    assert inventory.finals == ("3074", "3003")
    assert inventory.components == ()
    assert inventory.other == ("226668", "999999")
    assert inventory.free_slots == 2


@pytest.mark.parametrize("owned,discount,consumed", [
    ({"3077": 1}, {"3077": 1}, {"3077": 1}),
    ({"1036": 2}, {"1036": 2}, {"1036": 2}),
    ({"1036": 3}, {"1036": 3}, {"1036": 3}),
])
def test_hydra_recursive_recipe_cost_uses_fixture_prices_only_once(
    monkeypatch, tmp_path, owned, discount, consumed,
):
    data = _data(monkeypatch, tmp_path)
    original = Counter(owned)
    gold, used = remaining_cost("3074", original, data)
    assert used == Counter(consumed)
    assert gold == _price("3074") - sum(_price(k) * count for k, count in discount.items())
    assert original == Counter(owned)


def test_hydra_uses_tiamat_instead_of_also_consuming_its_long_swords(monkeypatch, tmp_path):
    data = _data(monkeypatch, tmp_path)
    gold, consumed = remaining_cost("3074", Counter({"3077": 1, "1036": 2}), data)
    # Both longs are still usable in the OTHER branches (1053 and 3133).
    assert gold == _price("3074") - _price("3077") - 2 * _price("1036")
    assert consumed == Counter({"3077": 1, "1036": 2})


def test_hydra_cannot_reuse_one_long_sword_across_recipe_branches(monkeypatch, tmp_path):
    data = _data(monkeypatch, tmp_path)
    gold, consumed = remaining_cost("3074", Counter({"1036": 1}), data)
    assert gold == _price("3074") - _price("1036")
    assert consumed == Counter({"1036": 1})


def test_owned_target_item_is_fully_paid_and_consumed(monkeypatch, tmp_path):
    data = _data(monkeypatch, tmp_path)
    gold, consumed = remaining_cost("3074", Counter({"3074": 1, "1036": 2}), data)
    assert gold == 0
    assert consumed == Counter({"3074": 1})


def test_full_build_has_six_owned_finals_and_no_seventh_purchase(monkeypatch, tmp_path):
    data = _data(monkeypatch, tmp_path)
    owned = ["3074", "3003", "3004", "3119", "3006", "3047"]
    assert all(data.get_item(item_id).final for item_id in owned)
    inventory = build_inventory(owned, data)
    champion = ChampionMeta(id="lux", name="Lux", stats=StatVector(ap=0.9))
    result = suggest_build(champion, [], owned, 5000, data.recommendable_items(), inventory=inventory)
    assert result.full_build == owned
    assert result.next_item_id is None


def test_build_slots_ignore_components_and_rewards_while_preserving_physical_inventory(
    monkeypatch, tmp_path,
):
    data = _data(monkeypatch, tmp_path)
    owned = ["1036", "1001", "3074", "226668"]
    inventory = build_inventory(owned, data)
    champion = ChampionMeta(id="lux", name="Lux", stats=StatVector(ap=0.9))
    result = suggest_build(champion, [], owned, 0, data.recommendable_items(), inventory=inventory)
    assert result.full_build[0] == "3074"
    assert len(result.full_build) == 6
    assert "1036" not in result.full_build
    assert "1001" not in result.full_build
    assert "226668" not in result.full_build
    assert result.purchased_items == owned


def test_pipeline_canonicalizes_enemy_items_and_keeps_item_pool_gate(monkeypatch, tmp_path):
    data = _data(monkeypatch, tmp_path)
    data._champions = {
        "lux": ChampionMeta(id="lux", name="Lux", stats=StatVector(ap=0.9)),
    }
    monkeypatch.setattr("backend.workflow.pipeline.get_all_personal_winrates", lambda _: {})
    original_get_item = data.get_item
    observed_lookups = []

    def observe_item(item_id):
        observed_lookups.append(item_id)
        return original_get_item(item_id)

    data.get_item = observe_item
    snapshot = GameSnapshot(
        game_id="b2-offline", phase=GamePhase.IN_GAME,
        champion_id="lux", augment_choices=[], chosen_augments=[],
        purchased_items=["773074", "1036", "226668"], current_gold=0, game_time=20,
        enemy_champion_ids=["lux"],
        enemy_states=[EnemyState("lux", ["3040"])],
    )
    result = Pipeline(data).run(snapshot)
    assert result is not None
    assert result.build_state.full_build[0] == "3074"
    assert "1036" not in result.build_state.full_build
    assert "226668" not in result.build_state.full_build
    assert result.build_state.data_version["availability"] == "verified_two_source"
    assert "3003" in observed_lookups  # Special recipe alias of enemy 3040.
