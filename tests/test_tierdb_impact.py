"""Impact metric (owner decisions 23/11): per game, z(damage to champions/min) +
z(heal+shield/min), both against the champion's own baseline, summed. No role
labels: each build counts by what it actually produces. Shrunk by n, bounded.
"""
from backend.tierdb.impact import ImpactConfig, augment_impact


def _row(champ, aug, dmg, mins=20, heal=0, win=1):
    return {"champion_id": champ, "augments": [aug], "duration": mins * 60,
            "damage_to_champions": dmg, "heal_shield": heal, "heal_total": heal,
            "win": win}


def test_augment_that_adds_damage_scores_positive_and_shrinks_with_few_games():
    many = [_row("garen", "a", 20000 + 50 * i) for i in range(40)] + \
           [_row("garen", "b", 30000 + 50 * i) for i in range(40)]
    few = [_row("garen", "a", 20000 + 50 * i) for i in range(6)] + \
          [_row("garen", "b", 30000 + 50 * i) for i in range(6)]
    out = augment_impact(many)
    assert out[("garen", "b")]["impact"] > 0 > out[("garen", "a")]["impact"]
    small = augment_impact(few)
    assert 0 < small[("garen", "b")]["impact"] < out[("garen", "b")]["impact"]


def test_tank_measured_against_its_own_baseline():
    rows = [_row("ornn", "x", 18000 + 100 * i) for i in range(30)] + \
           [_row("ornn", "y", 26000 + 100 * i) for i in range(30)]
    out = augment_impact(rows)
    assert out[("ornn", "y")]["impact"] > 0.3


def test_no_role_labels_full_ap_sona_counts_by_damage_and_healer_by_heal():
    rows = [_row("sona", "ap", 30000 + 10 * i, heal=2000) for i in range(30)] + \
           [_row("sona", "heal", 8000 + 10 * i, heal=15000) for i in range(30)] + \
           [_row("sona", "weak", 8000 + 10 * i, heal=2000) for i in range(30)]
    out = augment_impact(rows)
    assert out[("sona", "ap")]["impact"] > 0
    assert out[("sona", "heal")]["impact"] > 0
    assert out[("sona", "weak")]["impact"] < 0
    assert out[("sona", "ap")]["metric"] == "z_damage_plus_heal_shield"


def test_heal_shield_falls_back_to_total_heal_when_missing():
    rows = [dict(_row("sona", "h", 8000, heal=0), heal_shield=None, heal_total=15000)
            for _ in range(20)] + \
           [dict(_row("sona", "w", 8000, heal=0), heal_shield=None, heal_total=1000)
            for _ in range(20)]
    out = augment_impact(rows)
    assert out[("sona", "h")]["impact"] > 0 > out[("sona", "w")]["impact"]


def test_impact_is_bounded_needs_minimum_games_and_skips_remakes():
    rows = [_row("lux", "a", 10000), _row("lux", "b", 90000)]
    assert augment_impact(rows, config=ImpactConfig(min_games=5)) == {}
    rows = [_row("lux", "a", 10000) for _ in range(20)] + \
           [_row("lux", "b", 90000) for _ in range(20)] + \
           [_row("lux", "c", 999999, mins=3) for _ in range(20)]
    out = augment_impact(rows)
    assert ("lux", "c") not in out
    assert all(-1.0 <= v["impact"] <= 1.0 for v in out.values())
