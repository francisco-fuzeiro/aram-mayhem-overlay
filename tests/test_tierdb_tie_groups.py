"""Tie groups must not chain (Fiora match test 23/11: "tied #32-#69").

A tie group means "not distinguishable from the group's first item". Comparing
each item only with its neighbour chained evenly spaced items into one huge
group even when the ends were clearly different.
"""
import numpy as np

from backend.tierdb.augment_tiers import AugmentTierConfig, build_augment_tiers
from backend.tierdb.champion_tiers import ChampionTierConfig, build_champion_tiers
from backend.tierdb.item_tiers import ItemTierConfig, _rank


def _group_sizes(groups):
    sizes = {}
    for g in groups:
        sizes[g] = sizes.get(g, 0) + 1
    return sizes


def test_augment_tie_groups_do_not_chain_across_a_clear_gap():
    pairs = {("fiora", f"a{i:02d}"): (int(2000 * (0.40 + 0.005 * i)), 2000) for i in range(41)}
    champions = {"fiora": (100000, 200000), "garen": (5000, 10000)}
    rows, _ = build_augment_tiers(champions, pairs, {a: "gold" for _, a in pairs},
                                  {c: "fighter" for c in champions}, {},
                                  AugmentTierConfig(draws=300))
    mine = sorted((r for r in rows if r.champion_id == "fiora"), key=lambda r: r.rank)
    assert mine[0].tie_group != mine[-1].tie_group
    assert max(_group_sizes(r.tie_group for r in mine).values()) <= 15


def test_champion_tie_groups_do_not_chain_across_a_clear_gap():
    champions = {f"c{i:02d}": (int(4000 * (0.40 + 0.005 * i)), 4000) for i in range(41)}
    deltas = {c: {"gold": [0.0, 0.05]} for c in champions}
    rows, _ = build_champion_tiers(champions, deltas, ChampionTierConfig(draws=300))
    rows = sorted(rows, key=lambda r: r.rank)
    assert rows[0].tie_group != rows[-1].tie_group
    assert max(_group_sizes(r.tie_group for r in rows).values()) <= 15


def test_item_tie_groups_do_not_chain_across_a_clear_gap():
    rng = np.random.default_rng(1)
    scored = {f"i{i:02d}": ("champion", rng.normal(10 - 0.1 * i, 0.3, 300)) for i in range(41)}
    ids, groups = _rank(scored, ItemTierConfig())
    assert groups[ids[0]][1] != groups[ids[-1]][1]
    assert max(_group_sizes(g for _, g in groups.values()).values()) <= 15
