from backend.models import GameSnapshot, GamePhase, PipelineResult, EnemyState
from backend.static_data.loader import StaticData
from backend.engine.ranker import rank_augments, should_reroll
from backend.engine.build_suggester import suggest_build
from backend.engine.inventory import build_inventory
from backend.engine.team_context import analyze_enemies, analyze_allies
from backend.storage.db import get_all_personal_winrates
from backend.config import config
from backend.workflow.f0_trace import classify_build_evidence, emit_f0_trace


class Pipeline:
    def __init__(self, static_data: StaticData):
        self.data = static_data

    def run(self, snapshot: GameSnapshot) -> PipelineResult | None:
        champion = self.data.get_champion(snapshot.champion_id)
        if champion is None:
            emit_f0_trace("build", "build_inputs", "rejected",
                          "champion_unknown", source="lcda")
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
            enemy_states, self.data.get_champion,
            lambda item_id: self.data.get_item(self.data.canonical_item_id(item_id)),
        )
        allies = [
            self.data.get_champion(cid) for cid in snapshot.ally_champion_ids
        ]
        # The player's own champion is part of the allied composition.
        # Count it exactly once even if an upstream collector repeats its ID.
        ally_profile = analyze_allies(
            [champion] + [
                ally for ally in allies
                if ally is not None and ally.id != champion.id
            ]
        )

        personal_wrs = get_all_personal_winrates(champion.id)
        all_items = self.data.all_items()
        # Production item catalogs are fail-closed. Synthetic, explicitly
        # injected dictionaries retain the pre-B2 test compatibility path.
        build_items = (
            self.data.recommendable_items()
            if self.data.item_pool_meta is not None else all_items
        )
        inventory = build_inventory(snapshot.purchased_items, self.data)

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
            all_items=build_items,
            inventory=inventory,
            item_data=self.data,
            exclusive_item_groups=self.data.exclusive_item_groups,
            catalog_verified=(
                self.data.item_pool_meta is not None
                and self.data.item_pool_meta.availability == "verified_two_source"
            ),
            enemy_profile=enemy_profile,
            ally_profile=ally_profile,
            build_style=snapshot.build_style,
        )
        meta = self.data.item_pool_meta
        if meta is not None:
            build_state.data_version = {
                "policy_version": meta.policy_version,
                "ddragon_version": meta.ddragon_version,
                "cdragon_patch": meta.cdragon_patch,
                "overrides_version": meta.overrides_version,
                "availability": meta.availability,
            }
            if meta.availability != "verified_two_source":
                # Recognition-only names are not permission to recommend buys.
                build_state.next_item_id = None
                build_state.next_item_gold_needed = 0
                build_state.gold_to_next = 0
                build_state.slot_blocked = False
                build_state.full_build = []
                build_state.alternatives = {}
                build_state.boot_replacement = None
                build_state.build_unavailable_reason = "item_availability_unknown"

        # Only observe existing decisions; no candidate is reranked or promoted.
        pool_verified = bool(
            meta is not None and meta.availability == "verified_two_source"
        )
        inventory_known = not any(
            self.data.get_item(ident) is None
            or self.data.get_item(ident).item_class == "unknown"
            for ident in inventory.other
        )
        confirmed_ids_resolved = len(existing) == len(snapshot.chosen_augments)
        evidence_status, evidence_reason = classify_build_evidence(
            champion_known=True, pool_verified=pool_verified,
            inventory_known=inventory_known,
            augments_confirmed=confirmed_ids_resolved,
        )
        emit_f0_trace("build", "build_inputs", evidence_status,
                      evidence_reason, source="pipeline")
        if build_state.next_item_id:
            emit_f0_trace(
                "build", "next_item", "accepted", "ranked_next_item",
                source="pipeline", item_id=build_state.next_item_id,
            )
        else:
            abstain_reason = build_state.build_unavailable_reason
            if abstain_reason not in (
                "item_pool_unverified", "item_availability_unknown",
                "inventory_unknown", "item_recipe_unknown", "slot_blocked",
            ):
                abstain_reason = "no_candidate"
            if abstain_reason == "item_availability_unknown":
                abstain_reason = "item_pool_unverified"
            emit_f0_trace("build", "next_item", "unknown",
                          abstain_reason, source="pipeline")
        # No per-item factor contribution is exposed in build_state yet.
        emit_f0_trace("build", "eligibility", "unknown",
                      "score_breakdown_unavailable", source="pipeline")

        return PipelineResult(
            phase=snapshot.phase,
            recommendations=recommendations,
            build_state=build_state,
            suggest_reroll=reroll,
            reroll_reason=reroll_reason,
            enemy_analysis={**enemy_profile.as_dict(), "notes": enemy_profile.notes()},
            ally_analysis={**ally_profile.as_dict(), "notes": ally_profile.notes()},
        )
