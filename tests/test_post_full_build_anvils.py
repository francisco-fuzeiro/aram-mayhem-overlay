"""F3: post-build Stat Anvil priorities are model advice, not offered-card identity."""
from backend.engine.build_suggester import suggest_build
from backend.engine.inventory import build_inventory
from backend.engine.team_context import EnemyThreatProfile
from backend.models import (
    AugmentData, AugmentTier, ChampionMeta, GamePhase, GameSnapshot,
    PipelineResult, StatVector,
)
from backend.static_data.loader import StaticData
from backend.workflow.pipeline import Pipeline
from backend.api.server import _serialize_result
from tests.test_build_rules_b3 import _verified_data, _champion

OWNED = ["3047", "3074", "3053", "3089", "3031", "3165"]


def _build(sd, *, owned=OWNED, champ=None, augments=None, verified=True, enemy=None):
    champion = champ or _champion()
    return suggest_build(
        champion, augments or [], owned, 5000, sd.recommendable_items(),
        inventory=build_inventory(owned, sd), item_data=sd,
        catalog_verified=verified,
        exclusive_item_groups=sd.exclusive_item_groups,
        enemy_profile=enemy,
    )


def test_six_observed_owned_finals_trigger_stat_priorities_after_final_purchase(
    monkeypatch, tmp_path,
):
    sd = _verified_data(monkeypatch, tmp_path)
    state = _build(sd)
    assert state.full_build == OWNED
    assert state.next_item_id is None
    assert 1 <= len(state.anvil_stat_priorities) <= 3
    assert state.anvil_stat_priorities[0]["stat"] == "ap"
    assert all(row["stat"] in {
        "ap", "ad", "attack_speed", "hp", "crit", "cdr", "lethality"
    } for row in state.anvil_stat_priorities)
    assert len({row["stat"] for row in state.anvil_stat_priorities}) == len(state.anvil_stat_priorities)
    assert all("label" in row and "reason" in row for row in state.anvil_stat_priorities)
    assert all("score" not in row and "available" not in row for row in state.anvil_stat_priorities)

    wire = _serialize_result(PipelineResult(GamePhase.IN_GAME, [], state, False), sd)
    assert wire["build_state"]["anvil_stat_priorities"] == state.anvil_stat_priorities


def test_partial_and_component_only_inventory_must_not_offer_postbuild_advice(
    monkeypatch, tmp_path,
):
    sd = _verified_data(monkeypatch, tmp_path)
    assert _build(sd, owned=OWNED[:-1]).anvil_stat_priorities == []
    assert _build(sd, owned=["1036"] * 6).anvil_stat_priorities == []
    assert _build(sd, owned=OWNED[:-1] + ["999999"]).anvil_stat_priorities == []


def test_catalog_unverified_and_unknown_champion_abstain(monkeypatch, tmp_path):
    sd = _verified_data(monkeypatch, tmp_path)
    assert _build(sd, verified=False).anvil_stat_priorities == []
    sd._champions = {}
    assert _build(sd).anvil_stat_priorities == []


def test_only_confirmed_augments_shift_full_build_stat_priorities(monkeypatch, tmp_path):
    sd = _verified_data(monkeypatch, tmp_path)
    champion = ChampionMeta("lux", "Lux", StatVector(ad=0.9, ap=0.1), role="fighter")
    sd._champions = {"lux": champion}
    aug = AugmentData(
        id="synthetic-confirmed-ap", name="Confirmed AP", tier=AugmentTier.GOLD,
        description="", contribution=StatVector(ap=6.0),
    )
    sd._augments = {aug.id: aug}
    monkeypatch.setattr("backend.workflow.pipeline.get_all_personal_winrates", lambda _: {})

    def run(offers, chosen):
        return Pipeline(sd).run(GameSnapshot(
            game_id="anvil-fixture", phase=GamePhase.IN_GAME,
            champion_id="lux", augment_choices=offers,
            chosen_augments=chosen, purchased_items=OWNED,
            current_gold=100, game_time=700, enemy_champion_ids=[],
        )).build_state.anvil_stat_priorities

    before = run([], [])
    only_offered = run([aug.id], [])
    confirmed = run([aug.id], [aug.id])
    assert before == only_offered
    assert before[0]["stat"] == "ad"
    assert confirmed[0]["stat"] == "ap"
    assert all(row["stat"] in StatVector.fields() for row in confirmed)


