"""P0 field fix (Fiora match 23/11): cards vanish -> pick inferred from cursor.

Read-only: the cursor POSITION is sampled while a verified offer is on screen
(GetCursorPos); mouse buttons are never read and nothing is clicked. The pick
is inferred only when the cursor sat over ONE card in the last second before
two OCR-free probes saw the card background vanish. Otherwise Alt+N stays.
"""
import asyncio
from pathlib import Path

from PIL import Image

from backend.collectors import card_presence as cp
from backend.collectors.offer_visibility import card_background_cue
from backend.workflow.offer_ledger import OfferLedger

ROOT = Path(__file__).resolve().parents[1]
RECT = (0, 0, 2560, 1440)


def _trail(*rows):
    return [cp.Probe(t, cue, slot) for t, cue, slot in rows]


def test_cursor_maps_to_card_bodies_in_client_coordinates():
    assert cp.slot_at((1280, 600), RECT) == "centre"
    assert cp.slot_at((1280 - 660, 600), RECT) == "left"
    assert cp.slot_at((1280 + 660, 600), RECT) == "right"
    assert cp.slot_at((1280, 1400), RECT) is None   # below cards (reroll/HUD)
    assert cp.slot_at((1280 + 1000, 600), (1000, 0, 3560, 1440)) == "centre"
    assert cp.slot_at(None, RECT) is None


def test_pick_is_the_single_card_under_the_cursor_just_before_vanishing():
    trail = _trail((0.0, "present", None), (0.3, "present", "left"),
                   (0.6, "present", "left"), (0.9, "absent", "centre"),
                   (1.2, "absent", "centre"))
    assert cp.infer_pick(trail) == "left"


def test_cursor_moving_to_the_champion_after_the_click_is_ignored():
    # The cursor rests on the centre AFTER the cards are gone: not evidence.
    trail = _trail((0.0, "present", "right"), (0.3, "absent", "centre"),
                   (0.6, "absent", "centre"), (5.0, "absent", "centre"))
    assert cp.infer_pick(trail) == "right"


def test_two_cards_in_the_last_second_or_no_card_abstains():
    assert cp.infer_pick(_trail((0.0, "present", "left"), (0.3, "present", "centre"),
                                (0.6, "absent", None), (0.9, "absent", None))) is None
    assert cp.infer_pick(_trail((0.0, "present", None), (0.3, "absent", None),
                                (0.6, "absent", None))) is None
    # Old hover (> 1 s before vanishing) is not evidence either.
    assert cp.infer_pick(_trail((0.0, "present", "left"), (2.0, "present", None),
                                (2.3, "absent", None), (2.6, "absent", None))) is None


def test_one_absent_probe_never_closes():
    assert not cp.cards_gone(_trail((0.0, "present", "left"), (0.3, "absent", None)))
    assert cp.cards_gone(_trail((0.0, "present", "left"), (0.3, "absent", None),
                                (0.6, "absent", None)))
    assert not cp.cards_gone(_trail((0.3, "absent", None), (0.6, "absent", None)))
    assert not cp.cards_gone(_trail((0.0, "present", "left"), (0.3, "absent", None),
                                    (0.6, "unavailable", None)))


def test_downsampled_cue_keeps_the_real_fixture_verdicts():
    titles = sorted((ROOT / "tests/fixtures/ocr_titles/1440p").glob("*.png"))[:3]
    negatives = sorted((ROOT / "tests/fixtures/ocr_titles/no_offer").glob("*.png"))[:3]
    for paths, expected in ((titles, "present"), (negatives, "absent")):
        crops = dict(zip(("left", "centre", "right"),
                         (Image.open(p).convert("RGB") for p in paths)))
        assert card_background_cue(crops) == expected
        assert card_background_cue(cp.downsample(crops)) == expected


def test_policy_reads_position_only_never_buttons():
    source = (ROOT / "backend/collectors/card_presence.py").read_text(encoding="utf-8")
    assert "GetCursorPos" in source
    for banned in ("VK_LBUTTON", "GetAsyncKeyState", "GetKeyState", "SendInput",
                   "mouse_event", "SetCursorPos"):
        assert banned not in source


def visible_offer():
    ledger = OfferLedger((3, 7, 11, 15))
    offer = ledger.on_level(3)
    ledger.on_verified_titles({"left": "2083", "centre": "1038", "right": "3129"},
                              offer.epoch)
    return ledger, offer


def test_inferred_pick_is_correctable_by_alt_n():
    ledger, offer = visible_offer()
    picked = ledger.confirm_inferred("centre")
    assert picked.state == "confirmed" and picked.pick_source == "cursor_inferred"
    assert ledger.active_augment_ids() == [offer.slots["centre"].augment_id]
    fixed = ledger.confirm_slot("left")
    assert fixed.pick_source == "user_confirm"
    assert ledger.active_augment_ids() == [offer.slots["left"].augment_id]


def test_inferred_pick_never_overrides_a_manual_pick():
    ledger, offer = visible_offer()
    ledger.confirm_slot("right")
    import pytest
    from backend.workflow.offer_ledger import LedgerError
    with pytest.raises(LedgerError):
        ledger.confirm_inferred("left")
    assert ledger.active_augment_ids() == [offer.slots["right"].augment_id]


# -- server: the probe step closes the offer and saves the inferred pick ------

def _server_state():
    from backend.api.server import GameState
    state = GameState()
    state.match_id = "m"
    state.scan_window_open = True
    offer = state.offer_ledger.on_level(3)
    state.offer_epoch = offer.epoch
    state.offer_ledger.on_verified_titles(
        {"left": "2083", "centre": "1038", "right": "3129"}, offer.epoch)
    state.ocr_slot_choices = {"left": "2083", "centre": "1038", "right": "3129"}
    state.augment_choices[:] = ["2083", "1038", "3129"]
    return state


def _feed(state, *rows):
    from backend.api.server import _presence_step
    out = []
    for t, cue, slot in rows:
        out.append(asyncio.run(_presence_step(state, cp.Probe(t, cue, slot), t)))
    return out


def test_augment_cards_gone_with_cursor_saves_the_pick_and_closes(monkeypatch):
    from backend.api import server
    monkeypatch.setattr(server.static_data, "get_stat_anvil", lambda i: None)
    state = _server_state()
    _feed(state, (0.0, "present", "centre"), (0.3, "absent", None), (0.6, "absent", None))
    assert state.chosen_augments == ["1038"]
    assert state.offer_ledger.offers[-1].pick_source == "cursor_inferred"
    assert state.scan_window_open is False and state.confirmation_pending is False


def test_augment_cards_gone_without_cursor_evidence_keeps_alt_n(monkeypatch):
    from backend.api import server
    monkeypatch.setattr(server.static_data, "get_stat_anvil", lambda i: None)
    state = _server_state()
    _feed(state, (0.0, "present", None), (0.3, "absent", None), (0.6, "absent", None))
    assert state.chosen_augments == []
    assert state.scan_window_open is False
    assert state.confirmation_pending is True and state.awaiting_stat_delta is True


def test_probe_is_idle_without_a_verified_offer():
    from backend.api.server import GameState, _presence_armed
    state = GameState()
    assert _presence_armed(state) is None
    state.match_id = "m"
    state.scan_window_open = True
    state.ocr_slot_choices = {"left": "2083", "centre": None, "right": "3129"}
    assert _presence_armed(state) is None
