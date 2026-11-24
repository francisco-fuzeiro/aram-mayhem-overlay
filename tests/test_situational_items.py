"""Research 24/11 situational item rules (thresholds are proposals)."""
from __future__ import annotations

from types import SimpleNamespace as NS

from backend.api import server
from backend.engine import situational_items as si
from backend.models import EnemyState


def champ(cid, name, role, ap=0.0, ad=0.0):
    return NS(id=cid, name=name, role=role, stats=NS(ap=ap, ad=ad, heal_power=0, shield=0))


def item(iid, name, tags=(), cost=3000):
    return NS(id=iid, name=name, tags=list(tags), cost=cost, final=True, boots=False,
              properties=frozenset({"anti_heal"} if name in (
                  "Morellonomicon", "Mortal Reminder", "Thornmail",
                  "Chempunk Chainsword") else ()),
              stats=NS(ap=0, ad=0, crit=0, lethality=0, attack_speed=0, heal_power=0))


CHAMPS = {c.id: c for c in (
    champ("soraka", "Soraka", "support", ap=0.6), champ("vlad", "Vladimir", "mage", ap=0.9),
    champ("aatrox", "Aatrox", "fighter", ad=0.8), champ("malz", "Malzahar", "mage", ap=0.9),
    champ("zed", "Zed", "assassin", ad=0.9), champ("lux", "Lux", "mage", ap=0.9),
    champ("jinx", "Jinx", "marksman", ad=0.9), champ("annie", "Annie", "mage", ap=0.9),
    champ("garen", "Garen", "fighter", ad=0.7), champ("mundo", "Dr. Mundo", "tank", ad=0.4),
)}
ITEMS = {i.id: i for i in (
    item("morello", "Morellonomicon", ["SpellDamage"]), item("mortal", "Mortal Reminder", ["Damage"]),
    item("thorn", "Thornmail", ["Armor"]), item("chem", "Chempunk Chainsword", ["Damage"]),
    item("qss", "Quicksilver Sash", ["SpellBlock"]), item("merc", "Mercurial Scimitar", ["Damage"]),
    item("zhonya", "Zhonya's Hourglass", ["SpellDamage", "Armor"]),
    item("banshee", "Banshee's Veil", ["SpellDamage", "SpellBlock"]),
    item("visage", "Spirit Visage", ["SpellBlock"]), item("fon", "Force of Nature", ["SpellBlock"]),
    item("void", "Void Staff", ["SpellDamage"]), item("bork", "Blade of The Ruined King", ["Damage"]),
    item("shieldbow", "Immortal Shieldbow", ["Damage"]),
)}


def facts(own, enemies, augments=(), owned=(), kind=None, profile=None):
    states = [EnemyState(cid, [], kills, deaths) for cid, kills, deaths in enemies]
    return si.gather_facts(CHAMPS.get(own), states, profile or {}, [ITEMS[i] for i in owned],
                           augments, CHAMPS.get, ITEMS.get, own_kind=kind)


def rules(f):
    return [r.rule for r in si.fire_rules(f)]


def test_heavy_healing_fires_urgent_gw_per_class():
    f = facts("lux", [("soraka", 0, 0), ("vlad", 0, 0), ("aatrox", 0, 0)], kind="ap")
    assert f.heal_score >= si.THRESHOLDS["heal_score_urgent"]
    out = si.suggestions(f, ITEMS.values(), set(), lambda _i: True)
    assert out[0]["id"] == "morello" and out[0]["urgent"] and out[0]["rule"] == "GW2"


def test_gw_never_twice_and_grievous_venom_suppresses_it():
    heal = [("soraka", 0, 0), ("vlad", 0, 0)]
    assert "GW1" not in rules(facts("lux", heal, owned=("morello",), kind="ap"))
    assert not {"GW1", "GW2"} & set(rules(facts("lux", heal, augments=("Grievous Venom",))))


def test_suppression_asks_a_cleanse_for_carries():
    out = si.suggestions(facts("jinx", [("malz", 0, 0)], kind="ad"),
                         ITEMS.values(), set(), lambda _i: True)
    assert out[0]["id"] == "merc" and out[0]["rule"] == "CC1"
    assert "CC1" not in rules(facts("jinx", [("malz", 0, 0)], augments=("Fallen Aegis",)))


def test_magic_heavy_team_gives_mr_by_role():
    mages = [("lux", 0, 0), ("annie", 0, 0), ("malz", 0, 0)]
    assert "MR1" in rules(facts("aatrox", mages, kind="ad"))   # fighter that heals
    assert rules(facts("mundo", mages)) == ["MR1"]              # tank that heals: Visage
    CHAMPS["leona"] = champ("leona", "Leona", "tank", ad=0.3)
    assert "MR2" in rules(facts("leona", mages))                # tank without healing
    assert "MR3" in rules(facts("garen", mages, kind="ad"))


def test_fed_assassin_is_urgent_and_capped_at_two_situational():
    f = facts("lux", [("zed", 8, 1), ("soraka", 0, 0), ("vlad", 0, 0)], kind="ap")
    out = si.suggestions(f, ITEMS.values(), set(), lambda _i: True)
    assert len(out) == si.THRESHOLDS["max_situational"]
    assert {o["rule"] for o in out} == {"GW1", "BU1"} and all(o["urgent"] for o in out if o["rule"] == "BU1")


def test_no_enemy_data_means_no_rules():
    assert si.fire_rules(si.Facts()) == []


def test_unavailable_items_are_never_suggested():
    f = facts("lux", [("soraka", 0, 0), ("vlad", 0, 0), ("aatrox", 0, 0)], kind="ap")
    pool = [i for i in ITEMS.values() if i.id != "morello"]
    assert all(o["id"] != "morello" for o in si.suggestions(f, pool, set(), lambda _i: True))


def test_urgent_alternative_replaces_next_with_reason():
    sd = NS(get_item=lambda i: NS(id=i, name=i.upper(), boots=False, cost=3000),
            canonical_item_id=str)
    mayhem = {"adapted": [{"id": "a"}, {"id": "b"}], "boots": None,
              "alternatives": [{"id": "morello", "urgent": True,
                                "reason": "heavy enemy healing"}]}
    out = server._align_next_with_mayhem_build(
        {"next_item_id": "a", "purchased_items": []}, mayhem, 0, sd)
    assert out["next_item_id"] == "morello" and out["next_reason"] == "heavy enemy healing"
    mayhem["alternatives"][0]["urgent"] = False
    out = server._align_next_with_mayhem_build(
        {"next_item_id": "x", "purchased_items": []}, mayhem, 0, sd)
    assert out["next_item_id"] == "a"


def test_server_wiring_uses_visible_enemies_and_fails_closed():
    sd = NS(get_item=ITEMS.get, get_champion=CHAMPS.get,
            recommendable_items=lambda: list(ITEMS.values()),
            get_augment=lambda _a: None)
    states = [EnemyState("soraka"), EnemyState("vlad"), EnemyState("aatrox")]
    out = server._situational_alternatives(
        CHAMPS["lux"], [], [], ["void"], {}, states, "ap", lambda a, b: False, sd)
    assert out and out[0]["id"] == "morello"
    assert server._situational_alternatives(
        CHAMPS["lux"], [], [], [], {}, None, "ap", lambda a, b: False, sd) == []
    broken = NS(**{**vars(sd), "get_champion": lambda _c: 1 / 0})
    assert server._situational_alternatives(
        CHAMPS["lux"], [], [], [], {}, states, "ap", lambda a, b: False, broken) == []
