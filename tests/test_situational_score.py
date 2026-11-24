"""Continuous situational augment score (owner decisions 24/11)."""
import json

import pytest

from backend.api import server
from backend.tierdb import service as tier_service
from backend.tierdb.situational_score import (
    SituationalWeights, load_weights, position_of, situational_delta)

HAND = SituationalWeights()


def test_hand_weights_file_is_the_decided_proposal():
    w = load_weights(calibration=None)
    assert w.source == "hand" and w.total_cap_pp == 3.0
    assert w.pp("build") == 1.5 and w.pp("synergy") == 1.5 and w.pp("impact") == 0.0


def test_total_is_capped_at_three_points():
    votes = {"build": (1.0, "fits your build"), "synergy": (1.0, "stacks"),
             "enemy": (1.0, "tanks"), "sustain": (1.0, "heals")}
    delta, reason, parts = situational_delta(votes, HAND)
    assert sum(parts.values()) == 5.0
    assert delta == 3.0
    assert reason in {"fits your build", "stacks"}  # the biggest contributor leads


def test_no_votes_no_change_and_missing_data_never_moves():
    assert situational_delta({}, HAND) == (0.0, None, {})
    assert situational_delta({"build": (0.0, None)}, HAND)[0] == 0.0


def test_position_excludes_its_own_base_entry():
    effects = [5.0, 3.0, 1.0, 0.0, -1.0]
    assert position_of(1.0, 1.0, effects) == 3        # unchanged
    assert position_of(4.0, 1.0, effects) == 2        # +3 pp passes the 3.0 entry
    assert position_of(-2.0, 1.0, effects) == 5       # below everything else


def test_calibration_needs_acceptance(tmp_path):
    cal = tmp_path / "cal.json"
    cal.write_text(json.dumps({"accepted": False, "pp_per_vote": {"build": 9}}))
    assert load_weights(calibration=cal).pp("build") == 1.5
    cal.write_text(json.dumps({"accepted": True, "pp_per_vote": {"build": 2.0, "impact": 5}}))
    w = load_weights(calibration=cal)
    assert w.source == "calibrated" and w.pp("build") == 2.0
    assert w.pp("impact") == 0.0          # impact keeps its own holdout gate


EXPORT = {
    "schema_version": 1, "patch": "16.23", "run_id": 1,
    "generated_at": "2026-11-24T00:00:00+00:00", "sources": [],
    "augment_columns": ["augment_id", "rank", "tie_group", "tier", "level", "confidence",
                        "rank_all", "effect_pp"],
    "augments": {"ahri": {"gold": [
        ["1", 1, 1, "S", "champion", "high", i + 1, round(6.0 - i * 0.5, 2)]
        for i in range(0)] + [
        [str(100 + i), i + 1, i + 1, "S", "champion", "high", i + 1, round(10.0 - i * 0.2, 2)]
        for i in range(40)] + [["900", 41, 41, "E", "borrowed", "low", 41, 12.0]]}},
    "champion_columns": ["champion_id", "rank", "tie_group", "tier", "confidence", "potential"],
    "champions": [["ahri", 1, 1, "S", "high", "low"]],
}


@pytest.fixture()
def tiers(tmp_path, monkeypatch):
    export = tmp_path / "tierlist.json"
    export.write_text(json.dumps(EXPORT), encoding="utf-8")
    svc = tier_service.TierListService(export_path=export,
                                       preferences_path=tmp_path / "p.json",
                                       db_path=tmp_path / "t.sqlite")
    monkeypatch.setattr(server, "tier_service", svc)
    monkeypatch.setattr("backend.tierdb.situational_score.CALIBRATION_FILE", tmp_path / "none.json")
    return svc


def _adjuster(votes, block=None):
    def adjust(_aid):
        return 0, None
    adjust.situational = lambda _aid: {"block": block, "votes": votes}
    return adjust


def test_offer_moves_by_position_and_never_leaks_the_effect(tiers):
    # #31 (effect 4.0, tier B) + 3 pp -> 7.0 -> position 16 -> tier A
    out = server._augment_tier_payload(
        "ahri", ["130"], adjust=_adjuster({"build": (1.0, "fits your build"),
                                           "synergy": (1.0, "stacks with your augments")}))
    t = out["augment_tiers"]["130"]
    assert t["tier"] == "B" and t["adjusted_rank"] == 16 and t["adjusted_tier"] == "A"
    assert t["adjust"] == 1 and t["adjust_reason"] in {"fits your build",
                                                       "stacks with your augments"}
    assert "effect_pp" not in t


def test_borrowed_stays_e_and_block_is_e(tiers):
    out = server._augment_tier_payload("ahri", ["900"], adjust=_adjuster({"build": (1.0, "x")}))
    assert out["augment_tiers"]["900"]["adjusted_tier"] == "E"
    out = server._augment_tier_payload("ahri", ["101"], adjust=_adjuster({}, block="needs mana"))
    t = out["augment_tiers"]["101"]
    assert t["adjusted_tier"] == "E" and t["adjust_reason"] == "needs mana"
