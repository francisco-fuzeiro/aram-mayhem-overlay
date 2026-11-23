"""F5 champion tier list (synthetic inputs only)."""
import pytest

from backend.tierdb.champion_tiers import (
    ChampionTierConfig,
    augment_leverage,
    build_champion_tiers,
    expected_max_of_three,
)

CFG = ChampionTierConfig(draws=300)


def _row(rows, champion):
    (row,) = [r for r in rows if r.champion_id == champion]
    return row


def test_weights_are_the_decided_ones():
    assert CFG.weights == {"win": 50, "combat": 19, "leverage": 23, "consistency": 8}


def test_expected_max_of_three_is_exact():
    assert expected_max_of_three([1.0, 2.0, 3.0]) == pytest.approx(3.0)
    # P(max=3)=1/4, P(max=4)=3/4 for 3 draws without replacement from 4.
    assert expected_max_of_three([4.0, 1.0, 3.0, 2.0]) == pytest.approx(3.75)
    assert expected_max_of_three([1.0, 2.0]) is None


def test_leverage_averages_rarities_with_enough_augments():
    deltas = {"gold": [0.0, 0.1, 0.2, 0.3], "silver": [0.5, 0.5], "prismatic": [0.1] * 3}
    expected = (expected_max_of_three(deltas["gold"]) + 0.1) / 2
    assert augment_leverage(deltas) == pytest.approx(expected)
    assert augment_leverage({"gold": [0.1]}) is None


def _many(extra=None, n=20000):
    champions = {f"c{i:02d}": (int(n * (0.45 + 0.005 * i)), n) for i in range(20)}
    deltas = {c: {"gold": [0.0, 0.05, 0.1, 0.15]} for c in champions}
    if extra:
        champions.update(extra[0])
        deltas.update(extra[1])
    return champions, deltas


def test_higher_win_rate_ranks_higher_with_equal_leverage():
    champions, deltas = _many()
    rows, _ = build_champion_tiers(champions, deltas, CFG)
    assert _row(rows, "c19").rank < _row(rows, "c00").rank
    assert sorted(r.rank for r in rows) == list(range(1, 21))


def test_leverage_lifts_a_champion_with_the_same_win_rate():
    champions, deltas = _many()
    deltas["c10"] = {"gold": [0.0, 0.4, 0.8, 1.2]}
    base, _ = build_champion_tiers(*_many(), CFG)
    lifted, _ = build_champion_tiers(champions, deltas, CFG)
    assert _row(lifted, "c10").score > _row(base, "c10").score
    assert _row(lifted, "c10").rank < _row(base, "c10").rank


def test_missing_components_are_redistributed():
    champions, deltas = _many()
    rows, _ = build_champion_tiers(champions, deltas, CFG)
    comps = dict(_row(rows, "c05").components)
    assert comps["combat"] is None and comps["consistency"] is None
    expected = 10 * (50 * comps["win"] + 23 * comps["leverage"]) / 73
    assert _row(rows, "c05").score == pytest.approx(expected, abs=0.6)


def test_small_sample_champion_cannot_be_op():
    champions, deltas = _many(extra=({"tiny": (300, 400)}, {"tiny": {"gold": [0.0, 0.1, 0.9]}}))
    rows, _ = build_champion_tiers(champions, deltas, CFG)
    assert _row(rows, "tiny").tier != "OP"


def test_overlay_never_needs_win_rate():
    rows, _ = build_champion_tiers(*_many(), CFG)
    fields = set(rows[0].__dataclass_fields__)
    assert not fields & {"win_rate", "wins", "games"}


def test_same_inputs_same_output():
    assert build_champion_tiers(*_many(), CFG) == build_champion_tiers(*_many(), CFG)


def test_relative_gain_breaks_ties_and_labels_augment_friendly():
    # Two statistically indistinguishable champions: the one whose augments
    # lift it more above its own baseline goes first inside the tie group.
    champions = {f"c{i:02d}": (int(20000 * (0.45 + 0.005 * i)), 20000) for i in range(20)}
    champions["twin_a"] = (10001, 20000)
    champions["twin_b"] = (10000, 20000)
    deltas = {c: {"gold": [0.0, 0.05, 0.1, 0.15]} for c in champions}
    gain = {c: 0.1 for c in champions}
    gain["twin_b"] = 0.9
    rows, _ = build_champion_tiers(champions, deltas, CFG, relative_gain=gain)
    a, b = _row(rows, "twin_a"), _row(rows, "twin_b")
    assert a.tie_group == b.tie_group
    assert b.rank < a.rank
    assert b.augment_friendly is True
    assert a.augment_friendly is False
    assert sorted(r.rank for r in rows) == list(range(1, len(rows) + 1))


def test_without_relative_gain_nobody_is_labelled():
    rows, _ = build_champion_tiers(*_many(), CFG)
    assert not any(r.augment_friendly for r in rows)
