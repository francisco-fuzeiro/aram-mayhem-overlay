"""Build paths that react to chosen augments and player-visible opponents.

The original ARAM Oracle stat-vector scoring is retained as the foundation.
Our contextual adjustments are small and interpretable, not measured win odds.
"""
import logging
import os
from collections import Counter

from backend.engine.anvil_priorities import rank_anvil_stats
from backend.engine.inventory import Inventory, remaining_cost
from backend.models import ChampionMeta, AugmentData, ItemData, BuildState, BootReplacement
from backend.engine.scoring import score_item
from backend.workflow.f0_trace import emit_f0_trace
from backend.engine.team_context import EnemyThreatProfile, AllyTeamProfile

logger = logging.getLogger("aram-oracle.engine.build")

BUILD_STYLES = ("Balanced", "Damage", "Survival", "Utility")
ENEMY_REACTION_BONUS = 0.15
ENEMY_REACTION_MAX = 0.30


def _enemy_reaction_bonus(
    item: ItemData,
    champion: ChampionMeta,
    enemy: EnemyThreatProfile | None,
) -> float:
    """Bounded additive response only to observed enemy item/kit signals."""
    if (enemy is None or enemy.enemies_analyzed == 0
            or item.item_class != "final" or not item.properties):
        return 0.0
    properties = item.properties
    ap_champion = (
        champion.role.lower() == "mage"
        or champion.stats.ap > champion.stats.ad
    )
    reactions = 0
    if ((enemy.sustain_pressure >= 0.35 or enemy.healing_items >= 3)
            and "anti_heal" in properties):
        reactions += 1
    if (enemy.armor_items >= 3 or enemy.tanks >= 2):
        if ("magic_pen" if ap_champion else "armor_pen") in properties:
            reactions += 1
    if enemy.magic_resist_items >= 3 and "magic_pen" in properties:
        reactions += 1
    if enemy.physical_pressure >= 0.6 and "armor" in properties:
        reactions += 1
    if enemy.magic_pressure >= 0.6 and "magic_resist" in properties:
        reactions += 1
    if enemy.burst_pressure >= 0.5 and properties & {"shield", "health"}:
        reactions += 1
    if enemy.cc_pressure >= 0.5 and properties & {"tenacity", "cleanse"}:
        reactions += 1
    return min(ENEMY_REACTION_MAX, ENEMY_REACTION_BONUS * reactions)

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
              weight * _item_role_bonus(item, enemy, allies, direction) +
              _enemy_reaction_bonus(item, champion, enemy)),
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

    # F0 read-only, opt-in sampling: at most 12 bounded classification
    # events per build computation. No names, free-form scores or item changes.
    trace_enabled = os.environ.get("ARAM_ORACLE_F0_TRACE") == "1"
    diagnostic_budget = 12

    def trace_candidate(item: ItemData, status: str, reason: str) -> None:
        nonlocal diagnostic_budget
        if trace_enabled and diagnostic_budget > 0:
            emit_f0_trace("build", "eligibility", status, reason,
                          source="catalog", item_id=item.id)
            diagnostic_budget -= 1

    def eligible(item: ItemData) -> bool:
        # Identical filters/order to the established build eligibility policy.
        available = (
            item.id not in seen
            and _item_name_key(item) not in named
            and not (is_tier_two(item) and boots_taken)
            and not (memberships.get(item.id, set()) & occupied)
            and item.item_class not in {"component", "boots_tier1"}
        )
        if not available:
            reason = (
                "already_in_build" if item.id in seen
                else "item_name_duplicate" if _item_name_key(item) in named
                else "boots_conflict" if is_tier_two(item) and boots_taken
                else "exclusive_group_conflict"
                if memberships.get(item.id, set()) & occupied
                else "item_class_excluded"
                if item.item_class in {"component", "boots_tier1"}
                else "candidate_excluded"
            )
            trace_candidate(item, "rejected", reason)
        return available

    def take(item: ItemData) -> None:
        nonlocal boots_taken
        selected.append(item.id)
        seen.add(item.id)
        named.add(_item_name_key(item))
        occupied.update(memberships.get(item.id, set()))
        boots_taken |= is_tier_two(item)
        trace_candidate(item, "accepted", "slot_candidate_selected")

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
    # A scoring model for an unrecognized champion is insufficient evidence
    # for a destructive late-game sell recommendation.
    if item_data is not None and item_data.get_champion(champion.id) is None:
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
        ) + _enemy_reaction_bonus(item, champion, enemy)

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
    item_data=None,
    exclusive_item_groups: dict[str, frozenset[str]] | None = None,
    catalog_verified: bool = False,
) -> BuildState:
    """Return one stable selected-style build and its recipe-aware next purchase.

    The input augment list is the previously selected/confirmed set, not
    an unconfirmed offered candidate. No automatic purchase is performed.
    """
    selected_style = build_style if build_style in BUILD_STYLES else "Balanced"
    purchased = list(purchased_items)
    owned_finals = list(inventory.finals) if inventory is not None else purchased
    # Preserve original in-game item IDs and their observed display names,
    # while build planning continues to use the same canonical inventory IDs.
    # Do not infer an item purchase from a matching offer or item name.
    owned_build_names: dict[str, str] = {}
    if item_data is not None and inventory is not None:
        for raw_id in purchased:
            canonical = item_data.canonical_item_id(raw_id)
            if canonical not in owned_finals or canonical in owned_build_names:
                continue
            observed = item_data.get_item(raw_id)
            if observed is not None and observed.name:
                owned_build_names[canonical] = observed.name
            elif hasattr(item_data, "get_item_name"):
                observed_name = item_data.get_item_name(raw_id)
                if observed_name and observed_name != str(raw_id):
                    owned_build_names[canonical] = observed_name
    available = [
        item for item in all_items
        if item.id not in owned_finals
        and (not catalog_verified or item.final)
    ]
    ranked = _rank_items(
        champion, active_augments, available, enemy_profile, ally_profile,
        selected_style,
    )
    full_build = _fill_slots(
        ranked, inventory if inventory is not None else purchased,
        all_items, build_size, exclusive_item_groups,
    )
    by_id = {item.id: item for item in all_items}

    # Never skip an expensive first unowned item to propose an affordable
    # later item: purchase order is independent of the current wallet.
    remaining = [ident for ident in full_build if ident not in owned_finals]
    next_item = by_id.get(remaining[0]) if remaining else None
    gold_needed = 0
    gold_to_next = 0
    slot_blocked = False
    build_unavailable_reason = None

    if item_data is not None and inventory is not None:
        # Physical slots occupied by unrecognized items cannot be assumed
        # available or legal; fail closed on incomplete inventory evidence.
        if any(
            item_data.get_item(ident) is None
            or item_data.get_item(ident).item_class == "unknown"
            for ident in inventory.other
        ):
            next_item = None
            build_unavailable_reason = "inventory_unknown"

    if next_item is not None:
        if item_data is not None and inventory is not None:
            try:
                gold_needed, consumed = remaining_cost(
                    next_item.id, Counter(inventory.components), item_data,
                )
            except (ValueError, TypeError, KeyError):
                next_item = None
                build_unavailable_reason = "item_recipe_unknown"
                consumed = Counter()
            if next_item is not None:
                slot_blocked = inventory.free_slots == 0 and not consumed
        else:
            # Historical direct-call/synthetic tests have no physical recipe
            # source: retain a conservative undiscounted full-price estimate.
            gold_needed = next_item.cost
        if next_item is not None:
            gold_to_next = max(0, gold_needed - max(0, current_gold))

    # Preserve the optional verified boot swap for the single selected build.
    boot_replacement = _boot_replacement(
        champion, active_augments,
        ([item_data.canonical_item_id(ident) for ident in purchased]
         if item_data is not None else purchased),
        all_items, enemy_profile, ally_profile, selected_style, build_size,
        catalog_verified=catalog_verified,
        exclusive_item_groups=exclusive_item_groups,
        item_data=item_data,
        inventory=inventory,
    )

    # Six *observed* final items, not six planned items or occupied components,
    # authorize post-build advice. A boot swap remains a separate higher-priority
    # optional item action; it is never a seventh direct purchase.
    anvil_stat_priorities = []
    if (catalog_verified and inventory is not None and item_data is not None
            and item_data.get_champion(champion.id) is not None
            and inventory.used_slots == build_size
            and len(inventory.finals) == build_size
            and len(set(inventory.finals)) == build_size
            and len(full_build) == build_size
            and set(inventory.finals) == set(full_build)
            and build_unavailable_reason is None):
        observed_items = [item_data.get_item(ident) for ident in inventory.finals]
        if all(item is not None and item.final for item in observed_items):
            anvil_stat_priorities = rank_anvil_stats(
                champion, active_augments, observed_items, enemy_profile,
            )

    reasons = ["Adjusted for your current champion and chosen augments"]
    if enemy_profile and enemy_profile.enemies_analyzed:
        reasons.extend(enemy_profile.notes())
    if ally_profile and ally_profile.known:
        reasons.extend(ally_profile.notes())
    if selected_style != "Balanced":
        reasons.append(f"Selected build path: {selected_style}")

    return BuildState(
        champion_id=champion.id,
        chosen_augments=[aug.id for aug in active_augments],
        purchased_items=purchased,
        next_item_id=next_item.id if next_item else None,
        next_item_gold_needed=gold_needed,
        gold_to_next=gold_to_next,
        slot_blocked=slot_blocked,
        full_build=full_build,
        alternatives={},
        reasons=reasons,
        selected_style=selected_style,
        boot_replacement=boot_replacement,
        build_unavailable_reason=build_unavailable_reason,
        owned_build_ids=list(owned_finals),
        owned_build_names=owned_build_names,
        anvil_stat_priorities=anvil_stat_priorities,
    )
