"""Experimental 0.0–10.0 augment rating, using existing ARAM Oracle scoring.

The empirical input is opt-in and strictly local. The capability is disabled
by default pending a separate Riot policy determination. A derived numerical
rating is NOT evidence of approval for real-time augment recommendations.
"""
import math

from backend.engine.composite_score import CompositeRating, WinEvidence, composite_rating
from backend.engine.scoring import score_augment
from backend.models import AugmentData, ChampionMeta
from backend.engine.team_context import EnemyThreatProfile, augment_threat_modifier


def rate_augment(
    champion: ChampionMeta,
    augment: AugmentData,
    existing: list[AugmentData],
    enemies: list[ChampionMeta] | None = None,
    personal_record: tuple[int, int] | None = None,
    threat_profile: EnemyThreatProfile | None = None,
    *,
    allow_empirical: bool = False,
) -> CompositeRating:
    """Blend kit synergy, enemy context and optional local win/loss evidence.

    The bounded, monotone transform maps our *heuristic* raw scoring engine
    to a 0–10 scale. It is not a statistical prediction or rate conversion.
    A 5.0 context is neutral when no enemy information is available.
    """
    raw_base = score_augment(champion, augment, existing, enemies=None)
    raw_with_context = score_augment(champion, augment, existing, enemies=enemies)

    # Monotone absolute normalization; unlike min/max across offered cards,
    # this does not make a uniformly bad offer look like a perfect 10/10.
    synergy = round(10.0 * (1.0 - math.exp(-max(0.0, raw_base) / 1.2)), 2)
    context_delta = (raw_with_context - raw_base) + augment_threat_modifier(
        augment.contribution, threat_profile
    )
    context = round(max(0.0, min(10.0, 5.0 + 4.0 * math.tanh(context_delta * 4.0))), 2)

    evidence = None
    if allow_empirical and personal_record:
        wins, games = personal_record
        # Very small personal samples are not actionable evidence.
        if games >= 5:
            evidence = WinEvidence(wins=wins, games=games)

    return composite_rating(synergy=synergy, context=context, evidence=evidence)
