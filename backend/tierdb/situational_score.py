"""Continuous situational score of an offered augment (owner decisions 24/11).

final = base effect (blended ΔWR in pp, per champion, from the tier export)
      + sum over signals of vote (-1..1) x pp_per_vote, total capped at ±3 pp.

The shown tier comes from where ``final`` would sit in the champion's own list
(OP 1-5, S 6-15, ...). Starting weights are hand-set (Proposta) in
``data/augments/situational_weights.json``; a calibration from the player's
own games replaces them only after >= 200 games and a better temporal holdout
(``backend.tierdb.situational_calibration``). Missing data never moves a score.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

WEIGHTS_FILE = Path(__file__).resolve().parents[2] / "data" / "augments" / "situational_weights.json"
CALIBRATION_FILE = Path.home() / ".aram-oracle" / "situational_calibration.json"
SIGNALS = ("build", "synergy", "enemy", "sustain", "allies", "personal", "impact")
DEFAULT_PP = {"build": 1.5, "synergy": 1.5, "enemy": 1.0, "sustain": 1.0,
              "allies": 0.5, "personal": 0.5, "impact": 0.0}


@dataclass(frozen=True)
class SituationalWeights:
    pp_per_vote: tuple = tuple(DEFAULT_PP.items())
    total_cap_pp: float = 3.0
    source: str = "hand"          # "hand" or "calibrated"

    def pp(self, signal: str) -> float:
        return float(dict(self.pp_per_vote).get(signal, 0.0))


def _read(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        logger.warning("Unreadable situational weights %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def _pp_map(raw) -> dict[str, float]:
    out = dict(DEFAULT_PP)
    for key, value in (raw or {}).items():
        if key in out and isinstance(value, (int, float)) and value >= 0:
            out[key] = float(value)
    return out


def load_weights(path: Path | None = None, calibration: Path | None = None) -> SituationalWeights:
    hand = _read(path or WEIGHTS_FILE)
    cap = hand.get("total_cap_pp")
    cap = float(cap) if isinstance(cap, (int, float)) and cap >= 0 else 3.0
    cal = _read(calibration if calibration is not None else CALIBRATION_FILE)
    if cal.get("accepted") is True and isinstance(cal.get("pp_per_vote"), dict):
        pp = _pp_map(cal["pp_per_vote"])
        # The impact vote keeps its own holdout gate (23/11); never calibrated here.
        pp["impact"] = _pp_map(hand.get("pp_per_vote")).get("impact", 0.0)
        return SituationalWeights(tuple(pp.items()), cap, "calibrated")
    return SituationalWeights(tuple(_pp_map(hand.get("pp_per_vote")).items()), cap, "hand")


def situational_delta(votes: dict, weights: SituationalWeights) -> tuple[float, str | None, dict]:
    """(delta pp within ±cap, leading reason, per-signal contribution)."""
    parts: dict[str, float] = {}
    reasons: dict[str, str | None] = {}
    for signal, (vote, reason) in (votes or {}).items():
        pp = weights.pp(signal)
        if pp <= 0 or not isinstance(vote, (int, float)) or not vote:
            continue
        parts[signal] = max(-1.0, min(1.0, float(vote))) * pp
        reasons[signal] = reason
    raw = sum(parts.values())
    cap = weights.total_cap_pp
    delta = max(-cap, min(cap, raw))
    if not delta:
        return 0.0, None, parts
    sign = 1 if delta > 0 else -1
    lead = max((v * sign, k) for k, v in parts.items() if reasons.get(k) and v * sign > 0)[1] \
        if any(reasons.get(k) and v * sign > 0 for k, v in parts.items()) else None
    return round(delta, 3), reasons.get(lead) if lead else None, parts


def position_of(score_pp: float, own_base_pp: float | None, effects: list[float]) -> int:
    """1-based position ``score_pp`` takes in ``effects`` (best first, includes own base)."""
    better = sum(1 for e in effects if e > score_pp + 1e-9)
    if own_base_pp is not None and own_base_pp > score_pp + 1e-9:
        better -= 1          # its own base entry is not a competitor
    return max(1, better + 1)
