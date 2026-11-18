"""Deterministic enemy/ally and build adaptation cases (no live LoL required)."""

from backend.collectors.lcda import parse_game_snapshot
from backend.engine.augment_rating import rate_augment
from backend.engine.build_suggester import suggest_build
from backend.engine.team_context import (
    AllyTeamProfile, EnemyThreatProfile, analyze_allies,
    analyze_enemies,
)
from backend.models import (
    AugmentData, AugmentTier, ChampionMeta, EnemyState, GamePhase,
    ItemData, StatVector,
)


def champion(identifier, role, **stats):
    return ChampionMeta(
        id=identifier, name=identifier.title(), role=role,
        stats=StatVector(**stats),
    )


def item(identifier, tags=(), **stats):
    return ItemData(
        identifier, identifier.title(), 1500, StatVector(**stats),
        tags=list(tags),
    )


def test_enemy_threat_uses_known_champion_stats_and_visible_items_only():
    tank = champion("tank", "tank", hp=0.9, hard_cc=0.9)
    mage = champion("mage", "mage", ap=0.95, cdr=0.7)
    items = {
        "armor": item("armor", ["Armor"]),
        "mr": item("mr", ["SpellBlock"]),
    }
    threats = analyze_enemies(
        [
            EnemyState("tank", ["armor", "armor"], kills=7, deaths=1),
            EnemyState("mage", ["mr"], kills=0, deaths=3),
        ],
        {"tank": tank, "mage": mage}.get,
        items.get,
    )
    assert threats.enemies_visible == 2
    assert threats.enemies_analyzed == 2
    assert threats.tanks == 1
    assert threats.armor_items == 2
    assert threats.magic_resist_items == 1
    assert threats.visible_items == 3
    assert threats.high_kill_enemies == 1
    assert 0.0 <= threats.magic_pressure <= 1.0
    assert "Visible armor stacking" in threats.notes()


def test_absent_and_unknown_enemy_data_is_explicit():
    empty = analyze_enemies([], lambda _: None, lambda _: None)
    unknown = analyze_enemies(
        [EnemyState("not-visible-in-catalog")], lambda _: None, lambda _: None
    )
    assert empty.confidence == "low"
    assert empty.notes() == ["Enemy composition unavailable"]
    assert unknown.enemies_visible == 1
    assert unknown.enemies_analyzed == 0
    assert unknown.visible_items == 0


def test_ally_roles_identify_missing_frontline():
    profile = analyze_allies([
        champion("lux", "mage", ap=0.9),
        champion("jinx", "marksman", ad=0.8),
    ])
    assert profile.known == 2
    assert profile.frontline == 0
    assert "Allies lack frontline" in profile.notes()


def test_enemy_context_changes_defensive_augment_score():
    me = champion("adc", "marksman", ad=0.9, attack_speed=0.9, hp=0.2)
    shield = AugmentData(
        "shield", "Shield", AugmentTier.GOLD, "",
        StatVector(shield=0.85, hp=0.55),
    )
    baseline = rate_augment(me, shield, [])
    threats = EnemyThreatProfile(
        enemies_visible=5, enemies_analyzed=5,
        cc_pressure=0.9, burst_pressure=0.8,
    )
    counter = rate_augment(me, shield, [], threat_profile=threats)
    assert counter.context > baseline.context
    assert counter.score > baseline.score


def test_magic_resistance_changes_build_paths_only_with_observed_enemy():
    me = champion("mage", "mage", ap=0.8)
    plain = item("a_plain", ap=0.6)
    resist = item("z_resist", ["SpellBlock"], ap=0.6)
    without = suggest_build(me, [], [], 2000, [plain, resist])
    threats = EnemyThreatProfile(
        enemies_visible=5, enemies_analyzed=5,
        magic_pressure=0.9, physical_pressure=0.1,
    )
    with_magic = suggest_build(
        me, [], [], 2000, [plain, resist], enemy_profile=threats
    )
    assert without.alternatives["Survival"][0] == "a_plain"
    assert with_magic.alternatives["Survival"][0] == "z_resist"
    assert with_magic.next_item_id == "z_resist"
    assert "Damage" in with_magic.alternatives
    assert "Utility" in with_magic.alternatives
    assert "Survival" in with_magic.alternatives


def test_owned_boots_prevent_additional_boots():
    me = champion("lux", "mage", ap=0.9)
    owned_boots = ItemData("boots1", "Boots 1", 1000, StatVector(cdr=0.4), boots=True)
    other_boots = ItemData("boots2", "Boots 2", 1000, StatVector(ap=1.0), boots=True)
    other_item = item("staff", ap=0.7)
    result = suggest_build(
        me, [], ["boots1"], 2000, [owned_boots, other_boots, other_item],
    )
    assert "boots2" not in result.full_build
    assert result.next_item_id == "staff"
    assert all("boots2" not in path for path in result.alternatives.values())


def test_lcda_only_exposes_visible_teams_and_enemy_items():
    raw = {
        "activePlayer": {
            "summonerName": "me", "currentGold": 1000, "level": 5,
            "championStats": {"maxHealth": 1000, "currentHealth": 500},
        },
        "allPlayers": [
            {"summonerName": "me", "team": "ORDER", "championName": "Lux",
             "items": [{"itemID": 3001}]},
            {"summonerName": "ally", "team": "ORDER", "championName": "Jinx"},
            {"summonerName": "enemy", "team": "CHAOS", "championName": "Sion",
             "items": [{"itemID": 3006}], "scores": {"kills": 7, "deaths": 1}},
        ],
        "gameData": {"gameTime": 420, "gameId": 7},
    }
    snapshot = parse_game_snapshot(raw, GamePhase.IN_GAME)
    assert snapshot.champion_id == "lux"
    assert snapshot.ally_champion_ids == ["jinx"]
    assert snapshot.enemy_champion_ids == ["sion"]
    assert len(snapshot.enemy_states) == 1
    assert snapshot.enemy_states[0].item_ids == ["3006"]
    assert snapshot.enemy_states[0].kills == 7


def test_unknown_champion_still_counts_visible_item_metadata():
    armor = item("armor", ["Armor"])
    profile = analyze_enemies(
        [EnemyState("not-in-catalog", ["armor", "unknown-item"])],
        lambda _: None,
        {"armor": armor}.get,
    )
    assert profile.enemies_visible == 1
    assert profile.enemies_analyzed == 0
    assert profile.visible_items == 2
    assert profile.armor_items == 1
    assert profile.unknown_items == 1
    assert profile.confidence == "low"


def test_partial_enemy_catalog_cannot_report_high_confidence():
    known = champion("known", "mage", ap=0.8)
    item_db = {"armor": item("armor", ["Armor"])}
    players = [EnemyState("known", ["armor"]) for _ in range(4)]
    players.append(EnemyState("missing", ["armor"]))
    partial = analyze_enemies(players, {"known": known}.get, item_db.get)
    assert partial.enemies_analyzed == 4
    assert partial.visible_items == 5
    assert partial.confidence == "medium"
    assert "Partial enemy coverage" in " ".join(partial.notes())

    complete = analyze_enemies(
        [EnemyState("known", ["armor"]) for _ in range(5)],
        {"known": known}.get, item_db.get,
    )
    assert complete.confidence == "high"
