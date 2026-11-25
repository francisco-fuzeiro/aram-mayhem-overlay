"""The impact holdout reports counts and a verdict, never identities."""
import random

from scripts.validate_impact_holdout import evaluate


def _rows(n_games, seed=1):
    rnd = random.Random(seed)
    rows = []
    for g in range(n_games):
        for slot in range(10):
            strong = rnd.random() < 0.5
            win = rnd.random() < (0.65 if strong else 0.35)
            rows.append({"game": f"k{g}", "duration": 1200, "champion_id": f"c{slot}",
                         "augments": ["s" if strong else "w"], "win": win,
                         "damage_to_champions": (30000 if strong else 20000) + rnd.randint(0, 4000),
                         "heal_shield": 0, "heal_total": 0})
    return rows


def test_small_history_is_insufficient():
    assert evaluate(_rows(5))["verdict"] == "insufficient_data"


def test_holdout_scores_and_no_identities():
    out = evaluate(_rows(300))
    assert out["test_rows"] >= 500 and out["auc_impact"] > 0.55
    assert out["verdict"] in {"enable", "keep_off"}
    assert "c0" not in str(out) and "k0" not in str(out)
