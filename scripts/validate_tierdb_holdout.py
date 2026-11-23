"""F7 offline temporal-holdout validation of the tier DB (design §6).

Train on patch N, test on patch N+1 (two AramHex dataset directories).
Prints aggregate rank-agreement metrics only; run it locally and keep the
output outside the public repository.

    python scripts/validate_tierdb_holdout.py TRAIN_DIR TEST_DIR
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.tierdb.aramhex import load_aramhex_dataset  # noqa: E402
from backend.tierdb.augment_tiers import (  # noqa: E402
    AugmentTierConfig, _logit, baseline_without, build_augment_tiers)
from backend.tierdb.champion_tiers import ChampionTierConfig, build_champion_tiers  # noqa: E402
from backend.tierdb.pipeline import _shrunk_delta  # noqa: E402


def kendall_tau_b(x, y) -> float | None:
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3:
        return None
    dx = np.sign(x[:, None] - x[None, :])
    dy = np.sign(y[:, None] - y[None, :])
    iu = np.triu_indices(len(x), 1)
    dx, dy = dx[iu], dy[iu]
    num = float(np.sum(dx * dy))
    den = float(np.sqrt(np.sum(dx != 0) * np.sum(dy != 0)))
    return num / den if den else None


def load(directory):
    heroes = json.loads((Path(directory) / "heroes.json").read_text(encoding="utf-8-sig"))
    ds = load_aramhex_dataset(directory, {k: k for k in heroes})
    champs = {o.champion_id: (o.wins, o.n) for o in ds.observations if o.scope == "champion"}
    pairs = {(o.champion_id, o.augment_id): (o.wins, o.n)
             for o in ds.observations if o.scope == "champ_aug"}
    rarity = {a: r for a, (_, r) in ds.augments.items()}
    return champs, pairs, rarity


def raw_delta(champs, pairs, key):
    w, g = pairs[key]
    p0 = baseline_without(*champs[key[0]], w, g)
    return float(_logit(min(max(w / g, 1e-4), 1 - 1e-4)) - _logit(p0))


def mean_group_tau(pred: dict, truth: dict, rarity: dict) -> tuple[float, int]:
    groups: dict = {}
    for key in pred.keys() & truth.keys():
        groups.setdefault((key[0], rarity[key[1]]), []).append(key)
    taus = []
    for keys in groups.values():
        t = kendall_tau_b([pred[k] for k in keys], [truth[k] for k in keys])
        if t is not None:
            taus.append(t)
    return float(np.mean(taus)), len(taus)


def main(train_dir, test_dir):
    tc, tp, tr = load(train_dir)
    vc, vp, vr = load(test_dir)
    roles = {c: "all" for c in tc}  # no role map offline; role level == global
    truth = {k: raw_delta(vc, vp, k) for k in vp if k[0] in vc and k[1] in vr}

    report = {"train_pairs": len(tp), "test_pairs": len(vp)}
    raw = {k: raw_delta(tc, tp, k) for k in tp if k[0] in tc and k[1] in tr}
    report["augments_tau_raw_dwr"] = mean_group_tau(raw, truth, tr)
    for k in (30, 100, 300, 1000, 3000):
        shrunk = {}
        for key in raw:
            w, g = tp[key]
            shrunk[key] = _shrunk_delta(w, g, baseline_without(*tc[key[0]], w, g), k)
        report[f"augments_tau_shrunk_k{k}"] = mean_group_tau(shrunk, truth, tr)

    rows, _ = build_augment_tiers(tc, tp, tr, roles, {}, AugmentTierConfig(draws=200))
    comp = {(r.champion_id, r.augment_id): r.score for r in rows if r.score is not None}
    # Same key set as the ΔWR-only predictors (pairs with train-patch data).
    report["augments_tau_composite"] = mean_group_tau(
        {k: v for k, v in comp.items() if k in raw}, truth, tr)
    # Pairs without train-patch data: only the fallback levels can rank them.
    report["augments_tau_composite_fallback_only"] = mean_group_tau(
        {k: v for k, v in comp.items() if k not in raw}, truth, tr)
    # Tier stability between patches.
    rows_v, _ = build_augment_tiers(vc, vp, vr, {c: "all" for c in vc}, {},
                                    AugmentTierConfig(draws=200))
    order = "OP S A B C D E".split()
    tv = {(r.champion_id, r.augment_id): r.tier for r in rows_v if r.tier}
    diffs = [abs(order.index(r.tier) - order.index(tv[(r.champion_id, r.augment_id)]))
             for r in rows if r.tier and (r.champion_id, r.augment_id) in tv]
    report["augment_tier_same_or_adjacent"] = round(float(np.mean(np.array(diffs) <= 1)), 4)
    report["augment_tier_identical"] = round(float(np.mean(np.array(diffs) == 0)), 4)

    # Champions: composite vs WR only, target = next-patch win rate.
    rel_deltas: dict = {}
    for (c, a), (w, g) in tp.items():
        if c in tc and a in tr:
            rel_deltas.setdefault(c, {}).setdefault(tr[a], []).append(
                _shrunk_delta(w, g, baseline_without(*tc[c], w, g), 300))
    from backend.tierdb.champion_tiers import augment_leverage
    gain = {c: augment_leverage(v) for c, v in rel_deltas.items()}
    for mode in ("absolute", "relative"):
        deltas: dict = {}
        for (c, a), (w, g) in tp.items():
            if c in tc and a in tr:
                p0 = baseline_without(*tc[c], w, g)
                value = _shrunk_delta(w, g, p0, 300)
                if mode == "absolute":
                    value += float(_logit(p0))
                deltas.setdefault(c, {}).setdefault(tr[a], []).append(value)
        crows, _ = build_champion_tiers(tc, deltas, ChampionTierConfig(draws=200))
        common = [r.champion_id for r in crows if r.champion_id in vc]
        target = [vc[c][0] / vc[c][1] for c in common]
        comp_c = {r.champion_id: r.score for r in crows}
        report[f"champions_tau_composite_{mode}"] = kendall_tau_b(
            [comp_c[c] for c in common], target)
        lev = {r.champion_id: dict(r.components)["leverage"] for r in crows}
        report[f"champions_tau_leverage_only_{mode}"] = kendall_tau_b(
            [lev[c] or 0 for c in common], target)
        if mode == "absolute":
            tb_rows, _ = build_champion_tiers(tc, deltas, ChampionTierConfig(draws=200),
                                              relative_gain=gain)
            rank = {r.champion_id: -r.rank for r in tb_rows}
            report["champions_tau_rank_absolute_with_gain_tiebreak"] = kendall_tau_b(
                [rank[c] for c in common], target)
            rank0 = {r.champion_id: -r.rank for r in crows}
            report["champions_tau_rank_absolute_no_tiebreak"] = kendall_tau_b(
                [rank0[c] for c in common], target)
            report["champions_potential_counts"] = {
                p: sum(r.potential == p for r in tb_rows)
                for p in ("very_low", "low", "medium", "high", "very_high")}
    report["champions_tau_wr_only"] = kendall_tau_b([tc[c][0] / tc[c][1] for c in common], target)
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
