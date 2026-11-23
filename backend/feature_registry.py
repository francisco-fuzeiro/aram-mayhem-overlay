"""P0 subset of the shared per-feature diagnostics contract.

When integrating independent TierDB draft #106, combine BOTH registries and
reason vocabularies. No tier-list functionality is copied into P0.
"""
from __future__ import annotations

FEATURES: dict[str, tuple[bool, str]] = {
    "build.item_pool": (True, "Verified current-patch item pool contains final items"),
}
UI_FEATURES = frozenset()  # backend-only catalog decision; no fake render ACK
STATUSES = ("ok", "failed", "skipped")
REASONS = frozenset(("final_items", "no_final_items", "unverified"))
