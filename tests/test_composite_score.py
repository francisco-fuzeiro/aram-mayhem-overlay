"""Statistical confidence and provenance tests for the composite scoring engine."""
import pytest

from backend.engine.composite_score import WinEvidence, composite_rating


def test_evidence_with_no_games_uses_only_gameplay_heuristics():
    rating = composite_rating(synergy=8.0, context=6.0)
    assert rating.score == 7.2
    assert rating.confidence == 0.0
    assert rating.performance is None
    assert rating.evidence_source == "none"
    assert rating.sample_size == 0


def test_composite_is_not_win_rate_rescaling():
    rating = composite_rating(
        synergy=9.0, context=7.0, evidence=WinEvidence(80, 100)
    )
    # 80% empirical success is neither 8.0/10 nor the entire score.
    assert 0.0 <= rating.score <= 10.0
    assert rating.score != 8.0
    assert rating.performance is not None
    assert rating.synergy == 9.0
    assert rating.context == 7.0


def test_small_samples_cannot_dominate_heuristic():
    baseline = composite_rating(synergy=8.0, context=8.0)
    tiny = composite_rating(
        synergy=8.0, context=8.0, evidence=WinEvidence(1, 1)
    )
    assert abs(tiny.score - baseline.score) <= 0.2
    assert tiny.confidence < 0.1


def test_large_samples_have_more_weight_than_one_game():
    tiny = composite_rating(6, 6, WinEvidence(1, 1))
    large = composite_rating(6, 6, WinEvidence(900, 1000))
    assert large.confidence > tiny.confidence
    assert large.score > tiny.score


def test_known_stale_patch_is_excluded():
    rating = composite_rating(
        synergy=9.0, context=5.0,
        evidence=WinEvidence(100, 100, patch="old"),
        active_patch="new",
    )
    assert rating.sample_size == 0
    assert rating.performance is None
    assert rating.evidence_source == "none"


def test_unknown_patch_is_downweighted():
    rating = composite_rating(6.0, 6.0, WinEvidence(100, 100), active_patch="26.22")
    with_patch = composite_rating(
        6.0, 6.0, WinEvidence(100, 100, patch="26.22"), active_patch="26.22"
    )
    assert rating.confidence < with_patch.confidence
    assert rating.score < with_patch.score


def test_serialized_rating_excludes_raw_win_rate_and_win_counts():
    payload = composite_rating(7, 7, WinEvidence(40, 50)).as_dict()
    assert "wins" not in payload
    assert "win_rate" not in payload
    assert payload["score"] <= 10.0
    assert payload["sample_size"] == 50


@pytest.mark.parametrize("wins,games", [(5, 2), (-1, 10), (1, -1), (0, 0.5)])
def test_invalid_win_evidence_is_rejected(wins, games):
    with pytest.raises(ValueError):
        WinEvidence(wins, games)


def test_out_of_range_scores_are_clamped_and_nan_is_rejected():
    assert composite_rating(20, -5).score == 5.8
    with pytest.raises(ValueError):
        composite_rating(float("nan"), 5)
