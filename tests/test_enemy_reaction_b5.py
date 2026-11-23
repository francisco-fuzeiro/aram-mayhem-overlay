"""B5: patch-derived visible-item properties and bounded enemy reaction."""

import copy
import json
from pathlib import Path

import pytest

from backend.engine.build_suggester import (
    ENEMY_REACTION_BONUS, ENEMY_REACTION_MAX, suggest_build,
)
from backend.engine.inventory import Inventory
from backend.engine.team_context import EnemyThreatProfile, analyze_enemies
from backend.models import ChampionMeta, EnemyState, ItemData, StatVector
from backend.static_data.item_policy import item_properties
from backend.static_data.loader import (
    _ITEM_CACHE_SCHEMA, _encode_item_cache, _parse_item_cache,
    _verified_cached_items,
)
from backend.static_data.item_policy import ItemPoolMeta
from backend.static_data.loader import ItemCatalog


FIXTURES = Path(__file__).parent / "fixtures" / "items"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def champion(name, role="fighter", **stats):
    return ChampionMeta(id=name, name=name, role=role, stats=StatVector(**stats))


def item(ident, properties=(), **stats):
    return ItemData(
        id=ident, name=f"Item {ident}", cost=3000,
        stats=StatVector(**stats), item_class="final",
        properties=frozenset(properties),
    )


def enemy_profile(enemy_items, *, role="fighter"):
    enemy = champion("opponent", role, ad=0.45, hp=0.1)
    return analyze_enemies(
        [EnemyState("opponent", list(enemy_items))],
        {enemy.id: enemy}.get,
        {
            "heal": item("heal", {"lifesteal"}),
            "armor": item("armor", {"armor"}),
            "mr": item("mr", {"magic_resist"}),
            "shield": item("shield", {"shield"}),
            "tenacity": item("tenacity", {"tenacity"}),
        }.get,
    )


def test_all_181_item_properties_match_versioned_fixture():
    expected = fixture("expected_item_properties_16.23.1.json")
    details = fixture("ddragon_items_16.23.1_details.json")["items"]
    pool = set(fixture("expected_item_pool_16.23.1.json")["pool_ids"])
    assert len(pool) == 181
    assert set(details) >= pool

    # The archived compact/details fixtures preserve numeric stats and
    # named passives, not raw full DD descriptions. Build deterministic
    # description inputs from the fixture's expected textual properties;
    # independently test HTML stripping and word boundaries below.
    text_labels = {
        "omnivamp": "Omnivamp", "anti_heal": "Grievous Wounds",
        "armor_pen": "Armor Penetration", "magic_pen": "Magic Penetration",
        "tenacity": "Tenacity", "shield": "Shield", "cleanse": "Quicksilver",
    }
    numeric_labels = {"armor", "magic_resist", "health", "lifesteal"}
    actual_by_property = {prop: set() for prop in expected["properties"]}
    for ident in sorted(pool):
        descriptions = [
            f"<main>{text_labels[prop]}</main>"
            for prop in text_labels if ident in expected["properties"][prop]
        ]
        dd = {
            "stats": details[ident]["stats"],
            "description": "<br/>".join(descriptions),
        }
        actual = item_properties(dd)
        assert isinstance(actual, frozenset)
        for prop in actual:
            actual_by_property[prop].add(ident)
        for prop in numeric_labels:
            assert (prop in actual) == (ident in expected["properties"][prop])
    assert actual_by_property == {
        prop: set(ids) for prop, ids in expected["properties"].items()
    }
    assert set(expected["properties"]["anti_heal"]) == {
        "3033", "3075", "3076", "3123", "3165", "3916", "6609",
    }


@pytest.mark.parametrize("description,expected", [
    ("<span class='Wounds Shield'>plain text</span>", frozenset()),
    ("<main>Grievous <b>Wounds</b></main>", frozenset({"anti_heal"})),
    ("No Woundsmith here", frozenset()),
    ("<stats>10 Armor Penetration</stats><br/>Quicksilver",
     frozenset({"armor_pen", "cleanse"})),
    ("<main>Magic Penetration</main> and <i>Omnivamp</i>",
     frozenset({"magic_pen", "omnivamp"})),
    ("Shield &amp; Tenacity", frozenset({"shield", "tenacity"})),
    ("Omnivamp and Grievous&nbsp;Wounds", frozenset({"omnivamp", "anti_heal"})),
])
def test_text_classifier_strips_html_and_uses_complete_wounds_word(description, expected):
    assert item_properties({"stats": {}, "description": description}) == expected


