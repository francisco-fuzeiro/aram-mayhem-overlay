"""In-match context adjustment of augment tiers (owner decision 2026-11-23).

Final tier = measured base tier (ΔWR, unchanged list rank) shifted by at most
one step. The shift is heuristic and bounded: fit with the current/adapted
build stats, synergy with augments already chosen, answer to the enemy comp,
and the player's own games under strong shrinkage. Each shift carries one
short reason. Inputs are StatVector-style dicts {field: weight}.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from backend.tierdb.augment_tiers import LEVEL_CAP, TIER_ORDER


@dataclass(frozen=True)
class AdjustConfig:
    max_steps: int = 1
    threshold: float = 0.35          # |weighted vote| needed to move one tier
    fit_up: float = 0.6              # cosine with build demand to count as a fit
    fit_down: float = 0.15           # cosine below this = stats the build ignores
    synergy: float = 0.7             # cosine with a chosen augment
    personal_k: float = 30.0         # strong shrinkage of the player's own record
    personal_scale: float = 0.08     # shrunk win-rate delta that counts as a full vote
    personal_min_games: int = 5
    # "impact" (local 10-player history, backend.tierdb.impact) stays at 0 =
    # off until scripts/validate_impact_holdout.py shows it improves the holdout.
    # Owner 24/11: healing/shield augments on champions that heal themselves
    # (Swain, Maokai, Zac...) make them much harder to kill.
    weights: tuple = (("build", 0.40), ("synergy", 0.25), ("enemy", 0.20),
                      ("sustain", 0.35), ("personal", 0.15), ("impact", 0.0))


def _cos(a: dict, b: dict) -> float | None:
    keys = set(a) | set(b)
    na = math.sqrt(sum(float(a.get(k, 0.0)) ** 2 for k in keys))
    nb = math.sqrt(sum(float(b.get(k, 0.0)) ** 2 for k in keys))
    if na <= 0 or nb <= 0:
        return None
    return sum(float(a.get(k, 0.0)) * float(b.get(k, 0.0)) for k in keys) / (na * nb)


def _clean(vec: dict | None) -> dict:
    return {k: float(v) for k, v in (vec or {}).items()
            if isinstance(v, (int, float)) and v > 0}


def context_adjust(
    augment: dict | None,
    *,
    demand: dict | None,
    chosen: list[dict] | None = None,
    enemy: dict | None = None,
    personal: tuple[int, int] | None = None,
    personal_base: float | None = None,
    impact: float | None = None,
    own_healing: float = 0.0,
    config: AdjustConfig = AdjustConfig(),
) -> tuple[int, str | None]:
    """(step in -1..1, reason) for one offered augment; (0, None) without context."""
    if augment is None:
        return 0, None
    aug = _clean(augment)
    votes: dict[str, tuple[float, str | None]] = {}
    if aug and _clean(demand):
        c = _cos(aug, _clean(demand))
        if c is not None:
            if c >= config.fit_up:
                votes["build"] = (1.0, "fits your build")
            elif c <= config.fit_down:
                votes["build"] = (-1.0, "your build does not use these stats")
            else:
                votes["build"] = (0.0, None)
    if aug and chosen:
        best = max((_cos(aug, _clean(o)) or 0.0) for o in chosen)
        votes["synergy"] = ((1.0, "stacks with your augments") if best >= config.synergy
                            else (0.0, None))
    e = enemy or {}
    if aug and e.get("enemies_analyzed", 0) > 0:
        vote = (0.0, None)
        if aug.get("pen", 0) + aug.get("lethality", 0) >= 0.5 and e.get("tanks", 0) >= 2:
            vote = (1.0, "cuts through enemy tanks")
        elif aug.get("hp", 0) + aug.get("shield", 0) >= 0.5 and e.get("burst_pressure", 0) >= 0.5:
            vote = (1.0, "survives enemy burst")
        elif aug.get("heal_power", 0) >= 0.5 and e.get("anti_heal_items", 0) >= 2:
            # Fix 24/11: enemy HEALING items never cut our healing; their
            # Grievous Wounds items do.
            vote = (-1.0, "enemies cut healing")
        votes["enemy"] = vote
    if aug and own_healing > 0 and aug.get("heal_power", 0) + aug.get("shield", 0) >= 0.5:
        cut = e.get("anti_heal_items", 0) >= 2
        votes["sustain"] = ((0.0, None) if cut else
                            (min(1.0, own_healing), "amplifies your healing"))
    if personal and personal_base is not None:
        wins, games = personal
        if games >= config.personal_min_games:
            shrunk = (wins - games * personal_base) / (games + config.personal_k)
            v = max(-1.0, min(1.0, shrunk / config.personal_scale))
            votes["personal"] = (v, "wins in your own games" if v > 0
                                 else "loses in your own games" if v < 0 else None)
    if impact is not None:
        v = max(-1.0, min(1.0, float(impact)))
        votes["impact"] = (v, "does more in your local games" if v > 0
                           else "does less in your local games" if v < 0 else None)
    weights = dict(config.weights)
    votes = {k: v for k, v in votes.items() if weights.get(k, 0.0) > 0}
    if not votes:
        return 0, None
    total_w = sum(weights[k] for k in votes)
    score = sum(weights[k] * v for k, (v, _) in votes.items()) / total_w
    if abs(score) < config.threshold:
        return 0, None
    step = 1 if score > 0 else -1
    reason = max(((weights[k] * v * step, r) for k, (v, r) in votes.items() if r and v * step > 0),
                 default=(0, None))[1]
    return step, reason


def shift_tier(tier: str, step: int, level: str) -> str:
    """Move a tier by at most one step, within the data level's cap."""
    if tier not in TIER_ORDER or not step:
        return tier
    step = max(-1, min(1, int(step)))
    idx = TIER_ORDER.index(tier) - step
    cap = TIER_ORDER.index(LEVEL_CAP.get(level, "A"))
    idx = max(idx, min(cap, TIER_ORDER.index(tier)))
    return TIER_ORDER[max(0, min(idx, len(TIER_ORDER) - 1))]
