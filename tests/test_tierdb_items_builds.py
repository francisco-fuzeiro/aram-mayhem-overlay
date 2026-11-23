"""I2-I4: item tiers, reference build, heuristic Stat Anvils, in-match adaptation."""
import json

import pytest

from backend.tierdb.anvil_stats import (
    ANVIL_STATS, anvil_stat_for_kind, rank_anvil_options, stat_demand,
)
from backend.tierdb.build_adapt import AdaptConfig, adapt_build
from backend.tierdb.item_tiers import ItemTierConfig, build_item_tiers, reference_build

CFG = ItemTierConfig(draws=200)


def _champ(n_items=12, base=(5000, 10000)):
    finals = {}
    for i in range(n_items):
        iid = str(3000 + i)
        finals[iid] = (int(1000 * (0.44 + 0.01 * i)), 1000)
    return {"base": base, "finals": finals,
            "boots": {"3020": (520, 1000), "3047": (480, 1000)},
            "boots_base": base,
            "cores": [(("3011", "3010", "3009"), 600, 1000, 0.30),
                      (("3000", "3001", "3002"), 450, 1000, 0.10)]}


def _rows(data=None, **kw):
    data = data or {"ahri": _champ(), "garen": _champ()}
    return build_item_tiers(data, CFG, **kw)


def test_weights_are_the_decided_ones():
    assert CFG.weights == {"win": 50, "core": 30, "fit": 20}
    assert AdaptConfig().max_swaps == 3 and AdaptConfig().threshold == 0.5


def test_higher_delta_ranks_higher_and_every_item_ranked_once():
    rows = [r for r in _rows() if r.champion_id == "ahri" and r.kind == "final"]
    ranks = {r.item_id: r.rank for r in rows}
    assert sorted(ranks.values()) == list(range(1, len(rows) + 1))
    assert ranks["3011"] < ranks["3000"]
    assert {r.level for r in rows} == {"champion"}


def test_small_share_items_fall_back_to_heuristic_and_are_capped():
    data = {"ahri": _champ()}
    data["ahri"]["finals"]["4999"] = (10, 10)  # 100 % WR on 10 games
    rows = {r.item_id: r for r in _rows(data, fit={("ahri", "4999"): 1.0})}
    assert rows["4999"].level == "heuristic"
    assert rows["4999"].tier not in {"OP", "S"}


def test_eligibility_filters_and_canonicalises():
    data = {"ahri": _champ()}
    canon = {"223011": "3011"}
    data["ahri"]["finals"]["223011"] = (300, 500)
    eligible = {str(3000 + i) for i in range(12)} - {"3005"}
    rows = [r for r in _rows(data, eligible=eligible, canonical=lambda x: canon.get(x, x))
            if r.kind == "final"]
    ids = [r.item_id for r in rows]
    assert "3005" not in ids and "223011" not in ids and ids.count("3011") == 1


def test_eligible_items_without_data_are_still_listed_as_heuristic():
    eligible = {str(3000 + i) for i in range(12)} | {"6655"}
    rows = {r.item_id: r for r in _rows({"ahri": _champ()}, eligible=eligible,
                                        fit={("ahri", "6655"): 0.9}) if r.kind == "final"}
    assert rows["6655"].level == "heuristic" and rows["6655"].rank is not None


def test_boots_are_a_separate_list():
    boots = [r for r in _rows() if r.champion_id == "ahri" and r.kind == "boots"]
    assert [r.item_id for r in sorted(boots, key=lambda r: r.rank)] == ["3020", "3047"]


def test_deterministic():
    assert _rows() == _rows()


def test_reference_build_uses_measured_core_then_tiers():
    data = {"ahri": _champ()}
    rows = _rows(data)
    ref = reference_build("ahri", data["ahri"]["cores"], rows)
    assert ref.items[:3] == ("3011", "3010", "3009")  # best shrunk core, pick >= 5 %
    assert len(ref.items) == 6 and len(set(ref.items)) == 6
    assert ref.sources[:3] == ("core",) * 3 and set(ref.sources[3:]) == {"tier"}
    assert ref.boots == "3020"


def test_reference_build_without_core_uses_tiers():
    data = {"ahri": dict(_champ(), cores=[])}
    rows = _rows(data)
    ref = reference_build("ahri", [], rows)
    assert ref.sources == ("tier",) * 6


def test_reference_build_respects_conflicts():
    data = {"ahri": _champ()}
    rows = _rows(data)
    ref = reference_build("ahri", data["ahri"]["cores"], rows,
                          conflicts=lambda a, b: {a, b} == {"3011", "3010"})
    assert not {"3011", "3010"} <= set(ref.items)


# -- Stat Anvils (heuristic, owner decision 23/11) ------------------------------