def test_verified_properties_persist_and_old_cache_cannot_be_reused(tmp_path):
    assert _ITEM_CACHE_SCHEMA == 5  # B3 already consumed schema 4.
    meta = ItemPoolMeta(
        policy_version="item_pool_v5", ddragon_version="16.23.1",
        cdragon_patch="16.23.8406595+branch.test",
        cdragon_sha256="a" * 64, cdragon_fetched_at="2026-11-20T00:00:00Z",
        overrides_version="2026-11-20.1", availability="verified_two_source",
    )
    original = item("3072", {"lifesteal", "shield"}, ad=0.7)
    catalog = ItemCatalog(
        {"3072": original}, meta, {"3072": "final"}, "network",
        exclusive_item_groups={},
    )
    encoded = _encode_item_cache(catalog)
    assert encoded["schema"] == 5
    assert encoded["items"]["3072"]["properties"] == ["lifesteal", "shield"]
    parsed = _parse_item_cache(encoded["items"])
    assert parsed["3072"].properties == original.properties
    path = tmp_path / "items_v5_16.23.1.json"
    path.write_text(json.dumps(encoded), encoding="utf-8")
    assert _verified_cached_items(path, "16.23.1", meta.overrides_version)["3072"].properties == original.properties
    prior_policy = copy.deepcopy(encoded)
    prior_policy["meta"]["policy_version"] = "item_pool_v3"
    path.write_text(json.dumps(prior_policy), encoding="utf-8")
    assert _verified_cached_items(path, "16.23.1", meta.overrides_version) is None
    old = copy.deepcopy(encoded)
    old["schema"] = 4
    path.write_text(json.dumps(old), encoding="utf-8")
    assert _verified_cached_items(path, "16.23.1", meta.overrides_version) is None
    stale = copy.deepcopy(encoded)
    del stale["items"]["3072"]["properties"]
    path.write_text(json.dumps(stale), encoding="utf-8")
    assert _verified_cached_items(path, "16.23.1", meta.overrides_version) is None


def test_visible_properties_replace_tags_without_guessing():
    player = champion("visible", "fighter", heal_power=0.0)
    seen = [
        EnemyState("visible", ["heal", "heal", "heal", "armor", "mr", "shield", "tenacity", "unknown"]),
    ]
    known = {
        "heal": item("heal", {"lifesteal"}, ad=0.4),
        "armor": item("armor", {"armor"}),
        "mr": item("mr", {"magic_resist"}),
        "shield": item("shield", {"shield"}),
        "tenacity": item("tenacity", {"tenacity"}),
    }
    threat = analyze_enemies(seen, {"visible": player}.get, known.get)
    assert threat.healing_items == 3
    assert threat.armor_items == threat.magic_resist_items == 1
    assert threat.shield_items == threat.tenacity_items == 1
    assert threat.visible_items == 8
    assert threat.unknown_items == 1
    assert threat.sustain_pressure == pytest.approx(0.15)
    # Enemy item class/role is never inferred from unrelated DD tags.
    fake_tags = item("fake", ad=0.5)
    fake_tags.tags = ["Armor", "LifeSteal", "SpellBlock"]
    no_guess = analyze_enemies(
        [EnemyState("visible", ["fake"])], {"visible": player}.get,
        {"fake": fake_tags}.get,
    )
    assert no_guess.armor_items == no_guess.magic_resist_items == no_guess.healing_items == 0


@pytest.mark.parametrize("style,role,stats,counter_id,counter_properties", [
    ("Damage", "fighter", {"ad": 0.9}, "3033", {"anti_heal", "armor_pen"}),
    ("Damage", "mage", {"ap": 0.9}, "3165", {"anti_heal"}),
    ("Survival", "fighter", {"hp": 0.9}, "3075", {"anti_heal", "armor"}),
])
def test_three_lifesteal_items_promote_role_specific_anti_heal(
    style, role, stats, counter_id, counter_properties,
):
    player = champion("player", role, **stats)
    common_stats = {"ap": 0.8} if role == "mage" else (
        {"hp": 0.8} if style == "Survival" else {"ad": 0.8}
    )
    candidates = [
        item("1000", **common_stats),
        item(counter_id, counter_properties, **common_stats),
    ]
    normal = suggest_build(player, [], [], 0, candidates, build_size=1, build_style=style)
    threats = enemy_profile(["heal"] * 3)
    reacted = suggest_build(
        player, [], [], 0, candidates, build_size=1,
        build_style=style, enemy_profile=threats,
    )
    assert threats.healing_items == 3
    assert counter_id not in normal.full_build
    assert reacted.full_build == [counter_id]
    assert reacted.next_item_id == counter_id
    assert reacted.alternatives == {}


