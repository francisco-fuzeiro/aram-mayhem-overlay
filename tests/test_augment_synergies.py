"""Research S1-S70 synergies: data rules now, curated lists only with history."""
import json
from types import SimpleNamespace

from backend.engine.augment_synergies import (
    BLOCK, SYNERGY_FILE, SynergyContext, SynergyTable, build_context, load_table,
)
from backend.models import CCAbility, CCProfile


def ctx(**kw):
    return SynergyContext(**kw)


def test_table_is_valid_and_marked_as_proposal():
    data = json.loads(SYNERGY_FILE.read_text(encoding="utf-8"))
    assert data["status"].startswith("Decidido")
    allowed = {1, -1, BLOCK}
    ids = [r["id"] for r in data["rules"]]
    assert len(ids) == len(set(ids)) and len(ids) >= 70
    for rule in data["rules"]:
        assert rule["effect"] in allowed and rule["confidence"] in {"certo", "provavel", "por_confirmar"}
        assert rule["augments"] and rule["reason"]
        # Curated champion lists are never "certo" (owner decision via coordinator 24/11),
        # unless the rule carries evidence checked against data (K rules, approved 25/11).
        conds = [rule.get("when") or {}] + rule.get("any_of", []) + rule.get("none_of", [])
        if any("champ" in c or "champ_not" in c or "allies_any" in c for c in conds):
            assert (rule["confidence"] in ("provavel", "por_confirmar")
                    or rule["id"] in {"S12", "S16"} or rule.get("evidence"))


def test_blocks_need_the_data_and_come_first():
    table = load_table()
    melee = ctx(champion_id="garen", role="fighter", attack_range=175.0)
    assert table.evaluate("Draw Your Sword", melee)[0] == BLOCK
    assert table.evaluate("Draw Your Sword", ctx(champion_id="x"))[0] == 0  # range unknown
    energy = ctx(champion_id="zed", resource="energy")
    assert table.evaluate("Overflow", energy)[:2] == (BLOCK, "needs mana")
    assert table.evaluate("Overflow", ctx(champion_id="ryze", resource="mana"))[0] == 0
    no_mark = ctx(spells=frozenset({"flash", "heal"}))
    assert table.evaluate("Snowball Upgrade", no_mark)[0] == BLOCK
    assert table.evaluate("Flashy", no_mark)[0] == 0
    assert table.evaluate("Snowball Upgrade", ctx(spells=frozenset({"mark", "flash"})))[0] == 0


def test_data_rules_apply_now():
    table = load_table()
    assert table.evaluate("Upgrade Collector", ctx(build_items=frozenset({"6676"})))[0] == 1
    assert table.evaluate("Upgrade Collector", ctx(build_items=frozenset({"3031"})))[0] == -1
    crit = ctx(role="fighter", build_tags={"CriticalStrike": 1})
    assert table.evaluate("It's Critical", crit)[0] == 1
    assert table.evaluate("Courage of the Colossus", ctx(hard_cc=2))[0] == 1
    assert table.evaluate("Courage of the Colossus", ctx(hard_cc=0))[0] == -1
    assert table.evaluate("Courage of the Colossus", ctx(hard_cc=1))[0] == 0
    assert table.evaluate("Frost Wraith", ctx(chosen=frozenset({"cruelty"})))[0] == 1
    # Lightning Strikes: +1 with two attack-speed augments, -1 otherwise.
    two = ctx(chosen=frozenset({"deft", "tapdancer"}))
    assert table.evaluate("Lightning Strikes", two)[0] == 1
    assert table.evaluate("Lightning Strikes", ctx())[0] == -1


def test_curated_lists_need_confirming_history():
    table = load_table()
    swain = ctx(champion_id="swain", role="mage")
    assert table.evaluate("Dawnbringer's Resolve", swain)[0] == 0                  # no history
    assert table.evaluate("Dawnbringer's Resolve", swain, (10, 20), 0.5)[0] == 0   # n < 30
    assert table.evaluate("Dawnbringer's Resolve", swain, (20, 30), 0.5)[0] == 1   # confirmed
    assert table.evaluate("Dawnbringer's Resolve", swain, (12, 30), 0.5)[0] == 0   # record disagrees


