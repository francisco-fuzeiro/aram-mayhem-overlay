"""P0 field fix: DD 16.23.1 omits ``from`` on every base component.

Real match (23/11): Long Sword 1036 was classed ``unknown`` because DD has no
``from`` key while CDragon publishes ``from: []``; the inventory then blocked
build.next_item with ``inventory_unknown``. The DD omission means "no recipe",
exactly like the terminal ``into`` omission. A non-empty CD recipe still fails.
Shapes copied from the public 16.23 records (no game data, no network).
"""
from backend.static_data.item_policy import classify_item, sources_agree

DD_LONG_SWORD = {
    "name": "Long Sword", "gold": {"base": 350, "total": 350, "purchasable": True},
    "into": ["1053", "3133"], "tags": ["Damage", "Lane"], "maps": {"12": True},
}
CD_LONG_SWORD = {
    "id": 1036, "inStore": True, "from": [], "to": [1053, 3133],
    "requiredChampion": "", "requiredAlly": "", "requiredBuffCurrencyName": "",
    "requiredBuffCurrencyCost": 0, "specialRecipe": 0, "priceTotal": 350,
    "displayInItemSets": True,
}


def test_base_component_without_dd_from_agrees_with_empty_cd_from():
    assert sources_agree(DD_LONG_SWORD, CD_LONG_SWORD) is True
    assert classify_item("1036", DD_LONG_SWORD, CD_LONG_SWORD, {"force_class": {}}) == "component"


def test_missing_dd_from_never_matches_a_real_cd_recipe():
    cd = {**CD_LONG_SWORD, "from": [1036]}
    assert sources_agree(DD_LONG_SWORD, cd) is False
    cd = {**CD_LONG_SWORD}
    del cd["from"]
    assert sources_agree(DD_LONG_SWORD, cd) is False
    assert sources_agree({**DD_LONG_SWORD, "from": None}, CD_LONG_SWORD) is False


def test_item_cache_policy_is_bumped_so_old_unknown_classes_rebuild():
    from backend.static_data.item_policy import ITEM_POLICY_VERSION
    assert ITEM_POLICY_VERSION == "item_pool_v5"
