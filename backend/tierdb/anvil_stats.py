"""Heuristic Stat Anvil ranking per champion (owner decision 2026-11-23).

No legal source measures Stat Anvil choices (AramHex, arammayhem.com and the
Riot API have none), so every result here is an *estimate*: tier capped at A,
level "estimate", never a win rate.

Which stats help a champion (``stat_demand``) comes from data where it can:
the stat types of the champion's best measured items (AramHex tier list),
falling back to a role prior. Ability-ratio demand from CommunityDragon
champion bins is the planned second half (design §3) and is not wired yet;
until then its weight redistributes to the measured builds.

The shard catalogue (stat kind and value per Silver/Gold/Prismatic shard) is
game data read from CommunityDragon by ``static_data.anvil_public_catalog``
(#107). A kind we cannot map to one stat abstains ("unmodelled").
"""
from __future__ import annotations

import re

# 13 Anvil/item stats. The augment StatVector (12 dims) lacks armor, MR,
# movement speed, tenacity and omnivamp, so Anvils use their own space.
ANVIL_STATS = ("ad", "ap", "as", "hp", "armor", "mr", "ah", "crit", "ms",
               "lethality", "mpen", "omnivamp", "tenacity")

_KIND_PATTERNS = (
    ("lethality", r"lethality|armorpen"),
    ("mpen", r"magicpen|magicpenetration|spellpen"),
    ("mr", r"magicresist|spellblock|^mr$"),
    ("armor", r"armor"),
    ("ap", r"abilitypower|^ap$|magicdamage"),
    ("ad", r"attackdamage|^ad$|physicaldamage"),
    ("as", r"attackspeed"),
    ("ah", r"abilityhaste|cooldown"),
    ("crit", r"crit"),
    ("ms", r"movespeed|movementspeed"),
    ("omnivamp", r"omnivamp|lifesteal|spellvamp|vamp"),
    ("tenacity", r"tenacity"),
    ("hp", r"health|^hp$|maxhealth"),
)

# DDragon/AramHex item type tags -> stats.
_TAG_STATS = {
    "SpellDamage": ("ap",), "Damage": ("ad",), "AttackSpeed": ("as",),
    "Health": ("hp",), "Armor": ("armor",), "SpellBlock": ("mr",),
    "MagicResist": ("mr",), "AbilityHaste": ("ah",), "CooldownReduction": ("ah",),
    "CriticalStrike": ("crit",), "NonbootsMovement": ("ms",),
    "ArmorPenetration": ("lethality",), "MagicPenetration": ("mpen",),
    "LifeSteal": ("omnivamp",), "SpellVamp": ("omnivamp",), "Tenacity": ("tenacity",),
}

_ROLE_PRIOR = {
    "marksman": {"as": 3, "crit": 3, "ad": 3, "omnivamp": 1, "ms": 1},
    "mage": {"ap": 4, "ah": 2, "mpen": 2, "hp": 1},
    "assassin": {"ad": 3, "lethality": 3, "ah": 1, "ap": 1},
    "fighter": {"ad": 3, "hp": 2, "ah": 2, "armor": 1, "omnivamp": 1},
    "tank": {"hp": 4, "armor": 2, "mr": 2, "ah": 1},
    "support": {"ah": 3, "hp": 2, "ap": 1, "ms": 1},
}

MAX_TIER = "A"
_TIER_CUTS = (("A", 8.0), ("B", 6.0), ("C", 4.0), ("D", 2.0))


def anvil_stat_for_kind(kind: str) -> str | None:
    """Map a public shard kind (DataValues name) to one stat, else None."""
    if not isinstance(kind, str) or "+" in kind:
        return None
    key = re.sub(r"[^a-z]", "", kind.lower()).replace("flat", "").replace("percent", "")
    for stat, pattern in _KIND_PATTERNS:
        if re.search(pattern, key):
            return stat
    return None


def _normalise(weights: dict) -> dict:
    total = sum(weights.values())
    if total <= 0:
        return {s: 1.0 / len(ANVIL_STATS) for s in ANVIL_STATS}
    return {s: weights.get(s, 0.0) / total for s in ANVIL_STATS}


