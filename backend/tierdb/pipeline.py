"""Build one tier run for a patch from the stored observations."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Callable
from datetime import datetime, timezone

from backend.tierdb.augment_tiers import (
    AugmentTierConfig,
    _logit,
    baseline_without,
    build_augment_tiers,
)
from backend.tierdb.champion_tiers import (
    ChampionTierConfig,
    augment_leverage,
    build_champion_tiers,
)
from backend.tierdb.anvil_stats import stat_demand
from backend.tierdb.item_tiers import ItemTierConfig, build_item_tiers, reference_build
from backend.tierdb.store import TierStore


@dataclass(frozen=True)
class ItemInputs:
    """The verified item pool from the app's catalog (item eligibility fix, #107).

    Without it no item tiers are built: observed AramHex items alone are not
    proof that an item is purchasable in this patch's Mayhem shop.
    """
    eligible: set
    boots_eligible: set
    canonical: Callable[[str], str] = staticmethod(lambda x: x)
    fit: dict = field(default_factory=dict)
    item_types: dict | None = None  # item -> stat tags; default: AramHex item_metadata
    conflicts: Callable[[str, str], bool] | None = None


class MultiSourceError(RuntimeError):
    """More than one source carries win data for the patch.

    Precision-weighted fusion of per-source lifts (design §19.3) is not
    implemented; sources are never summed blindly.
    """


def _shrunk_delta(wins: int, games: int, p0: float, k: float) -> float:
    a, b = wins + k * p0, games - wins + k * (1 - p0)
    return float(_logit(a / (a + b)) - _logit(p0))


def run_build(
    store: TierStore,
    patch: str,
    roles: dict[str, str],
    heuristic: dict[tuple[str, str], float | None] | None = None,
    *,
    aug_config: AugmentTierConfig = AugmentTierConfig(),
    champ_config: ChampionTierConfig = ChampionTierConfig(),
    commercial_only: bool = False,
    code_sha: str | None = None,
    leverage_mode: str = "absolute",
    items: ItemInputs | None = None,
    item_config: ItemTierConfig = ItemTierConfig(),
    champion_pool_patches: tuple[str, ...] | None = None,
) -> int:
    """``leverage_mode``: "absolute" (default) feeds the champion leverage
    component with shrunk logit win rates of each champion+augment pair, i.e.
    strength when taking the best of three offers; "relative" uses ΔWR against
    the champion's own baseline. The F7 holdout (16.22 -> 16.23) showed the
    relative form anti-correlates with next-patch win rate (tau -0.25) while
    the absolute one keeps the composite within 0.02 of win rate alone."""
    if leverage_mode not in ("absolute", "relative"):
        raise ValueError(f"unknown leverage_mode {leverage_mode!r}")
    obs = store.observations(patch=patch, metric="win", commercial_only=commercial_only)
    latest: dict[str, int] = {}
    for o in obs:
        latest[o.source_name] = max(latest.get(o.source_name, 0), o.snapshot_id)
    if not latest:
        raise ValueError(f"no win data stored for patch {patch}")
    if len(latest) > 1:
        raise MultiSourceError(f"win data from several sources: {sorted(latest)}")
    (source_name, snap_id), = latest.items()
    snap = store.snapshot(snap_id)
    obs = [o for o in obs if o.snapshot_id == snap_id]

    champions = {o.champion_id: (o.wins, o.n) for o in obs if o.scope == "champion"}
    pairs = {(o.champion_id, o.augment_id): (o.wins, o.n) for o in obs if o.scope == "champ_aug"}
    rarity = store.augment_rarities(patch)
    heuristic = heuristic or {}

    aug_rows, aug_thresholds = build_augment_tiers(
        champions, pairs, rarity, roles, heuristic, aug_config)

    pair_deltas: dict[str, dict[str, list[float]]] = {}
    relative: dict[str, dict[str, list[float]]] = {}
    for (c, a), (w, g) in sorted(pairs.items()):
        if c in champions and a in rarity:
            p0 = baseline_without(*champions[c], w, g)
            delta = _shrunk_delta(w, g, p0, aug_config.k_win)
            value = delta + float(_logit(p0)) if leverage_mode == "absolute" else delta
            pair_deltas.setdefault(c, {}).setdefault(rarity[a], []).append(value)
            relative.setdefault(c, {}).setdefault(rarity[a], []).append(delta)
    # Owner decision 23/11: relative gain = tie-breaker + visible "potential".
    relative_gain = {c: augment_leverage(by_r, champ_config.rarity_frequency)
                     for c, by_r in relative.items()}
    # Owner decisions 24/11: the champion list pools the previous patch's
    # champion games with this patch, the current patch weighing >= 50%;
    # augments, leverage and potential stay on this patch only.
    pool_patches = (tuple(champion_pool_patches) if champion_pool_patches is not None
                    else _previous_patches(store, patch, source_name))
    pooled, pooled_from, pool_scale = _pooled_champions(
        store, champions, pool_patches, source_name, commercial_only)
    champ_rows, champ_thresholds = build_champion_tiers(
        pooled, pair_deltas, champ_config, relative_gain=relative_gain)

    item_rows, references, demands = _build_items(
        store, patch, snap_id, roles, items, item_config) if items else ([], {}, {})

    empirical = [{"source": source_name, "snapshot_sha256": snap.sha256, "region": snap.region}]
    curated = [{"source": "curated_heuristic"}]
    con = store.connection
    with con:
        cur = con.execute(
            """INSERT INTO tier_run (patch, created_at, code_sha, weights_json,
                   thresholds_json, snapshot_ids_json, seed) VALUES (?,?,?,?,?,?,?)""",
            (
                patch, datetime.now(timezone.utc).isoformat(), code_sha,
                json.dumps({"augments": aug_config.weights, "champions": champ_config.weights}),
                json.dumps({"augments": aug_thresholds, "champions": champ_thresholds,
                            "leverage_mode": leverage_mode,
                            "augment_config": asdict(aug_config),
                            "item_config": asdict(item_config),
                            "champion_config": asdict(champ_config),
                            "champion_pool": [{"patch": p_, "snapshot_id": i_}
                                              for p_, i_ in pooled_from],
                            "champion_pool_scale": pool_scale}, sort_keys=True),
                json.dumps([snap_id] + [i_ for _p, i_ in pooled_from]), aug_config.seed,
            ),
        )
        run_id = cur.lastrowid
        con.executemany(
            """INSERT INTO augment_tier (run_id, champion_id, rarity, augment_id, score,
                   score_p20, score_p80, rank, tie_group, tier, level, confidence,
                   n_eff, sources_json, rank_all, effect_pp)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (run_id, r.champion_id, r.rarity, r.augment_id, r.score, r.score_p20,
                 r.score_p80, r.rank, r.tie_group, r.tier, r.level, r.confidence, r.n_eff,
                 json.dumps(curated if r.level == "curated" else [] if r.level == "none"
                            else empirical), r.rank_all, r.effect_pp)
                for r in aug_rows
            ],
        )
        con.executemany(
            """INSERT INTO champion_tier (run_id, champion_id, score, components_json,
                   rank, tie_group, tier, confidence, n, potential)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
            [
                (run_id, r.champion_id, r.score, json.dumps(dict(r.components)), r.rank,
                 r.tie_group, r.tier, r.confidence, r.n, r.potential)
                for r in champ_rows
            ],
        )
        con.executemany(
            """INSERT INTO item_tier (run_id, champion_id, item_id, kind, score, score_p20,
                   score_p80, rank, tie_group, tier, level, confidence)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            [(run_id, r.champion_id, r.item_id, r.kind, r.score, r.score_p20, r.score_p80,
              r.rank, r.tie_group, r.tier, r.level, r.confidence) for r in item_rows],
        )
        rows = []
        for champion, ref in references.items():
            rows += [(run_id, champion, slot, iid, src)
                     for slot, (iid, src) in enumerate(zip(ref.items, ref.sources), start=1)]
            if ref.boots:
                rows.append((run_id, champion, 0, ref.boots, "boots"))
        con.executemany(
            "INSERT INTO reference_build (run_id, champion_id, slot, item_id, source) "
            "VALUES (?,?,?,?,?)", rows)
        con.executemany(
            "INSERT INTO champion_stat_demand (run_id, champion_id, stat, weight, source) "
            "VALUES (?,?,?,?,?)",
            [(run_id, champion, stat, round(w, 6), src)
             for champion, (weights, src) in demands.items() for stat, w in weights.items()])
    return run_id