@pytest.mark.parametrize("style,role,stats,counter_id", [
    ("Damage", "fighter", {"ad": 0.9}, "3033"),
    ("Damage", "mage", {"ap": 0.9}, "3165"),
    ("Survival", "fighter", {"hp": 0.9}, "3075"),
])
def test_without_enemy_healing_anti_heal_does_not_increase(style, role, stats, counter_id):
    stat = "ap" if role == "mage" else ("hp" if style == "Survival" else "ad")
    options = [item("1000", **{stat: 0.8}),
               item(counter_id, {"anti_heal"}, **{stat: 0.8})]
    no_enemy = suggest_build(
        champion("player", role, **stats), [], [], 0, options,
        build_size=1, build_style=style,
    )
    without_healing = suggest_build(
        champion("player", role, **stats), [], [], 0, options,
        build_size=1, build_style=style, enemy_profile=enemy_profile([]),
    )
    assert sum("anti_heal" in next(i for i in options if i.id == ident).properties
               for ident in without_healing.full_build) <= sum(
        "anti_heal" in next(i for i in options if i.id == ident).properties
        for ident in no_enemy.full_build
    )


def test_four_visible_armor_items_promote_physical_penetration():
    options = [item("1000", ad=0.8), item("3035", {"armor_pen"}, ad=0.8)]
    me = champion("player", "fighter", ad=0.9)
    assert suggest_build(me, [], [], 0, options, build_size=1,
                         build_style="Damage").full_build == ["1000"]
    threat = enemy_profile(["armor"] * 4)
    assert threat.armor_items == 4
    assert suggest_build(
        me, [], [], 0, options, build_size=1, build_style="Damage",
        enemy_profile=threat,
    ).full_build == ["3035"]


def test_three_visible_mr_items_change_ap_build_between_ticks():
    options = [item("1000", ap=0.8), item("3135", {"magic_pen"}, ap=0.8)]
    me = champion("player", "mage", ap=0.9)
    first = suggest_build(
        me, [], [], 0, options, build_size=1, build_style="Damage",
        enemy_profile=enemy_profile([]),
    )
    second = suggest_build(
        me, [], [], 0, options, build_size=1, build_style="Damage",
        enemy_profile=enemy_profile(["mr"] * 3),
    )
    assert first.full_build == ["1000"]
    assert second.full_build == ["3135"]
    assert first.next_item_id == "1000"
    assert second.next_item_id == "3135"
    assert second.alternatives == {}


def test_unanalyzed_opponents_do_not_add_a_bonus():
    options = [item("1000", ad=0.8), item("3035", {"armor_pen"}, ad=0.8)]
    me = champion("player", "fighter", ad=0.9)
    unanalyzed = EnemyThreatProfile(
        enemies_visible=5, enemies_analyzed=0, armor_items=5,
        magic_resist_items=5, healing_items=5, tanks=3,
    )
    no_profile = suggest_build(me, [], [], 0, options, build_size=1)
    with_unknown = suggest_build(
        me, [], [], 0, options, build_size=1, enemy_profile=unanalyzed,
    )
    assert with_unknown.full_build == no_profile.full_build
    assert with_unknown.next_item_id == no_profile.next_item_id
    assert with_unknown.alternatives == no_profile.alternatives == {}


def test_bounded_reaction_thresholds_final_only_and_determinism():
    from backend.engine.build_suggester import _enemy_reaction_bonus
    assert ENEMY_REACTION_BONUS == 0.15
    assert ENEMY_REACTION_MAX == 0.30
    enemy = EnemyThreatProfile(
        enemies_analyzed=5, healing_items=3, armor_items=4, tanks=2,
        physical_pressure=0.75, magic_pressure=0.7,
        cc_pressure=0.8, burst_pressure=0.8,
    )
    me = champion("player", "fighter", ad=0.9)
    many = item("3033", {"anti_heal", "armor_pen", "armor", "health", "tenacity"}, ad=0.8)
    assert _enemy_reaction_bonus(many, me, enemy) == pytest.approx(0.30)
    component = copy.copy(many)
    component.item_class = "component"
    assert _enemy_reaction_bonus(component, me, enemy) == 0
    assert _enemy_reaction_bonus(many, me, None) == 0
    assert _enemy_reaction_bonus(many, me, EnemyThreatProfile()) == 0
    options = [item("1000", ad=0.8), many]
    first = suggest_build(me, [], [], 0, options, build_size=1, enemy_profile=enemy)
    second = suggest_build(me, [], [], 0, list(reversed(options)), build_size=1, enemy_profile=enemy)
    assert first.full_build == second.full_build
    assert first.next_item_id == second.next_item_id


