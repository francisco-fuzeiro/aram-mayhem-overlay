"""End-to-end pipeline contract: same visible threat changes cards and builds."""
from backend.models import (
    AugmentData, AugmentTier, ChampionMeta, EnemyState,
    GamePhase, GameSnapshot, ItemData, StatVector,
)
from backend.static_data.loader import StaticData
from backend.workflow.pipeline import Pipeline


def test_enemy_item_change_updates_build_and_augment_context(monkeypatch):
    from backend.workflow import pipeline as module
    monkeypatch.setattr(module, "get_all_personal_winrates", lambda _: {})

    sd = StaticData()
    sd._champions = {
        "lux": ChampionMeta(
            "lux", "Lux", StatVector(ap=0.9, hp=0.2), role="mage",
        ),
        "enemy": ChampionMeta(
            "enemy", "Enemy", StatVector(ap=0.95, hard_cc=0.9),
            role="mage",
        ),
        "ally": ChampionMeta(
            "ally", "Ally", StatVector(ad=0.9), role="marksman",
        ),
    }
    sd._augments = {
        "a1": AugmentData(
            "a1", "Protection", AugmentTier.GOLD, "",
            StatVector(hp=0.6, shield=0.8),
        ),
    }
    sd._items = {
        "a_plain": ItemData(
            "a_plain", "Plain", 1400, StatVector(ap=0.6)
        ),
        "z_resist": ItemData(
            "z_resist", "Resist", 1400, StatVector(ap=0.6),
            tags=["SpellBlock"],
        ),
    }

    def snap(enemy_states):
        return GameSnapshot(
            game_id="one", phase=GamePhase.AUG_PICK_1,
            champion_id="lux", augment_choices=["a1"],
            chosen_augments=[], purchased_items=[], current_gold=2000,
            game_time=500, enemy_champion_ids=[
                entry.champion_id for entry in enemy_states
            ], ally_champion_ids=["ally"], enemy_states=enemy_states,
        )

    baseline = Pipeline(sd).run(snap([]))
    against_magic = Pipeline(sd).run(snap([
        EnemyState("enemy", ["z_resist"], kills=7, deaths=0),
    ]))
    assert baseline is not None
    assert against_magic is not None
    assert baseline.build_state.next_item_id == "a_plain"
    assert against_magic.build_state.next_item_id == "z_resist"
    assert against_magic.recommendations[0].score >= baseline.recommendations[0].score
    assert against_magic.enemy_analysis["enemies_analyzed"] == 1
    assert against_magic.enemy_analysis["high_kill_enemies"] == 1
    assert against_magic.ally_analysis["physical"] == 1
    assert against_magic.ally_analysis["magic"] == 1
    assert against_magic.ally_analysis["known"] == 2
    assert against_magic.build_state.full_build[0] == "z_resist"
    assert against_magic.build_state.alternatives == {}
