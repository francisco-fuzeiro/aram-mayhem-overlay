"""In-match adaptation on top of the measured reference build.

Owner decision 2026-11-23 ("more adaptation"): at most 3 of the 6 slots may
change, and only when the candidate beats the slot it replaces by at least 0.5
on the 0-10 scale. Slot 1 and items already owned never change. Every swap
carries the reason that produced it, so the overlay can show "Reference" and
"Adapted for this match" side by side.

``strength`` is the item's 0-10 standing for this champion (from its tier
list rank); ``context(item) -> (bonus, reason)`` adds the bounded match
context: confirmed augments, enemies and allies. Context is heuristic except
the Weapon of Fate items, which AramHex measures.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class AdaptConfig:
    max_swaps: int = 3
    threshold: float = 0.5
    locked_slots: int = 1


@dataclass(frozen=True)
class AdaptedBuild:
    items: tuple[str, ...]
    swaps: tuple[dict, ...]  # {"slot", "out", "in", "gain", "reason"}


def adapt_build(
    reference: list[str] | tuple[str, ...],
    strength: dict[str, float],
    *,
    context: Callable[[str], tuple[float, str | None]],
    owned: set[str] | None = None,
    conflicts: Callable[[str, str], bool] | None = None,
    config: AdaptConfig = AdaptConfig(),
) -> AdaptedBuild:
    owned = owned or set()
    conflicts = conflicts or (lambda a, b: False)
    items = list(reference)
    cache: dict[str, tuple[float, str | None]] = {}

    def value(iid: str) -> tuple[float, str | None]:
        if iid not in cache:
            bonus, reason = context(iid)
            cache[iid] = (strength.get(iid, 0.0) + bonus, reason)
        return cache[iid]

    swaps: list[dict] = []
    while len(swaps) < config.max_swaps:
        best = None
        for slot, current in enumerate(items):
            if slot < config.locked_slots or current in owned:
                continue
            if any(s["slot"] == slot for s in swaps):
                continue
            current_value = value(current)[0]
            others = [o for i, o in enumerate(items) if i != slot]
            for cand in strength:
                if cand in items or any(conflicts(cand, o) for o in others):
                    continue
                cand_value, reason = value(cand)
                gain = cand_value - current_value
                # One swap per reason (owner 24/11: one item per reason), so a
                # single axis such as vamp never takes over the build.
                if any(s["reason"] == reason for s in swaps):
                    continue
                if gain >= config.threshold and reason and (best is None or gain > best[0]):
                    best = (gain, slot, current, cand, reason)
        if best is None:
            break
        gain, slot, out_item, in_item, reason = best
        items[slot] = in_item
        swaps.append({"slot": slot + 1, "out": out_item, "in": in_item,
                      "gain": round(gain, 2), "reason": reason})
    return AdaptedBuild(tuple(items), tuple(swaps))


def strength_from_rank(rank: int | None, total: int | None) -> float:
    """0-10 standing from a tier-list rank (best = 10), without exporting scores."""
    if not rank or not total:
        return 0.0
    return round(10.0 * (total - rank + 0.5) / total, 3)


def item_archetype(item) -> str | None:
    """'ad' (physical/crit), 'ap' (magic) or None (tank, utility, hybrid)."""
    if item is None:
        return None
    tags = set(getattr(item, "tags", None) or ())
    stats = getattr(item, "stats", None)
    physical = magic = 0.0
    if stats is not None:
        physical = (float(stats.ad or 0) + float(stats.crit or 0)
                    + float(stats.lethality or 0) + 0.5 * float(stats.attack_speed or 0))
        magic = float(stats.ap or 0)
    physical += 1.0 * bool(tags & {"Damage", "CriticalStrike", "ArmorPenetration"})
    magic += 1.0 * bool(tags & {"SpellDamage", "MagicPenetration"})
    if physical > 1.2 * magic and physical > 0:
        return "ad"
    if magic > 1.2 * physical and magic > 0:
        return "ap"
    return None


def owned_archetype(owned_items, min_gold: int = 1000) -> str | None:
    """What the player is actually building, weighted by gold spent."""
    gold = {"ad": 0, "ap": 0}
    for item in owned_items:
        kind = item_archetype(item)
        if kind and not getattr(item, "boots", False):
            gold[kind] += int(getattr(item, "cost", 0) or 0)
    best = max(gold, key=gold.get)
    other = "ap" if best == "ad" else "ad"
    if gold[best] >= min_gold and gold[best] > 1.5 * gold[other]:
        return best
    return None


def follow_owned(
    plan: list[str] | tuple[str, ...],
    owned_order: list[str],
    *,
    get_item: Callable[[str], object],
    ranked: list[str],
    conflicts: Callable[[str, str], bool] | None = None,
    size: int = 6,
) -> tuple[list[str], str | None]:
    """Field 24/11 (AD crit Shaco shown AP items): the plan follows the
    player's purchases. Owned finals come first; if what they bought is
    physical while the plan is magic (or the reverse), the remaining slots are
    refilled with the best-ranked finals of the player's archetype, preferring
    items their owned components build into. Returns (plan, archetype or None
    when the plan was kept)."""
    conflicts = conflicts or (lambda a, b: False)
    items = {iid: get_item(iid) for iid in set(plan) | set(owned_order) | set(ranked)}
    owned_finals = [i for i in owned_order
                    if getattr(items.get(i), "final", False) and i not in ("",)]
    mine = owned_archetype([items.get(i) for i in owned_order])
    plan_kinds = [item_archetype(items.get(i)) for i in plan]
    plan_kind = None
    if plan_kinds.count("ap") > plan_kinds.count("ad"):
        plan_kind = "ap"
    elif plan_kinds.count("ad") > plan_kinds.count("ap"):
        plan_kind = "ad"
    out: list[str] = []

    def add(iid: str) -> None:
        if iid not in out and len(out) < size and not any(conflicts(iid, o) for o in out):
            out.append(iid)

    for iid in owned_finals:
        add(iid)
    switch = mine is not None and plan_kind is not None and mine != plan_kind
    if not switch:
        for iid in plan:
            add(iid)
        return out, None
    builds_into = set()
    for iid in owned_order:
        builds_into |= set(getattr(items.get(iid), "into_ids", ()) or ())
    for iid in plan:  # boots and archetype-neutral plan items keep their place
        item = items.get(iid)
        if getattr(item, "boots", False):
            add(iid)
    pool = [i for i in ranked if item_archetype(items.get(i)) == mine
            and not getattr(items.get(i), "boots", False)]
    for iid in sorted(pool, key=lambda i: (i not in builds_into, ranked.index(i))):
        add(iid)
    return out, mine
