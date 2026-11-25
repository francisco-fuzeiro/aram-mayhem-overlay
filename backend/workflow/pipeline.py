from backend.models import GameSnapshot, GamePhase, PipelineResult, EnemyState
from backend.static_data.loader import StaticData
from backend.engine.ranker import rank_augments, should_reroll
from backend.engine.build_suggester import suggest_build
from backend.engine.anvil_priorities import (
    rate_stat_anvil_offer, rate_verified_anvil_options,
)
from backend.models import AugmentTier
from backend.engine.inventory import build_inventory
from backend.engine.team_context import analyze_enemies, analyze_allies
from backend.storage.db import get_all_personal_winrates
from backend.config import config
from backend.workflow.f0_trace import classify_build_evidence, emit_f0_trace
from backend import feature_diagnostics


def _record_next_item_decision(build_state, meta) -> None:
    """Observe the actual post-policy next-item verdict, not a shop claim."""
    if meta is None or meta.availability != "verified_two_source":
        status, reason = "skipped", "unverified"
    elif build_state.slot_blocked:
        status, reason = "skipped", "slot_blocked"
    elif build_state.build_unavailable_reason == "inventory_unknown":
        status, reason = "skipped", "inventory_unknown"
    elif build_state.build_unavailable_reason == "item_recipe_unknown":
        status, reason = "skipped", "item_recipe_unknown"
    elif build_state.next_item_id:
        status, reason = "ok", "ranked"
    else:
        status, reason = "skipped", "no_candidate"
    feature_diagnostics.record("build.next_item", status, reason)



class Pipeline:
    def __init__(self, static_data: StaticData):
        self.data = static_data

    def _rate_anvil_offer(self, snapshot, champion, existing, inventory, enemy):
        """Score only a server-verified popup (anvil_offer_ids); else nothing."""
        ids = list(getattr(snapshot, "anvil_offer_ids", None) or [])
        catalog_fn = getattr(self.data, "stat_anvil_catalog", None)
        if not ids or not callable(catalog_fn):
            return []
        catalog = catalog_fn()
        if any(i not in catalog for i in ids):
            return []
        ratings = rate_stat_anvil_offer(
            champion, [catalog[i] for i in ids], list(catalog.values()), existing,
            [self.data.get_item(ident) for ident in inventory.finals], enemy,
        )
        feature_diagnostics.record(
            "anvil.offer_rating", *(("ok", "scored") if ratings else ("skipped", "unmodelled")),
        )
        return ratings

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

        anvil_only = bool(choices) and all(
            aug.tier == AugmentTier.STAT_ANVIL for aug in choices
        )
        # A mixed augment/Stat-Anvil OCR catalog is ambiguous: abstain.
        mixed_offer = bool(choices) and any(
            aug.tier == AugmentTier.STAT_ANVIL for aug in choices
        ) and not anvil_only

        recommendations = [] if anvil_only or mixed_offer else rank_augments(
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
        # Optional heuristic scores for exact tier-zero options, never a
        # classification or observation of a visible purchased Anvil popup.
        anvil_ratings = (
            rate_verified_anvil_options(
                champion, choices, existing,
                [self.data.get_item(ident) for ident in inventory.finals],
                enemy_profile,
            ) if anvil_only and len(choices) == 3 and
                 len({aug.id for aug in choices}) == 3 else []
        )
        offer_ratings = self._rate_anvil_offer(
            snapshot, champion, existing, inventory, enemy_profile,
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

        # Record the final, already fail-closed item decision. No item IDs or
        # personal data enter the per-feature diagnostic journal.
        _record_next_item_decision(build_state, meta)

        # Only observe existing decisions; no candidate is reranked or promoted.
        pool_verified = bool(
            meta is not None and meta.availability == "verified_two_source"
        )
        inventory_known = not any(
            self.data.get_item(ident) is None
            or self.data.get_item(ident).item_class == "unknown"
            for ident in inventory.other
        )
        # Zero confirmed selections is not proof that all shown picks were recorded.
        confirmed_ids_resolved = bool(existing) and len(existing) == len(snapshot.chosen_augments)
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
            anvil_recommendations=anvil_ratings,
            anvil_offer_ratings=offer_ratings,
        )