def test_owned_final_is_first_and_next_purchase_remains_first_unowned():
    owned = item("owned", ad=0.7)
    options = [owned, item("1000", ad=0.8), item("3035", {"armor_pen"}, ad=0.8)]
    me = champion("player", "fighter", ad=0.9)
    inventory = Inventory(finals=("owned",), components=(), other=())
    result = suggest_build(
        me, [], ["owned"], 0, options, build_size=3,
        build_style="Damage", inventory=inventory,
        enemy_profile=enemy_profile(["armor"] * 4),
    )
    assert result.full_build[0] == "owned"
    assert result.next_item_id == next(
        (ident for ident in result.full_build if ident not in inventory.finals), None,
    )
    assert result.alternatives == {}


def test_pipeline_reacts_to_visible_items_and_preserves_serialized_b4_payload(monkeypatch):
    from backend.api.server import _serialize_result
    from backend.models import GamePhase, GameSnapshot
    from backend.static_data.loader import StaticData
    from backend.workflow import pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "get_all_personal_winrates", lambda _: {})
    me = champion("player", "mage", ap=0.9)
    opponent = champion("opponent", "fighter", ad=0.4)
    options = [item("1000", ap=0.8), item("3135", {"magic_pen"}, ap=0.8)]
    data = StaticData()
    data._champions = {me.id: me, opponent.id: opponent}
    data._items = {i.id: i for i in options}
    data._items["mr"] = item("mr", {"magic_resist"})

    def run(visible):
        state = GameSnapshot(
            game_id="b5-live-ticks", phase=GamePhase.IN_GAME,
            champion_id=me.id, augment_choices=[], chosen_augments=[],
            purchased_items=[], current_gold=2500, game_time=300,
            enemy_champion_ids=[opponent.id],
            enemy_states=[EnemyState(opponent.id, visible)],
            build_style="Damage",
        )
        return pipeline_module.Pipeline(data).run(state)

    tick1 = run([])
    tick2 = run(["mr"] * 3)
    assert tick1 is not None and tick2 is not None
    assert tick1.build_state.full_build[0] == "1000"
    assert tick2.build_state.full_build[0] == "3135"
    assert tick2.enemy_analysis["magic_resist_items"] == 3
    assert tick2.build_state.next_item_id == tick2.build_state.full_build[0]
    serialized = _serialize_result(tick2, data)
    assert serialized["build_state"]["alternatives"] == {}
    assert serialized["enemy_analysis"]["magic_resist_items"] == 3


def test_two_source_loader_computes_properties_from_raw_dd_and_persists_them(tmp_path):
    """Exercise the production DD extraction path, not only a direct cache."""
    from backend.static_data.loader import _assemble_item_catalog

    meta = ItemPoolMeta(
        policy_version="item_pool_v5", ddragon_version="16.23.1",
        cdragon_patch="16.23.8406595+branch.test",
        cdragon_sha256="b" * 64, cdragon_fetched_at="2026-11-20T00:00:00Z",
        overrides_version="2026-11-20.1", availability="verified_two_source",
    )
    dd = {"3072": {
        "name": "Synthetic Bloodthirster", "maps": {"12": True},
        "gold": {"purchasable": True, "total": 3400},
        "from": [], "into": [], "tags": ["Damage"],
        "stats": {"PercentLifeStealMod": 0.15},
        "description": "<main>Gain a <b>Shield</b> on damage</main>",
    }}
    cd = {"3072": {
        "inStore": True, "displayInItemSets": True,
        "priceTotal": 3400, "from": [], "to": [],
        "requiredBuffCurrencyName": "", "requiredBuffCurrencyCost": 0,
    }}
    source = _assemble_item_catalog(dd, cd, {"force_class": {}}, meta, "network")
    assert source["3072"].item_class == "final"
    assert source["3072"].properties == frozenset({"lifesteal", "shield"})
    payload = _encode_item_cache(source)
    assert payload["items"]["3072"]["properties"] == ["lifesteal", "shield"]
    path = tmp_path / "items_v5_16.23.1.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    restored = _verified_cached_items(path, "16.23.1", meta.overrides_version)
    assert restored is not None
    assert restored["3072"].properties == source["3072"].properties
