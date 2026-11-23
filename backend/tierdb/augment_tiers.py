"""Per-champion augment tier lists (design: docs/plans/DESENHO_TIERDB_2026-11-23.md §4).

All empirical values are deltas against the champion's own baseline. For a
champion ``c`` and augment ``a``:

* baseline ``p0`` = win rate of ``c`` in games *without* ``a``;
* posterior ``Beta(w + k*p0, g - w + k*(1 - p0))`` shrinks small samples to
  the baseline (``k = 300``, AramHex's own recommendation; calibrate in F7);
* ``ΔWR = logit(p) - logit(p0)``.

Levels (decided fallback): champion+augment (max OP) -> role+augment (max S)
-> global augment (max S) -> curated heuristic (max A) -> no data. Levels
blend smoothly with ``w_j = n_j / (n_j + k_j)``; the level shown is the one
with the largest effective weight. Each component is mapped to [0, 1] by a
mid-rank empirical CDF within ``rarity x patch x level``; missing components
have their weight redistributed; without ΔWR a level is unavailable.

Uncertainty is propagated by Monte-Carlo draws with a fixed seed, so runs are
reproducible. Nothing here is shown to users except tier, rank, tie group,
level and confidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

TIER_ORDER = ("OP", "S", "A", "B", "C", "D", "E")
LEVELS = ("champion", "role", "global", "curated")
LEVEL_CAP = {"champion": "OP", "role": "S", "global": "S", "curated": "A"}
LEVEL_CONFIDENCE = {"champion": "high", "role": "medium", "global": "low",
                    "curated": "heuristic"}


@dataclass(frozen=True)
class AugmentTierConfig:
    k_win: float = 300.0
    k_levels: tuple[float, float, float] = (200.0, 500.0, 1000.0)
    draws: int = 400
    seed: int = 20261123
    tie_probability: float = 0.75
    # Tier lower bounds as percentiles of the patch reference distribution.
    percentiles: dict = field(default_factory=lambda: {
        "OP": 97, "S": 85, "A": 65, "B": 40, "C": 20, "D": 7})
    # Decided 2026-11-23 (win rate >= 50 %, rest proportional).
    weights: dict = field(default_factory=lambda: {
        "win": 50, "combat": 15, "participation": 12,
        "duration": 8, "context": 8, "consistency": 7})


@dataclass(frozen=True)
class AugmentTierRow:
    champion_id: str
    augment_id: str
    rarity: str
    score: float | None
    score_p20: float | None
    score_p80: float | None
    rank: int | None
    tie_group: int | None
    tier: str | None
    level: str
    confidence: str
    n_eff: float


def combine_components(z: dict, weights: dict):
    """Weighted 0-10 score of [0, 1] components; missing ones redistribute.

    Returns None when the win component is missing: a level is not scored
    from secondary metrics alone. Works on floats or numpy arrays.
    """
    if z.get("win") is None:
        return None
    present = {k: v for k, v in z.items() if v is not None and k in weights}
    total = sum(weights[k] for k in present)
    return 10.0 * sum(weights[k] * v for k, v in present.items()) / total


def baseline_without(champ_wins: int, champ_games: int, wins: int, games: int) -> float:
    """Champion win rate in games without the augment (falls back to overall)."""
    rest_g, rest_w = champ_games - games, champ_wins - wins
    if rest_g > 0 and 0 <= rest_w <= rest_g:
        p = rest_w / rest_g
    else:
        p = champ_wins / champ_games if champ_games > 0 else 0.5
    return float(min(max(p, 1e-4), 1 - 1e-4))


def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _delta(wins: float, games: float, p0: float, k: float, rng, draws: int):
    """(posterior-median ΔWR, ΔWR draws) for wins/games against baseline p0."""
    a, b = wins + k * p0, (games - wins) + k * (1 - p0)
    median = float(_logit(a / (a + b)) - _logit(p0))
    samples = _logit(rng.beta(a, b, size=draws)) - _logit(p0)
    return median, samples


def _midrank_cdf(reference: np.ndarray, values):
    """Mid-rank empirical CDF: ties sit in the middle, not at the top."""
    lo = np.searchsorted(reference, values, side="left")
    hi = np.searchsorted(reference, values, side="right")
    return (lo + hi) / (2.0 * len(reference))


def _tier_for(score: float, p20: float, thresholds: dict, level: str) -> str:
    tier = "E"
    for name in TIER_ORDER[:-1]:
        if score >= thresholds[name] and (name != "OP" or p20 >= thresholds[name]):
            tier = name
            break
    cap = LEVEL_CAP[level]
    return TIER_ORDER[max(TIER_ORDER.index(tier), TIER_ORDER.index(cap))]


def build_augment_tiers(
    champions: dict[str, tuple[int, int]],
    pairs: dict[tuple[str, str], tuple[int, int]],
    rarity: dict[str, str],
    roles: dict[str, str],
    heuristic: dict[tuple[str, str], float | None],
    config: AugmentTierConfig = AugmentTierConfig(),
) -> tuple[list[AugmentTierRow], dict[str, dict[str, float]]]:
    """Return (rows, thresholds per rarity).

    ``champions``: champion -> (wins, games); ``pairs``: (champion, augment)
    -> (wins, games); ``rarity``: catalog of the patch (every augment listed
    appears for every champion); ``heuristic``: optional curated 0-10 score.
    """
    rng = np.random.default_rng(config.seed)
    D = config.draws
    k1, k2, k3 = config.k_levels
    champs = sorted(set(champions) | {c for c, _ in heuristic})

    # Per-pair baseline (games without the augment) and level aggregates.
    p0 = {}
    role_agg: dict[tuple[str, str], list[float]] = {}
    glob_agg: dict[str, list[float]] = {}
    for (c, a), (w, g) in sorted(pairs.items()):
        if c not in champions or a not in rarity or g <= 0:
            continue
        p0[(c, a)] = baseline_without(*champions[c], w, g)
        for agg, key in ((role_agg, (roles.get(c, ""), a)), (glob_agg, a)):
            acc = agg.setdefault(key, [0.0, 0.0, 0.0])
            acc[0] += w
            acc[1] += g
            acc[2] += g * p0[(c, a)]

    def level_stats(agg):
        out = {}
        for key in sorted(agg):
            w, g, gp = agg[key]
            out[key] = (g, *_delta(w, g, gp / g, config.k_win, rng, D))
        return out

    glob = level_stats(glob_agg)          # aug -> (n, median, draws)
    role = level_stats(role_agg)          # (role, aug) -> ...
    champ = {}
    for key in sorted(p0):
        w, g = pairs[key]
        champ[key] = (g, *_delta(w, g, p0[key], config.k_win, rng, D))

    # Reference distributions per (level, rarity) of posterior medians.
    def refs(stats, aug_of):
        out: dict[str, list[float]] = {}
        for key, (_, med, _) in stats.items():
            out.setdefault(rarity[aug_of(key)], []).append(med)
        return {r: np.sort(np.array(v)) for r, v in out.items()}

    ref_champ = refs(champ, lambda k: k[1])
    ref_role = refs(role, lambda k: k[1])
    ref_glob = refs(glob, lambda k: k)

    def level_score(stats, ref, key, r):
        item = stats.get(key)
        if item is None or r not in ref:
            return None, 0.0
        n, _, draws = item
        z = _midrank_cdf(ref[r], draws)
        return combine_components({"win": z}, config.weights), float(n)

    raw: dict[tuple[str, str], tuple] = {}
    for c in champs:
        for a in sorted(rarity):
            r = rarity[a]
            levels = []
            for name, stats, ref, key, k in (
                ("champion", champ, ref_champ, (c, a), k1),
                ("role", role, ref_role, (roles.get(c, ""), a), k2),
                ("global", glob, ref_glob, a, k3),
            ):
                s, n = level_score(stats, ref, key, r)
                if s is not None:
                    levels.append((name, s, n, n / (n + k)))
            h = heuristic.get((c, a))
            if h is not None:
                levels.append(("curated", np.full(D, float(h)), 0.0, 1.0))
            if not levels:
                raw[(c, a)] = None
                continue
            # Nested blend from the bottom: acc = w_j*S_j + (1-w_j)*acc.
            acc = None
            for name, s, n, w in reversed(levels):
                acc = s if acc is None else w * s + (1 - w) * acc
            # Effective weights; the lowest present level takes the residual.
            eff, remaining = [], 1.0
            for i, (name, s, n, w) in enumerate(levels):
                share = remaining if i == len(levels) - 1 else remaining * w
                eff.append((share, name, n))
                remaining -= share
            _, level, n_eff = max(eff, key=lambda t: t[0])
            raw[(c, a)] = (acc, level, n_eff)

    # Frozen thresholds per rarity from the empirical (levels 1-2) reference.
    thresholds: dict[str, dict[str, float]] = {}
    for r in sorted(set(rarity.values())):
        scored = [(float(np.median(v[0])), v[1]) for (c, a), v in raw.items()
                  if v is not None and rarity[a] == r]
        ref = [s for s, lvl in scored if lvl in ("champion", "role")] or [s for s, _ in scored]
        if ref:
            thresholds[r] = {t: float(np.percentile(ref, p))
                             for t, p in config.percentiles.items()}

    rows: list[AugmentTierRow] = []
    for c in champs:
        for r in sorted(set(rarity.values())):
            augs = [a for a in sorted(rarity) if rarity[a] == r]
            scored = [(a, raw[(c, a)]) for a in augs if raw.get((c, a)) is not None]
            scored.sort(key=lambda t: (-float(np.median(t[1][0])), t[0]))
            group = 0
            leader = None
            for rank, (a, (draws, level, n_eff)) in enumerate(scored, start=1):
                # Tied = not distinguishable from the group's first augment
                # (comparing neighbours only chained whole lists together).
                if leader is None or float(np.mean(leader > draws)) >= config.tie_probability:
                    group = rank
                    leader = draws
                med = float(np.median(draws))
                p20, p80 = (float(x) for x in np.percentile(draws, [20, 80]))
                rows.append(AugmentTierRow(
                    champion_id=c, augment_id=a, rarity=r,
                    score=round(med, 4), score_p20=round(p20, 4), score_p80=round(p80, 4),
                    rank=rank, tie_group=group,
                    tier=_tier_for(med, p20, thresholds[r], level),
                    level=level, confidence=LEVEL_CONFIDENCE[level], n_eff=n_eff,
                ))
            for a in augs:
                if raw.get((c, a)) is None:
                    rows.append(AugmentTierRow(
                        champion_id=c, augment_id=a, rarity=r, score=None,
                        score_p20=None, score_p80=None, rank=None, tie_group=None,
                        tier=None, level="none", confidence="none", n_eff=0.0,
                    ))
    return rows, thresholds
