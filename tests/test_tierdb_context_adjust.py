"""In-match "context adjustment" of augment tiers (owner decision 23/11).

Final tier = measured base tier shifted by at most one step from: fit with the
current/adapted build stats, synergy with augments already chosen, answer to
the enemy comp, and the player's own games (strong shrinkage). Each shift has
a short reason. Ranks of the full list never change.
"""
from backend.tierdb.context_adjust import AdjustConfig, context_adjust, shift_tier

AD = {"ad": 1.0, "attack_speed": 0.6, "crit": 0.5}
AP = {"ap": 1.0, "cdr": 0.4}


def test_fit_with_build_raises_one_tier_with_reason():
    step, reason = context_adjust(AD, demand={"ad": 1.0, "crit": 0.6, "attack_speed": 0.5})
    assert (step, reason) == (1, "fits your build")


def test_stats_your_build_does_not_use_lower_one_tier():
    step, reason = context_adjust(AP, demand={"ad": 1.0, "crit": 0.6, "hp": 0.3})
    assert (step, reason) == (-1, "your build does not use these stats")


def test_synergy_with_chosen_augments():
    step, reason = context_adjust({"attack_speed": 1.0}, demand={},
                                  chosen=[{"attack_speed": 0.8, "ad": 0.2}])
    assert (step, reason) == (1, "stacks with your augments")


def test_enemy_comp_answer():
    step, reason = context_adjust({"pen": 1.0, "lethality": 0.5}, demand={},
                                  enemy={"enemies_analyzed": 5, "tanks": 3})
    assert (step, reason) == (1, "cuts through enemy tanks")
    step, reason = context_adjust({"hp": 1.0, "shield": 0.6}, demand={},
                                  enemy={"enemies_analyzed": 5, "burst_pressure": 0.7})
    assert (step, reason) == (1, "survives enemy burst")


def test_personal_history_needs_many_games_to_move():
    # 3 wins of 3 is noise under strong shrinkage; 18 of 20 is not.
    assert context_adjust({}, demand={}, personal=(3, 3), personal_base=0.5)[0] == 0
    step, reason = context_adjust({}, demand={}, personal=(18, 20), personal_base=0.5)
    assert (step, reason) == (1, "wins in your own games")
    step, _ = context_adjust({}, demand={}, personal=(2, 20), personal_base=0.5)
    assert step == -1


def test_no_context_no_change():
    assert context_adjust({}, demand={}) == (0, None)
    assert context_adjust(None, demand={"ad": 1.0}) == (0, None)


def test_shift_is_bounded_and_respects_level_caps():
    assert shift_tier("B", 1, "champion") == "A"
    assert shift_tier("B", -1, "champion") == "C"
    assert shift_tier("S", 1, "champion") == "OP"
    assert shift_tier("S", 1, "role") == "S"        # role level is capped at S
    assert shift_tier("A", 1, "curated") == "A"     # curated capped at A
    assert shift_tier("E", -1, "champion") == "E"
    assert shift_tier("B", 3, "champion") == "A"    # never more than one step


def test_config_defaults_are_the_decided_bounds():
    cfg = AdjustConfig()
    assert cfg.max_steps == 1
    assert cfg.personal_k >= 20


# -- wired into the in-match offer payload ------------------------------------
import json  # noqa: E402

from backend import feature_diagnostics as diag  # noqa: E402
from backend.api import server  # noqa: E402
from backend.tierdb import service as tier_service  # noqa: E402
from tests.test_tierdb_overlay_integration import EXPORT  # noqa: E402


def _svc(tmp_path, monkeypatch):
    export = tmp_path / "tierlist.json"
    # Owner decision 24/11: tier = list position (OP 1-5, S 6-15, A 16-30,
    # B 31-50). Ranks chosen so the expected tiers stay S / A / B.
    doc = json.loads(json.dumps(EXPORT))
    ranks = {"1001": 12, "1002": 20, "1003": 40}
    for row in doc["augments"]["ahri"]["gold"]:
        if row[0] in ranks:
            row[1] = row[2] = ranks[row[0]]
    export.write_text(json.dumps(doc), encoding="utf-8")
    svc = tier_service.TierListService(export_path=export,
                                       preferences_path=tmp_path / "p.json",
                                       db_path=tmp_path / "t.sqlite")
    monkeypatch.setattr(server, "tier_service", svc)