def stat_demand(role: str, top_items: list[str], item_types: dict) -> dict[str, float]:
    """How much each stat helps this champion, summing to 1.

    Measured part: stats of the champion's best items (in tier order, earlier
    items weigh more). Fallback: role prior. A small floor keeps every stat
    rankable.
    """
    weights = {s: 0.0 for s in ANVIL_STATS}
    used = 0
    for pos, iid in enumerate(top_items[:8]):
        stats = {s for tag in item_types.get(iid, ()) for s in _TAG_STATS.get(tag, ())}
        if not stats:
            continue
        used += 1
        for s in stats:
            weights[s] += (1.0 / (1 + 0.25 * pos)) / len(stats)
    if not used:
        weights = {s: float(v) for s, v in _ROLE_PRIOR.get(role, {}).items()}
    base = _normalise(weights)
    return _normalise({s: base[s] + 0.01 for s in ANVIL_STATS})


def _context(stat: str, enemy: dict | None, allies: dict | None,
             augment_stats: dict | None) -> tuple[float, float, str | None]:
    """(multiplier, additive augment demand in units of the peak, reason)."""
    mult, reason = 1.0, None
    enemy = enemy or {}
    magic, physical = enemy.get("magic_pressure"), enemy.get("physical_pressure")
    if stat == "mr" and magic is not None and magic >= 0.55:
        mult, reason = 1.0 + 2.0 * magic, "enemies deal mostly magic damage"
    elif stat == "armor" and physical is not None and physical >= 0.55:
        mult, reason = 1.0 + 2.0 * physical, "enemies deal mostly physical damage"
    elif stat == "tenacity" and enemy.get("cc_pressure", 0) >= 0.5:
        mult, reason = 1.0 + 2.0 * enemy["cc_pressure"], "heavy enemy crowd control"
    elif stat == "mr" and magic is not None and magic <= 0.3:
        mult = 0.6
    elif stat == "armor" and physical is not None and physical <= 0.3:
        mult = 0.6
    if stat in ("hp", "armor", "mr") and allies and allies.get("known") and \
            allies.get("frontline", 1) == 0:
        mult *= 1.2
        reason = reason or "allies lack frontline"
    boost = max(0.0, min(float((augment_stats or {}).get(stat, 0.0)), 1.0))
    if boost > 0:
        reason = reason or "fits your augments"
    return mult, boost, reason


def rank_anvil_options(
    shards: list[dict],
    demand: dict[str, float],
    *,
    enemy: dict | None = None,
    allies: dict | None = None,
    augment_stats: dict | None = None,
) -> list[dict]:
    """Rank the visible shards (each {id, kind, tier, values}); estimates only.

    Score 0-10 is relative to the most wanted stat for this champion, then
    adjusted by enemies, allies and confirmed augments. Tier is capped at A.
    """
    peak = max(demand.values()) if demand else 1.0
    out = []
    for shard in shards:
        stat = anvil_stat_for_kind(shard.get("kind"))
        if stat is None:
            out.append({"id": shard.get("id"), "stat": None, "score": None, "tier": None,
                        "rank": None, "level": "unmodelled", "reason": None})
            continue
        mult, boost, reason = _context(stat, enemy, allies, augment_stats)
        score = min(10.0, 10.0 * (demand.get(stat, 0.0) / peak + boost) * mult)
        tier = next((t for t, cut in _TIER_CUTS if score >= cut), "E")
        out.append({"id": shard.get("id"), "stat": stat, "score": round(score, 1),
                    "tier": tier, "rank": None, "level": "estimate",
                    "reason": reason or "suits this champion's usual build"})
    ranked = sorted((r for r in out if r["score"] is not None),
                    key=lambda r: (-r["score"], str(r["id"])))
    for pos, row in enumerate(ranked, start=1):
        row["rank"] = pos
    return ranked + [r for r in out if r["score"] is None]


def top_stats(demand: dict[str, float], n: int = 5) -> list[str]:
    return [s for s, _ in sorted(demand.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]
