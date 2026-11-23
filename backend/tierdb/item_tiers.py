"""Per-champion item tier lists and reference builds (design: DESENHO_ITENS_BUILDS_ANVILS).

Measured inputs come from AramHex equipment tables: finished items held at
game end (with their own champion denominator), Boots-typed holdings, and the
ordered first-three-legendary cores. Win-rate deltas are biased by game length
(items that finish late only appear in long games), so they only order items
within a champion, are shrunk to the champion's own equipment baseline and
share the score with core-build presence and stat fit:

    S = 10 * (0.50 * pct(ΔWR) + 0.30 * pct(core presence) + 0.20 * pct(fit))

Missing components redistribute their weight. Items below 2 % of the
champion's games (or 200 games) are not measured: they fall back to a
heuristic level ranked by fit only and capped at tier A. Nothing here is
exported except tier, rank, tie group, level and confidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

import numpy as np

from backend.tierdb.augment_tiers import TIER_ORDER, _logit, _midrank_cdf

ITEM_LEVELS = ("champion", "heuristic")
ITEM_LEVEL_CAP = {"champion": "OP", "heuristic": "A"}
ITEM_LEVEL_CONFIDENCE = {"champion": "high", "heuristic": "heuristic"}


@dataclass(frozen=True)
class ItemTierConfig:
    k_win: float = 300.0
    min_share: float = 0.02
    min_games: int = 200
    min_core_pick: float = 0.05
    draws: int = 300
    seed: int = 20261125
    tie_probability: float = 0.75
    percentiles: dict = field(default_factory=lambda: {
        "OP": 97, "S": 85, "A": 65, "B": 40, "C": 20, "D": 7})
    # Proposal approved with the design 2026-11-23 (win rate weight 50 %).
    weights: dict = field(default_factory=lambda: {"win": 50, "core": 30, "fit": 20})


@dataclass(frozen=True)
class ItemTierRow:
    champion_id: str
    item_id: str
    kind: str  # final | boots
    score: float | None
    score_p20: float | None
    score_p80: float | None
    rank: int | None
    tie_group: int | None
    tier: str | None
    level: str
    confidence: str


@dataclass(frozen=True)
class ReferenceBuild:
    champion_id: str
    items: tuple[str, ...]
    sources: tuple[str, ...]  # core | tier
    boots: str | None


def _shrunk(wins: float, games: float, p0: float, k: float) -> float:
    return (wins + k * p0) / (games + k)


def _merge(rows: dict, canonical: Callable[[str], str], eligible) -> dict:
    out: dict[str, list[int]] = {}
    for raw, (wins, games) in rows.items():
        iid = canonical(str(raw))
        if eligible is not None and iid not in eligible:
            continue
        acc = out.setdefault(iid, [0, 0])
        acc[0] += int(wins)
        acc[1] += int(games)
    return out


def _tier(score: float, p20: float, thresholds: dict, level: str) -> str:
    tier = "E"
    for name in TIER_ORDER[:-1]:
        if score >= thresholds[name] and (name != "OP" or p20 >= thresholds[name]):
            tier = name
            break
    cap = ITEM_LEVEL_CAP[level]
    return TIER_ORDER[max(TIER_ORDER.index(tier), TIER_ORDER.index(cap))]


def _score_one(champion: str, kind: str, base: tuple[int, int], items: dict,
               cores: list, fit: dict, config: ItemTierConfig, rng,
               extra_ids: Iterable[str]):
    """Score draws for one champion and one list (finals or boots)."""
    base_w, base_n = base
    p0 = (base_w + 1.0) / (base_n + 2.0)
    measured = {iid: wg for iid, wg in items.items()
                if wg[1] >= config.min_games and base_n and wg[1] / base_n >= config.min_share}
    presence: dict[str, float] = {}
    if kind == "final":
        for core_items, wins, games, pick in cores:
            weight = (pick or 0.0) * _shrunk(wins, games, p0, config.k_win)
            for iid in set(core_items):
                presence[iid] = presence.get(iid, 0.0) + weight
    weights = dict(config.weights)
    if kind != "final" or not presence:
        weights.pop("core", None)
    ids = sorted(set(items) | set(extra_ids))
    fit_known = {i: fit.get((champion, i)) for i in ids}
    if all(v is None for v in fit_known.values()):
        weights.pop("fit", None)
    result = {}
    meas_ids = sorted(measured)
    if meas_ids:
        a = np.array([measured[i][0] + config.k_win * p0 for i in meas_ids])
        b = np.array([measured[i][1] - measured[i][0] + config.k_win * (1 - p0) for i in meas_ids])
        median = _logit(a / (a + b)) - _logit(p0)
        draws = _logit(rng.beta(a[:, None], b[:, None], size=(len(meas_ids), config.draws))) \
            - _logit(p0)
        ref_sorted = np.sort(median)
        z_win = np.stack([_midrank_cdf(np.sort(draws[:, d]), draws[:, d])
                          for d in range(config.draws)], axis=1)
        pres = np.array([presence.get(i, 0.0) for i in meas_ids])
        z_core = _midrank_cdf(np.sort(pres), pres) if "core" in weights else None
        fits = np.array([fit_known.get(i) if fit_known.get(i) is not None else 0.5
                         for i in meas_ids])
        z_fit = _midrank_cdf(np.sort(fits), fits) if "fit" in weights else None
        total = sum(weights.values())
        score_draws = weights["win"] * z_win
        if z_core is not None:
            score_draws = score_draws + weights["core"] * z_core[:, None]
        if z_fit is not None:
            score_draws = score_draws + weights["fit"] * z_fit[:, None]
        score_draws = 10.0 * score_draws / total
        del ref_sorted
        for idx, iid in enumerate(meas_ids):
            result[iid] = ("champion", score_draws[idx])
    # Heuristic level: unmeasured items, ranked by fit only (capped at A).
    rest = [i for i in ids if i not in measured]
    if rest:
        fits = np.array([fit_known.get(i) if fit_known.get(i) is not None else 0.0
                         for i in rest])
        z = _midrank_cdf(np.sort(fits), fits) if len(rest) > 1 else np.array([0.5])
        for idx, iid in enumerate(rest):
            # Heuristic items stay below measured ones of equal fit.
            result[iid] = ("heuristic", np.full(config.draws, 10.0 * 0.5 * z[idx]))
    return result


def _rank(scored: dict, config: ItemTierConfig):
    ids = sorted(scored, key=lambda i: (-float(np.median(scored[i][1])), i))
    groups, group = {}, 0
    for pos, iid in enumerate(ids, start=1):
        if pos == 1:
            group = 1
        else:
            prev = scored[ids[pos - 2]][1]
            cur = scored[iid][1]
            if float(np.mean(prev > cur)) >= config.tie_probability:
                group = pos
        groups[iid] = (pos, group)
    return ids, groups


def build_item_tiers(
    data: dict[str, dict],
    config: ItemTierConfig = ItemTierConfig(),
    *,
    eligible: set[str] | None = None,
    boots_eligible: set[str] | None = None,
    canonical: Callable[[str], str] | None = None,
    fit: dict[tuple[str, str], float] | None = None,
) -> list[ItemTierRow]:
    """Item and boots tiers per champion.

    ``data[champion]`` = {"base": (wins, games), "finals": {item: (wins, games)},
    "boots": {...}, "boots_base": (wins, games), "cores": [(items, wins, games, pick)]}.
    ``eligible`` (canonical ids) comes from the verified item pool; without it
    only observed items are listed. Eligible items without data are listed at
    the heuristic level so every recommendable item has a place.
    """
    canonical = canonical or (lambda x: x)
    fit = fit or {}
    rng = np.random.default_rng(config.seed)
    scored: dict[tuple[str, str], dict] = {}
    for champion in sorted(data):
        d = data[champion]
        finals = _merge(d.get("finals", {}), canonical, eligible)
        boots = _merge(d.get("boots", {}), canonical, boots_eligible)
        cores = [(tuple(canonical(i) for i in items), w, g, pick)
                 for items, w, g, pick in d.get("cores", [])
                 if (pick or 0) >= config.min_core_pick]
        scored[(champion, "final")] = _score_one(
            champion, "final", d.get("base", (0, 0)), finals, cores, fit, config, rng,
            eligible or ())
        scored[(champion, "boots")] = _score_one(
            champion, "boots", d.get("boots_base", d.get("base", (0, 0))), boots, [], fit,
            config, rng, boots_eligible or ())
    reference = np.array(sorted(float(np.median(s)) for sc in scored.values()
                                for level, s in sc.values() if level == "champion"))
    thresholds = ({t: float(np.percentile(reference, p)) for t, p in config.percentiles.items()}
                  if len(reference) else {t: 10.0 for t in config.percentiles})
    rows: list[ItemTierRow] = []
    for (champion, kind), sc in scored.items():
        ids, groups = _rank(sc, config)
        for iid in ids:
            level, draws = sc[iid]
            med = float(np.median(draws))
            p20, p80 = (float(np.percentile(draws, q)) for q in (20, 80))
            rank, group = groups[iid]
            rows.append(ItemTierRow(
                champion_id=champion, item_id=iid, kind=kind, score=round(med, 4),
                score_p20=round(p20, 4), score_p80=round(p80, 4), rank=rank,
                tie_group=group, tier=_tier(med, p20, thresholds, level), level=level,
                confidence=ITEM_LEVEL_CONFIDENCE[level]))
    return rows


def reference_build(
    champion: str,
    cores: list,
    rows: list[ItemTierRow],
    *,
    config: ItemTierConfig = ItemTierConfig(),
    size: int = 6,
    conflicts: Callable[[str, str], bool] | None = None,
    canonical: Callable[[str], str] | None = None,
) -> ReferenceBuild:
    """Slots 1-3 from the best measured core (order kept), 4-6 from item tiers."""
    canonical = canonical or (lambda x: x)
    conflicts = conflicts or (lambda a, b: False)
    mine = [r for r in rows if r.champion_id == champion]
    finals = sorted((r for r in mine if r.kind == "final"), key=lambda r: r.rank or 10**6)
    allowed = {r.item_id for r in finals}
    boots = sorted((r for r in mine if r.kind == "boots"), key=lambda r: r.rank or 10**6)
    items: list[str] = []
    sources: list[str] = []

    def fits(iid):
        return iid in allowed and iid not in items and not any(conflicts(iid, o) for o in items)

    best, best_value = None, -1.0
    total_w = sum(w for _, w, _, _ in cores) or 0
    total_g = sum(g for _, _, g, _ in cores) or 0
    p0 = (total_w + 1.0) / (total_g + 2.0)
    for core_items, wins, games, pick in cores:
        if (pick or 0) < config.min_core_pick:
            continue
        value = _shrunk(wins, games, p0, config.k_win)
        if value > best_value:
            best, best_value = tuple(canonical(i) for i in core_items), value
    for iid in best or ():
        if len(items) < size and fits(iid):
            items.append(iid)
            sources.append("core")
    for row in finals:
        if len(items) >= size:
            break
        if fits(row.item_id):
            items.append(row.item_id)
            sources.append("tier")
    return ReferenceBuild(champion, tuple(items), tuple(sources),
                          boots[0].item_id if boots else None)