def test_offer_payload_adds_adjusted_tier_without_touching_rank(tmp_path, monkeypatch):
    _svc(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(diag, "record", lambda *a, **k: calls.append(a) or True)
    contexts = {"1002": (1, "fits your build"), "1003": (-1, "your build does not use these stats")}
    payload = server._augment_tier_payload("ahri", ["1001", "1002", "1003"],
                                           adjust=lambda aid: contexts.get(aid, (0, None)))
    t = payload["augment_tiers"]
    assert (t["1002"]["tier"], t["1002"]["adjusted_tier"], t["1002"]["adjust"]) == ("A", "S", 1)
    assert t["1002"]["adjust_reason"] == "fits your build"
    assert t["1002"]["rank"] == 20                        # list rank unchanged
    assert (t["1003"]["adjusted_tier"], t["1003"]["adjust"]) == ("C", -1)
    assert (t["1001"]["adjusted_tier"], t["1001"]["adjust"]) == ("S", 0)
    assert ("tierdb.context_adjust", "ok", "adjusted", 2) in calls


def test_offer_payload_without_context_reports_skip(tmp_path, monkeypatch):
    _svc(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(diag, "record", lambda *a, **k: calls.append(a) or True)
    payload = server._augment_tier_payload("ahri", ["1001"])
    assert payload["augment_tiers"]["1001"]["adjusted_tier"] == "S"
    assert ("tierdb.context_adjust", "skipped", "no_context") in calls


def test_match_adjuster_uses_build_augments_enemy_and_personal(monkeypatch):
    from types import SimpleNamespace
    from backend.models import StatVector

    sv = lambda **k: StatVector(**k)  # noqa: E731
    augments = {"crit_aug": sv(crit=1.0, ad=0.5), "ap_aug": sv(ap=1.0),
                "as_chosen": sv(attack_speed=1.0)}
    sd = SimpleNamespace(
        get_augment=lambda a: SimpleNamespace(stats=augments[a]) if a in augments else None,
        get_champion=lambda c: SimpleNamespace(stats=sv(ad=0.8, attack_speed=0.4, crit=0.6)),
        get_item=lambda i: SimpleNamespace(stats=sv(ad=1.0, crit=0.8)),
    )
    monkeypatch.setattr(server, "get_all_personal_winrates",
                        lambda champ: {"ap_aug": (1, 12)})
    monkeypatch.setattr(server, "get_champion_record", lambda champ: (30, 60))
    adjust = server._offer_context_adjuster(
        "fiora", ["as_chosen"], {"adapted": [{"id": "x"}]}, {"enemies_analyzed": 0}, sd)
    assert adjust("crit_aug") == (1, "fits your build")
    assert adjust("ap_aug")[0] == -1
    assert adjust("unknown") == (0, None)


def test_impact_vote_is_off_by_default_and_works_when_weighted():
    from backend.tierdb.context_adjust import AdjustConfig, context_adjust
    assert context_adjust({"ad": 1.0}, demand=None, impact=1.0) == (0, None)
    cfg = AdjustConfig(weights=(("build", 0.4), ("impact", 0.3)))
    step, reason = context_adjust({"ad": 1.0}, demand=None, impact=0.9, config=cfg)
    assert step == 1 and reason == "does more in your local games"


def test_audit_2411_adjuster_reads_real_augment_contribution(monkeypatch):
    # Audit 24/11: real AugmentData has ``contribution``, not ``stats``; the
    # adjustment never ran with real augments.
    from types import SimpleNamespace
    from backend.models import AugmentData, AugmentTier, StatVector

    real = {
        "crit_aug": AugmentData("crit_aug", "Crit", list(AugmentTier)[0], "",
                                StatVector(crit=1.0, ad=0.5)),
        "ap_aug": AugmentData("ap_aug", "AP", list(AugmentTier)[0], "", StatVector(ap=1.0)),
    }
    assert not hasattr(real["crit_aug"], "stats")
    sd = SimpleNamespace(
        get_augment=lambda a: real.get(a),
        get_champion=lambda c: SimpleNamespace(stats=StatVector(ad=0.8, crit=0.6)),
        get_item=lambda i: SimpleNamespace(stats=StatVector(ad=1.0, crit=0.8)),
    )
    monkeypatch.setattr(server, "get_all_personal_winrates", lambda champ: {})
    monkeypatch.setattr(server, "get_champion_record", lambda champ: None)
    adjust = server._offer_context_adjuster("fiora", [], {"adapted": [{"id": "x"}]},
                                            {"enemies_analyzed": 0}, sd)
    assert adjust("crit_aug") == (1, "fits your build")
    assert adjust("ap_aug")[0] == -1
    assert server._stat_vector_of(real["ap_aug"]).ap == 1.0


def test_owner_2411_tier_is_the_list_position():
    from backend.tierdb.runtime import rank_tier
    assert [rank_tier(r) for r in (1, 5, 6, 15, 16, 30, 31, 50, 51, 75, 76, 100, 101)] == [
        "OP", "OP", "S", "S", "A", "A", "B", "B", "C", "C", "D", "D", "E"]
    assert rank_tier(1, "curated") == "A"   # a guess is never shown as OP
    assert rank_tier(None, "champion", "B") == "B"
    # Shares of a 237-augment list (proposal 25/11): E only past the list.
    assert [rank_tier(r, total=237) for r in (12, 13, 36, 37, 84, 112, 137, 237, 238)] == [
        "OP", "S", "S", "A", "B", "B", "C", "D", "E"]
