"""Heuristic Stat Anvil ranking per champion (owner decision 2026-11-23).

No legal source measures Stat Anvil choices (AramHex, arammayhem.com and the
Riot API have none), so every result here is an *estimate*: tier capped at A,
level "estimate", never a win rate.

Which stats help a champion (``stat_demand``) comes from data where it can:
the stat types of the champion's best measured items (AramHex tier list),
falling back to a role prior. Ability-ratio demand from CommunityDragon
champion bins is the planned second half (design §3) and is not wired yet;
until then its weight redistributes to the measured builds.

The shard catalogue is game data pinned per patch by #107
(``data/anvils/stat_anvils_<patch>.json``, from CommunityDragon
``game/maps/modespecificdata/statanvils.bin.json`` on 16.23). Each shard
carries canonical ``stats`` ({stat: value}); ranking uses them, so hybrids
score on both stats, weighted by value against the pure shard of the same
tier. Side effects (size, ranged omnivamp share) never score. A shard with no
known stat abstains ("unmodelled").
"""
from __future__ import annotations

import re

# 14 Anvil/item stats. The augment StatVector (12 dims) lacks armor, MR,
# movement speed, tenacity, omnivamp and heal/shield power, so Anvils use
# their own space.
ANVIL_STATS = ("ad", "ap", "as", "hp", "armor", "mr", "ah", "crit", "ms",
               "lethality", "mpen", "omnivamp", "tenacity", "heal_shield")

# Canonical catalogue stats (#107) -> Anvil demand stats.
_CATALOG_STAT = {"hp_pct": "hp", "armor_pen_pct": "lethality", "mpen_pct": "mpen",
                 "crit_damage": "crit"}
SIDE_EFFECT_STATS = frozenset({"size", "omnivamp_ranged"})

_KIND_PATTERNS = (
    ("lethality", r"lethality|armorpen"),
    ("mpen", r"magicpen|magicpenetration|spellpen|^mpen$"),
    ("mr", r"magicresist|spellblock|^mr$"),
    ("armor", r"armor|^ar$"),
    ("ap", r"abilitypower|^ap$|magicdamage"),
    ("ad", r"attackdamage|^ad$|physicaldamage"),
    ("as", r"attackspeed|^as$"),
    ("ah", r"abilityhaste|cooldown|^ah$"),
    ("crit", r"crit"),
    ("ms", r"movespeed|movementspeed|^ms$"),
    ("omnivamp", r"omnivamp|lifesteal|spellvamp|vamp"),
    ("tenacity", r"tenacity"),
    ("heal_shield", r"healshield|^hs$"),
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
    "support": {"ah": 3, "hp": 2, "heal_shield": 2, "ap": 1, "ms": 1},
}

MAX_TIER = "A"
_TIER_CUTS = (("A", 8.0), ("B", 6.0), ("C", 4.0), ("D", 2.0))


def anvil_stat_for_kind(kind: str) -> str | None:
    """Map one shard kind, catalogue stat or raw DataValues name to a stat.

    Multi-stat kinds ("as+ah", "MinAS+MinAH") return None: hybrids are ranked
    from the catalogue's ``stats`` instead.
    """
    if not isinstance(kind, str) or "+" in kind:
        return None
    if kind in ANVIL_STATS:
        return kind
    if kind in _CATALOG_STAT:
        return _CATALOG_STAT[kind]
    if kind in SIDE_EFFECT_STATS:
        return None
    key = re.sub(r"[^a-z]", "", kind.lower()).replace("flat", "").replace("percent", "")
    key = re.sub(r"^min(?=[a-z])", "", key)
    for stat, pattern in _KIND_PATTERNS:
        if re.search(pattern, key):
            return stat
    return None


def _normalise(weights: dict) -> dict:
    total = sum(weights.values())
    if total <= 0:
        return {s: 1.0 / len(ANVIL_STATS) for s in ANVIL_STATS}
    return {s: weights.get(s, 0.0) / total for s in ANVIL_STATS}


def _item_stats(iid: str, item_types: dict) -> set[str]:
    return {s for tag in item_types.get(iid, ()) for s in _TAG_STATS.get(tag, ())}


