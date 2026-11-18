"""M2/E3 red-first regressions for unrated augments and reroll safety."""

import json

from backend.api.server import _serialize_result
from backend.engine.augment_rating import rate_augment
from backend.engine.ranker import rank_augments, should_reroll
from backend.models import (
    AugmentData, AugmentTier, BuildState, ChampionMeta, GamePhase,
    PipelineResult, StatVector,
)
from backend.static_data.loader import StaticData, _parse_description_to_stats


def champion():
    return ChampionMeta("lux", "Lux", StatVector(ap=0.9, cdr=0.8), role="mage")


def augment(name, **stats):
    return AugmentData(name, name, AugmentTier.GOLD, "",
                       StatVector(**stats))


def unrated_offer():
    return [
        AugmentData(name, name, AugmentTier.GOLD, "",
                    _parse_description_to_stats("", name))
        for name in ("Impassable", "Tooth Fairy", "Shark Bait")
    ]


def test_real_unknown_offer_all_none_and_no_reroll():
    cards = unrated_offer()
    assert all(not card.modelled for card in cards)
    ratings = [rate_augment(champion(), card, []) for card in cards]
    assert [rating.score for rating in ratings] == [None, None, None]
    recommendations = rank_augments(champion(), cards, [], [])
    assert [r.score for r in recommendations] == [None, None, None]
    assert should_reroll(recommendations, champion(), []) == (False, "")


def test_three_known_low_scored_augments_may_still_suggest_reroll():
    cards = [
        augment("weak-ad", ad=0.1),
        augment("weak-crit", crit=0.05),
        augment("weak-lethality", lethality=0.1),
    ]
    recommendations = rank_augments(champion(), cards, [], [])
    assert len(recommendations) == 3
    assert all(r.score is not None and r.score < 4 for r in recommendations)
    reroll, reason = should_reroll(recommendations, champion(), [])
    assert reroll
    assert "reroll" in reason.lower()


def test_two_known_cards_never_trigger_reroll():
    cards = [augment("weak-ad", ad=0.1), augment("weak-crit", crit=0.05)]
    recommendations = rank_augments(champion(), cards, [], [])
    assert should_reroll(recommendations, champion(), []) == (False, "")


def test_incomplete_or_unrated_three_card_offer_never_rerolls():
    cards = [augment("weak-ad", ad=0.1), augment("weak-crit", crit=0.05),
             unrated_offer()[0]]
    recommendations = rank_augments(champion(), cards, [], [])
    assert should_reroll(recommendations, champion(), []) == (False, "")
    assert len({r.augment_id for r in recommendations}) == 3


def test_duplicate_identified_card_is_not_a_valid_three_card_offer():
    card = augment("weak-ad", ad=0.1)
    recommendations = rank_augments(champion(), [card, card, card], [], [])
    assert should_reroll(recommendations, champion(), []) == (False, "")


def test_valid_scores_sorted_before_missing_scores_and_stay_numeric():
    cards = [unrated_offer()[0], augment("weak-ad", ad=0.1),
             augment("strong-ap", ap=0.9)]
    recommendations = rank_augments(champion(), cards, [], [])
    assert recommendations[0].augment_id == "strong-ap"
    assert recommendations[1].augment_id == "weak-ad"
    assert recommendations[2].score is None
    assert recommendations[0].score > recommendations[1].score


def test_negative_contribution_is_modelled_not_missing_data():
    card = augment("negative", ad=-0.1)
    assert card.modelled
    assert isinstance(rate_augment(champion(), card, []).score, float)


def test_api_serializes_null_without_nan_or_fake_scores():
    cards = unrated_offer()
    recommendations = rank_augments(champion(), cards, [], [])
    data = StaticData()
    data._champions = {"lux": champion()}
    payload = _serialize_result(PipelineResult(
        phase=GamePhase.IN_GAME, recommendations=recommendations,
        build_state=BuildState(champion_id="lux"), suggest_reroll=False,
    ), data)
    assert [r["score"] for r in payload["recommendations"]] == [None, None, None]
    serialized = json.dumps(payload, allow_nan=False)
    assert '"score": null' in serialized
    assert "NaN" not in serialized
