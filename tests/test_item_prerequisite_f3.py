"""F3/#49: evidence-bound shop eligibility, not inferred quest entitlements.

All changed source fields are synthetic fixture mutations. No player data is
used and no item access is inferred from seeing or hovering an augment.
"""
import copy
import json

import pytest

from backend.static_data.item_policy import classify_item, load_item_overrides
from backend.static_data.loader import StaticData, _load_items
from tests import test_item_pool_b1 as b1


def _fixture_item(item_id="3074"):
    dd, cd, _ = b1.sources()
    return copy.deepcopy(dd[item_id]), copy.deepcopy(cd[item_id])


def test_currency_cost_without_currency_name_is_conditional_not_shop_final():
    dd, cd = _fixture_item()
    assert classify_item("3074", dd, cd, {"force_class": {}}) == "final"
    cd["requiredBuffCurrencyName"] = ""
    cd["requiredBuffCurrencyCost"] = 1
    assert classify_item("3074", dd, cd, {"force_class": {}}) == "conditional"
    cd["requiredBuffCurrencyCost"] = 0
    assert classify_item("3074", dd, cd, {"force_class": {}}) == "final"


@pytest.mark.parametrize("value", [-1, 1.5, "1", True, None])
def test_uncertain_or_malformed_currency_cost_cannot_be_assumed_free(value):
    dd, cd = _fixture_item()
    cd["requiredBuffCurrencyName"] = ""
    cd["requiredBuffCurrencyCost"] = value
    assert classify_item("3074", dd, cd, {"force_class": {}}) != "final"


def test_unknown_item_metadata_with_special_recipe_never_enters_shop_pool():
    dd, cd = _fixture_item()
    cd["specialRecipe"] = 12345
    assert classify_item("3074", dd, cd, {"force_class": {}}) == "conditional"


def test_manual_overrides_cannot_promote_quest_reward_into_shop():
    dd, cd = _fixture_item("226668")
    overrides = {
        "force_class": {
            "226668": {
                "class": "final", "reason": "synthetic unsafe example",
                "source": "synthetic fixture",
            }
        }
    }
    assert classify_item("226668", dd, cd, overrides) == "augment_reward"


@pytest.mark.parametrize("promoted", ["final", "boots_tier2", "component", "boots_tier1"])
def test_invalid_positive_item_overrides_rejected_at_load(tmp_path, promoted):
    file = tmp_path / "item_overrides.json"
    file.write_text(json.dumps({
        "version": "synthetic.1",
        "force_class": {
            "226668": {
                "class": promoted, "reason": "fixture",
                "source": "synthetic test",
            }
        }
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="only exclude"):
        load_item_overrides(file)


def test_conditional_currency_item_absent_from_loaded_build_candidates(monkeypatch, tmp_path):
    original = b1.sources

    def gated_catalog():
        dd, cd, raw = original()
        cd = copy.deepcopy(cd)
        raw = copy.deepcopy(raw)
        column = raw["fields"].index("requiredBuffCurrencyCost")
        for row in raw["rows"]:
            if row[0] == 3074:
                row[column] = 1
                break
        cd["3074"]["requiredBuffCurrencyCost"] = 1
        assert not cd["3074"]["requiredBuffCurrencyName"]
        return dd, cd, raw

    monkeypatch.setattr(b1, "sources", gated_catalog)
    b1.offline_loader(monkeypatch, tmp_path)
    catalog = _load_items()
    data = StaticData()
    data._items = catalog

    assert catalog.meta.availability == "verified_two_source"
    assert catalog.classes["3074"] == "conditional"
    assert "3074" not in catalog.pool_ids
    assert "3074" not in catalog.recommendable_ids
    assert "3074" not in {item.id for item in data.recommendable_items()}
    assert "226668" not in catalog.recommendable_ids
    # End-to-end: build selection, next purchase, and swaps see only the
    # filtered catalog, never an unearned / conditional item.
    from backend.models import ChampionMeta, GamePhase, GameSnapshot, StatVector
    from backend.workflow.pipeline import Pipeline

    data._champions = {
        "lux": ChampionMeta(id="lux", name="Lux", stats=StatVector(ap=0.9)),
    }
    monkeypatch.setattr(
        "backend.workflow.pipeline.get_all_personal_winrates", lambda _: {},
    )
    snapshot = GameSnapshot(
        game_id="synthetic-shop-prerequisite", phase=GamePhase.IN_GAME,
        champion_id="lux", augment_choices=[], chosen_augments=[],
        purchased_items=[], current_gold=5000, game_time=100,
        enemy_champion_ids=[],
    )
    actual = Pipeline(data).run(snapshot)
    assert actual is not None
    assert "3074" not in actual.build_state.full_build
    assert actual.build_state.next_item_id != "3074"
    assert actual.build_state.boot_replacement is None
    # All other fixture candidates retain the existing two-source proof.
    assert len(data.recommendable_items()) == 110


def test_old_policy_cache_cannot_promote_unsafe_item_when_sources_unavailable(
    monkeypatch, tmp_path,
):
    b1.offline_loader(monkeypatch, tmp_path)
    fresh = _load_items()
    assert fresh.meta.availability == "verified_two_source"

    cache_file = tmp_path / "items_v5_16.23.1.json"
    cached = json.loads(cache_file.read_text(encoding="utf-8"))
    cached["meta"]["policy_version"] = "item_pool_v2"
    cache_file.write_text(json.dumps(cached), encoding="utf-8")

    # Versioned shop rules changed, so historic proof no longer authorizes
    # new recommendations if current CDragon patch data is unavailable.
    b1.offline_loader(monkeypatch, tmp_path, cdragon=False)
    old = _load_items()
    data = StaticData()
    data._items = old
    assert old.meta.availability == "unknown"
    assert not old.pool_ids
    assert data.recommendable_items() == []