def test_anvil_stat_space_covers_the_missing_dimensions():
    assert {"armor", "mr", "ms", "tenacity", "omnivamp", "ah", "mpen"} <= set(ANVIL_STATS)
    assert anvil_stat_for_kind("FlatArmor") == "armor"
    assert anvil_stat_for_kind("MagicResist") == "mr"
    assert anvil_stat_for_kind("PercentAttackSpeed") == "as"
    assert anvil_stat_for_kind("MoveSpeed") == "ms"
    assert anvil_stat_for_kind("Armor+MagicResist") is None  # multi-stat: abstain
    assert anvil_stat_for_kind("SomethingNew") is None


def test_stat_demand_comes_from_measured_build_types_then_role():
    types = {"3089": ("SpellDamage",), "4645": ("SpellDamage", "MagicPenetration"),
             "3157": ("SpellDamage", "Armor")}
    demand = stat_demand("mage", top_items=["3089", "4645", "3157"], item_types=types)
    assert max(demand, key=demand.get) == "ap"
    assert demand["mpen"] > demand["ad"]
    fallback = stat_demand("marksman", top_items=[], item_types={})
    assert fallback["as"] > fallback["ap"]
    assert abs(sum(demand.values()) - 1) < 1e-9


def _shards(*kinds, tier="gold"):
    return [{"id": f"s{i}", "kind": k, "tier": tier, "values": (10.0,)} for i, k in enumerate(kinds)]


def test_anvil_options_follow_champion_demand_and_are_estimates():
    demand = stat_demand("mage", top_items=["3089"], item_types={"3089": ("SpellDamage",)})
    out = rank_anvil_options(_shards("AbilityPower", "AttackDamage", "Armor"), demand)
    assert out[0]["id"] == "s0" and out[0]["stat"] == "ap"
    assert all(r["level"] == "estimate" for r in out)
    assert all(r["tier"] not in {"OP", "S"} for r in out)
    assert [r["rank"] for r in out] == [1, 2, 3]
    assert not set().union(*out) & {"win_rate", "wins", "games"}


def test_anvil_context_prefers_resist_against_damage_type_and_augments():
    demand = stat_demand("tank", top_items=[], item_types={})
    vs_magic = rank_anvil_options(_shards("Armor", "MagicResist", "Health"), demand,
                                  enemy={"magic_pressure": 0.8, "physical_pressure": 0.2})
    assert vs_magic[0]["stat"] == "mr" and "magic damage" in vs_magic[0]["reason"]
    vs_phys = rank_anvil_options(_shards("Armor", "MagicResist", "Health"), demand,
                                 enemy={"magic_pressure": 0.2, "physical_pressure": 0.8})
    assert vs_phys[0]["stat"] == "armor"
    boosted = rank_anvil_options(_shards("AttackSpeed", "AbilityHaste"),
                                 stat_demand("fighter", top_items=[], item_types={}),
                                 augment_stats={"as": 1.0})
    assert boosted[0]["stat"] == "as" and "augment" in boosted[0]["reason"]


def test_unknown_anvil_kind_is_unmodelled_not_scored():
    out = rank_anvil_options(_shards("AbilityPower", "Weird"), stat_demand("mage", [], {}))
    weird = [r for r in out if r["id"] == "s1"][0]
    assert weird["tier"] is None and weird["rank"] is None and weird["level"] == "unmodelled"


# -- In-match adaptation (owner decision 23/11: max 3 swaps, threshold 0.5) -------------

def _strength(ids):
    return {i: 10.0 - n for n, i in enumerate(ids)}


def test_no_context_keeps_reference():
    ref = ["a", "b", "c", "d", "e", "f"]
    out = adapt_build(ref, _strength(ref + ["x", "y"]), context=lambda i: (0.0, None))
    assert out.items == tuple(ref) and out.swaps == ()


def test_swaps_are_capped_at_three_and_slot_one_is_locked():
    ref = ["a", "b", "c", "d", "e", "f"]
    strength = _strength(ref + ["w", "x", "y", "z"])
    boost = {"w": 9, "x": 9, "y": 9, "z": 9, "a": -9}
    out = adapt_build(ref, strength, context=lambda i: (boost.get(i, 0.0), "enemies heal")
                      if i in boost else (0.0, None))
    assert out.items[0] == "a"
    assert len(out.swaps) == 3
    assert all(s["reason"] == "enemies heal" for s in out.swaps)


def test_small_gains_below_threshold_do_not_swap():
    ref = ["a", "b", "c", "d", "e", "f"]
    strength = {**_strength(ref), "x": 5.0}  # f = 5.0
    out = adapt_build(ref, strength, context=lambda i: (0.4, "minor") if i == "x" else (0.0, None))
    assert out.swaps == ()


def test_owned_items_are_never_swapped_and_conflicts_respected():
    ref = ["a", "b", "c", "d", "e", "f"]
    strength = {**_strength(ref), "x": 9.0}
    out = adapt_build(ref, strength, owned={"f", "e", "d", "c", "b"},
                      context=lambda i: (5.0, "r") if i == "x" else (0.0, None))
    assert out.swaps == ()
    out = adapt_build(ref, strength, conflicts=lambda a, b: {a, b} == {"x", "b"},
                      context=lambda i: (5.0, "r") if i == "x" else (0.0, None))
    assert out.swaps == () or out.swaps[0]["out"] == "b"


