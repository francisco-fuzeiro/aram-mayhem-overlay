"""F3/#84: synthetic regression for scaling-only Mayhem model coverage.

A real scaling model already drives score_augment. It must not be silently
erased by vector-only modelled gating in rating, ranker or diagnostics.
No patch-wide performance inference, player data or Riot win rates.
"""
import pytest

from backend.engine import scoring
from backend.engine.augment_rating import rate_augment
from backend.engine.ranker import rank_augments
from backend.models import (
    AugmentData, AugmentTier, ChampionMeta, ScalingSpec, ScalingType, StatVector,
)
from backend.static_data.loader import StaticData


def card(aid: str, tier: AugmentTier, *, ad=0.0, provenance="none"):
    return AugmentData(aid, aid, tier, "", StatVector(ad=ad), provenance=provenance)


def spec(*, base=0.5, rate_stat="attack_speed"):
    return ScalingSpec(
        type=ScalingType.ON_HIT, base=base, rate_stat=rate_stat,
    )


def champion():
    return ChampionMeta(
        "synthetic", "Synthetic", StatVector(attack_speed=0.85), role="marksman",
    )


def test_existing_positive_scaling_spec_yields_usable_rating_and_ranker_model_flag(
    monkeypatch,
):
    aug = card("scaling", AugmentTier.GOLD)
    assert aug.modelled is False  # vector-only property; no mutation required
    monkeypatch.setattr(scoring, "_scaling_specs", {"scaling": [spec()]})

    rating = rate_augment(champion(), aug, [])
    assert rating.score is not None
    assert 0.0 < rating.score <= 10.0
    assert rating.sample_size == 0
    assert rating.performance is None
    rec = rank_augments(champion(), [aug], [], [])[0]
    assert rec.modelled is True
    assert rec.score == rating.score
    assert rec.confidence == rating.confidence
    assert rec.provenance == "none"


@pytest.mark.parametrize("bad_spec", [
    spec(base=0.0),
    spec(rate_stat="not_a_real_stat"),
])
def test_zero_or_unusable_scaling_cannot_fabricate_model_or_rating(
    monkeypatch, bad_spec,
):
    aug = card("unmodelled", AugmentTier.PRISMATIC)
    monkeypatch.setattr(scoring, "_scaling_specs", {"unmodelled": [bad_spec]})
    assert rate_augment(champion(), aug, []).score is None
    rec = rank_augments(champion(), [aug], [], [])[0]
    assert rec.score is None
    assert rec.modelled is False


def test_coverage_report_per_rarity_and_scaling_only_are_explicit(monkeypatch):
    monkeypatch.setattr(scoring, "_scaling_specs", {
        "scale_gold": [spec()],
        "empty_prismatic": [spec(base=0)],
    })
    data = StaticData()
    data._augments = {
        "modelled_silver": card("modelled_silver", AugmentTier.SILVER,
                                ad=0.5, provenance="override"),
        "unmodelled_silver": card("unmodelled_silver", AugmentTier.SILVER),
        "scale_gold": card("scale_gold", AugmentTier.GOLD),
        "empty_prismatic": card("empty_prismatic", AugmentTier.PRISMATIC),
    }
    data._stat_anvils = {"anvil": card("anvil", AugmentTier.STAT_ANVIL)}
    report = data.augment_coverage_report()
    assert (report["total"], report["modelled"], report["unmodelled"]) == (4, 2, 2)
    assert report["scaling_only"] == 1
    assert report["by_rarity"] == {
        "silver": {"total": 2, "modelled": 1, "unmodelled": 1,
                   "scaling_only": 0},
        "gold": {"total": 1, "modelled": 1, "unmodelled": 0,
                 "scaling_only": 1},
        "prismatic": {"total": 1, "modelled": 0, "unmodelled": 1,
                      "scaling_only": 0},
    }
    assert sum(report["by_provenance"].values()) == report["total"]


def test_no_catalog_never_reports_fabricated_ratings(monkeypatch):
    monkeypatch.setattr(scoring, "_scaling_specs", {})
    report = StaticData().augment_coverage_report()
    assert report["total"] == 0
    assert report["modelled"] == 0
    assert report["scaling_only"] == 0
    assert all(bucket["total"] == 0 for bucket in report["by_rarity"].values())