def stat_demand(role: str, top_items: list[str], item_types: dict,
                popular: dict[str, float] | None = None) -> dict[str, float]:
    """How much each stat helps this champion, summing to 1.

    Measured part: half from the champion's best items (tier order, earlier
    items weigh more), half from what players actually build on it (items
    weighted by games). Field test 23/11: Master Yi's best-ranked items are
    crit/lethality, yet attack speed is in most Yi builds; ranking alone hid
    it. Fallback: role prior. A small floor keeps every stat rankable.
    """
    weights = {s: 0.0 for s in ANVIL_STATS}
    used = 0
    for pos, iid in enumerate(top_items[:8]):
        stats = _item_stats(iid, item_types)
        if not stats:
            continue
        used += 1
        for s in stats:
            weights[s] += (1.0 / (1 + 0.25 * pos)) / len(stats)
    pop = {s: 0.0 for s in ANVIL_STATS}
    for iid, games in (popular or {}).items():
        stats = _item_stats(iid, item_types)
        if stats and games > 0:
            for s in stats:
                pop[s] += float(games) / len(stats)
    if not used and not any(pop.values()):
        base = _normalise({s: float(v) for s, v in _ROLE_PRIOR.get(role, {}).items()})
    elif not any(pop.values()):
        base = _normalise(weights)
    elif not used:
        base = _normalise(pop)
    else:
        a, b = _normalise(weights), _normalise(pop)
        base = {s: 0.5 * a[s] + 0.5 * b[s] for s in ANVIL_STATS}
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


def _shard_components(shard: dict) -> dict[str, float] | None:
    """{stat: value} from catalogue stats; None if the shard has no stats field."""
    stats = shard.get("stats")
    if not isinstance(stats, dict):
        return None
    out: dict[str, float] = {}
    for name, value in stats.items():
        if name in SIDE_EFFECT_STATS:
            continue
        stat = anvil_stat_for_kind(name)
        if stat is None or not isinstance(value, (int, float)):
            continue
        out[stat] = out.get(stat, 0.0) + abs(float(value))
    return out


def _pure_values(shards: list[dict], reference: list[dict] | None) -> dict:
    """(tier, stat) -> value of the single-stat shard, for hybrid weighting."""
    pure: dict[tuple, float] = {}
    for shard in list(reference or ()) + list(shards):
        comps = _shard_components(shard)
        if comps and len(comps) == 1:
            (stat, value), = comps.items()
            pure.setdefault((shard.get("tier"), stat), value)
    return pure


def rank_anvil_options(
    shards: list[dict],
    demand: dict[str, float],
    *,
    enemy: dict | None = None,
    allies: dict | None = None,
    augment_stats: dict | None = None,
    reference: list[dict] | None = None,
) -> list[dict]:
    """Rank Stat Anvil shards; estimates only.

    A shard is {id, tier, stats} from the pinned catalogue (preferred), or
    {id, stat} / {id, kind} for one stat. Score 0-10 is relative to the most
    wanted stat for this champion, adjusted by enemies, allies and confirmed
    augments. A hybrid adds each stat's score times its value over the pure
    shard of the same tier (from ``reference`` or the shards given; 1/n when
    unknown). Tier is capped at A.
    """
    peak = max(demand.values()) if demand else 1.0
    pure = _pure_values(shards, reference)
    out = []
    for shard in shards:
        comps = _shard_components(shard)
        if comps is None:
            stat = shard.get("stat") if shard.get("stat") in ANVIL_STATS \
                else anvil_stat_for_kind(shard.get("kind"))
            comps = {stat: None} if stat else {}
        if not comps:
            out.append({"id": shard.get("id"), "stat": None, "score": None, "tier": None,
                        "rank": None, "level": "unmodelled", "reason": None})
            continue
        parts = []
        for stat, value in comps.items():
            if len(comps) == 1:
                share = 1.0
            else:
                ref = pure.get((shard.get("tier"), stat))
                share = min(1.0, value / ref) if ref and value is not None else 1.0 / len(comps)
            mult, boost, reason = _context(stat, enemy, allies, augment_stats)
            part = share * 10.0 * (demand.get(stat, 0.0) / peak + boost) * mult
            parts.append((part, stat, reason))
        score = min(10.0, sum(p for p, _, _ in parts))
        _, stat, reason = max(parts, key=lambda p: (p[0], p[1]))
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
