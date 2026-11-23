"""Heuristic, evidence-bound Stat Anvil priorities; not on-screen OCR proof.

Each candidate score is a transparent relative fit of a confirmed *offered*
Anvil's curated stat vector, never an inferred win rate or an offer detector.
This module does not claim that any given stat appears in the current popup.
"""
from __future__ import annotations

import math

from backend.models import AugmentTier, StatVector
from backend.engine.scoring import _get_champion_vec
from backend.engine.team_context import EnemyThreatProfile

# StatVector fields representing stat quantities that may be described by
# Anvil options. Excludes hard/soft CC, shield and heal effects: those are
# mechanics, not independently verified purchase/popup stat choices.
_MODELLED_STATS = (
    "ap", "ad", "attack_speed", "hp", "crit", "cdr", "lethality",
)
_LABELS = {
    "ap": "Ability Power", "ad": "Attack Damage",
    "attack_speed": "Attack Speed", "hp": "Health",
    "crit": "Critical Strike", "cdr": "Ability Haste",
    "lethality": "Lethality",
}


def _stat_weights(champion, confirmed_augments, owned_items, enemy):
    if champion is None or not any(
        math.isfinite(getattr(champion.stats, field, 0)) and
        getattr(champion.stats, field, 0) > 0 for field in _MODELLED_STATS
    ):
        return {}
    raw = _get_champion_vec(champion)
    fields = StatVector.fields()
    weights = {}
    for index, field in enumerate(fields):
        if field not in _MODELLED_STATS:
            continue
        base = raw[index]
        if not math.isfinite(base):
            continue
        boost = 0.0
        if confirmed_augments:
            values = [
                getattr(aug.contribution, field, 0)
                for aug in confirmed_augments if aug is not None
            ]
            clean = [max(0.0, float(v)) for v in values
                     if isinstance(v, (int, float)) and not isinstance(v, bool)
                     and math.isfinite(v)]
            if clean:
                boost = 0.3 * sum(clean) / len(clean)
        owned = [
            getattr(item.stats, field, 0.0)
            for item in owned_items if item is not None
        ]
        owned = [max(0.0, float(v)) for v in owned
                 if isinstance(v, (int, float)) and not isinstance(v, bool)
                 and math.isfinite(v)]
        existing = 0.07 * sum(owned) / len(owned) if owned else 0.0
        modifier = 0.0
        if (field == "hp" and isinstance(enemy, EnemyThreatProfile)
                and enemy.enemies_analyzed > 0):
            modifier = 0.25 * min(1.0, max(0.0, enemy.burst_pressure))
            modifier += 0.25 * min(1.0, max(0.0, enemy.cc_pressure))
        weights[field] = max(0.0, float(base) + boost + existing + modifier)
    return weights if any(v > 0 for v in weights.values()) else {}


def rank_anvil_stats(champion, confirmed_augments, owned_items, enemy):
    """Top stat preferences after a verified full build, not offered choices.

    May not be used to label unseen choices or to infer an acquired Anvil.
    """
    weights = _stat_weights(champion, confirmed_augments, owned_items, enemy)
    ranked = sorted(
        ((field, value) for field, value in weights.items() if value > 0),
        key=lambda row: (-row[1], _MODELLED_STATS.index(row[0])),
    )
    results = []
    for field, _ in ranked[:3]:
        reasons = ["Champion role and known scaling"]
        if confirmed_augments:
            reasons.append("confirmed augments")
        if owned_items:
            reasons.append("observed items")
        if field == "hp" and isinstance(enemy, EnemyThreatProfile) and enemy.enemies_analyzed:
            reasons.append("visible enemy burst/CC context")
        results.append({
            "stat": field, "label": _LABELS[field],
            "reason": "; ".join(reasons) + " (heuristic, not a live Anvil offer)",
        })
    return results


def rate_verified_anvil_options(champion, offered_anvils, confirmed_augments,
                                owned_items, enemy):
    """Score only exact tier-zero Anvil IDs independently confirmed in a slot.

    Caller must separately prove a current-match, epoch-fenced three-slot
    offer. This pure ranking does not perform OCR or authorize display.
    """
    if not offered_anvils or any(
        aug is None or aug.tier != AugmentTier.STAT_ANVIL
        for aug in offered_anvils
    ):
        return []
    weights = _stat_weights(champion, confirmed_augments, owned_items, enemy)
    if not weights:
        return []
    results = []
    for aug in offered_anvils:
        # A catalog title alone does not imply a trustworthy model.
        fields = {
            field: float(getattr(aug.contribution, field, 0))
            for field in weights
            if isinstance(getattr(aug.contribution, field, 0), (float, int))
            and math.isfinite(getattr(aug.contribution, field, 0))
            and getattr(aug.contribution, field, 0) > 0
        }
        fit = sum(weights[field] * amount for field, amount in fields.items())
        score = round(10.0 * fit / (1.0 + fit), 1) if fit > 0 else None
        results.append({
            "anvil_id": aug.id, "anvil_name": aug.name, "score": score,
            "modelled": score is not None, "provenance": aug.provenance,
            "explanation": (
                "Heuristic fit from champion, confirmed augments, owned items "
                "and visible enemy context; not a win rate."
                if score is not None else "Stat contribution not modelled."
            ),
        })
    return sorted(results, key=lambda row: (
        row["score"] is None, -(row["score"] or 0), row["anvil_name"],
    ))
