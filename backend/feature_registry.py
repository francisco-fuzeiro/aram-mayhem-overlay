"""Strict per-feature P0 diagnostics, compatible with the shared TierDB pattern.

Merge the UNION of P0 and TierDB IDs/reasons on eventual integration with
sibling PR #106. Never log champion/player identities, OCR text or paths.
"""
from __future__ import annotations

FEATURES: dict[str, tuple[bool, str]] = {
    "build.item_pool": (True, "Current-patch public item catalog has safe final items"),
    "augment.stats_parser": (False, "Conservative stat vector mapping on fresh catalog"),
    "augment.cache_schema": (True, "Augment cache was current, rejected or absent"),
    "build.next_item": (True, "Backend selected or abstained from next purchase"),
    "build.next_item_render": (False, "Overlay rendered next-item advice"),
    "anvil.voucher_purchase": (False, "Observed genuine local-player voucher stack edge"),
    "anvil.offer_detected": (False, "Independently verified Stat Anvil popup"),
    "anvil.offer_render": (False, "Overlay rendered verified Stat Anvil cards"),
}
# Only actual browser/overlay rendering may ACK these IDs.
UI_FEATURES = frozenset(("build.next_item_render", "anvil.offer_render"))
STATUSES = ("ok", "failed", "skipped")
FEATURE_OUTCOMES: dict[str, frozenset[tuple[str, str]]] = {
    "build.item_pool": frozenset((
        ("ok", "final_items"), ("failed", "no_final_items"),
        ("skipped", "unverified"),
    )),
    "augment.stats_parser": frozenset((
        ("ok", "modelled"), ("skipped", "unmodelled"),
    )),
    "augment.cache_schema": frozenset((
        ("ok", "current"), ("skipped", "cache_missing"),
        ("failed", "cache_invalid"),
    )),
    "build.next_item": frozenset((
        ("ok", "ranked"), ("skipped", "unverified"),
        ("skipped", "slot_blocked"), ("skipped", "inventory_unknown"),
        ("skipped", "item_recipe_unknown"), ("skipped", "no_candidate"),
    )),
    "build.next_item_render": frozenset((("ok", "rendered"),)),
    "anvil.voucher_purchase": frozenset((
        ("ok", "positive_edge"), ("skipped", "no_edge"),
        ("skipped", "source_unavailable"),
    )),
    "anvil.offer_detected": frozenset((
        ("ok", "verified_offer"), ("skipped", "popup_unverified"),
    )),
    "anvil.offer_render": frozenset((("ok", "rendered"),)),
}
REASONS = frozenset(reason for allowed in FEATURE_OUTCOMES.values()
                    for _, reason in allowed)


def allowed_outcome(feature: object, status: object, reason: object) -> bool:
    """Closed outcomes per ID; source-agnostic input never becomes journal text."""
    return (isinstance(feature, str) and
            (status, reason) in FEATURE_OUTCOMES.get(feature, frozenset()))
