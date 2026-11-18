"""Regression tests for the experimental 0.0–10.0 augment rating."""
from backend.engine.augment_rating import rate_augment
from backend.engine.ranker import rank_augments
from backend.models import AugmentData, AugmentTier, ChampionMeta, StatVector


def champion():
    return ChampionMeta("lux", "Lux", StatVector(ap=0.9, cdr=0.8, pen=0.5), role="mage")


def augment(name, **stats):
    return AugmentData(name, name, AugmentTier.GOLD, "", StatVector(**stats))


def test_score_is_absolute_ten_point_not_best_of_three():
    lux = champion()
    terrible = augment("terrible", ad=0.1)
    excellent = augment("excellent", ap=0.9, cdr=0.8)
    poor_rating = rate_augment(lux, terrible, [])
    strong_rating = rate_augment(lux, excellent, [])
    assert 0.0 <= poor_rating.score < 4.0
    assert 4.0 < strong_rating.score <= 10.0
    assert strong_rating.score > poor_rating.score


def test_empirical_performance_disabled_by_default():
    lux = champion()
    aug = augment("ap", ap=0.6)
    baseline = rate_augment(lux, aug, [])
    disabled = rate_augment(lux, aug, [], personal_record=(90, 100))
    assert baseline.score == disabled.score
    assert disabled.performance is None
    assert disabled.sample_size == 0


def test_opt_in_uses_valid_personal_samples():
    lux = champion()
    aug = augment("ap", ap=0.6)
    baseline = rate_augment(lux, aug, [])
    with_record = rate_augment(
        lux, aug, [], personal_record=(90, 100), allow_empirical=True
    )
    assert with_record.sample_size == 100
    assert with_record.performance is not None
    assert with_record.score > baseline.score


def test_under_five_games_excluded_even_with_opt_in():
    lux = champion()
    aug = augment("ap", ap=0.6)
    low_sample = rate_augment(
        lux, aug, [], personal_record=(4, 4), allow_empirical=True
    )
    assert low_sample.performance is None
    assert low_sample.sample_size == 0


def test_enemy_team_changes_contextual_rating():
    lux = champion()
    cc = augment("stun", hard_cc=0.8)
    enemy = ChampionMeta("tank", "Tank", StatVector(hp=1.0), role="tank")
    alone = rate_augment(lux, cc, [])
    against_tank = rate_augment(lux, cc, [], enemies=[enemy])
    assert against_tank.context > alone.context
    assert against_tank.score > alone.score


def test_ranking_has_bounded_scores_and_is_sorted():
    lux = champion()
    cards = [
        augment("bad", ad=0.05),
        augment("good", ap=0.7, cdr=0.6),
        augment("medium", ap=0.3),
    ]
    recommendations = rank_augments(lux, cards, [], [])
    scores = [rec.score for rec in recommendations]
    assert scores == sorted(scores, reverse=True)
    assert len(scores) == 3
    assert all(0.0 <= score <= 10.0 for score in scores)
    assert all(rec.sample_size == 0 for rec in recommendations)


def test_empirical_signal_opt_in_changes_rank_when_heuristics_tie():
    lux = champion()
    cards = [augment("a", ap=0.5), augment("b", ap=0.5)]
    records = {"b": (80, 100)}
    default = rank_augments(lux, cards, [], [], personal_winrates=records)
    opt_in = rank_augments(
        lux, cards, [], [], personal_winrates=records,
        use_personal_performance=True,
    )
    assert default[0].score == default[1].score
    assert opt_in[0].augment_id == "b"
    assert opt_in[0].sample_size == 100