def test_cap_and_switches():
    table = load_table()
    both = ctx(role="marksman", build_tags={"CriticalStrike": 2})
    assert table.evaluate("It's Critical", both)[0] == 1   # several +1 still +1
    off = SynergyTable({"settings": {"enabled": False},
                        "rules": json.loads(SYNERGY_FILE.read_text())["rules"]})
    assert off.evaluate("Upgrade Collector", ctx(build_items=frozenset({"6676"})))[0] == 0
    no_hist = SynergyTable({"settings": {"provavel_needs_history": False},
                            "rules": json.loads(SYNERGY_FILE.read_text())["rules"]})
    assert no_hist.evaluate("Dawnbringer's Resolve", ctx(champion_id="swain"))[0] == 1


def test_build_context_reads_kit_items_and_live_data():
    champ = SimpleNamespace(role="mage", cc_profile=CCProfile(abilities=[
        CCAbility("a", "stun", True, 1.0, 10.0), CCAbility("b", "slow", False, 1.0, 5.0)]))
    items = {"3157": SimpleNamespace(tags=["SpellDamage", "Active"])}
    sd = SimpleNamespace(get_item=lambda i: items.get(i))
    c = build_context("annie", champ, ["3157", ""], ["Cruelty", None], sd=sd,
                      live_stats={"attackRange": 625.0}, spells=["Flash", "Mark"],
                      resource="MANA")
    assert c.hard_cc == 1 and c.attack_range == 625.0 and c.resource == "mana"
    assert c.spells == {"flash", "mark"} and c.build_tags == {"SpellDamage": 1, "Active": 1}
    assert c.chosen == {"cruelty"}


def test_live_client_spells_and_resource_are_parsed():
    from backend.collectors.lcda import parse_game_snapshot
    from backend.models import GamePhase
    raw = {"activePlayer": {"riotId": "a#1", "championStats": {"resourceType": "ENERGY",
                                                               "attackRange": 125.0}},
           "allPlayers": [{"riotId": "a#1", "championName": "Zed", "team": "ORDER",
                           "summonerSpells": {"summonerSpellOne": {"displayName": "Flash"},
                                              "summonerSpellTwo": {"displayName": "Mark"}}}],
           "gameData": {}}
    snap = parse_game_snapshot(raw, GamePhase.IN_GAME)
    assert snap.summoner_spells == ["Flash", "Mark"] and snap.resource_type == "ENERGY"
    assert snap.champion_stats["attackRange"] == 125.0


def test_offer_tiers_show_blocked_augment_as_e(monkeypatch):
    from backend.api import server
    monkeypatch.setattr(server.tier_service, "enabled", lambda: True)
    monkeypatch.setattr(server.tier_service.provider, "augment_tier",
                        lambda c, a: {"tier": "S", "rank": 8, "level": "champion"})
    out = server._augment_tier_payload("zed", ["1"], adjust=lambda a: (BLOCK, "needs mana"))
    t = out["augment_tiers"]["1"]
    assert t["adjusted_tier"] == "E" and t["adjust"] == -1 and t["adjust_reason"] == "needs mana"


def test_kit_only_rules_are_priors_skipped_with_champion_games():
    """Owner 25/11: champion/role rules are already inside the champion ΔWR."""
    table = load_table()
    rules = {r["id"]: r for r in json.loads(SYNERGY_FILE.read_text(encoding="utf-8"))["rules"]}
    assert SynergyTable.is_prior(rules["S41"]) and not SynergyTable.is_prior(rules["K1"])
    assert not SynergyTable.is_prior(rules["S21"])           # depends on chosen augments
    garen = ctx(champion_id="garen")
    assert table.evaluate("Spin To Win", garen, (20, 30), 0.5)[0] == 1
    assert table.evaluate("Spin To Win", garen, (20, 30), 0.5, champion_level=True)[0] == 0


def test_corrections_from_aramhex_are_applied():
    table = load_table()
    rules = {r["id"]: r for r in json.loads(SYNERGY_FILE.read_text(encoding="utf-8"))["rules"]}
    assert "Dashing" not in rules["S37"]["augments"]
    assert "Goredrink" not in rules["S23"]["augments"]
    assert rules["S43"]["confidence"] == "por_confirmar"
    assert "gwen" not in table.lists["SPIN"]