# Stats a build must not miss when most of the champion's games use them.
REQUIRED_STAT_TAGS = {"as": ("AttackSpeed",)}
REQUIRED_STAT_COVERAGE = 0.6   # item-instances with the stat per champion game


def required_stats(finals: dict, champion_games: int, types: dict, *,
                   canonical=lambda x: x) -> dict[str, set[str]]:
    """{stat: items giving it} for stats in >= 60% of the champion's games."""
    if champion_games <= 0:
        return {}
    out = {}
    for stat, tags in REQUIRED_STAT_TAGS.items():
        givers = {canonical(i) for i in finals if set(types.get(i, ())) & set(tags)}
        games = sum(n for i, (_w, n) in finals.items() if canonical(i) in givers)
        if givers and games / champion_games >= REQUIRED_STAT_COVERAGE:
            out[stat] = givers
    return out


def _patch_key(patch: str) -> tuple:
    return tuple(int(x) if x.isdigit() else x for x in re.split(r"[.\-]", patch))


def _previous_patches(store: TierStore, patch: str, source_name: str) -> tuple[str, ...]:
    """The newest stored patch older than ``patch`` from the same source."""
    rows = store.connection.execute(
        """SELECT DISTINCT s.patch FROM snapshot s JOIN source src ON src.id = s.source_id
           WHERE src.name = ?""", (source_name,)).fetchall()
    try:
        older = [p for (p,) in rows if _patch_key(p) < _patch_key(patch)]
    except TypeError:
        return ()
    return (max(older, key=_patch_key),) if older else ()


