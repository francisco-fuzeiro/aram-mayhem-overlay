"""M5/C2: strict slot-locked title OCR; no confidence-sorted card identity.

Tests use deterministic synthetic title images and injected Tesseract outputs.
Real title-band screenshot evidence is separately reviewed outside Git.
"""
from PIL import Image, ImageDraw
import pytest

from backend.collectors import screen_ocr
from backend.collectors.card_title_geometry import title_bands_from_client_rect
from backend.collectors.slot_title_ocr import (
    SLOTS, SlotMatches, strict_match_title, recognize_title_slots,
    crop_title_slots,
)


NAMES = {
    "1": "En Passant",
    "2": "Ravenous Bind",
    "3": "It's Killing Time",
    "4": "Take'em Down Down Down",
    "5": "En Passant Deluxe",
}


def test_strict_whole_title_not_substrings_or_descriptions():
    assert strict_match_title("En Passant", NAMES) == ("1", "En Passant", 100)
    assert strict_match_title("It s Killing Time", NAMES) == ("3", "It's Killing Time", 100)
    assert strict_match_title("Take'em Down Down\nDown", NAMES) == (
        "4", "Take'em Down Down Down", 100,
    )
    assert strict_match_title("En Passant Deluxe", NAMES) == (
        "5", "En Passant Deluxe", 100,
    )
    assert strict_match_title("En Passant on champions grants movement speed", NAMES) is None
    assert strict_match_title("En Pas", NAMES) is None
    assert strict_match_title("Damage Utility Speed", NAMES) is None


def test_ambiguous_catalog_names_fail_closed():
    names = {"1": "En Passant", "2": "En Paszant"}
    assert strict_match_title("En Paszant", names) == ("2", "En Paszant", 100)
    assert strict_match_title("En Pasxant", names) is None
    assert strict_match_title("Unique", {"1": "Unique", "2": "Unique"}) == ("1", "Unique", 100)


def test_read_each_slot_and_preserve_left_centre_right_not_confidence_rank(monkeypatch):
    crops = {slot: Image.new("RGB", (340, 90)) for slot in SLOTS}
    # Different scores would historically sort Ravenous Bind first. Slots win.
    ocr = iter(["En Pasant", "Ravenous Bind", "It s Killing Time"])
    monkeypatch.setattr(screen_ocr.pytesseract, "image_to_string", lambda *_a, **_k: next(ocr))
    result = recognize_title_slots(crops, NAMES)
    assert isinstance(result, SlotMatches)
    assert list(result.slots) == ["left", "centre", "right"]
    assert result.slots["left"][0] == "1"
    assert result.slots["centre"][0] == "2"
    assert result.slots["right"][0] == "3"
    assert [r[0] for r in result] == ["1", "2", "3"]


def test_wrapped_title_psm7_failure_uses_psm6_in_same_slot(monkeypatch):
    crops = {slot: Image.new("RGB", (340, 90)) for slot in SLOTS}
    seen = []
    def fake_ocr(_im, *, lang, config):
        seen.append(config)
        if len(seen) == 1:
            return "PO ee Down |"  # observed psm7 can fuse two-line titles
        if len(seen) == 2:
            return "Take'em Down Down\nDown"
        return {"left": "n/a", "centre": "Ravenous Bind", "right": "It's Killing Time"}["centre"]
    monkeypatch.setattr(screen_ocr.pytesseract, "image_to_string", fake_ocr)
    result = recognize_title_slots(crops, NAMES)
    assert result.slots["left"][0] == "4"
    assert "--psm 7" in seen[0]
    assert "--psm 6" in seen[1]


def test_unknown_card_cannot_shift_other_identified_slots(monkeypatch):
    crops = {slot: Image.new("RGB", (340, 90)) for slot in SLOTS}
    texts = iter(["Dialogue obscures title", "Still obscured", "Ravenous Bind", "It's Killing Time"])
    monkeypatch.setattr(screen_ocr.pytesseract, "image_to_string", lambda *_a, **_k: next(texts))
    result = recognize_title_slots(crops, NAMES)
    assert list(result.slots) == ["left", "centre", "right"]
    assert result.slots["left"] is None
    assert result.slots["centre"][0] == "2"
    assert result.slots["right"][0] == "3"
    assert [v[0] for v in result] == ["2", "3"]


def test_duplicate_identifications_are_unknown_not_two_cards(monkeypatch):
    crops = {slot: Image.new("RGB", (340, 90)) for slot in SLOTS}
    texts = iter(["Ravenous Bind", "Ravenous Bind", "It's Killing Time"])
    monkeypatch.setattr(screen_ocr.pytesseract, "image_to_string", lambda *_a, **_k: next(texts))
    result = recognize_title_slots(crops, NAMES)
    assert result.slots["left"] is None
    assert result.slots["centre"] is None
    assert result.slots["right"][0] == "3"


def test_explicit_unknown_all_slots_still_has_three_positions(monkeypatch):
    crops = {slot: Image.new("RGB", (340, 90)) for slot in SLOTS}
    monkeypatch.setattr(screen_ocr.pytesseract, "image_to_string",
                        lambda *_a, **_k: "Overlapping dialogue")
    result = recognize_title_slots(crops, NAMES)
    assert not result
    assert result.slots == dict.fromkeys(SLOTS)