def test_stat_demand_counts_what_players_build_not_only_the_best_ranked():
    # Field test 23/11 (Master Yi): top-ranked items are crit/lethality, but
    # attack-speed items are in most builds; AS must not vanish from demand.
    types = {"ie": ("CriticalStrike", "Damage"), "ldr": ("Damage", "CriticalStrike"),
             "botrk": ("Damage", "AttackSpeed"), "guinsoo": ("AttackSpeed", "SpellDamage")}
    ranked_only = stat_demand("fighter", ["ie", "ldr"], types)
    blended = stat_demand("fighter", ["ie", "ldr"], types,
                          popular={"ie": 160000, "ldr": 90000, "botrk": 200000,
                                   "guinsoo": 65000})
    assert blended["as"] > 3 * ranked_only["as"]
    assert blended["crit"] > blended["mr"] and abs(sum(blended.values()) - 1) < 1e-9


def test_build_keeps_attack_speed_when_most_games_use_it():
    # Field test 23/11 (Master Yi): crit/lethality ranked top, the six slots had
    # no attack speed although most Yi games build it.
    from backend.tierdb.item_tiers import ItemTierRow, reference_build
    from backend.tierdb.pipeline import required_stats

    def row(iid, rank):
        return ItemTierRow(champion_id="yi", item_id=iid, kind="final", score=1.0,
                           score_p20=0.0, score_p80=1.0, rank=rank, tie_group=rank,
                           tier="A", level="champion", confidence=1.0)
    ranked = ["ldr", "ie", "sterak", "dd", "er", "terminus", "collector", "botrk"]
    rows = [row(i, n) for n, i in enumerate(ranked, start=1)]
    types = {"terminus": ("Damage", "AttackSpeed"), "botrk": ("Damage", "AttackSpeed"),
             "navori": ("AttackSpeed",), "guinsoo": ("AttackSpeed",), "kraken": ("AttackSpeed",),
             "ie": ("CriticalStrike",), "ldr": ("Damage",)}
    finals = {"botrk": (1, 200000), "navori": (1, 81000), "guinsoo": (1, 65000),
              "kraken": (1, 49000), "terminus": (1, 21000), "ie": (1, 160000)}
    req = required_stats(finals, 531000, types)
    assert set(req) == {"as"}
    cores = [(("collector", "ie", "ldr"), 55000, 94000, 0.06)]
    plain = reference_build("yi", cores, rows)
    assert not {"terminus", "botrk"} & set(plain.items)
    fixed = reference_build("yi", cores, rows, required=req)
    assert fixed.items[:3] == ("collector", "ie", "ldr")      # core untouched
    assert "terminus" in fixed.items and fixed.sources[fixed.items.index("terminus")] == "stat"
    assert len(fixed.items) == 6
    # A champion whose players rarely build attack speed gets no forced item.
    assert required_stats({"botrk": (1, 1000)}, 531000, types) == {}


def test_old_reference_build_table_is_migrated_to_allow_stat_slots(tmp_path):
    import sqlite3

    from backend.tierdb.store import SCHEMA, TierStore
    path = tmp_path / "old.sqlite"
    con = sqlite3.connect(path)
    con.executescript(SCHEMA.replace("'core', 'tier', 'stat', 'boots'", "'core', 'tier', 'boots'"))
    con.close()
    store = TierStore(path)
    sql = store.connection.execute(
        "SELECT sql FROM sqlite_master WHERE name='reference_build'").fetchone()[0]
    assert "'stat'" in sql
    store.close()


def test_spread_out_champion_still_gets_its_most_played_core():
    # Field test 23/11 (Kha'Zix): every core < 5 % pick, so the build used item
    # win rate alone and rushed Death's Dance instead of Hubris.
    from backend.tierdb.item_tiers import ItemTierRow, reference_build

    def row(iid, rank):
        return ItemTierRow(champion_id="kz", item_id=iid, kind="final", score=1.0,
                           score_p20=0.0, score_p80=1.0, rank=rank, tie_group=rank,
                           tier="A", level="champion", confidence=1.0)
    rows = [row(i, n) for n, i in enumerate(
        ["dd", "sterak", "youmuu", "hubris", "voltaic", "serylda", "collector"], start=1)]
    cores = [(("hubris", "voltaic", "serylda"), 22000, 42000, 0.023),
             (("hubris", "collector", "ie"), 20000, 40000, 0.022),
             (("rare", "x", "y"), 900, 1500, 0.001)]
    ref = reference_build("kz", cores, rows)
    assert ref.items[0] == "hubris" and ref.sources[:3] == ("core", "core", "core")
    assert ref.items[:3] == ("hubris", "voltaic", "serylda")
    # Without enough games, no fallback core: tiers only, as before.
    tiny = [(c, w, 100, p) for c, w, _g, p in cores]
    assert reference_build("kz", tiny, rows).items[0] == "dd"
