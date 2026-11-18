"""Build paths that react to chosen augments and player-visible opponents.

The original ARAM Oracle stat-vector scoring is retained as the foundation.
Our contextual adjustments are small and interpretable, not measured win odds.
"""
import logging

from backend.models import ChampionMeta, AugmentData, ItemData, BuildState
from backend.engine.scoring import score_item
from backend.engine.team_context import EnemyThreatProfile, AllyTeamProfile

logger = logging.getLogger("aram-oracle.engine.build")

BUILD_STYLES = ("Balanced", "Damage", "Survival", "Utility")


def _item_role_bonus(
    item: ItemData,
    enemy: EnemyThreatProfile | None,
    allies: AllyTeamProfile | None,
    direction: str,
) -> float:
    stats = item.stats
    tags = {t.lower() for t in item.tags}

    # Builds can still work before the opposing five players are revealed.
    visible = bool(enemy and enemy.enemies_analyzed)
    tanks = min(enemy.tanks / 3.0, 1.0) if visible else 0.0
    cc = enemy.cc_pressure if visible else 0.0
    burst = enemy.burst_pressure if visible else 0.0
    magic = enemy.magic_pressure if visible else 0.0
    physical = enemy.physical_pressure if visible else 0.0
    ally_no_frontline = bool(allies and allies.known and not allies.frontline)

    damage = (
        0.42 * stats.pen +
        0.40 * stats.lethality +
        0.22 * stats.ad +
        0.22 * stats.ap +
        0.35 * stats.attack_speed * tanks
    )
    if visible and enemy.armor_items >= 2:
        damage += 0.22 * stats.lethality
    if visible and enemy.magic_resist_items >= 2:
        damage += 0.22 * stats.pen

    survival = (
        (0.3 + 0.45 * burst + 0.25 * cc) * stats.hp +
        (0.2 + 0.45 * burst + 0.35 * cc) * stats.shield
    )
    if visible and "armor" in tags:
        survival += 0.65 * physical
    if visible and tags & {"spellblock", "magicresist", "magic_resist"}:
        survival += 0.65 * magic
    if ally_no_frontline:
        survival += 0.25 * stats.hp

    utility = (
        0.48 * stats.heal_power +
        0.42 * stats.hard_cc +
        0.35 * stats.shield +
        0.30 * stats.cdr
    )
    if ally_no_frontline:
        utility += 0.20 * stats.hard_cc

    if direction == "Damage":
        return damage
    if direction == "Survival":
        return survival
    if direction == "Utility":
        return utility
    # All three dimensions matter in the flexible default.
    return 0.45 * damage + 0.50 * survival + 0.25 * utility


def _rank_items(
    champion: ChampionMeta,
    augments: list[AugmentData],
    available: list[ItemData],
    enemy: EnemyThreatProfile | None,
    allies: AllyTeamProfile | None,
    direction: str,
) -> list[ItemData]:
    weights = {"Balanced": 0.9, "Damage": 1.65, "Survival": 1.9, "Utility": 1.75}
    weight = weights[direction]
    return sorted(
        available,
        key=lambda item: (
            -(score_item(champion, item, augments) +
              weight * _item_role_bonus(item, enemy, allies, direction)),
            item.id,
        ),
    )


def _fill_slots(
    ranked: list[ItemData], owned: list[str], all_items: list[ItemData], size: int,
) -> list[str]:
    by_id = {item.id: item for item in all_items}
    selected = list(owned)
    seen = set(owned)
    boots_taken = any(by_id.get(item_id) and by_id[item_id].boots for item_id in owned)
    for item in ranked:
        if len(selected) >= size:
            break
        if item.id in seen or (item.boots and boots_taken):
            continue
        selected.append(item.id)
        seen.add(item.id)
        if item.boots:
            boots_taken = True
    return selected


def suggest_build(
    champion: ChampionMeta,
    active_augments: list[AugmentData],
    purchased_items: list[str],
    current_gold: int,
    all_items: list[ItemData],
    build_size: int = 6,
    enemy_profile: EnemyThreatProfile | None = None,
    ally_profile: AllyTeamProfile | None = None,
    build_style: str = "Balanced",
) -> BuildState:
    """Return one flexible path and optional Damage/Survival/Utility paths.

    Builds keep purchased items in their current slots. A player can select
    another style without changing their existing items. Item-purchase paths
    and game-mode-specific item restrictions need further data validation.
    """
    # Client-selected style changes ordering, but cannot force or buy an item.
    # Invalid external snapshot values fall back to the neutral default.
    selected_style = build_style if build_style in BUILD_STYLES else "Balanced"
    purchased = list(purchased_items)
    available = [item for item in all_items if item.id not in purchased]
    rankings = {
        style: _rank_items(
            champion, active_augments, available, enemy_profile, ally_profile, style
        )
        for style in BUILD_STYLES
    }
    paths = {
        style: _fill_slots(rankings[style], purchased, all_items, build_size)
        for style in BUILD_STYLES
    }
    full_build = paths[selected_style]

    # Do not recommend a seventh item. Even if the catalog offers thousands
    # of candidates, "next item" must actually belong to the selected path.
    remaining = [item_id for item_id in full_build[len(purchased):]]
    by_id = {item.id: item for item in all_items}
    next_item = next(
        (by_id[item_id] for item_id in remaining
         if item_id in by_id and by_id[item_id].cost <= current_gold),
        None,
    )
    gold_to_next = 0
    if next_item is None and remaining:
        first = by_id.get(remaining[0])
        if first is not None:
            gold_to_next = max(0, first.cost - current_gold)

    alternatives = paths

    reasons = ["Adjusted for your current champion and chosen augments"]
    if enemy_profile and enemy_profile.enemies_analyzed:
        reasons.extend(enemy_profile.notes())
    if ally_profile and ally_profile.known:
        reasons.extend(ally_profile.notes())
    if selected_style != "Balanced":
        reasons.append(f"Selected build path: {selected_style}")
    if next_item is None and remaining:
        logger.debug("%s has no affordable recommended item at %dg", champion.id, current_gold)

    return BuildState(
        champion_id=champion.id,
        chosen_augments=[aug.id for aug in active_augments],
        purchased_items=purchased,
        next_item_id=next_item.id if next_item else None,
        gold_to_next=gold_to_next,
        full_build=full_build,
        alternatives=alternatives,
        reasons=reasons,
        selected_style=selected_style,
    )
