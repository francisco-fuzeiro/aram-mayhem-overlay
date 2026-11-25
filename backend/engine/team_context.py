"""Team and enemy threat indicators derived only from visible match information.

These are heuristic features for contextual recommendations. They are NOT
measured damage percentages or inferred hidden opponent choices.
Implementation is original to this project.
"""
from dataclasses import asdict, dataclass

from backend.models import ChampionMeta, EnemyState, ItemData


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class EnemyThreatProfile:
    enemies_visible: int = 0
    enemies_analyzed: int = 0
    tanks: int = 0
    magic_pressure: float = 0.0
    physical_pressure: float = 0.0
    cc_pressure: float = 0.0
    sustain_pressure: float = 0.0
    shield_pressure: float = 0.0
    burst_pressure: float = 0.0
    armor_items: int = 0
    magic_resist_items: int = 0
    healing_items: int = 0
    shield_items: int = 0
    tenacity_items: int = 0
    anti_heal_items: int = 0  # visible Grievous Wounds sources (field 24/11)
    visible_items: int = 0
    unknown_items: int = 0
    high_kill_enemies: int = 0
    confidence: str = "low"

    def as_dict(self) -> dict:
        return asdict(self)

    def notes(self) -> list[str]:
        if not self.enemies_analyzed:
            return ["Enemy composition unavailable"]
        result = []
        if self.enemies_analyzed < self.enemies_visible:
            result.append(f"Partial enemy coverage ({self.enemies_analyzed}/{self.enemies_visible} champions)")
        if self.unknown_items:
            result.append(f"{self.unknown_items} visible item(s) without catalog data")
        if self.tanks >= 2:
            result.append(f"{self.tanks} frontline threats")
        if self.cc_pressure >= 0.55:
            result.append("Heavy crowd-control threat")
        if self.burst_pressure >= 0.6:
            result.append("High burst threat")
        if self.sustain_pressure >= 0.55:
            result.append("Strong enemy sustain")
        if self.armor_items >= 2:
            result.append("Visible armor stacking")
        if self.magic_resist_items >= 2:
            result.append("Visible magic-resist stacking")
        if self.high_kill_enemies:
            result.append(f"{self.high_kill_enemies} high-kill opponent(s)")
        return result or ["No dominant threat identified"]


@dataclass(frozen=True)
class AllyTeamProfile:
    known: int = 0
    frontline: int = 0
    magic: int = 0
    physical: int = 0
    support: int = 0

    def as_dict(self) -> dict:
        return asdict(self)

    def notes(self) -> list[str]:
        if not self.known:
            return ["Allied composition unavailable"]
        notes = []
        if self.frontline == 0:
            notes.append("Allies lack frontline")
        if self.magic == 0:
            notes.append("Allies lack a clear magic damage role")
        if self.physical == 0:
            notes.append("Allies lack a clear physical damage role")
        return notes or ["Balanced allied role coverage"]


def analyze_allies(allies: list[ChampionMeta]) -> AllyTeamProfile:
    roles = [champ.role.lower() for champ in allies]
    return AllyTeamProfile(
        known=len(allies),
        frontline=sum(role in ("tank", "fighter") for role in roles),
        magic=roles.count("mage"),
        physical=sum(role in ("marksman", "assassin") for role in roles),
        support=roles.count("support"),
    )


