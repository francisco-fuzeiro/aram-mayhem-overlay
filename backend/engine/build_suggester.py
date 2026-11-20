"""Build paths that react to chosen augments and player-visible opponents.

The original ARAM Oracle stat-vector scoring is retained as the foundation.
Our contextual adjustments are small and interpretable, not measured win odds.
"""
import logging

from backend.engine.inventory import Inventory
from backend.models import ChampionMeta, AugmentData, ItemData, BuildState, BootReplacement
from backend.engine.scoring import score_item
from backend.engine.team_context import EnemyThreatProfile, AllyTeamProfile

logger = logging.getLogger("aram-oracle.engine.build")

BUILD_STYLES = ("Balanced", "Damage", "Survival", "Utility")

def _item_name_key(item: ItemData) -> str:
    """Treat catalog variants with the same display name as one build choice.

    DataDragon may include map/mode-specific IDs for the same item. We don't
    claim those variants are mutually purchasable or different upgrades.
    """
    return " ".join(item.name.casefold().split())


# A neutral baseline used only to compare listed flat and percentage item MS.
# Actual champion movement speed, soft caps and active effects are not modeled.
_LISTED_MS_BASELINE = 335.0
_BOOT_SWAP_MIN_GAIN = 0.65
_BOOT_SWAP_MS_COST = 0.014


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
    ranked: list[ItemData],
    owned: list[str] | Inventory,
    all_items: list[ItemData],
    size: int,
    exclusive_item_groups: dict[str, frozenset[str]] | None = None,
) -> list[str]:
    """Preserve acquired finals and fill only legal, distinct build slots."""
    finals = list(owned.finals) if isinstance(owned, Inventory) else list(owned)
    selected = list(finals)
    by_id = {item.id: item for item in all_items}
    groups = exclusive_item_groups or {}
    memberships: dict[str, set[str]] = {}
    for name, members in groups.items():
        for ident in members:
            memberships.setdefault(str(ident), set()).add(name)

    seen = set(finals)
    named = {_item_name_key(by_id[ident]) for ident in finals if ident in by_id}
    occupied = set().union(*(memberships.get(ident, set()) for ident in finals))
    boots_taken = any(
        by_id.get(ident) is not None
        and (by_id[ident].item_class == "boots_tier2" or by_id[ident].boots)
        for ident in finals
    )
    basic_boots = (
        isinstance(owned, Inventory)
        and "1001" in owned.components
        and not boots_taken
    )

    def is_tier_two(item: ItemData) -> bool:
        return item.item_class == "boots_tier2" or (
            item.boots and item.item_class not in {"component", "boots_tier1"}
        )

    def eligible(item: ItemData) -> bool:
        return (
            item.id not in seen
            and _item_name_key(item) not in named
            and not (is_tier_two(item) and boots_taken)
            and not (memberships.get(item.id, set()) & occupied)
            and item.item_class not in {"component", "boots_tier1"}
        )

    def take(item: ItemData) -> None:
        nonlocal boots_taken
        selected.append(item.id)
        seen.add(item.id)
        named.add(_item_name_key(item))
        occupied.update(memberships.get(item.id, set()))
        boots_taken |= is_tier_two(item)

    # Reserve a final slot for an upgrade when basic Boots is equipped.
    for item in ranked:
        if len(selected) >= size:
            break
        if not eligible(item):
            continue
        if basic_boots and not boots_taken and not is_tier_two(item):
            if len(selected) >= size - 1:
                continue
        take(item)

    if basic_boots and not boots_taken and len(selected) < size:
        upgrade = next(
            (item for item in ranked if is_tier_two(item) and eligible(item)),
            None,
        )
        if upgrade is not None:
            take(upgrade)
    return selected


