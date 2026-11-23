"""Champion tier list for ARAM: Mayhem (design §5, approved 2026-11-23).

Components (decided weights; missing ones redistribute):

* ``win`` 50 — champion win rate shrunk to the mode mean (Beta, k = 500);
* ``leverage`` 23 — strength when taking the best of three random augment
  offers: mean over rarities of ``E[max of 3 offered values]`` (exact order
  statistics). The pipeline feeds shrunk absolute logit win rates by default;
  relative ΔWR is available but anti-correlated with winning (F7 holdout);
* ``combat`` 19 — role-relative combat metrics (needs per-match data);
* ``consistency`` 8 — rank stability across snapshots (needs >= 2 patches).

Each component is mapped to [0, 1] with a mid-rank empirical CDF across
champions. Win rate is never exported; only tier, rank, tie group and
confidence are.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import comb

import numpy as np

from backend.tierdb.augment_tiers import TIER_ORDER, _midrank_cdf, combine_components


@dataclass(frozen=True)
class ChampionTierConfig:
    k_win: float = 500.0
    draws: int = 400
    seed: int = 20261124
    tie_probability: float = 0.75
    op_min_games: int = 500
    percentiles: dict = field(default_factory=lambda: {
        "OP": 97, "S": 85, "A": 65, "B": 40, "C": 20, "D": 7})
    weights: dict = field(default_factory=lambda: {
        "win": 50, "combat": 19, "leverage": 23, "consistency": 8})
    # Offer frequency per rarity; None = equal (assumption until measured).
    rarity_frequency: dict | None = None
    # "Uses augments well" label: relative gain strictly above this percentile.
    friendly_percentile: float = 80.0


@dataclass(frozen=True)
class ChampionTierRow:
    champion_id: str
    score: float
    score_p20: float
    score_p80: float
    rank: int
    tie_group: int
    tier: str
    confidence: str
    n: int
    components: tuple  # ((name, value in [0, 1] or None), ...)
    augment_friendly: bool = False


def expected_max_of_three(values) -> float | None:
    """E[max] of 3 draws without replacement; None with fewer than 3 values."""
    v = sorted(values)
    m = len(v)
    if m < 3:
        return None
    total = comb(m, 3)
    return sum(comb(i, 2) * v[i] for i in range(2, m)) / total


def augment_leverage(deltas_by_rarity: dict[str, list[float]], frequency=None) -> float | None:
    parts = {}
    for r, values in sorted(deltas_by_rarity.items()):
        e = expected_max_of_three(values)
        if e is not None:
            parts[r] = e
    if not parts:
        return None
    freq = {r: (frequency or {}).get(r, 1.0) for r in parts}
    total = sum(freq.values())
    return sum(freq[r] * parts[r] for r in parts) / total


def _confidence(n: int) -> str:
    # Proposal: bands on the champion's games in the snapshot.
    return "high" if n >= 5000 else "medium" if n >= 500 else "low"


def build_champion_tiers(
    champions: dict[str, tuple[int, int]],
    pair_deltas: dict[str, dict[str, list[float]]],
    config: ChampionTierConfig = ChampionTierConfig(),
    extra_components: dict[str, dict[str, float | None]] | None = None,
    relative_gain: dict[str, float | None] | None = None,
) -> tuple[list[ChampionTierRow], dict[str, float]]:
    """``champions``: id -> (wins, games); ``pair_deltas``: id -> rarity ->
    shrunk ΔWR of each augment with champion-level data. ``extra_components``
    may supply already-normalised ``combat``/``consistency`` in [0, 1].

    ``relative_gain`` (owner decision 2026-11-23: ARAM is for fun) is how far
    the best augment offers lift a champion above its *own* baseline. It does
    not move a champion between tie groups or tiers; it orders champions
    inside a statistical tie group and labels the top ones as
    ``augment_friendly``. As a score component it would reward weak
    champions and hurt prediction (F7 holdout)."""
    rng = np.random.default_rng(config.seed)
    ids = sorted(c for c, (_, g) in champions.items() if g > 0)
    total_w = sum(champions[c][0] for c in ids)
    total_g = sum(champions[c][1] for c in ids)
    mu = total_w / total_g
    k = config.k_win

    medians, draws = {}, {}
    for c in ids:
        w, g = champions[c]
        a, b = w + k * mu, g - w + k * (1 - mu)
        medians[c] = a / (a + b)
        draws[c] = rng.beta(a, b, size=config.draws)
    ref_win = np.sort(np.array([medians[c] for c in ids]))

    leverage = {c: augment_leverage(pair_deltas.get(c, {}), config.rarity_frequency) for c in ids}
    lev_known = np.sort(np.array([v for v in leverage.values() if v is not None]))

    scores, comps = {}, {}
    for c in ids:
        z = {"win": _midrank_cdf(ref_win, draws[c])}
        z_lev = None
        if leverage[c] is not None and len(lev_known):
            z_lev = float(_midrank_cdf(lev_known, leverage[c]))
        z["leverage"] = z_lev
        extra = (extra_components or {}).get(c, {})
        z["combat"] = extra.get("combat")
        z["consistency"] = extra.get("consistency")
        scores[c] = combine_components(z, config.weights)
        comps[c] = (
            ("win", round(float(_midrank_cdf(ref_win, medians[c])), 4)),
            ("leverage", None if z_lev is None else round(z_lev, 4)),
            ("combat", z["combat"]),
            ("consistency", z["consistency"]),
        )

    med = {c: float(np.median(scores[c])) for c in ids}
    thresholds = {t: float(np.percentile(list(med.values()), p))
                  for t, p in config.percentiles.items()}

    gain = {c: (relative_gain or {}).get(c) for c in ids}
    known_gain = [g for g in gain.values() if g is not None]
    friendly_cut = (float(np.percentile(known_gain, config.friendly_percentile))
                    if known_gain else None)

    # Statistical tie groups on the score order.
    order = sorted(ids, key=lambda c: (-med[c], c))
    groups: list[list[str]] = []
    prev = None
    for c in order:
        if prev is None or float(np.mean(prev > scores[c])) >= config.tie_probability:
            groups.append([])
        groups[-1].append(c)
        prev = scores[c]

    rows = []
    rank = 0
    for members in groups:
        group_id = rank + 1
        # Inside a tie group the relative augment gain decides the order.
        members = sorted(members, key=lambda c: (
            -(gain[c] if gain[c] is not None else float("-inf")), -med[c], c))
        for c in members:
            rank += 1
            p20, p80 = (float(x) for x in np.percentile(scores[c], [20, 80]))
            n = champions[c][1]
            tier = "E"
            for name in TIER_ORDER[:-1]:
                if med[c] >= thresholds[name] and (
                    name != "OP" or (p20 >= thresholds[name] and n >= config.op_min_games)
                ):
                    tier = name
                    break
            rows.append(ChampionTierRow(
                champion_id=c, score=round(med[c], 4), score_p20=round(p20, 4),
                score_p80=round(p80, 4), rank=rank, tie_group=group_id, tier=tier,
                confidence=_confidence(n), n=n, components=comps[c],
                augment_friendly=bool(
                    friendly_cut is not None and gain[c] is not None
                    and gain[c] > friendly_cut),
            ))
    return rows, thresholds
