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


# --- P0-D: scores for a VERIFIED real-catalogue offer (stat_anvil_offer) ----

# Canonical catalogue stat -> champion StatVector field it is valued by.
_OFFENSIVE = {
    "ad": "ad", "ap": "ap", "as": "attack_speed", "crit": "crit",
    "crit_damage": "crit", "lethality": "lethality", "armor_pen_pct": "lethality",
    "mpen": "pen", "mpen_pct": "pen", "ah": "cdr", "hp": "hp", "hp_pct": "hp",
    "heal_shield": "heal_power",
}
_STAT_LABELS = {
    "ad": "attack damage", "ap": "ability power", "as": "attack speed",
    "crit": "crit chance", "crit_damage": "crit damage", "lethality": "lethality",
    "armor_pen_pct": "armor penetration", "mpen": "magic penetration",
    "mpen_pct": "magic penetration", "ah": "ability haste", "hp": "health",
    "hp_pct": "health", "heal_shield": "heal & shield power", "armor": "armor",
    "mr": "magic resist", "ms": "move speed", "tenacity": "tenacity",
    "omnivamp": "omnivamp",
}
_IGNORED = frozenset({"size", "omnivamp_ranged"})


def _shard_demand(champion, confirmed_augments, owned_items, enemy):
    """Per-catalogue-stat demand >= 0, or {} when the champion is unmodelled.

    Offence reuses the augment stat model (_stat_weights). Defence and
    utility, which the augment StatVector cannot express, come from the
    champion's frontline weight and the visible enemy damage/CC profile.
    """
    base = _stat_weights(champion, confirmed_augments, owned_items, enemy)
    if not base:
        return {}
    vec = dict(zip(StatVector.fields(), _get_champion_vec(champion)))
    for extra in ("pen", "heal_power", "shield"):
        value = vec.get(extra, 0.0)
        if extra not in base and math.isfinite(value):
            base[extra] = max(0.0, float(value))
    demand = {stat: base.get(field, 0.0) for stat, field in _OFFENSIVE.items()}
    demand["heal_shield"] += 0.5 * max(0.0, float(vec.get("shield", 0.0)))
    frontline = min(1.2, max(0.0, float(vec.get("hp", 0.0))))
    known = isinstance(enemy, EnemyThreatProfile) and enemy.enemies_analyzed > 0
    physical = enemy.physical_pressure if known else 0.5
    magic = enemy.magic_pressure if known else 0.5
    cc = enemy.cc_pressure if known else 0.3
    demand["armor"] = (0.2 + 0.6 * frontline) * (0.5 + physical)
    demand["mr"] = (0.2 + 0.6 * frontline) * (0.5 + magic)
    demand["tenacity"] = 0.15 + 0.6 * min(1.0, max(0.0, cc)) * (0.5 + frontline)
    role = getattr(champion, "role", "")
    demand["ms"] = 0.25 + (0.2 if role in ("marksman", "assassin") else 0.0)
    demand["omnivamp"] = 0.25 + (0.3 if role in ("fighter", "assassin") else 0.0)
    return {k: max(0.0, float(v)) for k, v in demand.items() if math.isfinite(v)}


def _strengths(shard, singles):
    """Per-stat strength vs this tier's single-stat shard (hybrids < 1)."""
    out = {}
    for stat, value in shard.stats:
        if stat in _IGNORED:
            continue
        ref = singles.get((shard.tier, stat)) or value
        out[stat] = max(0.0, min(1.0, value / ref)) if ref else 0.0
    return out


def _singles(catalog):
    result = {}
    for shard in catalog:
        scored = [(k, v) for k, v in shard.stats if k not in _IGNORED]
        if len(scored) == 1:
            result[(shard.tier, scored[0][0])] = scored[0][1]
    return result


def rate_stat_anvil_offer(champion, offered, catalog, confirmed_augments,
                          owned_items, enemy):
    """Own 0.0-10.0 score per verified shard; never a win rate or OP.GG grade.

    10 = the best shard of this tier for this champion and context; the score
    is fit / best possible fit within the same tier of the real catalogue.
    Returns [] (abstain) when the champion cannot be modelled.
    """
    offered = list(offered or ())
    catalog = list(catalog or ())
    if not offered or not catalog or len({s.tier for s in offered}) != 1:
        return []
    demand = _shard_demand(champion, confirmed_augments, owned_items, enemy)
    if not demand:
        return []
    singles = _singles(catalog)
    tier = offered[0].tier

    def fit(shard):
        parts = {stat: demand.get(stat, 0.0) * strength
                 for stat, strength in _strengths(shard, singles).items()}
        return sum(parts.values()), parts

    best = max((fit(s)[0] for s in catalog if s.tier == tier), default=0.0)
    if best <= 0:
        return []
    known_enemy = isinstance(enemy, EnemyThreatProfile) and enemy.enemies_analyzed > 0
    rows = []
    for shard in offered:
        total, parts = fit(shard)
        driver = max(parts, key=parts.get) if parts else None
        reason = f"{_STAT_LABELS.get(driver, driver)} suits this champion"
        if driver in ("armor", "mr") and known_enemy:
            reason = ("enemies deal mostly physical damage" if driver == "armor"
                      else "enemies deal mostly magic damage")
        elif driver == "tenacity" and known_enemy:
            reason = "heavy enemy crowd control"
        rows.append({
            "anvil_id": shard.id, "anvil_name": shard.title, "tier": tier,
            "stats": dict(shard.stats),
            "score": round(10.0 * min(1.0, total / best), 1),
            "modelled": True, "provenance": "public_game_bin",
            "reason": reason,
            "confidence": "medium" if known_enemy else "low",
            "explanation": ("Own heuristic: champion stats, confirmed augments, "
                            "owned items and visible enemies; not a win rate."),
        })
    return sorted(rows, key=lambda r: (-r["score"], r["anvil_name"]))