def analyze_enemies(
    enemy_states: list[EnemyState], get_champion, get_item,
) -> EnemyThreatProfile:
    """Summarize champion kits and *visible* item inventory, without guessing.

    Champion stats are manually curated relative traits, not empirical in-game
    damage. This model avoids presenting its output as measured damage share.
    """
    if not enemy_states:
        return EnemyThreatProfile()

    known = tanks = armor = magic_resist = items_seen = high_kill = 0
    healing = shields = tenacity = anti_heal = 0
    unknown_items = 0
    magic_sum = physical_sum = cc_sum = sustain_sum = shield_sum = burst_sum = 0.0

    for player in enemy_states:
        # The inventory is visible independently of our champion catalog.
        # Do not lose verified item observations when a champion is unmapped.
        player_healing_items = 0
        for item_id in player.item_ids:
            items_seen += 1
            item: ItemData | None = get_item(item_id)
            if item is None:
                unknown_items += 1
                continue
            properties = item.properties
            armor += int("armor" in properties)
            magic_resist += int("magic_resist" in properties)
            heals = bool(properties & {"lifesteal", "omnivamp"})
            healing += int(heals)
            player_healing_items += int(heals)
            shields += int("shield" in properties)
            tenacity += int("tenacity" in properties)
            anti_heal += int("anti_heal" in properties)

        champion: ChampionMeta | None = get_champion(player.champion_id)
        if champion is None:
            continue
        known += 1
        role = champion.role.lower()
        stats = champion.stats
        magic_sum += _clamp01(stats.ap + (0.15 if role == "mage" else 0))
        physical_sum += _clamp01(max(stats.ad, stats.attack_speed, stats.lethality) +
                                 (0.15 if role in ("marksman", "assassin") else 0))
        cc_sum += _clamp01(max(stats.hard_cc, stats.soft_cc * 0.6,
                               champion.cc_profile.cc_uptime_rating))
        sustain_sum += _clamp01(stats.heal_power) + 0.05 * player_healing_items
        shield_sum += _clamp01(stats.shield)
        burst_sum += _clamp01(max(stats.lethality, stats.ap * 0.7))

        if role == "tank" or (role == "fighter" and stats.hp >= 0.55):
            tanks += 1
        if player.kills >= 6 and player.kills - player.deaths >= 5:
            high_kill += 1

    if not known:
        return EnemyThreatProfile(
            enemies_visible=len(enemy_states), visible_items=items_seen,
            unknown_items=unknown_items, armor_items=armor,
            magic_resist_items=magic_resist,
            healing_items=healing, shield_items=shields,
            tenacity_items=tenacity, anti_heal_items=anti_heal,
        )

    power_total = magic_sum + physical_sum
    magic_mix = magic_sum / power_total if power_total else 0.5
    physical_mix = 1.0 - magic_mix
    return EnemyThreatProfile(
        enemies_visible=len(enemy_states),
        enemies_analyzed=known,
        tanks=tanks,
        magic_pressure=round(_clamp01(magic_mix), 2),
        physical_pressure=round(_clamp01(physical_mix), 2),
        cc_pressure=round(_clamp01(cc_sum / known), 2),
        sustain_pressure=round(_clamp01(sustain_sum / known), 2),
        shield_pressure=round(_clamp01(shield_sum / known), 2),
        burst_pressure=round(_clamp01(burst_sum / known), 2),
        armor_items=armor,
        magic_resist_items=magic_resist,
        healing_items=healing, shield_items=shields,
        tenacity_items=tenacity, anti_heal_items=anti_heal,
        visible_items=items_seen,
        unknown_items=unknown_items,
        high_kill_enemies=high_kill,
        confidence="high" if known >= 5 and known == len(enemy_states)
                           and items_seen >= 5 and not unknown_items
                   else "medium" if known >= 3 else "low",
    )


def augment_threat_modifier(
    contribution, enemy: EnemyThreatProfile | None,
) -> float:
    """Small bounded adjustment to augment-context score, not the base fit.

    Anti-frontline and defensive utility are useful examples, not universal
    guarantees of victory. Missing enemy data must result in zero adjustment.
    """
    if not enemy or not enemy.enemies_analyzed:
        return 0.0
    anti_tank = min(enemy.tanks, 3) / 3.0
    anti_cc = enemy.cc_pressure
    anti_burst = max(enemy.burst_pressure, 0.25 * enemy.high_kill_enemies)
    # Keep context impact limited until calibrated using real game outcomes.
    modifier = (
        anti_tank * (0.35 * contribution.attack_speed + 0.35 * contribution.pen)
        + anti_cc * (0.3 * contribution.shield + 0.2 * contribution.hp)
        + anti_burst * (0.3 * contribution.hp + 0.2 * contribution.shield)
        + min(enemy.magic_resist_items, 3) / 3 * 0.2 * contribution.pen
    )
    return round(max(0.0, min(0.7, modifier)), 3)
