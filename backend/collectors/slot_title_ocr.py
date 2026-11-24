"""M5/C2: strict, position-locked title recognition for Mayhem card bands.

Reads each individual client-relative title crop, never infers position from
confidence-sorted OCR of the whole region. Unknown and duplicate titles fail
closed. No capture, disk access, gameplay input, or diagnostics here.
"""
from __future__ import annotations

import re
import os
from PIL import Image
import pytesseract
from rapidfuzz import fuzz

from backend.collectors.card_title_geometry import title_bands_from_client_rect
from backend.workflow.f0_trace import emit_f0_trace

SLOTS = ("left", "centre", "right")
MATCH_THRESHOLD = 90
MIN_MARGIN = 8


class SlotMatches(list):
    """Recognized matches in physical slot order and three explicit slot values."""

    def __init__(self, slots: dict[str, tuple[str, str, int] | None]):
        if list(slots) != list(SLOTS):
            raise ValueError("expected left/centre/right slot order")
        self.slots = dict(slots)
        super().__init__(match for match in self.slots.values() if match is not None)


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.casefold()).split())


def strict_match_title(
    text: str, augment_names: dict[str, str], *,
    trace_slot: str | None = None,
) -> tuple[str, str, int] | None:
    """Whole-title matching only; best >=90 and beats runner-up by >=8.

    Diagnostic trace_slot controls optional enum evidence only. The raw OCR
    text is never written to disk, and the matching decision is unchanged.
    """
    if not isinstance(text, str) or not isinstance(augment_names, dict):
        emit_f0_trace("augment", "matching", "unknown", "title_input_invalid",
                      source="ocr", slot=trace_slot)
        return None
    observed = _normalize(text)
    if len(observed) < 4:
        emit_f0_trace("augment", "matching", "unknown", "title_short",
                      source="ocr", slot=trace_slot)
        return None
    if not augment_names:
        emit_f0_trace("augment", "matching", "unknown", "catalog_empty",
                      source="ocr", slot=trace_slot)
        return None
    # Duplicate IDs for the same normalized title are a single candidate:
    # they must never consume the best-vs-runner-up confidence margin.
    by_title: dict[str, tuple[str, str]] = {}

    def id_priority(aid: str) -> tuple[int, int, str]:
        try:
            number = int(aid)
        except (TypeError, ValueError, OverflowError):
            # Preserve compatibility with nonnumeric test/extension IDs;
            # production catalog IDs are numeric strings.
            return (2, 0, aid)
        return (0 if number >= 1000 else 1, number, aid)

    for aid, name in augment_names.items():
        if not isinstance(aid, str) or not isinstance(name, str):
            continue
        normalized = _normalize(name)
        if not normalized:
            continue
        current = by_title.get(normalized)
        if current is None or id_priority(aid) < id_priority(current[0]):
            by_title[normalized] = (aid, name)

    if not by_title:
        emit_f0_trace("augment", "matching", "unknown", "catalog_empty",
                      source="ocr", slot=trace_slot)
        return None
    scored = [
        (fuzz.ratio(observed, normalized), normalized, aid, name)
        for normalized, (aid, name) in by_title.items()
    ]
    scored.sort(key=lambda row: (-row[0], row[1]))
    best, _, aid, name = scored[0]
    second = scored[1][0] if len(scored) >= 2 else 0
    if best < MATCH_THRESHOLD:
        emit_f0_trace("augment", "matching", "rejected", "below_threshold",
                      source="ocr", slot=trace_slot, similarity=int(best))
        return None
    if best - second < MIN_MARGIN:
        emit_f0_trace("augment", "matching", "rejected", "insufficient_margin",
                      source="ocr", slot=trace_slot, similarity=int(best))
        return None
    emit_f0_trace("augment", "matching", "accepted", "title_matched",
                  source="ocr", slot=trace_slot, similarity=int(best), augment_id=aid)
    return aid, name, int(best)


def crop_title_slots(
    image: Image.Image,
    client_rect: tuple[int, int, int, int],
    roi: tuple[float, float, float, float],
) -> dict[str, Image.Image] | None:
    """Extract all three geometrically verified titles from one League ROI."""
    if not hasattr(image, "size") or len(client_rect) != 4 or len(roi) != 4:
        return None
    left, top, right, bottom = client_rect
    width, height = right - left, bottom - top
    bands = title_bands_from_client_rect(client_rect)
    if bands is None:
        return None
    a, b, c, d = roi
    expected = int(width * (c - a)), int(height * (d - b))
    if image.size != expected:
        return None
    rx, ry = int(width * a), int(height * b)
    bounds = {}
    for slot, (x, y, w, h) in bands.items():
        lx, ly = x - rx, y - ry
        if lx < 0 or ly < 0 or lx + w > expected[0] or ly + h > expected[1]:
            return None
        bounds[slot] = lx, ly, lx+w, ly+h
    return {slot: image.crop(bounds[slot]) for slot in SLOTS}


def recognize_title_slot(
    slot: str, crop: Image.Image, augment_names: dict[str, str],
) -> tuple[str, str, int] | None:
    """Read one physical title with the same C2 strict matching contract."""
    if slot not in SLOTS:
        raise ValueError("invalid physical card slot")
    # Experimental V1.2: change the recognizer only, not physical position,
    # offer proof, strict matching, epochs or temporal double reads.
    # Field 24/11 (latency, owner: augments in < 5 s): PP-OCRv4 (~16 ms per
    # crop, in-process) is used whenever its verified model is installed;
    # Tesseract (3-6 process launches per read) stays the fallback.
    # ARAM_ORACLE_OCR_ENGINE=tesseract forces the old engine.
    if os.environ.get("ARAM_ORACLE_OCR_ENGINE", "auto").strip().lower() != "tesseract":
        from backend.collectors.ppocr_v4 import recognize_text
        raw = recognize_text(crop)
        if raw is not None:
            # A working but uncertain v4 must abstain, not seek a more
            # permissive answer from another recognizer.
            return strict_match_title(raw, augment_names, trace_slot=slot)
        # Invalid/missing v4 runtime: preserve the installed Tesseract path.
    from backend.collectors.screen_ocr import preprocess_for_ocr

    processed = preprocess_for_ocr(crop)
    for psm in (7, 6):
        try:
            raw = pytesseract.image_to_string(
                processed, lang="eng", config=f"--psm {psm} --oem 3",
            )
        except (OSError, RuntimeError):
            raw = ""
        match = strict_match_title(raw, augment_names, trace_slot=slot)
        if match is not None:
            return match
    return None


def recognize_title_slots(
    crops: dict[str, Image.Image], augment_names: dict[str, str],
) -> SlotMatches:
    """Use PSM 7 for a line, then PSM 6 if a wrapped title was unreadable."""
    if list(crops) != list(SLOTS):
        raise ValueError("exactly three ordered title crops required")
    matches = {
        slot: recognize_title_slot(slot, crop, augment_names)
        for slot, crop in crops.items()
    }

    # If two slots look identical, do not assign either guessed position.
    locations = {}
    for slot, match in matches.items():
        if match is not None:
            locations.setdefault(match[0], []).append(slot)
    for group in locations.values():
        if len(group) > 1:
            for slot in group:
                matches[slot] = None
    return SlotMatches(matches)
