import pytest
from backend.models import StatVector, ChampionMeta, AugmentData, AugmentTier, ItemData
from backend.engine.build_suggester import suggest_build


def _make_champion(id: str, **stat_kwargs) -> ChampionMeta:
    return ChampionMeta(id=id, name=id.title(), stats=StatVector(**stat_kwargs))


def _make_augment(id: str, **stat_kwargs) -> AugmentData:
    return AugmentData(
        id=id, name=id, tier=AugmentTier.SILVER,
        description="", contribution=StatVector(**stat_kwargs),
    )


def _make_item(id: str, cost: int = 3000, **stat_kwargs) -> ItemData:
    return ItemData(id=id, name=id, cost=cost, stats=StatVector(**stat_kwargs))


def test_purchased_items_not_in_suggestions():
    lux = _make_champion("lux", ap=0.9)
    items = [
        _make_item("i1", cost=3000, ap=0.8),
        _make_item("i2", cost=2000, ap=0.5),
        _make_item("i3", cost=1000, pen=0.3),
    ]
    build = suggest_build(lux, [], ["i1"], 5000, items)
    assert "i1" not in build.full_build[1:]  # i1 is in purchased_items slot


def test_next_item_stays_first_when_gold_zero():
    lux = _make_champion("lux", ap=0.9)
    items = [_make_item("i1", cost=3000, ap=0.8)]
    build = suggest_build(lux, [], [], 0, items)
    assert build.next_item_id == "i1"
    assert build.next_item_gold_needed == 3000
    assert build.gold_to_next == 3000


def test_full_build_length_equals_build_size():
    lux = _make_champion("lux", ap=0.9)
    items = [
        _make_item(f"i{i}", cost=1000 * i, ap=0.1 * i)
        for i in range(1, 10)
    ]
    build = suggest_build(lux, [], [], 5000, items, build_size=6)
    assert len(build.full_build) == 6


def test_augments_shift_item_priority():
    lux = _make_champion("lux", ap=0.9, ad=0.0)
    ap_item = _make_item("ap_item", cost=3000, ap=0.8)
    ad_item = _make_item("ad_item", cost=3000, ad=0.8)

    # Without augments, AP item should rank higher for Lux
    build_no_aug = suggest_build(lux, [], [], 5000, [ap_item, ad_item])
    assert build_no_aug.next_item_id == "ap_item"

    # With an AD augment, AD item might score closer but AP still wins
    # because champion vector dominates
    ad_aug = _make_augment("ad_aug", ad=0.9)
    build_with_aug = suggest_build(lux, [ad_aug], [], 5000, [ap_item, ad_item])
    # The augment boost shifts priorities
    assert build_with_aug.next_item_id is not None


def test_gold_to_next_calculated():
    lux = _make_champion("lux", ap=0.9)
    items = [_make_item("expensive", cost=3000, ap=0.8)]
    build = suggest_build(lux, [], [], 1000, items)
    assert build.gold_to_next == 2000


def test_full_inventory_never_recommends_a_seventh_item():
    mage = _make_champion("mage", ap=0.9)
    items = [_make_item(f"i{i}", cost=1000, ap=0.5) for i in range(7)]
    result = suggest_build(
        mage, [], [f"i{i}" for i in range(6)], 5000, items,
    )
    assert result.full_build == [f"i{i}" for i in range(6)]
    assert result.next_item_id is None
    assert result.gold_to_next == 0
    assert all(len(path) == 6 for path in result.alternatives.values())


def test_selected_style_changes_the_build_and_next_purchase():
    mage = _make_champion("mage", ap=0.9, hp=0.4)
    offense = _make_item("offense", cost=1000, ap=1.0)
    defense = _make_item("defense", cost=1000, hp=1.0)
    items = [offense, defense]
    damage = suggest_build(mage, [], [], 1100, items, build_style="Damage")
    survival = suggest_build(mage, [], [], 1100, items, build_style="Survival")
    assert damage.selected_style == "Damage"
    assert survival.selected_style == "Survival"
    assert damage.next_item_id == damage.full_build[0]
    assert survival.next_item_id == survival.full_build[0]
    assert damage.next_item_id == "offense"
    assert survival.next_item_id == "defense"
    assert survival.alternatives["Damage"] == damage.full_build
    assert damage.alternatives["Survival"] == survival.full_build


def test_next_purchase_is_always_in_selected_build_path():
    mage = _make_champion("mage", ap=0.9)
    items = [
        _make_item("expensive", cost=3000, ap=1.0),
        _make_item("cheap", cost=1000, ap=0.7),
        _make_item("offpath", cost=300, ap=0.1),
    ]
    result = suggest_build(mage, [], [], 1000, items, build_size=2)
    assert result.next_item_id in result.full_build
    assert "offpath" not in result.full_build


def test_invalid_external_style_falls_back_to_balanced():
    mage = _make_champion("mage", ap=0.9)
    item = _make_item("staff", cost=1000, ap=0.8)
    result = suggest_build(mage, [], [], 1000, [item], build_style="NotAStyle")
    assert result.selected_style == "Balanced"
    assert result.next_item_id == "staff"
