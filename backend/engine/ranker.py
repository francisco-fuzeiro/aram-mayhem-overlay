"""Augment ranking in a comparable 0.0–10.0 experimental score range."""
import logging

from backend.models import (
    ChampionMeta, AugmentData, ItemData, AugmentRecommendation,
)
from backend.engine.augment_rating import rate_augment
from backend.engine.scoring import score_item
from backend.engine.label import derive_label, derive_explanation

logger = logging.getLogger("aram-oracle.engine.ranker")

# Provisional heuristic reroll threshold; validate against offline match samples.
REROLL_THRESHOLD = 4.0


def rank_augments(
    champion: ChampionMeta,
    choices: list[AugmentData],
    existing: list[AugmentData],
    all_items: list[ItemData],
    personal_winrates: dict[str, tuple[int, int]] | None = None,
    enemies: list[ChampionMeta] | None = None,
    use_personal_performance: bool = False,
) -> list[AugmentRecommendation]:
    """Rank cards by composite score, independent of offer-best normalization.

    Match evidence requires an explicit opt-in and at least 5 local matches.
    Score is not a win rate or a prediction of winning.
    """
    results = []
    for aug in choices:
        record = personal_winrates.get(aug.id) if personal_winrates else None
        rating = rate_augment(
            champion, aug, existing, enemies=enemies,
            personal_record=record, allow_empirical=use_personal_performance,
        )
        label = derive_label(champion, aug)
        explanation = derive_explanation(champion, aug)
        core_items = _suggest_core_items(champion, aug, existing, all_items)

        results.append(AugmentRecommendation(
            augment_id=aug.id,
            augment_name=aug.name,
            score=rating.score,
            label=label,
            core_items=core_items,
            explanation=explanation,
            confidence=rating.confidence,
            sample_size=rating.sample_size,
            components=rating.as_dict()["components"],
        ))

    return sorted(results, key=lambda r: (-r.score, r.augment_name))


def should_reroll(
    recommendations: list[AugmentRecommendation],
    champion: ChampionMeta,
    existing: list[AugmentData],
) -> tuple[bool, str]:
    """Simple absolute-fit warning; does not estimate unseen reroll outcomes."""
    if not recommendations:
        return False, ""
    best = recommendations[0]
    if best.score < REROLL_THRESHOLD:
        logger.debug("Weak augment offer: highest composite score %.1f/10", best.score)
        return (
            True,
            f"Best available option scores {best.score:.1f}/10 in the "
            "experimental model. Consider rerolling.",
        )
    return False, ""


def _suggest_core_items(
    champion: ChampionMeta,
    augment: AugmentData,
    existing: list[AugmentData],
    all_items: list[ItemData],
    n: int = 3,
) -> list[str]:
    """Returns top-n item IDs that synergize with champion + this augment."""
    scored = sorted(
        all_items,
        key=lambda item: score_item(champion, item, existing + [augment]),
        reverse=True,
    )
    result = []
    boots_seen = False
    for item in scored:
        if item.boots:
            if boots_seen:
                continue
            boots_seen = True
        result.append(item.id)
        if len(result) == n:
            break
    return result
