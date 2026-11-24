"""F3/F4 augment tier list math (synthetic inputs only)."""
import pytest

from backend.tierdb.augment_tiers import (
    AugmentTierConfig,
    baseline_without,
    build_augment_tiers,
    combine_components,
)

CFG = AugmentTierConfig(draws=300)


def _by(rows, champion, augment):
    (row,) = [r for r in rows if r.champion_id == champion and r.augment_id == augment]
    return row


def _world(pairs, champions=None, rarity=None, roles=None, heuristic=None, cfg=CFG):
    champions = champions or {"ahri": (5000, 10000), "garen": (5000, 10000)}
    rarity = rarity or {aid: "gold" for (_, aid) in pairs}
    roles = roles or {c: "mage" for c in champions}
    return build_augment_tiers(champions, pairs, rarity, roles, heuristic or {}, cfg)


# -- F3: components and shrinkage -------------------------------------------

def test_missing_metric_weight_is_redistributed():
    w = CFG.weights
    assert combine_components({"win": 0.8}, w) == pytest.approx(8.0)
    both = combine_components({"win": 0.8, "combat": 0.2}, w)
    assert both == pytest.approx(10 * (50 * 0.8 + 15 * 0.2) / 65)


def test_without_win_component_level_is_unavailable():
    assert combine_components({"combat": 0.9}, CFG.weights) is None


def test_weights_are_the_decided_ones():
    assert CFG.weights == {"win": 50, "combat": 15, "participation": 12,
                           "duration": 8, "context": 8, "consistency": 7}


def test_baseline_excludes_the_augment_itself():
    # Champion 5000/10000; games with the augment 900/1000 -> others 4100/9000.
    assert baseline_without(5000, 10000, 900, 1000) == pytest.approx(4100 / 9000)


def test_three_wins_in_three_games_do_not_reach_the_top():
    pairs = {("ahri", "lucky"): (3, 3), ("ahri", "solid"): (1200, 2000),
             ("ahri", "meh"): (980, 2000), ("garen", "solid"): (1000, 2000)}
    rows, _ = _world(pairs)
    lucky, solid = _by(rows, "ahri", "lucky"), _by(rows, "ahri", "solid")
    assert solid.rank < lucky.rank
    assert lucky.level != "champion"


def test_more_games_with_same_rate_gives_more_confidence():
    pairs = {("ahri", "small"): (60, 100), ("ahri", "big"): (6000, 10000),
             ("garen", "x"): (500, 1000)}
    champions = {"ahri": (20000, 40000), "garen": (5000, 10000)}
    rows, _ = _world(pairs, champions=champions)
    small, big = _by(rows, "ahri", "small"), _by(rows, "ahri", "big")
    assert big.n_eff > small.n_eff
    assert big.score > small.score
    assert (big.score_p80 - big.score_p20) < (small.score_p80 - small.score_p20)


# -- F3: hierarchy fallback and caps ----------------------------------------

def test_pair_without_data_falls_back_to_role_level():
    champions = {"ahri": (5000, 10000), "lux": (50000, 100000), "garen": (5000, 10000)}
    roles = {"ahri": "mage", "lux": "mage", "garen": "fighter"}
    pairs = {("lux", "burn"): (6000, 10000), ("garen", "burn"): (500, 1000)}
    rows, _ = _world(pairs, champions=champions, roles=roles)
    row = _by(rows, "ahri", "burn")
    # Owner 24/11: no game on the champion -> borrowed score, always tier E.
    assert row.level == "borrowed"
    assert row.confidence == "low"
    assert row.tier == "E"


def test_augments_without_champion_games_rank_after_those_with_games():
    """OP.GG check 24/11: role/global fallbacks (Draw Your Sword on melee,
    Blue Barrier on manaless champions) were topping champion lists."""
    champions = {"rengar": (5000, 10000), "yi": (50000, 100000)}
    roles = {"rengar": "assassin", "yi": "assassin"}
    pairs = {("yi", "great"): (70000, 100000), ("rengar", "weak"): (900, 2000),
             ("yi", "weak"): (900, 2000)}
    rows, _ = _world(pairs, champions=champions, roles=roles)
    great, weak = _by(rows, "rengar", "great"), _by(rows, "rengar", "weak")
    assert great.level == "borrowed" and great.tier == "E"
    assert weak.rank < great.rank
    assert weak.rank_all < great.rank_all
    assert great.tie_group != weak.tie_group


