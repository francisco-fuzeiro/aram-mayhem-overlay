"""Experimental private per-champion augment roster ranks.

A relative, same-rarity heuristic. Does not claim empirically calibrated OP/S/A
tiers, win-rate probability or Riot product approval. No gameplay capture.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math

from backend.engine.augment_rating import rate_augment
from backend.models import AugmentTier, StatVector
from backend.engine.team_context import EnemyThreatProfile, AllyTeamProfile

_RARITIES = (AugmentTier.SILVER, AugmentTier.GOLD, AugmentTier.PRISMATIC)
_TIE_EPSILON = 0.02  # Differences below this are not actionable precision.


@dataclass(frozen=True)
class AugmentPlacement:
    augment_id: str
    augment_name: str
    rarity: AugmentTier
    score: float
    rank: int
    assessed_count: int
    catalog_count: int
    confidence: float
    sample_size: int
    ranking_value: float
    grade: str | None = None  # Uncalibrated; do not guess OP/S/A/B/C/D/E.
    scope: str = "same_rarity_modelled_catalog"

    def as_public_dict(self) -> dict:
        """No private tie-breaking precision, win-rate proxy or raw history."""
        return {
            "augment_id": self.augment_id,
            "augment_name": self.augment_name,
            "rarity": self.rarity.value,
            "score": self.score,
            "rank": self.rank,
            "assessed_count": self.assessed_count,
            "catalog_count": self.catalog_count,
            "confidence": self.confidence,
            "sample_size": self.sample_size,
            "grade": self.grade,
            "scope": self.scope,
        }


def rank_rated_catalog(pairs):
    """Competition rank within rarity; exclude duplicates/unmodelled candidates.

    catalog_count is the number of UNIQUE raw entries for that rarity,
    including unrated entries, not a fabricated full roster denominator.
    """
    from collections import defaultdict
    groups = defaultdict(list)
    seen = set()
    for augment, rating in pairs:
        if (augment is None or not isinstance(augment.id, str) or
                not augment.id or augment.id in seen or
                augment.tier not in _RARITIES):
            continue
        seen.add(augment.id)
        groups[augment.tier].append((augment, rating))

    rows = []
    for rarity in _RARITIES:
        entries = groups[rarity]
        rated = []
        for aug, rating in entries:
            value = getattr(rating, "ranking_value", None)
            display = getattr(rating, "score", None)
            if (not isinstance(value, (int, float)) or isinstance(value, bool)
                    or not math.isfinite(value) or value < 0 or value > 10
                    or not isinstance(display, (int, float))
                    or isinstance(display, bool) or not math.isfinite(display)
                    or display < 0 or display > 10):
                continue
            rated.append((aug, rating, float(value)))
        rated.sort(key=lambda row: (-row[2], row[0].id))
        previous_value = None
        rank = 0
        for index, (aug, rating, precise) in enumerate(rated, start=1):
            if previous_value is None or previous_value - precise > _TIE_EPSILON:
                rank = index
                previous_value = precise
            rows.append(AugmentPlacement(
                augment_id=aug.id, augment_name=aug.name,
                rarity=rarity, score=float(rating.score), rank=rank,
                assessed_count=len(rated), catalog_count=len(entries),
                confidence=rating.confidence, sample_size=rating.sample_size,
                ranking_value=precise,
            ))
    return rows


def _observed_item_synergy(augment, owned_items) -> float:
    """Small bounded modifier from definitely owned, shop-eligible item stats."""
    item_stats = [
        item.stats for item in owned_items
        if item is not None and item.final
    ]
    if not item_stats:
        return 0.0
    contributions = [
        max(0.0, float(getattr(augment.contribution, field)))
        for field in StatVector.fields()
    ]
    if not any(contributions):
        return 0.0
    dot = 0.0
    for item in item_stats:
        dot += sum(
            contribution * max(0.0, min(1.0, float(getattr(item, field))))
            for contribution, field in zip(contributions, StatVector.fields())
        )
    return min(0.3, dot / len(item_stats) * 0.18)


def _ally_modifier(augment, allies) -> float:
    if not isinstance(allies, AllyTeamProfile) or not allies.known:
        return 0.0
    if allies.frontline == 0:
        return min(0.12, max(0, augment.contribution.hp) * 0.12)
    if allies.support == 0:
        return min(0.08, max(0, augment.contribution.shield) * 0.08)
    return 0.0


def rank_augment_roster(
    champion, all_augments, confirmed_augments, *,
    owned_items=None, enemies=None, threat_profile=None, ally_profile=None,
):
    """Recompute deterministic base or confirmed-current-context placement.

    Never infer confirmed picks from offered choices, inventory from names,
    hidden enemy items, or unapproved player history. Grades need calibration.
    """
    if champion is None or not any(
        isinstance(v, (int, float)) and math.isfinite(v) and v > 0
        for v in champion.stats.to_array()
    ):
        return []
    confirmed = [a for a in confirmed_augments if a is not None]
    chosen_ids = {a.id for a in confirmed}
    rated = []
    for aug in all_augments:
        if aug is None or aug.id in chosen_ids or aug.tier not in _RARITIES:
            continue
        rating = rate_augment(
            champion, aug, confirmed, enemies=enemies,
            threat_profile=threat_profile, allow_empirical=False,
        )
        if rating.score is not None and rating.ranking_value is not None:
            contextual = (
                _observed_item_synergy(aug, owned_items or [])
                + _ally_modifier(aug, ally_profile)
            )
            unrounded = max(0.0, min(10.0, rating.ranking_value + contextual))
            rating = replace(
                rating, score=round(unrounded, 1), ranking_value=unrounded,
            )
        rated.append((aug, rating))
    return rank_rated_catalog(rated)
