"""Own-games recalibration of the situational weights (owner decisions 24/11)."""
import json
import math
import random

from backend.tierdb.situational_calibration import (
    AugmentVotes,
    Sample,
    calibrate,
    refresh,
    samples_from_participants,
)
from backend.tierdb.situational_score import SituationalWeights, load_weights

HAND = SituationalWeights()


def _games(n_games, true_build_pp, seed=7):
    rng = random.Random(seed)
    out = []
    for g in range(n_games):
        for _p in range(10):
            augs = [AugmentVotes(rng.uniform(-2, 2), {"build": rng.choice((-1.0, 0.0, 1.0))})
                    for _ in range(4)]
            z = sum(a.effect_pp + true_build_pp * a.votes["build"] for a in augs) / 25.0
            out.append(Sample(f"g{g}", rng.random() < 1 / (1 + math.exp(-z)), augs))
    return out


def test_needs_two_hundred_games():
    report = calibrate(_games(150, 3.0), HAND)
    assert report["reason"] == "insufficient_data" and report["accepted"] is False
    assert report["pp_per_vote"] is None and report["games"] == 150


def test_recovers_a_stronger_build_weight_and_beats_hand_on_holdout():
    report = calibrate(_games(400, 5.0), HAND)
    assert report["test_games"] == 120 and report["train_games"] == 280
    assert report["pp_per_vote"]["build"] > 2.5
    assert report["accepted"] is True and report["reason"] == "better_holdout"
    assert report["log_loss_calibrated"] < report["log_loss_hand"]


def test_weights_stay_bounded_and_never_include_personal_or_impact():
    report = calibrate(_games(250, 0.0), HAND)
    pp = report["pp_per_vote"]
    assert set(pp) == {"build", "synergy", "enemy", "sustain", "allies"}
    assert all(0.0 <= v <= 5.0 for v in pp.values())


def test_only_an_accepted_file_replaces_the_hand_weights(tmp_path):
    cal = tmp_path / "cal.json"
    cal.write_text(json.dumps({"accepted": False, "pp_per_vote": {"build": 4.0}}))
    assert load_weights(calibration=cal).source == "hand"
    cal.write_text(json.dumps({"accepted": True, "pp_per_vote": {"build": 4.0, "impact": 9}}))
    w = load_weights(calibration=cal)
    assert w.source == "calibrated" and w.pp("build") == 4.0 and w.pp("impact") == 0.0


class _Aug:
    def __init__(self, name):
        self.name, self.contribution = name, None


class _SD:
    def get_champion(self, _c): return None
    def get_item(self, _i): return None
    def get_augment(self, a): return _Aug(None)


class _Provider:
    def augment_tier(self, c, a):
        return {"effect_pp": 1.0, "level": "champion"} if a != "9" else \
            {"effect_pp": 2.0, "level": "borrowed"}


def test_samples_skip_borrowed_rows_and_unknown_results():
    rows = [{"game": "h1", "team": 100 if i < 5 else 200, "champion_id": f"c{i}",
             "win": (i < 5) if i != 3 else None, "augments": ["1", "9"], "items": []}
            for i in range(10)]
    samples = samples_from_participants(rows, _Provider(), _SD())
    assert len(samples) == 9
    assert all(len(s.augments) == 1 and s.augments[0].effect_pp == 1.0 for s in samples)


def test_refresh_without_samples_keeps_the_earlier_verdict(tmp_path):
    out = tmp_path / "cal.json"
    db = tmp_path / "local.db"
    out.write_text(json.dumps({"accepted": True, "pp_per_vote": {"build": 2.0}}))
    assert refresh(_Provider(), _SD(), db_path=db, out_path=out) == "insufficient_data"
    # Nothing to fit (e.g. tier list not loaded yet): the earlier verdict stays.
    assert json.loads(out.read_text())["accepted"] is True