def _boot_replacement(
    champion: ChampionMeta,
    augments: list[AugmentData],
    owned_ids: list[str],
    item_catalog: list[ItemData],
    enemy: EnemyThreatProfile | None,
    allies: AllyTeamProfile | None,
    style: str,
    slots: int,
    *,
    catalog_verified: bool = False,
    exclusive_item_groups: dict[str, frozenset[str]] | None = None,
    item_data=None,
    inventory: Inventory | None = None,
) -> BootReplacement | None:
    """Advisory boot sale for a verified, full and entirely known inventory.

    Only confirmed augments supplied by the caller may affect the contextual
    value; candidates visible in an offer must never be passed here.
    """
    if not catalog_verified:
        return None
    if inventory is not None:
        if inventory.used_slots != slots:
            return None
    elif len(owned_ids) != slots:
        return None

    by_id = {item.id: item for item in item_catalog}

    def resolve(ident: str) -> ItemData | None:
        return item_data.get_item(ident) if item_data is not None else by_id.get(ident)

    observed_items = [resolve(ident) for ident in owned_ids]
    if any(item is None or item.item_class == "unknown" for item in observed_items):
        return None
    current_boot = next(
        (item for item in observed_items if item is not None
         and (item.item_class in {"boots_tier1", "boots_tier2"} or item.boots)),
        None,
    )
    if current_boot is None:
        return None

    def listed_ms(item: ItemData) -> float:
        return item.move_speed_flat + _LISTED_MS_BASELINE * item.move_speed_percent

    boot_ms = listed_ms(current_boot)
    if boot_ms <= 0:
        return None

    weight = {"Balanced": 0.9, "Damage": 1.65, "Survival": 1.9, "Utility": 1.75}[style]

    def contextual_value(item: ItemData) -> float:
        return score_item(champion, item, augments) + weight * _item_role_bonus(
            item, enemy, allies, style
        )

    boot_value = contextual_value(current_boot)
    observed = set(owned_ids)
    owned_names = {_item_name_key(item) for item in observed_items if item is not None}
    groups = exclusive_item_groups or {}
    occupied_groups = {
        name for name, members in groups.items()
        if any(ident in members for ident in owned_ids if ident != current_boot.id)
    }

    candidates: list[tuple[float, str, ItemData, float]] = []
    for item in item_catalog:
        if (
            item.item_class != "final" or item.boots
            or item.id in observed or _item_name_key(item) in owned_names
            or listed_ms(item) <= 0
            or any(item.id in groups[name] for name in occupied_groups)
        ):
            continue
        speed_change = listed_ms(item) - boot_ms
        net_gain = (
            contextual_value(item) - boot_value
            - _BOOT_SWAP_MS_COST * max(0.0, -speed_change)
        )
        if net_gain > _BOOT_SWAP_MIN_GAIN:
            candidates.append((net_gain, item.id, item, speed_change))
    if not candidates:
        return None

    _, _, replacement, speed_change = sorted(
        candidates, key=lambda row: (-row[0], row[1])
    )[0]
    return BootReplacement(
        sell_item_id=current_boot.id,
        buy_item_id=replacement.id,
        buy_cost=replacement.cost,
        listed_ms_change=round(speed_change, 1),
        reason=(
            "Potential late-game stat upgrade for the selected build style. "
            "Movement-speed difference is estimated from listed item stats only; "
            "review passives and sell value before swapping."
        ),
    )


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
    inventory: Inventory | None = None,
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
    owned_finals = list(inventory.finals) if inventory is not None else purchased
    available = [item for item in all_items if item.id not in owned_finals]
    rankings = {
        style: _rank_items(
            champion, active_augments, available, enemy_profile, ally_profile, style
        )
        for style in BUILD_STYLES
    }
    paths = {
        style: _fill_slots(rankings[style], inventory if inventory is not None else purchased, all_items, build_size)
        for style in BUILD_STYLES
    }
    full_build = paths[selected_style]

    # Do not recommend a seventh item. Even if the catalog offers thousands
    # of candidates, "next item" must actually belong to the selected path.
    remaining = [item_id for item_id in full_build[len(owned_finals):]]
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
    boot_replacement = _boot_replacement(
        champion, active_augments, purchased, all_items,
        enemy_profile, ally_profile, selected_style, build_size,
    )

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
        boot_replacement=boot_replacement,
    )
