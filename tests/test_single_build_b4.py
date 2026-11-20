"""B4 contracts: one selected style, stable ranking and chosen-augment reactions."""

import backend.engine.build_suggester as build_engine
from backend.models import AugmentData, AugmentTier, ChampionMeta, ItemData, StatVector


def _item(ident: str, *, ap: float = 0.0, ad: float = 0.0) -> ItemData:
    return ItemData(
        id=ident, name=f"Item {ident}", cost=2800,
        stats=StatVector(ap=ap, ad=ad), item_class="final",
    )


def _champion() -> ChampionMeta:
    return ChampionMeta(
        id="synthetic", name="Synthetic", role="marksman",
        stats=StatVector(ad=0.85),
    )


def test_suggest_build_only_ranks_selected_style(monkeypatch):
    seen_styles = []
    original_rank = build_engine._rank_items

    def recording_rank(champion, augments, available, enemies, allies, direction):
        seen_styles.append(direction)
        return original_rank(champion, augments, available, enemies, allies, direction)

    monkeypatch.setattr(build_engine, "_rank_items", recording_rank)
    result = build_engine.suggest_build(
        _champion(), [], [], 5000, [_item("3101", ad=0.8)],
        build_style="Damage",
    )
    assert seen_styles == ["Damage"]
    assert result.selected_style == "Damage"
    assert result.alternatives == {}


def test_all_styles_keep_compatibility_without_alternative_builds():
    items = [_item("3101", ad=0.8), _item("3102", ap=0.8)]
    for style in (*build_engine.BUILD_STYLES, "unsupported"):
        result = build_engine.suggest_build(
            _champion(), [], [], 0, items, build_style=style,
        )
        assert result.selected_style == (style if style in build_engine.BUILD_STYLES else "Balanced")
        assert result.alternatives == {}
        assert result.next_item_id == result.full_build[0]


def test_synthetic_ap_augment_changes_single_full_build_and_reverts_exactly():
    # Synthetic Data Dragon-like positive AP flags are deliberately test-only.
    raw_stats = {
        "3101": {"FlatMagicDamageMod": 0},
        "3102": {"FlatMagicDamageMod": 0},
        "3103": {"FlatMagicDamageMod": 100},
        "3104": {"FlatMagicDamageMod": 90},
    }
    items = [
        _item("3102", ad=0.9),
        _item("3104", ap=0.9),
        _item("3101", ad=1.0),
        _item("3103", ap=1.0),
    ]
    augment = AugmentData(
        id="synthetic-ap", name="Synthetic AP", tier=AugmentTier.GOLD,
        description="Synthetic chosen AP contribution", contribution=StatVector(ap=12.0),
    )

    def suggest(active):
        return build_engine.suggest_build(
            _champion(), active, [], 4500, items,
            build_size=2, build_style="Balanced",
        )

    original = suggest([])
    changed = suggest([augment])
    reverted = suggest([])

    ap_count = lambda ids: sum(raw_stats[ident]["FlatMagicDamageMod"] > 0 for ident in ids)
    assert changed.full_build != original.full_build
    assert ap_count(changed.full_build) >= ap_count(original.full_build) + 1
    assert changed.chosen_augments == ["synthetic-ap"]
    assert original.chosen_augments == []
    assert reverted.full_build == original.full_build
    assert reverted.next_item_id == original.next_item_id
    assert reverted.alternatives == changed.alternatives == {}


def test_equal_scores_resolve_by_id_independent_of_catalog_order():
    first = _item("3101", ad=0.8)
    second = _item("3102", ad=0.8)
    one = build_engine.suggest_build(
        _champion(), [], [], 4000, [second, first], build_size=1,
    )
    two = build_engine.suggest_build(
        _champion(), [], [], 4000, [first, second], build_size=1,
    )
    assert one.full_build == two.full_build == ["3101"]
    assert one.alternatives == two.alternatives == {}
