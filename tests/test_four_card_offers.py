"""Field 24/11: Mayhem matches with FOUR-card augment offers (whole match).

Synthetic pixels and titles only; nothing opens League.
"""
from __future__ import annotations

import asyncio

from PIL import Image

from backend.collectors import card_presence as cp
from backend.collectors import screen_ocr, slot_title_ocr
from backend.collectors.card_title_geometry import (
    FOUR_SLOTS, four_title_bands, title_bands_from_client_rect,
)
from backend.collectors.league_window import LeagueWindow
from backend.collectors.window_capture import CaptureProof
from backend.workflow.offer_ledger import LedgerError, OfferLedger

RECT = (0, 0, 2544, 1353)


def test_four_bands_sit_between_the_three_card_positions():
    three = title_bands_from_client_rect(RECT)
    four = four_title_bands(RECT)
    assert list(four) == list(FOUR_SLOTS)
    centres = [x + w / 2 for x, _y, w, _h in four.values()]
    # Measured on the owner's 2546x1385 screenshots: ~580, 1040, 1502, 1964.
    assert [round(c) for c in centres] == [587, 1044, 1500, 1958]
    assert all(v[1:] == three["centre"][1:] for v in four.values())
    assert four_title_bands((0, 0, 500, 300)) is None


def test_cursor_maps_to_four_cards():
    assert cp.slot_at((1043, 600), RECT, four=True) == "c2"
    assert cp.slot_at((1958, 600), RECT, four=True) == "c4"
    assert cp.slot_at((1272, 600), RECT, four=True) in ("c2", "c3", None)
    assert cp.slot_at((1043, 1340), RECT, four=True) is None


def test_four_card_cue_needs_all_four():
    from backend.collectors.offer_visibility import CARD_BG_RGB
    teal = Image.new("RGB", (20, 10), CARD_BG_RGB)
    dark = Image.new("RGB", (20, 10), (0, 0, 0))
    assert cp.four_card_cue({s: teal for s in FOUR_SLOTS}) == "present"
    assert cp.four_card_cue({s: dark for s in FOUR_SLOTS}) == "absent"
    assert cp.four_card_cue({**{s: teal for s in FOUR_SLOTS}, "c4": dark}) == "mixed"


GAME = LeagueWindow(77, 0, 0, 2544, 1353, False)


def _verified(timestamp):
    proof = CaptureProof("wgc", GAME.hwnd, GAME.rect, timestamp, "other")
    w, h = 2544, 1353
    a, b, c, d = screen_ocr.get_augment_region(w, h)
    img = Image.new("RGB", (int(w * (c - a)), int(h * (d - b))), (0, 0, 0))
    return screen_ocr.RegionCapture(img, proof, "ok")


def test_watcher_verifies_four_titles_with_two_reads(monkeypatch):
    frames = [_verified(10.0), _verified(10.6), _verified(12.0)]
    reads = iter([("a", "A", 99), ("b", "B", 98), None, ("d", "D", 97)] * 3)
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: GAME)
    monkeypatch.setattr(screen_ocr, "capture_augment_region",
                        lambda *_a, **_k: frames.pop(0))
    monkeypatch.setattr(screen_ocr.ScreenWatcher, "_four_cards",
                        staticmethod(lambda *_a: True))
    monkeypatch.setattr(slot_title_ocr, "recognize_title_crop",
                        lambda _crop, _names, **_k: next(reads))
    watcher = screen_ocr.ScreenWatcher(sleep_fn=lambda _s: None)
    assert watcher.check({}) == ("transition", None)
    assert [m[0] if m else None for m in watcher.four_offer] == ["a", "b", None, "d"]
    assert watcher.last_scan_stage == "four_titles_detected"
    assert watcher.current_slots is None  # the three-slot pipeline stays closed
    watcher.reset()
    assert watcher.four_offer is None


def test_ledger_confirms_a_four_card_pick_and_allows_correction():
    ledger = OfferLedger((3, 7, 11, 15))
    ledger.on_level(3)
    four = ["a", "b", None, "d"]
    offer = ledger.confirm_four("d", four, inferred=True)
    assert offer.picked_id == "d" and offer.pick_source == "cursor_inferred"
    assert ledger.confirm_four("b", four, inferred=False).picked_id == "b"
    assert ledger.active_augment_ids() == ["b"]
    try:
        ledger.confirm_four("zzz", four, inferred=False)
    except LedgerError as exc:
        assert exc.code == "not_in_offer"
    else:
        raise AssertionError


def test_server_infers_the_four_card_pick_from_the_cursor(monkeypatch):
    from backend.api import server
    from backend.api.server import GameState, _presence_armed, _presence_step
    monkeypatch.setattr(server.static_data, "get_stat_anvil", lambda i: None)
    state = GameState()
    state.match_id = "m"
    state.scan_window_open = True
    state.offer_epoch = state.offer_ledger.on_level(3).epoch
    state.four_offer = ["a", "b", "c", "d"]
    assert _presence_armed(state) == "augment"
    for t, cue, slot in ((0.0, "present", "c3"), (0.3, "absent", None), (0.6, "absent", None)):
        asyncio.run(_presence_step(state, cp.Probe(t, cue, slot), t))
    assert state.chosen_augments == ["c"]
    assert state.four_offer is None and state.scan_window_open is False


def test_shop_frame_is_found_wherever_the_shop_was_dragged():
    from backend.collectors.shop_detect import shop_frame_found
    gold = (200, 160, 90)

    def frame(x0, y0, w, h, size=(1280, 680)):
        img = Image.new("RGB", size, (10, 20, 30))
        px = img.load()
        for x in range(x0, x0 + w):
            px[x, y0] = gold
        for y in range(y0, y0 + h):
            px[x0, y] = px[x0 + w - 1, y] = gold
        return img

    assert shop_frame_found(frame(300, 60, 650, 440))
    assert shop_frame_found(frame(600, 200, 650, 440))     # dragged right/down
    assert not shop_frame_found(frame(500, 130, 200, 330))  # an augment card
    assert not shop_frame_found(frame(300, 60, 650, 100))   # a long bar, no sides
    assert not shop_frame_found(Image.new("RGB", (1280, 680), (0, 0, 0)))


def test_shop_state_is_debounced():
    from backend.api.server import GameState, _shop_step
    state = GameState()
    assert asyncio.run(_shop_step(state, True)) is True and state.shop_open
    assert asyncio.run(_shop_step(state, False)) is False and state.shop_open
    assert asyncio.run(_shop_step(state, None)) is False and state.shop_open
    assert asyncio.run(_shop_step(state, False)) is True and not state.shop_open
