"""M5/C2: strict, position-locked title recognition for Mayhem card bands.

Reads each individual client-relative title crop, never infers position from
confidence-sorted OCR of the whole region. Unknown and duplicate titles fail
closed. No capture, disk access, gameplay input, or diagnostics here.
"""
from __future__ import annotations

import re
from PIL import Image
import pytesseract
from rapidfuzz import fuzz

from backend.collectors.card_title_geometry import title_bands_from_client_rect

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
    text: str, augment_names: dict[str, str],
) -> tuple[str, str, int] | None:
    """Whole-title matching only; best >=90 and beats runner-up by >=8."""
    if not isinstance(text, str) or not isinstance(augment_names, dict):
        return None
    observed = _normalize(text)
    if len(observed) < 4 or not augment_names:
        return None
    scored = []
    for aid, name in augment_names.items():
        if not isinstance(aid, str) or not isinstance(name, str):
            continue
        normalized = _normalize(name)
        if normalized:
            scored.append((fuzz.ratio(observed, normalized), aid, name))
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    best, aid, name = scored[0]
    second = scored[1][0] if len(scored) >= 2 else 0
    if best < MATCH_THRESHOLD or best - second < MIN_MARGIN:
        return None
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


def recognize_title_slots(
    crops: dict[str, Image.Image], augment_names: dict[str, str],
) -> SlotMatches:
    """Use PSM 7 for a line, then PSM 6 if a wrapped title was unreadable."""
    if list(crops) != list(SLOTS):
        raise ValueError("exactly three ordered title crops required")
    from backend.collectors.screen_ocr import preprocess_for_ocr

    matches = {}
    for slot, crop in crops.items():
        processed = preprocess_for_ocr(crop)
        match = None
        for psm in (7, 6):
            try:
                raw = pytesseract.image_to_string(
                    processed, lang="eng", config=f"--psm {psm} --oem 3",
                )
            except (OSError, RuntimeError):
                raw = ""
            match = strict_match_title(raw, augment_names)
            if match:
                break
        matches[slot] = match

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
