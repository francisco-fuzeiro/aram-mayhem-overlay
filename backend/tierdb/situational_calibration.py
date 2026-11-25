"""Recalibrate the situational pp-per-vote weights from the player's own games.

Owner decision 24/11: hand weights first; a calibration replaces them only
with >= MIN_GAMES local games AND a better temporal holdout (newest 30% of
games) than the hand weights. Everything stays local
(``~/.aram-oracle/situational_calibration.json``) and holds counts and
weights only: no champions, games or players.

Model, per player of a finished game (all 10 players, ``participants``):

    logit P(win) = b + sum over the player's augments of
                   (effect_pp + clamp(sum_s w_s * vote_s, ±cap)) / 25

``effect_pp`` is the export's blended ΔWR (logit x 25), so the situational
weights live on the same scale as the base. Votes are rebuilt from the
end-of-game data: champion + final items (build), the player's other augments
(synergy), the enemy team's champions and final items (enemy), own healing
(sustain) and the synergy rules with the allied champions (allies). The
player's own record (personal) is left out because it is computed from these
same games; impact keeps its own gate (23/11).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from backend.tierdb.situational_score import (
    CALIBRATION_FILE,
    SIGNALS,
    SituationalWeights,
    load_weights,
)

logger = logging.getLogger(__name__)

MIN_GAMES = 200
TRAIN_SHARE = 0.7
FITTED = tuple(s for s in SIGNALS if s not in ("personal", "impact"))
MAX_PP = 5.0
L2 = 2.0            # pull towards the hand weights (per pp², per sample count)
STEPS = 400
LR = 0.5


@dataclass
class AugmentVotes:
    effect_pp: float
    votes: dict = field(default_factory=dict)    # signal -> vote (-1..1)


@dataclass
class Sample:
    game: str
    win: bool
    augments: list = field(default_factory=list)  # list[AugmentVotes]


def _vec(obj) -> dict | None:
    from backend.models import StatVector
    stats = getattr(obj, "stats", None)
    if stats is None:
        stats = getattr(obj, "contribution", None)
    if stats is None:
        return None
    return {f: float(getattr(stats, f, 0.0) or 0.0) for f in StatVector.fields()}


def samples_from_participants(rows: list[dict], provider, sd, synergies=None) -> list[Sample]:
    """Rebuild per-player votes from stored games (rows oldest first)."""
    from backend.engine.augment_synergies import BLOCK, build_context, load_table
    from backend.engine.situational_items import sustain_level
    from backend.engine.team_context import analyze_enemies
    from backend.models import EnemyState
    from backend.tierdb.context_adjust import context_votes

    synergies = synergies if synergies is not None else load_table()
    get_aug = getattr(sd, "get_augment", lambda _a: None)
    canon = getattr(sd, "canonical_item_id", lambda i: i)
    games: dict[str, list[dict]] = {}
    for row in rows:
        games.setdefault(row["game"], []).append(row)
    out: list[Sample] = []
    for game, players in games.items():
        for row in players:
            if row.get("win") is None or not row.get("augments"):
                continue
            champ_id = str(row["champion_id"])
            champion = sd.get_champion(champ_id)
            items = [str(i) for i in row.get("items") or [] if i]
            demand: dict = {}
            for source in [champion] + [sd.get_item(canon(i)) for i in items]:
                for k, v in (_vec(source) or {}).items():
                    demand[k] = demand.get(k, 0.0) + v
            healer = sustain_level(champion, items, sd.get_item)
            if healer:
                peak = max(demand.values(), default=1.0) or 1.0
                demand["heal_power"] = demand.get("heal_power", 0.0) + healer * peak
            team = row.get("team")
            enemies = [EnemyState(champion_id=str(p["champion_id"]),
                                  item_ids=[str(i) for i in p.get("items") or [] if i])
                       for p in players if team is not None and p.get("team") not in (None, team)]
            enemy = analyze_enemies(enemies, sd.get_champion,
                                    lambda i: sd.get_item(canon(i))).as_dict() if enemies else {}
            allies = [str(p["champion_id"]) for p in players
                      if p is not row and team is not None and p.get("team") == team]
            names = {str(a): getattr(get_aug(str(a)), "name", None) for a in row["augments"]}
            augs: list[AugmentVotes] = []
            for aid in (str(a) for a in row["augments"]):
                entry = provider.augment_tier(champ_id, aid) if provider is not None else None
                effect = (entry or {}).get("effect_pp")
                if not isinstance(effect, (int, float)) or (entry or {}).get("level") == "borrowed":
                    continue
                chosen = [v for v in (_vec(get_aug(o)) for o in names if o != aid) if v]
                raw = context_votes(_vec(get_aug(aid)), demand=demand, chosen=chosen,
                                    enemy=enemy, own_healing=healer)
                votes = {k: float(v) for k, (v, _r) in raw.items() if k in FITTED}
                name = names.get(aid)
                if name:
                    others = [n for a, n in names.items() if a != aid and n]
                    ctx = build_context(champ_id, champion, items, others, sd=sd, allies=allies)
                    step, _reason, rule_id = synergies.evaluate(name, ctx)
                    if step == BLOCK:
                        continue
                    if step:
                        ch = "allies" if synergies.uses_allies(rule_id) else "synergy"
                        if abs(float(step)) >= abs(votes.get(ch, 0.0)):
                            votes[ch] = float(step)
                augs.append(AugmentVotes(float(effect), votes))
            if augs:
                out.append(Sample(game, bool(row["win"]), augs))
    return out


class _Arrays:
    """Flattened augments of a sample list, for vectorised fits."""

    def __init__(self, samples: list[Sample]):
        import numpy as np
        self.n = len(samples)
        self.y = np.array([1.0 if s.win else 0.0 for s in samples])
        self.idx = np.array([i for i, s in enumerate(samples) for _ in s.augments], dtype=int)
        self.effect = np.array([a.effect_pp for s in samples for a in s.augments], dtype=float)
        self.votes = np.array([[a.votes.get(k, 0.0) for k in FITTED]
                               for s in samples for a in s.augments], dtype=float
                              ).reshape(-1, len(FITTED))

    def logit(self, b: float, w, cap: float):
        """Logit per sample and d logit / d w (zero where the per-augment cap binds)."""
        import numpy as np
        raw = self.votes @ w
        per = (self.effect + np.clip(raw, -cap, cap)) / 25.0
        z = b + np.bincount(self.idx, weights=per, minlength=self.n)
        free = (np.abs(raw) < cap)[:, None] * self.votes / 25.0
        dz = np.stack([np.bincount(self.idx, weights=free[:, j], minlength=self.n)
                       for j in range(len(FITTED))], axis=1)
        return z, dz


def _log_loss(data: _Arrays, b: float, w, cap: float) -> float:
    import numpy as np
    p = np.clip(1.0 / (1.0 + np.exp(-data.logit(b, w, cap)[0])), 1e-9, 1 - 1e-9)
    return float(-np.mean(data.y * np.log(p) + (1 - data.y) * np.log(1 - p)))


def _fit(data: _Arrays, start, cap: float, *, fit_w: bool):
    import numpy as np
    b, w = 0.0, np.array(start, dtype=float)
    n = max(1, data.n)
    for _ in range(STEPS):
        z, dz = data.logit(b, w, cap)
        err = 1.0 / (1.0 + np.exp(-z)) - data.y
        b -= LR * err.sum() / n
        if fit_w:
            g = (err @ dz) / n + L2 * (w - start) / n
            w = np.clip(w - LR * 25.0 * g, 0.0, MAX_PP)
    return b, w


def calibrate(samples: list[Sample], hand: SituationalWeights | None = None,
              *, min_games: int = MIN_GAMES, train_share: float = TRAIN_SHARE) -> dict:
    """Verdict dict (counts, log-losses, weights, accepted); no identities."""
    hand = hand or load_weights(calibration=Path("/nonexistent"))
    start = {s: hand.pp(s) for s in FITTED}
    order = list(dict.fromkeys(s.game for s in samples))
    report = {"games": len(order), "players": len(samples), "min_games": min_games,
              "accepted": False, "pp_per_vote": None}
    if len(order) < min_games:
        report["reason"] = "insufficient_data"
        return report
    cut = set(order[int(len(order) * train_share):])
    train = [s for s in samples if s.game not in cut]
    test = [s for s in samples if s.game in cut]
    cap = hand.total_cap_pp
    import numpy as np
    start_v = np.array([start[k] for k in FITTED])
    tr, te = _Arrays(train), _Arrays(test)
    b_hand, _ = _fit(tr, start_v, cap, fit_w=False)
    b_fit, w_fit = _fit(tr, start_v, cap, fit_w=True)
    ll_hand = _log_loss(te, b_hand, start_v, cap)
    ll_fit = _log_loss(te, b_fit, w_fit, cap)
    report.update(train_games=len(order) - len(cut), test_games=len(cut),
                  log_loss_hand=round(ll_hand, 5), log_loss_calibrated=round(ll_fit, 5),
                  pp_per_vote={k: round(float(w_fit[j]), 3) for j, k in enumerate(FITTED)})
    report["accepted"] = bool(ll_fit < ll_hand)
    report["reason"] = "better_holdout" if report["accepted"] else "no_holdout_gain"
    return report


def refresh(provider, sd, *, db_path: Path | None = None,
            out_path: Path | None = None) -> str:
    """Rebuild samples, calibrate and write the local file; returns the reason."""
    from backend.storage.db import get_participants
    rows = get_participants(db_path=db_path) if db_path else get_participants()
    samples = samples_from_participants(rows, provider, sd)
    if not samples:
        # Tier list not loaded yet (or no history): keep any earlier verdict
        # instead of overwriting an accepted calibration with an empty one.
        return "insufficient_data"
    report = calibrate(samples)
    target = out_path or CALIBRATION_FILE
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not write situational calibration: %s", exc)
        return "error"
    return report["reason"]
