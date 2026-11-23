"""Field 23/11: boots follow the enemy team; enemy detection is diagnosed."""
from backend import feature_diagnostics as fd
from backend.api import server

ELIG = {"3006", "3111", "3047", "3008"}


def test_boots_follow_enemy_cc_or_physical_damage_else_usual_boots():
    assert server._context_boots("3006", ELIG, None) == ("3006", None)
    few = {"enemies_analyzed": 2, "cc_pressure": 0.9}
    assert server._context_boots("3006", ELIG, few) == ("3006", None)
    cc = {"enemies_analyzed": 5, "cc_pressure": 0.7, "physical_pressure": 0.5}
    assert server._context_boots("3006", ELIG, cc) == ("3111", "enemy crowd control")
    ad = {"enemies_analyzed": 5, "cc_pressure": 0.3, "physical_pressure": 0.8}
    assert server._context_boots("3006", ELIG, ad) == ("3047", "enemy physical damage")
    both = {"enemies_analyzed": 5, "cc_pressure": 0.6, "physical_pressure": 0.9}
    assert server._context_boots("3006", ELIG, both)[0] == "3047"
    assert server._context_boots("3006", {"3006"}, cc) == ("3006", None)  # not in pool


def test_enemy_detection_is_recorded_with_counts(monkeypatch):
    got = []
    monkeypatch.setattr(fd, "record", lambda *a: got.append(a))
    server._record_enemy_detection({})
    server._record_enemy_detection({"enemies_visible": 5, "enemies_analyzed": 0})
    server._record_enemy_detection({"enemies_visible": 5, "enemies_analyzed": 5})
    assert got == [("enemy.detection", "skipped", "no_enemies_listed"),
                   ("enemy.detection", "failed", "none_resolved", 5),
                   ("enemy.detection", "ok", "all_resolved", 5)]