def test_crop_uses_actual_client_origin_never_full_desktop():
    w, h = 2544, 1353
    strip = Image.new("RGB", (int(w * 0.70), int(h * 0.28)))
    draw = ImageDraw.Draw(strip)
    colors = {"left": (255, 0, 0), "centre": (0, 255, 0), "right": (0, 0, 255)}
    for slot, (x, y, bw, bh) in title_bands_from_client_rect((8, 31, 2552, 1384)).items():
        lx, ly = x - int(w * .15), y - int(h * .22)
        draw.rectangle((lx, ly, lx+bw-1, ly+bh-1), fill=colors[slot])
    crops = crop_title_slots(strip, (8, 31, 2552, 1384), (.15,.22,.85,.50))
    assert crops is not None
    assert list(crops) == list(SLOTS)
    for slot, crop in crops.items():
        assert crop.size == (340, 90)
        assert crop.getpixel((10, 10)) == colors[slot]
    assert crop_title_slots(strip, (8,31,2552,1384),(.15,.22,.4,.50)) is None


def test_no_real_title_crops_on_unsupported_resolution():
    assert crop_title_slots(
        Image.new("RGB", (1900, 400)),
        (0, 0, 2560, 1080),
        (.15,.22,.85,.50),
    ) is None


def test_watcher_emits_slot_matches_and_never_calls_legacy_whole_region(monkeypatch):
    from backend.collectors.league_window import LeagueWindow
    window = LeagueWindow(7,8,31,2552,1384,True)
    strip = Image.new("RGB", (int(2544*.70), int(1353*.28)))
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: window)
    from backend.collectors.window_capture import CaptureProof
    monkeypatch.setattr(screen_ocr, "capture_augment_region", lambda *a, **kw:
                        screen_ocr.RegionCapture(
                            strip, CaptureProof("wgc", window.hwnd, window.rect,
                                                10.0, "league"), "ok"))
    monkeypatch.setattr(screen_ocr, "extract_text", lambda *a, **kw:
                        pytest.fail("legacy whole-ROI OCR was called"))
    known = {"left": ("1", "En Passant", 96),
             "centre": ("2", "Ravenous Bind", 100),
             "right": ("3", "It's Killing Time", 100)}
    monkeypatch.setattr(screen_ocr, "_perceptual_hash", lambda _im: "0" * 64)
    from backend.collectors import slot_title_ocr
    monkeypatch.setattr(slot_title_ocr, "recognize_title_slot",
                        lambda slot, _crop, _names: known[slot])
    # C3: one provisional frame cannot be published as three confirmed cards.
    watcher = screen_ocr.ScreenWatcher()
    assert watcher.check(NAMES)[0] == "no_augments"
    action, matches = watcher.check(NAMES)
    assert action == "detected"
    assert matches.slots["left"][0] == "1"
    assert [m[0] for m in matches] == ["1","2","3"]


@pytest.mark.asyncio
async def test_rest_scan_all_unknowns_clear_stale_previous_card_ids(monkeypatch):
    from backend.api import server
    monkeypatch.setattr(server, "game_state", server.GameState())
    monkeypatch.setattr(server, "ocr_available", lambda: True)
    monkeypatch.setattr(server, "detect_augments", lambda names, *, save: SlotMatches(
        {"left": None, "centre": None, "right": None},
    ))
    server.game_state.augment_choices = ["previous"]
    server.game_state.ocr_last_detected = ["previous"]
    server.game_state.ocr_slot_choices = {
        "left": "previous", "centre": None, "right": None,
    }
    server.game_state.scan_window_open = True
    server.game_state.offer_lifecycle.open()
    result = await server.ocr_scan()
    assert result["augment_choices_set"] == []
    assert result["ocr_slots"] == dict.fromkeys(SLOTS)
    assert [d["slot"] for d in result["detected"]] == list(SLOTS)
    assert all(d["id"] is None for d in result["detected"])
    assert server.game_state.ocr_last_detected == []


def test_manual_scan_labels_partial_offer_without_shifting_slots(monkeypatch):
    from backend.api import server
    monkeypatch.setattr(server, "detect_augments", lambda names, *, save: SlotMatches(
        {"left": None, "centre": ("2", "Ravenous Bind", 100),
         "right": ("3", "It's Killing Time", 99)},
    ))
    ids, detected = server._run_ocr_scan_manual()
    assert ids == ["2", "3"]
    assert [d["slot"] for d in detected] == list(SLOTS)
    assert [d["id"] for d in detected] == [None, "2", "3"]


@pytest.mark.asyncio
async def test_live_poll_serializes_explicit_unknown_position_without_stealing_next_card():
    from tests.test_poll_tick_m1 import make_harness, make_snapshot
    from backend.api.server import poll_tick
    state, deps, messages = make_harness(
        [{"tick": 1}], [make_snapshot()], ocr=True,
        watcher_result=("detected", ["2", "3"], [
            {"slot": "left", "id": None, "name": None, "confidence": 0},
            {"slot": "centre", "id": "2", "name": "Ravenous Bind", "confidence": 100},
            {"slot": "right", "id": "3", "name": "It's Killing Time", "confidence": 99},
        ]),
    )
    await poll_tick(state, deps, 30.0)
    assert state.augment_choices == ["2", "3"]
    assert state.ocr_slot_choices == {
        "left": None, "centre": "2", "right": "3",
    }
    assert messages[0]["type"] == "ocr_result"
    assert [d["id"] for d in messages[0]["detected"]] == [None, "2", "3"]


def test_duplicate_slot_payload_is_rejected_before_mapping_to_ui():
    from backend.api.server import _slots_from_detected
    assert _slots_from_detected([
        {"slot": "left", "id": "same"},
        {"slot": "centre", "id": "same"},
        {"slot": "right", "id": "other"},
    ]) is None