CURRENT_PATCH_MIN_SHARE = 0.5   # owner 24/11: the current patch weighs at least half


def _pooled_champions(store, champions, patches, source_name, commercial_only,
                      min_share: float = CURRENT_PATCH_MIN_SHARE):
    """Champion (wins, games) of this patch plus ``patches``, the older games
    scaled down so this patch keeps at least ``min_share`` of the total."""
    older: dict[str, list[float]] = {}
    used = []
    for prev in patches:
        obs = [o for o in store.observations(patch=prev, metric="win", scope="champion",
                                             commercial_only=commercial_only)
               if o.source_name == source_name]
        if not obs:
            continue
        snap = max(o.snapshot_id for o in obs)
        for o in obs:
            if o.snapshot_id == snap and o.champion_id in champions:
                acc = older.setdefault(o.champion_id, [0.0, 0.0])
                acc[0] += o.wins
                acc[1] += o.n
        used.append((prev, snap))
    current_games = sum(g for _w, g in champions.values())
    older_games = sum(g for _w, g in older.values())
    scale = 1.0
    if older_games and min_share < 1:
        scale = min(1.0, current_games * (1 - min_share) / (min_share * older_games))
    pooled = {c: (int(round(w + scale * older.get(c, (0, 0))[0])),
                  int(round(g + scale * older.get(c, (0, 0))[1])))
              for c, (w, g) in champions.items()}
    return pooled, used, round(scale, 6)


def _build_items(store, patch, snap_id, roles, inputs: ItemInputs, config: ItemTierConfig):
    """Item tiers, reference builds and Anvil stat demand for one snapshot."""
    obs = [o for o in store.item_observations(patch) if o.snapshot_id == snap_id]
    if not obs:
        return [], {}, {}
    data: dict[str, dict] = {}
    for o in obs:
        d = data.setdefault(o.champion_id, {"finals": {}, "boots": {}, "cores": []})
        if o.scope == "champ_item":
            d["finals"][o.item_id] = (o.wins, o.n)
        elif o.scope == "champ_item_base":
            d["base"] = (o.wins, o.n)
        elif o.scope == "champ_boots":
            d["boots"][o.item_id] = (o.wins, o.n)
        elif o.scope == "champ_boots_base":
            d["boots_base"] = (o.wins, o.n)
        elif o.scope == "champ_core":
            d["cores"].append((o.items, o.wins, o.n, o.value))
    rows = build_item_tiers(
        data, config, eligible=set(inputs.eligible), boots_eligible=set(inputs.boots_eligible),
        canonical=inputs.canonical, fit=inputs.fit)
    types = inputs.item_types
    if types is None:
        types = {iid: tags for iid, (_, tags) in store.item_info(patch).items()}
    references, demands = {}, {}
    for champion, d in data.items():
        ref = reference_build(champion, d["cores"], rows, config=config,
                              conflicts=inputs.conflicts, canonical=inputs.canonical)
        core = [i for i, src in zip(ref.items, ref.sources) if src == "core"]
        ap_core = sum("SpellDamage" in types.get(i, ()) for i in core) >= 2
        required = {} if ap_core else required_stats(
            d.get("finals") or {}, (d.get("base") or (0, 0))[1], types,
            canonical=inputs.canonical)
        if required:  # AP cores (e.g. AP Trundle) never get a forced AS item
            ref = reference_build(champion, d["cores"], rows, config=config,
                                  conflicts=inputs.conflicts, canonical=inputs.canonical,
                                  required=required)
        boots_played = {inputs.canonical(i): n for i, (_w, n) in (d.get("boots") or {}).items()
                        if not inputs.boots_eligible
                        or inputs.canonical(i) in set(inputs.boots_eligible)}
        if boots_played:
            # Owner decision 23/11: the default boots are the ones most played on
            # the champion (Yi: Berserker's); the enemy team may change them live.
            import dataclasses
            ref = dataclasses.replace(ref, boots=max(sorted(boots_played),
                                                     key=lambda i: boots_played[i]))
        references[champion] = ref
        top = [r.item_id for r in sorted(
            (r for r in rows if r.champion_id == champion and r.kind == "final"
             and r.level == "champion"), key=lambda r: r.rank)]
        popular = {iid: n for iid, (_w, n) in d["finals"].items()
                   if not inputs.eligible or inputs.canonical(iid) in set(inputs.eligible)}
        weights = stat_demand(roles.get(champion, ""), top, types, popular=popular)
        demands[champion] = (weights, "builds" if any(types.get(i) for i in top[:8]) else "role")
    return rows, references, demands
