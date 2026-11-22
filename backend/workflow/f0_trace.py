"""F0-only evidence classifications and opt-in local diagnostic records.

This module never reads League data, runs OCR, changes gameplay state or stores
identifiers. Callers provide only existing, already observed facts. Classification
is about input completeness, not proof of recommendation correctness.
"""
from __future__ import annotations

import os
from collections.abc import Callable

from backend.diagnostic_events import _clean, events


def classify_champion_identity(draft: dict | None,
                               id_to_alias: dict[str, str]) -> tuple[str, str]:
    """Separate LCU local-player certainty from correct bench candidate listing."""
    if not isinstance(draft, dict):
        return "unknown", "lcu_unavailable"
    local_cell = draft.get("localPlayerCellId")
    if local_cell is None:
        return "unknown", "local_cell_missing"
    team = draft.get("myTeam")
    if not isinstance(team, list):
        return "rejected", "local_cell_not_found"
    matched = [
        row for row in team
        if isinstance(row, dict) and row.get("cellId") == local_cell
    ]
    if not matched:
        return "rejected", "local_cell_not_found"
    if len(matched) > 1:
        return "rejected", "local_cell_ambiguous"
    numeric = str(matched[0].get("championId", 0))
    if numeric == "0":
        return "unknown", "local_champion_unselected"
    if not isinstance(id_to_alias, dict) or not id_to_alias.get(numeric):
        return "rejected", "champion_unmapped"
    return "accepted", "local_champion_mapped"


def classify_offer_slots(slots: dict | None, *, stage: str,
                         stale: bool, epoch_valid: bool) -> tuple[str, str]:
    """Classify physical *identification* evidence, not whether names are right."""
    if not epoch_valid:
        return "rejected", "stale_epoch"
    if stale:
        return "rejected", "stale_offer"
    if stage != "titles_detected":
        if stage in ("titles_verifying", "titles_transition", "titles_unidentified",
                     "geometry_unsupported", "game_not_focused", "game_occluded",
                     "capture_unavailable", "ocr_unavailable", "verified_absence"):
            return "unknown", stage
        return "unknown", "capture_unverified"
    if not isinstance(slots, dict) or list(slots) != ["left", "centre", "right"]:
        return "rejected", "slot_order_invalid"
    values = list(slots.values())
    if any(x is not None and (not isinstance(x, str) or not x) for x in values):
        return "rejected", "slot_identity_invalid"
    valid = [x for x in values if x is not None]
    if len(valid) != len(set(valid)):
        return "rejected", "slot_identity_duplicate"
    if not valid:
        return "unknown", "titles_unidentified"
    if len(valid) < 3:
        return "accepted", "slots_verified_partial"
    return "accepted", "slots_verified_complete"


def classify_build_evidence(*, champion_known: bool, pool_verified: bool,
                            inventory_known: bool,
                            augments_confirmed: bool) -> tuple[str, str]:
    """An accepted envelope is not an objective score or verified best build."""
    if not champion_known:
        return "rejected", "champion_unknown"
    if not pool_verified:
        return "rejected", "item_pool_unverified"
    if not inventory_known:
        return "rejected", "inventory_unknown"
    if not augments_confirmed:
        return "unknown", "augments_unconfirmed"
    return "accepted", "inputs_present"


def classify_item_eligibility(item_id: str, item_class: str,
                              pool: set[str] | frozenset[str],
                              pool_verified: bool,
                              owned: set[str] | frozenset[str]) -> tuple[str, str]:
    """Read-only explanation of catalog membership; does not override shop rules.

    Other conditions (exclusive passives, recipes, conditional availability,
    contextual suitability) remain separate decisions in the existing engine.
    """
    if not pool_verified:
        return "rejected", "item_pool_unverified"
    if item_class not in ("final", "boots_tier2"):
        return "rejected", "item_class_excluded"
    if item_id not in pool:
        return "rejected", "item_not_in_verified_pool"
    if item_id in owned:
        return "rejected", "already_owned"
    return "accepted", "verified_candidate"


def emit_f0_trace(feature: str, stage: str, status: str, reason: str,
                  *, source: str = "none", slot: str | None = None,
                  epoch: int | None = None, count: int | None = None,
                  item_id: str | None = None,
                  similarity: float | None = None,
                  writer: Callable[..., bool] | None = None) -> bool:
    """Opt-in and whitelist *before* touching the existing local-only writer.

    ARAM_ORACLE_F0_TRACE=1 enables ONLY F0 enum traces. Even an opt-in caller
    cannot add names, OCR text, screenshot bytes, account IDs, HWND or paths.
    The existing bounded, rotating diagnostic journal is reused.
    """
    if os.environ.get("ARAM_ORACLE_F0_TRACE") != "1":
        return False
    fields = dict(feature=feature, stage=stage, status=status, reason=reason,
                  source=source)
    if slot is not None:
        fields["slot"] = slot
    if epoch is not None:
        fields["epoch"] = epoch
    if count is not None:
        fields["count"] = count
    if item_id is not None:
        fields["item_id"] = item_id
    if similarity is not None:
        fields["similarity"] = similarity
    safe = _clean("f0_trace", fields)
    # No incomplete/unknown status should become an unlabelled event.
    if safe is None or any(key not in safe for key in
                           ("feature", "stage", "status", "reason", "source")):
        return False
    if writer is not None:
        return bool(writer(**safe))
    return events.transition("f0_trace", **safe)


def emit_f0_geometry(
    client_size: tuple[int, int],
    bands: dict[str, tuple[int, int, int, int]],
    *, writer: Callable[..., bool] | None = None,
) -> bool:
    """Opt-in read-only measured L/C/R rectangles relative to the game client.

    Never persist a desktop coordinate, HWND, pixels, player name, raw OCR,
    screenshot, credential, or private path. Validate the complete geometry
    atomically before emitting any of the three bounded records.
    """
    if os.environ.get("ARAM_ORACLE_F0_TRACE") != "1":
        return False
    if (not isinstance(client_size, tuple) or len(client_size) != 2
            or any(type(v) is not int or not 1 <= v <= 8192
                   for v in client_size)):
        return False
    width, height = client_size
    slots = ("left", "centre", "right")
    if not isinstance(bands, dict) or list(bands) != list(slots):
        return False
    records = []
    for slot in slots:
        rect = bands[slot]
        if (not isinstance(rect, tuple) or len(rect) != 4
                or any(type(v) is not int for v in rect)):
            return False
        x, y, w, h = rect
        if not (0 <= x < width and 0 <= y < height and
                0 < w <= width - x and 0 < h <= height - y):
            return False
        clean = _clean("f0_geometry", {
            "slot": slot, "source": "client_geometry",
            "client_width": width, "client_height": height,
            "x": x, "y": y, "w": w, "h": h,
        })
        if clean is None or len(clean) != 8:
            return False
        records.append(clean)
    sink = writer if writer is not None else lambda **fields: events.emit(
        "f0_geometry", **fields
    )
    try:
        return all(bool(sink(**record)) for record in records)
    except Exception:
        # Optional diagnostics must never interrupt the live OCR watcher.
        return False
