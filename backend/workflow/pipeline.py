from backend.models import GameSnapshot, GamePhase, PipelineResult, EnemyState
from backend.static_data.loader import StaticData
from backend.engine.ranker import rank_augments, should_reroll
from backend.engine.build_suggester import suggest_build
from backend.engine.team_context import analyze_enemies, analyze_allies
from backend.storage.db import get_all_personal_winrates
from backend.config import config


class Pipeline:
    def __init__(self, static_data: StaticData):
        self.data = static_data

    def run(self, snapshot: GameSnapshot) -> PipelineResult | None:
        champion = self.data.get_champion(snapshot.champion_id)
        if champion is None:
            return None

        choices = [
            self.data.get_augment(aid) for aid in snapshot.augment_choices
        ]
        choices = [a for a in choices if a is not None]

        existing = [
            self.data.get_augment(aid) for aid in snapshot.chosen_augments
        ]
        existing = [a for a in existing if a is not None]

        # Resolve enemy champions for CC-aware scoring
        enemies = [
            self.data.get_champion(eid) for eid in snapshot.enemy_champion_ids
        ]
        enemies = [e for e in enemies if e is not None]

        # One shared enemy/ally snapshot drives both augment and item choices.
        enemy_states = snapshot.enemy_states or [
            EnemyState(champion_id=cid) for cid in snapshot.enemy_champion_ids
        ]
        enemy_profile = analyze_enemies(
            enemy_states, self.data.get_champion, self.data.get_item,
        )
        allies = [
            self.data.get_champion(cid) for cid in snapshot.ally_champion_ids
        ]
        ally_profile = analyze_allies([ally for ally in allies if ally is not None])

        personal_wrs = get_all_personal_winrates(champion.id)
        all_items = self.data.all_items()

        recommendations = rank_augments(
            champion=champion,
            choices=choices,
            existing=existing,
            all_items=all_items,
            personal_winrates=personal_wrs if personal_wrs else None,
            enemies=enemies if enemies else None,
            threat_profile=enemy_profile,
            use_personal_performance=bool(config.get("experimental_augment_evidence", False)),
        )

        reroll, reroll_reason = should_reroll(recommendations, champion, existing)

        build_state = suggest_build(
            champion=champion,
            active_augments=existing,
            purchased_items=snapshot.purchased_items,
            current_gold=snapshot.current_gold,
            all_items=all_items,
            enemy_profile=enemy_profile,
            ally_profile=ally_profile,
        )

        return PipelineResult(
            phase=snapshot.phase,
            recommendations=recommendations,
            build_state=build_state,
            suggest_reroll=reroll,
            reroll_reason=reroll_reason,
            enemy_analysis={**enemy_profile.as_dict(), "notes": enemy_profile.notes()},
            ally_analysis={**ally_profile.as_dict(), "notes": ally_profile.notes()},
        )
