"""SCORE-84 offline tier-list contract: honest ranks, source coverage and no fabricated grades."""
from backend.engine.composite_score import CompositeRating, composite_rating
from backend.engine.global_ranker import rank_rated_catalog, rank_augment_roster
from backend.models import AugmentData, AugmentTier, ChampionMeta, ItemData, StatVector


def augment(aid, tier=AugmentTier.GOLD, *, ap=0.8, ad=0.0):
    return AugmentData(aid, aid, tier, "", StatVector(ap=ap, ad=ad),
                       provenance="override")


def rated(score, precise):
    return CompositeRating(
        score=score, confidence=0.0, sample_size=0,
        performance=None, synergy=7.0, context=5.0,
        evidence_source="none", ranking_value=precise,
    )


def test_private_precision_while_public_score_rounded():
    a = composite_rating(8.04, 5.0)
    b = composite_rating(8.02, 5.0)
    assert a.score == b.score
    assert a.ranking_value > b.ranking_value
    assert "ranking_value" not in a.as_dict()
    assert "wins" not in a.as_dict()


def test_score_ties_and_rank_on_unrounded_fitness_without_inventing_tier_grade():
    rankings = rank_rated_catalog([
        (augment("b"), rated(8.7, 8.703)),
        (augment("a"), rated(8.7, 8.745)),
        (augment("c"), rated(8.7, 8.703)),
    ])
    assert [(r.augment_id, r.rank, r.score) for r in rankings] == [
        ("a", 1, 8.7), ("b", 2, 8.7), ("c", 2, 8.7),
    ]
    assert all(r.grade is None for r in rankings)
    assert all(r.assessed_count == 3 and r.catalog_count == 3 for r in rankings)


def test_same_rarity_only_and_no_fake_rank_for_unmodelled_or_bad_scores():
    placements = rank_rated_catalog([
        (augment("silver", AugmentTier.SILVER), rated(9.9, 9.9)),
        (augment("gold"), rated(6.0, 6.0)),
        (augment("unknown", ap=0.0), rated(None, None)),
        (augment("broken"), rated(6.0, float("nan"))),
        (augment("gold"), rated(6.0, 6.0)),
    ])
    assert [(r.augment_id, r.rank, r.assessed_count, r.catalog_count)
            for r in placements] == [
        ("silver", 1, 1, 1), ("gold", 1, 1, 3),
    ]
    assert all(r.scope == "same_rarity_modelled_catalog" for r in placements)


def test_full_champion_base_catalog_and_confirmed_augments_context():
    champion = ChampionMeta("lux", "Lux", StatVector(ap=0.9, ad=0.2),
                            role="mage")
    pool = [augment("ap"), augment("ad", ap=0.0, ad=0.9),
            augment("silver", AugmentTier.SILVER, ap=0.6),
            augment("no_model", ap=0.0)]
    baseline = rank_augment_roster(champion, pool, [])
    assert len(baseline) == 3
    assert {x.augment_id for x in baseline} == {"ap", "ad", "silver"}
    assert all(0 <= x.score <= 10 for x in baseline)
    assert all(x.grade is None for x in baseline)

    # Only independently confirmed augments change synergy and eligibility.
    adjusted = rank_augment_roster(champion, pool, [pool[0]])
    assert "ap" not in [x.augment_id for x in adjusted]
    assert {x.augment_id for x in adjusted} == {"ad", "silver"}
    assert [x.assessed_count for x in adjusted
            if x.rarity == AugmentTier.GOLD] == [1]


def test_observed_item_stats_shift_contextual_order_without_changing_base():
    champion = ChampionMeta("synthetic", "Synthetic",
                            StatVector(ap=0.6, ad=0.6), role="fighter")
    pool = [augment("ap", ap=0.8, ad=0.0),
            augment("ad", ap=0.0, ad=0.8)]
    baseline = rank_augment_roster(champion, pool, [])
    ap_item = ItemData("item", "Synthetic", 3000,
                       StatVector(ap=1.0), item_class="final")
    with_item = rank_augment_roster(champion, pool, [], owned_items=[ap_item])
    assert {x.augment_id for x in baseline} == {x.augment_id for x in with_item}
    a = {x.augment_id: x for x in baseline}
    b = {x.augment_id: x for x in with_item}
    assert (b["ap"].ranking_value - a["ap"].ranking_value) > (
        b["ad"].ranking_value - a["ad"].ranking_value)
    # A named item with unknown source eligibility must not contribute.
    unknown = ItemData("bad", "Unknown", 3000, StatVector(ap=1.0),
                       item_class="unknown")
    assert rank_augment_roster(champion, pool, [], owned_items=[unknown]) == baseline


def test_no_rated_rows_when_champion_unmodelled():
    champion = ChampionMeta("none", "None", StatVector(), role="")
    assert rank_augment_roster(champion, [augment("ap")], []) == []
