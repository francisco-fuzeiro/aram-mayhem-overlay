"""Per-augment impact from local 10-player Mayhem history (owner decisions 23/11).

Per game: z(damage to champions per minute) + z(heal+shield per minute), each
against that champion's own baseline in the local history, summed. There are no
role labels: a full-AP Sona counts by damage, a healing Sona by heal+shield, a
tank by the damage it really deals. Per (champion, augment) the mean game score
is shrunk by n and squashed to [-1, 1]. Win rates are never shown; this value
only feeds the bounded context adjustment, and only after the holdout passes.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

METRIC = "z_damage_plus_heal_shield"


@dataclass(frozen=True)
class ImpactConfig:
    min_games: int = 5             # games with the augment on that champion
    champion_min_games: int = 10   # games of the champion to form a baseline
    shrink_k: float = 20.0         # mean * n / (n + k)
    scale: float = 1.0             # z-sum that maps to tanh(1) ≈ 0.76
    min_secs: int = 300            # remakes are ignored
    prior_games: float = 20.0      # weight of the normal-ARAM prior, in pseudo-games


def _per_min(value, minutes: float) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or minutes <= 0:
        return None
    return float(value) / minutes


def _healing(row: dict):
    hs = row.get("heal_shield")
    return hs if hs is not None else row.get("heal_total")


def _moments(values: list[float]) -> tuple[int, float, float]:
    n = len(values)
    if not n:
        return 0, 0.0, 0.0
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1) if n > 1 else 0.0
    return n, mean, var


def _zscorer(values: list[float], prior: tuple[float, float] | None = None, k: float = 0.0):
    """z against the local baseline, blended with a (mean, sd) prior of weight k."""
    n, mean, var = _moments(values)
    if prior is not None and k > 0:
        m0, sd0 = prior
        w = n / (n + k)
        mean = w * mean + (1 - w) * m0
        var = (var * max(n - 1, 0) + k * sd0 * sd0) / (max(n - 1, 0) + k)
    elif n < 2:
        return lambda _v: 0.0
    std = math.sqrt(max(var, 0.0))
    if std <= max(1e-9, 1e-6 * abs(mean)):
        return lambda _v: 0.0
    return lambda v: (v - mean) / std


def _prior_scale(by_champ: dict, prior: dict, config: ImpactConfig) -> tuple[float, float]:
    """Mayhem/normal-ARAM ratio (damage, heal) from champions with local baselines."""
    def median(xs):
        xs = sorted(xs)
        return xs[len(xs) // 2] if xs else 1.0
    dmg, heal = [], []
    for champ, games in by_champ.items():
        p = prior.get(champ)
        if not p or len(games) < config.champion_min_games:
            continue
        if p["dmg_per_min_mean"] > 0:
            dmg.append(sum(g[1] for g in games) / len(games) / p["dmg_per_min_mean"])
        if p["heal_shield_per_min_mean"] > 0:
            heal.append(sum(g[2] for g in games) / len(games) / p["heal_shield_per_min_mean"])
    return median(dmg), median(heal)


def game_scores(rows: list[dict], config: ImpactConfig = ImpactConfig(),
                prior: dict | None = None) -> list[tuple[dict, float]]:
    """(row, summed z) for every valid row of a champion with a baseline.

    `prior` = backend.tierdb.riot_prior.load_prior(): per-champion normal-ARAM
    stats, rescaled to Mayhem levels and blended as `prior_games` pseudo-games.
    """
    by_champ: dict[str, list[tuple[dict, float, float]]] = defaultdict(list)
    for row in rows:
        secs = row.get("duration") or 0
        champ = row.get("champion_id")
        if not champ or secs < config.min_secs:
            continue
        minutes = secs / 60.0
        dmg = _per_min(row.get("damage_to_champions"), minutes)
        if dmg is None:
            continue
        heal = _per_min(_healing(row), minutes) or 0.0
        by_champ[champ].append((row, dmg, heal))
    prior = prior or {}
    fd, fh = _prior_scale(by_champ, prior, config) if prior else (1.0, 1.0)
    out = []
    for champ, games in by_champ.items():
        p = prior.get(champ)
        if len(games) < config.champion_min_games and not p:
            continue
        k = config.prior_games if p else 0.0
        zd = _zscorer([g[1] for g in games],
                      (p["dmg_per_min_mean"] * fd, p["dmg_per_min_sd"] * fd) if p else None, k)
        zh = _zscorer([g[2] for g in games],
                      (p["heal_shield_per_min_mean"] * fh,
                       p["heal_shield_per_min_sd"] * fh) if p else None, k)
        out.extend((row, zd(d) + zh(h)) for row, d, h in games)
    return out


def augment_impact(rows: list[dict], config: ImpactConfig = ImpactConfig(),
                   prior: dict | None = None) -> dict:
    """{(champion, augment): {impact in [-1,1], metric, n, mean_z}}."""
    acc: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row, score in game_scores(rows, config, prior):
        for aug in dict.fromkeys(str(a) for a in row.get("augments") or []):
            acc[(row["champion_id"], aug)].append(score)
    out = {}
    for key, scores in acc.items():
        n = len(scores)
        if n < config.min_games:
            continue
        mean = sum(scores) / n
        shrunk = mean * n / (n + config.shrink_k)
        out[key] = {"impact": round(math.tanh(shrunk / config.scale), 4),
                    "metric": METRIC, "n": n, "mean_z": round(mean, 4)}
    return out