def test_visible_enemy_pressure_can_promote_health_without_hidden_items():
    from backend.engine.anvil_priorities import rank_anvil_stats

    champ = ChampionMeta("test", "Test", StatVector(ap=0.8, hp=0.4), role="mage")
    base = rank_anvil_stats(champ, [], [], None)
    enemy = EnemyThreatProfile(
        enemies_analyzed=5, enemies_visible=5,
        burst_pressure=1.0, cc_pressure=1.0,
    )
    threatened = rank_anvil_stats(champ, [], [], enemy)
    ids_base = [row["stat"] for row in base]
    ids_threat = [row["stat"] for row in threatened]
    assert "hp" in ids_threat
    assert ids_threat.index("hp") <= ids_base.index("hp")
    assert rank_anvil_stats(champ, [], [], EnemyThreatProfile()) == base


def test_unmodelled_stat_vector_gives_no_fabricated_stat_priority():
    from backend.engine.anvil_priorities import rank_anvil_stats

    blank = ChampionMeta("none", "None", StatVector(), role="mage")
    assert rank_anvil_stats(blank, [], [], None) == []


def test_exact_three_known_stat_anvil_choices_receive_bounded_scores_only(
    monkeypatch, tmp_path,
):
    sd = _verified_data(monkeypatch, tmp_path)
    sd._stat_anvils = {
        "anvil-ap": AugmentData("anvil-ap", "Power", AugmentTier.STAT_ANVIL, "",
                               StatVector(ap=0.6), provenance="override"),
        "anvil-ad": AugmentData("anvil-ad", "Damage", AugmentTier.STAT_ANVIL, "",
                               StatVector(ad=0.6), provenance="override"),
        "anvil-blank": AugmentData("anvil-blank", "Unknown", AugmentTier.STAT_ANVIL, "",
                                  StatVector(), provenance="none"),
    }
    monkeypatch.setattr("backend.workflow.pipeline.get_all_personal_winrates", lambda _: {})
    def run(ids):
        return Pipeline(sd).run(GameSnapshot(
            game_id="synthetic-anvil-popup", phase=GamePhase.IN_GAME,
            champion_id="lux", augment_choices=ids, chosen_augments=[],
            purchased_items=OWNED, current_gold=500, game_time=500,
            enemy_champion_ids=[],
        ))
    ids = list(sd._stat_anvils)
    state = run(ids)
    assert state.recommendations == []
    assert state.suggest_reroll is False
    assert len(state.anvil_recommendations) == 3
    ratings = {row["anvil_id"]: row for row in state.anvil_recommendations}
    assert 0 < ratings["anvil-ad"]["score"] < ratings["anvil-ap"]["score"] <= 10
    assert ratings["anvil-blank"]["score"] is None
    assert ratings["anvil-blank"]["modelled"] is False
    wire = _serialize_result(state, sd)
    assert wire["anvil_recommendations"] == state.anvil_recommendations
    assert wire["recommendations"] == []
    assert run(ids[:2]).anvil_recommendations == []
    # Unverified cross-type OCR can never produce an authoritative Anvil card score.
    sd._augments["real"] = AugmentData(
        "real", "Real", AugmentTier.GOLD, "", StatVector(ap=1.0),
    )
    assert run(["anvil-ap", "real", "anvil-ad"]).anvil_recommendations == []
    assert run(["anvil-ap", "real", "anvil-ad"]).recommendations == []
