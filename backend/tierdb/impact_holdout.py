"""Temporal holdout for the impact metric (shared by the script and the server).

Train on the oldest local games, test on the newest; impact may feed the
in-match ±1 tier adjustment only when ΔWR + w·impact beats ΔWR alone by
>= MIN_GAIN AUC on >= MIN_TEST_ROWS rows (owner decision 23/11). Returns
counts and scores only: no champion names, games or players.
"""
from __future__ import annotations

from collections import defaultdict

from backend.tierdb.impact import ImpactConfig, augment_impact

MIN_TEST_ROWS = 500
MIN_GAIN = 0.01
WEIGHTS = (0.25, 0.5, 1.0)


def _auc(pairs: list[tuple[float, bool]]) -> float | None:
    pos = [s for s, w in pairs if w]
    neg = [s for s, w in pairs if not w]
    if not pos or not neg:
        return None
    ranked = sorted(pairs, key=lambda p: p[0])
    # Average ranks for ties (Mann-Whitney U).
    ranks, i = {}, 0
    while i < len(ranked):
        j = i
        while j < len(ranked) and ranked[j][0] == ranked[i][0]:
            j += 1
        for k in range(i, j):
            ranks[k] = (i + j + 1) / 2.0
        i = j
    rpos = sum(ranks[k] for k, (_, w) in enumerate(ranked) if w)
    return (rpos - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))


def _shrunk_wr(rows: list[dict], k: float = 20.0) -> dict:
    champ = defaultdict(lambda: [0, 0])
    pair = defaultdict(lambda: [0, 0])
    for r in rows:
        if r.get("win") is None:
            continue
        champ[r["champion_id"]][0] += int(r["win"]); champ[r["champion_id"]][1] += 1
        for a in dict.fromkeys(r.get("augments") or []):
            p = pair[(r["champion_id"], a)]; p[0] += int(r["win"]); p[1] += 1
    out = {}
    for (c, a), (w, n) in pair.items():
        cw, cn = champ[c]
        out[(c, a)] = (w - n * (cw / cn)) / (n + k)
    return out


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else 0.0


def evaluate(rows: list[dict], train_share: float = 0.7,
             config: ImpactConfig = ImpactConfig(), prior: dict | None = None) -> dict:
    games = list(dict.fromkeys(r["game"] for r in rows))
    cut = int(len(games) * train_share)
    train_games = set(games[:cut])
    train = [r for r in rows if r["game"] in train_games]
    test = [r for r in rows if r["game"] not in train_games and r.get("win") is not None]
    wr = _shrunk_wr(train)
    imp = {k: v["impact"] for k, v in augment_impact(train, config, prior).items()}
    feats = []
    for r in test:
        keys = [(r["champion_id"], a) for a in dict.fromkeys(r.get("augments") or [])]
        feats.append((_mean(wr.get(k) for k in keys), _mean(imp.get(k) for k in keys),
                      bool(r["win"])))
    result = {"games": len(games), "train_games": cut, "test_rows": len(test),
              "impact_pairs": len(imp), "prior_champions": len(prior or {}),
              "auc_wr": _auc([(a, w) for a, _, w in feats]),
              "auc_impact": _auc([(b, w) for _, b, w in feats])}
    # ΔWR is ~0.01-scale, impact is [-1, 1]: put impact on ΔWR's scale first.
    scale = 0.05
    result["auc_combined"] = {str(wt): _auc([(a + wt * scale * b, w) for a, b, w in feats])
                              for wt in WEIGHTS}
    best = max((v for v in result["auc_combined"].values() if v is not None), default=None)
    enough = len(test) >= MIN_TEST_ROWS and result["auc_wr"] is not None and best is not None
    result["verdict"] = ("insufficient_data" if not enough
                         else "enable" if best - result["auc_wr"] >= MIN_GAIN else "keep_off")
    return result
