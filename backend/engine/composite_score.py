"""Composite 0.0–10.0 recommendation rating (experimental).

This is *not* a win-rate rescaling. It combines independent gameplay signals
and uses win/loss evidence only where valid, permitted, and available.
For Augments, Riot explicitly disallows displaying win rates; approval of a
derived rating is not implied by hiding that figure.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class WinEvidence:
    wins: int
    games: int
    source: str = "personal_history"
    patch: str | None = None

    def __post_init__(self):
        if (
            not isinstance(self.wins, int)
            or not isinstance(self.games, int)
            or self.games < 0
            or self.wins < 0
            or self.wins > self.games
        ):
            raise ValueError("Invalid win/loss evidence")


@dataclass(frozen=True)
class CompositeRating:
    score: float | None
    confidence: float
    sample_size: int
    performance: float | None
    synergy: float | None
    context: float | None
    evidence_source: str
    method: str = "composite_v1"
    # Internal unrounded ordinal fit; intentionally not in public payload.
    ranking_value: float | None = None

    def as_dict(self) -> dict:
        # Deliberately omit raw win rates and win counts from overlay payloads.
        return {
            "score": self.score,
            "confidence": self.confidence,
            "sample_size": self.sample_size,
            "components": {
                "performance": self.performance,
                "synergy": self.synergy,
                "context": self.context,
            },
            "evidence_source": self.evidence_source,
            "method": self.method,
        }


def _clamp10(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("Expected a finite score")
    return max(0.0, min(10.0, float(value)))


def composite_rating(
    synergy: float,
    context: float,
    evidence: WinEvidence | None = None,
    *,
    active_patch: str | None = None,
    prior_games: int = 40,
) -> CompositeRating:
    """Combine performance (40%), synergy (35%), and context (25%).

    Performance comes from an empirical win rate adjusted toward a neutral
    prior (50%) by sample size. Confidence shrinks the empirical signal;
    it does *not* award extra points to commonly played augments.

    With weak evidence, taper in the performance component gradually; with
    no compatible evidence, use 35/60 synergy and 25/60 context only.
    Scores are ordinal estimates, not predicted probabilities.
    """
    if prior_games <= 0:
        raise ValueError("prior_games must be positive")
    synergy = _clamp10(synergy)
    context = _clamp10(context)

    valid = evidence is not None and evidence.games > 0
    if valid and active_patch and evidence.patch and evidence.patch != active_patch:
        valid = False  # never mix known stale patch performance into live recommendations

    if not valid:
        score = (0.35 * synergy + 0.25 * context) / 0.60
        return CompositeRating(
            score=round(score, 1), confidence=0.0, sample_size=0,
            ranking_value=score,
            performance=None, synergy=synergy, context=context,
            evidence_source="none",
        )

    # Beta-binomial smoothing, fixed prior of 50% over prior_games matches.
    posterior = (evidence.wins + 0.5 * prior_games) / (evidence.games + prior_games)
    # A +/-20 percentage-point *posterior* shift spans the full 0–10 scale.
    performance = _clamp10(5.0 + 25.0 * (posterior - 0.5))
    confidence = evidence.games / (evidence.games + prior_games)
    if active_patch and evidence.patch is None:
        # Personal history has no patch metadata. Keep but downweight confidence.
        confidence *= 0.5
        performance = 5.0 + (performance - 5.0) * 0.5

    # A single played game must not suddenly replace 40% of the heuristic
    # with a neutral prior. Introduce performance weight gradually, based on
    # evidence confidence, while preserving the target 40/35/25 blend at scale.
    heuristic = (0.35 * synergy + 0.25 * context) / 0.60
    empirical_weight = 0.40 * confidence
    score = (1.0 - empirical_weight) * heuristic + empirical_weight * performance
    return CompositeRating(
        score=round(_clamp10(score), 1), confidence=round(confidence, 2),
        ranking_value=_clamp10(score),
        sample_size=evidence.games, performance=round(performance, 2),
        synergy=synergy, context=context, evidence_source=evidence.source,
    )
