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