def test_heuristic_only_without_games_is_borrowed_tier_e():
    rarity = {"curated": "gold", "other": "gold"}
    rows, _ = build_augment_tiers(
        {"ahri": (5000, 10000)}, {}, rarity, {"ahri": "mage"},
        {("ahri", "curated"): 10.0, ("ahri", "other"): 1.0}, CFG,
    )
    row = _by(rows, "ahri", "curated")
    # Owner 24/11: no game of the augment on the champion -> tier E, last.
    assert row.level == "borrowed"
    assert row.tier == "E"


def test_no_data_and_no_model_is_explicit_not_zero():
    rows, _ = build_augment_tiers(
        {"ahri": (5000, 10000)}, {}, {"ghost": "silver"}, {"ahri": "mage"}, {}, CFG,
    )
    row = _by(rows, "ahri", "ghost")
    assert row.level == "none"
    assert row.score is None and row.tier is None and row.rank is None


def test_op_requires_champion_level_and_lower_bound():
    champions = {"ahri": (50000, 100000), "garen": (50000, 100000)}
    pairs = {("ahri", f"a{i}"): (4900 + 5 * i, 10000) for i in range(40)}
    pairs[("ahri", "star")] = (7000, 10000)
    pairs.update({("garen", f"a{i}"): (4950 + 3 * i, 10000) for i in range(40)})
    rows, thresholds = _world(pairs, champions=champions)
    star = _by(rows, "ahri", "star")
    assert star.level == "champion"
    assert star.tier == "OP"
    # A role-level row never becomes OP even with a top score.
    assert all(r.tier != "OP" for r in rows if r.level != "champion")
    assert set(thresholds["gold"]) == {"OP", "S", "A", "B", "C", "D"}


# -- F4: rank, ties, coverage, determinism ----------------------------------

def test_every_catalog_augment_appears_once_per_champion_and_rarity():
    rarity = {"g1": "gold", "g2": "gold", "s1": "silver", "p1": "prismatic"}
    pairs = {("ahri", "g1"): (600, 1000), ("garen", "s1"): (500, 1000)}
    rows, _ = _world(pairs, rarity=rarity)
    for champion in ("ahri", "garen"):
        mine = [r for r in rows if r.champion_id == champion]
        assert sorted(r.augment_id for r in mine) == sorted(rarity)
        for r in mine:
            assert r.rarity == rarity[r.augment_id]


def test_ranks_are_strict_and_restart_per_rarity():
    rarity = {"g1": "gold", "g2": "gold", "g3": "gold", "s1": "silver", "s2": "silver"}
    pairs = {("ahri", a): (500 + 40 * i, 1000) for i, a in enumerate(sorted(rarity))}
    rows, _ = _world(pairs, rarity=rarity)
    for r_name, size in (("gold", 3), ("silver", 2)):
        ranks = sorted(r.rank for r in rows if r.champion_id == "ahri" and r.rarity == r_name)
        assert ranks == list(range(1, size + 1))


def test_statistically_indistinguishable_augments_share_a_tie_group():
    pairs = {("ahri", "twin1"): (520, 1000), ("ahri", "twin2"): (521, 1000),
             ("ahri", "far"): (9000, 10000), ("garen", "twin1"): (500, 1000)}
    rows, _ = _world(pairs, champions={"ahri": (50000, 100000), "garen": (5000, 10000)})
    t1, t2, far = (_by(rows, "ahri", a) for a in ("twin1", "twin2", "far"))
    assert t1.tie_group == t2.tie_group
    assert far.tie_group != t1.tie_group
    assert far.rank == 1


def test_same_inputs_same_output():
    pairs = {("ahri", f"a{i}"): (400 + 10 * i, 1000) for i in range(20)}
    first, th1 = _world(pairs)
    second, th2 = _world(pairs)
    assert first == second and th1 == th2
