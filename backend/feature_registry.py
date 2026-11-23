"""Registry of feature ids for per-feature diagnostics (no imports, no I/O).

Every user-visible feature that a single end-to-end match test exercises gets
a dotted id (``area.name``) plus a closed set of reasons. Add new ids and
reasons here; free text never reaches the journal.
"""
from __future__ import annotations

# id -> (expected during one full Mayhem match test, short description)
FEATURES: dict[str, tuple[bool, str]] = {
    "tierdb.load": (True, "Tier list export read from disk"),
    "tierdb.update": (False, "Background download/build of the tier list"),
    "tierdb.switch": (True, "Tier list switch state at startup or after a change"),
    "tierdb.offer_tiers": (True, "Server attached tiers to the visible augment offer"),
    "tierdb.offer_render": (True, "Overlay drew tier lines on the offer cards"),
    "tierdb.champselect_tiers": (True, "Server attached strength/potential in champ select"),
    "tierdb.champselect_render": (True, "Overlay drew strength/potential in champ select"),
}

# Features the browser may report about itself (DOM rendering only).
UI_FEATURES = frozenset(("tierdb.offer_render", "tierdb.champselect_render"))

STATUSES = ("ok", "failed", "skipped")

REASONS = frozenset((
    # tierdb.load
    "loaded", "export_missing", "export_invalid",
    # tierdb.update
    "updated", "network", "bad_dataset", "license", "build_failed", "unexpected",
    "already_running", "fresh", "auto_update_off",
    # tierdb.switch
    "enabled", "disabled", "save_error",
    # tierdb.offer_tiers / champselect_tiers
    "tiers_attached", "tiers_off", "no_champion", "no_visible_augments",
    "champion_not_in_tierlist", "annotated", "no_candidates",
    "no_candidate_in_tierlist",
    # UI renders
    "rendered", "no_tier_data",
))
