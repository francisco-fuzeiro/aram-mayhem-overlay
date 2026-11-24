"""P0 field fix: OCR-free card presence probe + read-only cursor pick inference.

Field evidence (Fiora match, 23/11): the cards vanished after every pick and
the overlay never noticed, so it kept asking Alt+1/2/3 and the build never
adapted. While a verified offer (augments or Stat Anvil shards) is on screen,
a fast probe reads only the card-background colour of the three title bands
(no OCR) and the cursor POSITION. When two consecutive probes see the cards
gone, the pick is the one card the cursor sat over in the last second before
they vanished; any doubt abstains and the user confirms with Alt+N.

Policy: GetCursorPos only. Mouse buttons are never read, nothing is clicked
or moved, and positions stay in memory (never logged or stored).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable, Sequence

from backend.collectors.card_title_geometry import title_bands_from_client_rect
from backend.collectors.offer_visibility import card_background_cue
from backend.collectors.pick_clicks import SLOTS, card_body_rects

PROBE_INTERVAL_S = 0.3
ABSENT_PROBES_TO_CLOSE = 2
PICK_WINDOW_S = 1.0
TRAIL_LEN = 40
DOWNSAMPLE = 4


@dataclass(frozen=True)
class Probe:
    t: float
    cue: str           # present | absent | mixed | unavailable
    slot: str | None   # card under the cursor at that instant


def slot_at(point, client_rect, four: bool = False) -> str | None:
    """Card body (client-anchored) containing a desktop point, if any.

    four=True uses the four-card layout (slots c1..c4, field 24/11)."""
    if point is None or client_rect is None:
        return None
    if four:
        from backend.collectors.card_title_geometry import FOUR_SLOTS, four_title_bands
        bands, slots = four_title_bands(tuple(client_rect)), FOUR_SLOTS
    else:
        bands, slots = title_bands_from_client_rect(tuple(client_rect)), SLOTS
    if bands is None:
        return None
    left, top, right, bottom = client_rect
    rects = card_body_rects((left, top, right - left, bottom - top), bands, slots)
    x, y = point
    for slot in slots:
        r = rects[slot]
        if r[0] <= x < r[2] and r[1] <= y < r[3]:
            return slot
    return None


def four_card_cue(crops: dict) -> str:
    """present / absent / mixed over the four title bands (same thresholds)."""
    from backend.collectors.offer_visibility import (
        CARD_BG_ABSENT_MAX, CARD_BG_PRESENT_MIN, card_teal_fraction,
    )
    try:
        fractions = [card_teal_fraction(c) for c in crops.values()]
    except (AttributeError, TypeError, ValueError):
        return "mixed"
    if len(fractions) == 4 and all(f >= CARD_BG_PRESENT_MIN for f in fractions):
        return "present"
    if fractions and all(f <= CARD_BG_ABSENT_MAX for f in fractions):
        return "absent"
    return "mixed"


def _absent_tail(trail: Sequence[Probe]) -> int:
    i = len(trail)
    while i > 0 and trail[i - 1].cue == "absent":
        i -= 1
    return i


def cards_gone(trail: Sequence[Probe]) -> bool:
    """Two consecutive absent probes after the cards were seen present."""
    start = _absent_tail(trail)
    seen = any(p.cue == "present" for p in trail[:start])
    return seen and len(trail) - start >= ABSENT_PROBES_TO_CLOSE


def infer_pick(trail: Sequence[Probe]) -> str | None:
    """The card under the cursor last, within PICK_WINDOW_S before vanishing.

    Field test 23/11 (Master Yi): requiring ONE card in the whole last second
    abstained whenever the player swept over two cards before clicking, so
    every pick needed Alt+N. The click lands on the card the cursor was on
    last; Alt+N still corrects a wrong inference.
    """
    start = _absent_tail(trail)
    if start == 0 or start == len(trail):
        return None
    # Field 24/11 ("automatic pick never works"): the pick animation keeps
    # the cards half-visible ("mixed") for a while, so the cursor sample at
    # the click was older than the window counted from the FIRST absent
    # probe. Anchor the window on the last probe where all cards were still
    # fully present (the moment of the click).
    present = [p for p in trail[:start] if p.cue == "present"]
    anchor = present[-1].t if present else trail[start].t
    recent = [p for p in trail[:start]
              if p.cue != "absent" and anchor - PICK_WINDOW_S <= p.t]
    for probe in reversed(recent):
        if probe.slot is not None:
            return probe.slot
    return None


def downsample(crops: dict) -> dict:
    """Nearest-neighbour shrink: keeps exact colours, ~16x fewer pixels."""
    from PIL import Image
    return {k: v.resize((max(1, v.width // DOWNSAMPLE), max(1, v.height // DOWNSAMPLE)),
                        Image.NEAREST) for k, v in crops.items()}


def read_cursor() -> tuple[int, int] | None:
    """Desktop cursor position (Windows); None elsewhere. Read-only."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        point = wintypes.POINT()
        if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            return None
        return int(point.x), int(point.y)
    except (OSError, AttributeError, ValueError):
        return None


def probe_cards(now: float, cursor: Callable[[], tuple[int, int] | None] = read_cursor,
                four: bool = False) -> Probe:
    """One synchronous OCR-free observation (call through asyncio.to_thread)."""
    from backend.collectors.screen_ocr import (
        capture_augment_region, find_league_window, get_augment_region,
    )
    from backend.collectors.slot_title_ocr import crop_title_slots
    game = find_league_window()
    if game is None:
        return Probe(now, "unavailable", None)
    region = capture_augment_region(league_window=game)
    if region.reason != "ok" or region.image is None:
        return Probe(now, "unavailable", None)
    width, height = game.right - game.left, game.bottom - game.top
    if four:
        from backend.collectors.card_title_geometry import four_title_bands
        bands = four_title_bands(game.rect)
        a, b, _c, _d = get_augment_region(width, height)
        rx, ry = int(width * a), int(height * b)
        if bands is None:
            return Probe(now, "unavailable", None)
        try:
            crops = {s: region.image.crop((x - rx, y - ry, x - rx + w, y - ry + h))
                     for s, (x, y, w, h) in bands.items()}
        except (AttributeError, ValueError):
            return Probe(now, "unavailable", None)
        return Probe(now, four_card_cue(downsample(crops)),
                     slot_at(cursor(), game.rect, four=True))
    crops = crop_title_slots(region.image, game.rect, get_augment_region(width, height))
    if crops is None:
        return Probe(now, "unavailable", None)
    cue = card_background_cue(downsample(crops))
    if cue == "mixed":
        # Field 24/11: four cards read "mixed" through the three bands; their
        # own four bands still open the augment window at once.
        four = probe_cards(now, cursor, four=True)
        if four.cue == "present":
            return Probe(now, "present", None)
    return Probe(now, cue, slot_at(cursor(), game.rect))
