"""M1/P0.1: deterministic, in-memory regression harness for one poll tick.

Strict expected failures preserve documented AUD defects until M2/M3 changes.
No League client, Tesseract, screenshot or Windows session is required.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.api.server import GameState, poll_tick


def make_snapshot(level=3, *, dead=False, hp=1.0, attack_damage=100.0, items=()):
    return SimpleNamespace(
        level=level,
        is_dead=dead,
        health_pct=hp,
        champion_stats={"attackDamage": attack_damage, "maxHealth": 1000.0},
        augment_choices=[],
        chosen_augments=[],
        purchased_items=list(items),
        build_style="Balanced",
    )


def make_harness(raw_values, snapshots, *, ocr=False, watcher_result=None):
    state = GameState()
    state.ws_clients.add(object())  # enables the production polling path
    state.pipeline = None
    events = []
    watcher = SimpleNamespace(reset=Mock())
    raws = iter(raw_values)
    parsed = iter(snapshots)

    async def fake_thread(fn):
        return fn()

    async def broadcast(payload):
        events.append(json.loads(payload))

    async def match(_snapshot):
        # Model the existing auto-pick side effect when the delta path fires.
        state.chosen_augments.append("phantom-pick")

    async def confirm(_candidate):
        events.append({"type": "augment_confirm"})

    deps = SimpleNamespace(
        get_raw_game_data=lambda: next(raws),
        parse_game_snapshot=lambda _raw, _phase: next(parsed),
        read_champ_select_payload=lambda: None,
        ocr_available=lambda: ocr,
        run_watcher_check=lambda: watcher_result or ("unchanged", [], None),
        screen_watcher=watcher,
        to_thread=fake_thread,
        broadcast=broadcast,
        try_stat_delta_match=match,
        send_augment_confirm=confirm,
        serialize_result=lambda *args: {},
        static_data=object(),
    )
    return state, deps, events


@pytest.mark.asyncio
async def test_poll_tick_has_no_side_effects_without_clients():
    state, deps, events = make_harness([], [])
    state.ws_clients.clear()
    await poll_tick(state, deps, 1.0)
    assert events == []
    assert state.had_game_last_tick is False


@pytest.mark.asyncio
async def test_poll_tick_opens_eligible_offer_and_injects_ocr_result():
    state, deps, events = make_harness(
        [{"tick": 1}], [make_snapshot()],
        ocr=True,
        watcher_result=("detected", ["card-a", "card-b"], [
            {"id": "card-a", "name": "A", "confidence": 0.9},
            {"id": "card-b", "name": "B", "confidence": 0.8},
        ]),
    )
    await poll_tick(state, deps, 42.0)
    assert state.scan_window_open
    assert state.scan_window_level == 3
    assert state.augment_choices == ["card-a", "card-b"]
    assert events[0]["type"] == "ocr_result"
    deps.screen_watcher.reset.assert_called_once()


@pytest.mark.asyncio
async def test_v12_new_due_offer_invalidates_previous_ocr_while_scan_remains_open():
    """A new level's offer cannot inherit the prior offer's proven names.

    Reproduces the source-level transition after a first offer remains open
    (no authoritative automatic picked-augment event exists yet). Both scans
    are synthetic; a missing new title is not evidence of a picked card.
    """
    old = [
        {"slot": "left", "id": "first-left", "name": "Synthetic First Left", "confidence": 98},
        {"slot": "centre", "id": "first-centre", "name": "Synthetic First Centre", "confidence": 98},
        {"slot": "right", "id": "first-right", "name": "Synthetic First Right", "confidence": 98},
    ]
    state, deps, _events = make_harness(
        [{"tick": 1}, {"tick": 2}],
        [make_snapshot(level=3), make_snapshot(level=7)],
        ocr=True,
    )
    deps.run_watcher_check = Mock(side_effect=[
        ("detected", [row["id"] for row in old], old),
        ("no_augments", [], None),
    ])

    await poll_tick(state, deps, 50.0)
    assert state.scan_window_open
    assert state.offer_state == "present"
    assert state.ocr_slot_choices == {
        "left": "first-left", "centre": "first-centre", "right": "first-right",
    }
    first_epoch = state.offer_epoch

    await poll_tick(state, deps, 52.0)
    assert len(state.offer_ledger.offers) == 2
    assert state.offer_epoch > first_epoch
    assert state.offer_ledger.offers[-1].state == "due"
    # A next-offer due transition must invalidate all previously recognized
    # candidates before the watcher can identify *new* cards.
    assert state.augment_choices == []
    assert state.ocr_slot_choices is None
    assert state.ocr_last_detected == []
    assert state.offer_state == "pending"
    assert state.ocr_phase != "detected"
    assert deps.screen_watcher.reset.call_count == 2
    assert state.chosen_augments == []


@pytest.mark.asyncio
async def test_v12_due_offer_rejects_previous_verified_triple_replayed_after_reset():
    """Fresh OCR of *old physical cards* is not evidence of the next offer.

    A new level may become due before the previous cards visually disappear.
    Resetting hashes alone allows the same old three identities to be read
    twice and wrongly published in a later epoch. Reopen only on an
    independently checked, changed three-slot observation.
    """
    old = [
        {"slot": "left", "id": "old-left", "name": "Synthetic Old Left", "confidence": 98},
        {"slot": "centre", "id": "old-centre", "name": "Synthetic Old Centre", "confidence": 99},
        {"slot": "right", "id": "old-right", "name": "Synthetic Old Right", "confidence": 97},
    ]
    new = [
        {"slot": "left", "id": "new-left", "name": "Synthetic New Left", "confidence": 98},
        {"slot": "centre", "id": "new-centre", "name": "Synthetic New Centre", "confidence": 99},
        {"slot": "right", "id": "new-right", "name": "Synthetic New Right", "confidence": 97},
    ]
    state, deps, events = make_harness(
        [{"tick": 1}, {"tick": 2}, {"tick": 3}],
        [make_snapshot(level=3), make_snapshot(level=7), make_snapshot(level=7)],
        ocr=True,
    )
    deps.run_watcher_check = Mock(side_effect=[
        ("detected", [row["id"] for row in old], old),
        ("detected", [row["id"] for row in old], old),
        ("detected", [row["id"] for row in new], new),
    ])
    await poll_tick(state, deps, 100.0)
    assert state.offer_state == "present"
    assert state.ocr_slot_choices["left"] == "old-left"
    first_epoch = state.offer_epoch
    first_ledger = state.offer_ledger.offers[0]

    before_new_tick = len(events)
    await poll_tick(state, deps, 102.0)
    assert len(state.offer_ledger.offers) == 2
    assert state.offer_epoch > first_epoch
    assert state.offer_state != "present"
    assert state.ocr_phase != "detected"
    assert state.augment_choices == []
    assert state.ocr_slot_choices is None
    assert state.offer_ledger.offers[-1].state == "due"
    assert all(identity.augment_id is None
               for identity in state.offer_ledger.offers[-1].slots.values())
    assert not any(event.get("type") == "ocr_result"
                   and event.get("status") == "detected"
                   for event in events[before_new_tick:])
    assert first_ledger.slots["left"].augment_id == "old-left"
    assert state.chosen_augments == []

    await poll_tick(state, deps, 104.0)
    assert state.offer_state == "present"
    assert state.ocr_slot_choices == {
        "left": "new-left", "centre": "new-centre", "right": "new-right",
    }
    assert state.offer_ledger.offers[-1].slots["left"].augment_id == "new-left"
    assert state.chosen_augments == []


@pytest.mark.asyncio
async def test_poll_tick_inactive_without_match_sends_no_game():
    state, deps, events = make_harness([None], [])
    await poll_tick(state, deps, 8.0)
    assert events == [{"type": "no_game"}]
    assert not state.post_game


@pytest.mark.asyncio
async def test_aud03a_level_up_must_not_be_treated_as_augment_pick():
    state, deps, _events = make_harness(
        [{"tick": 1}, {"tick": 2}, {"tick": 3}, {"tick": 4}],
        [make_snapshot(), make_snapshot(level=4, attack_damage=125),
         make_snapshot(level=4, attack_damage=125),
         make_snapshot(level=4, attack_damage=125)],
    )
    await poll_tick(state, deps, 10.0)
    await poll_tick(state, deps, 12.0)
    await poll_tick(state, deps, 14.0)
    await poll_tick(state, deps, 16.0)
    assert state.chosen_augments == []
    assert not state.awaiting_stat_delta


@pytest.mark.asyncio
async def test_a1_item_purchase_during_offer_does_not_infer_pick():
    state, deps, _events = make_harness(
        [{"tick": tick} for tick in range(4)],
        [make_snapshot(attack_damage=100.0)]
        + [make_snapshot(attack_damage=145.0) for _ in range(3)],
    )
    for tick in range(4):
        await poll_tick(state, deps, 20.0 + 2 * tick)
    assert state.scan_window_open
    assert state.chosen_augments == []
    assert not state.awaiting_stat_delta


@pytest.mark.asyncio
async def test_a1_death_respawn_with_stat_changes_does_not_infer_pick():
    state, deps, _events = make_harness(
        [{"tick": tick} for tick in range(5)],
        [
            make_snapshot(),
            make_snapshot(dead=True, hp=0.0, attack_damage=110.0),
            make_snapshot(dead=True, hp=0.0, attack_damage=110.0),
            make_snapshot(dead=False, attack_damage=130.0),
            make_snapshot(dead=False, attack_damage=130.0),
        ],
    )
    for tick in range(5):
        await poll_tick(state, deps, 30.0 + 2 * tick)
    assert state.chosen_augments == []
    assert not state.awaiting_stat_delta


@pytest.mark.asyncio
async def test_a1_watcher_disappearance_still_arms_the_separate_confirmation_path():
    state, deps, _events = make_harness(
        [{"tick": 1}],
        [make_snapshot()],
        ocr=True,
        watcher_result=("disappeared", [], None),
    )
    await poll_tick(state, deps, 40.0)
    assert state.awaiting_stat_delta
    assert state.chosen_augments == []


@pytest.mark.asyncio
async def test_aud07_one_lcda_miss_must_not_end_existing_game():
    state, deps, events = make_harness(
        [{"tick": 1}, None], [make_snapshot()],
    )
    await poll_tick(state, deps, 10.0)
    await poll_tick(state, deps, 12.0)
    assert state.had_game_last_tick
    assert not state.post_game
    assert not any(event["type"] == "game_ended" for event in events)


@pytest.mark.asyncio
async def test_a2_level_seven_offer_at_sixty_percent_hp_still_scans():
    state, deps, events = make_harness(
        [{"tick": 1}, {"tick": 2}],
        [make_snapshot(level=7, hp=0.60), make_snapshot(level=7, hp=0.45)],
        ocr=True,
    )
    # A previous pick is already recorded; this is the newly due level-7 offer.
    state.chosen_augments.append("previous-pick")
    state.last_known_level = 6
    checks = Mock(return_value=("unchanged", [], None))
    deps.run_watcher_check = checks

    await poll_tick(state, deps, 20.0)
    assert state.scan_window_open
    assert state.scan_window_level == 7
    assert checks.call_count == 1

    await poll_tick(state, deps, 22.0)
    assert state.scan_window_open
    assert checks.call_count == 2
    assert state.chosen_augments == ["previous-pick"]
    assert not state.awaiting_stat_delta
    assert not any(event["type"] == "augment_confirm" for event in events)


@pytest.mark.asyncio
async def test_a2_damage_does_not_discard_detected_choices_or_request_confirmation():
    state, deps, events = make_harness(
        [{"tick": 1}, {"tick": 2}],
        [make_snapshot(), make_snapshot(hp=0.55)],
        ocr=True,
        watcher_result=("detected", ["left", "middle", "right"], [
            {"id": "left", "name": "Left", "confidence": 0.9},
            {"id": "middle", "name": "Middle", "confidence": 0.9},
            {"id": "right", "name": "Right", "confidence": 0.9},
        ]),
    )
    await poll_tick(state, deps, 30.0)
    assert state.augment_choices == ["left", "middle", "right"]

    deps.run_watcher_check = Mock(return_value=("unchanged", [], None))
    await poll_tick(state, deps, 32.0)
    assert state.scan_window_open
    assert state.augment_choices == ["left", "middle", "right"]
    assert state.chosen_augments == []
    assert not any(event["type"] == "augment_confirm" for event in events)
    deps.run_watcher_check.assert_called_once()


@pytest.mark.asyncio
async def test_a2_ocr_disappearance_at_low_hp_keeps_existing_confirmation_path():
    state, deps, events = make_harness(
        [{"tick": 1}, {"tick": 2}],
        [make_snapshot(), make_snapshot(hp=0.40)],
        ocr=True,
    )
    await poll_tick(state, deps, 40.0)
    deps.run_watcher_check = Mock(return_value=("disappeared", [], None))
    await poll_tick(state, deps, 42.0)
    assert not state.scan_window_open
    assert state.awaiting_stat_delta
    assert state.confirmation_pending
    assert state.chosen_augments == []
    assert not any(event["type"] == "augment_confirm" for event in events)
    deps.run_watcher_check.assert_called_once()


@pytest.mark.asyncio
async def test_aud03d_damage_must_not_close_ocr_window():
    state, deps, events = make_harness(
        [{"tick": 1}, {"tick": 2}],
        [make_snapshot(), make_snapshot(hp=0.75)],
    )
    await poll_tick(state, deps, 10.0)
    assert state.scan_window_open
    await poll_tick(state, deps, 12.0)
    assert state.scan_window_open


@pytest.mark.asyncio
async def test_a3_disappeared_offer_prompts_once_and_never_auto_chooses():
    state, deps, events = make_harness(
        [{"tick": i} for i in range(5)],
        [make_snapshot() for _ in range(5)],
        ocr=True,
        watcher_result=("disappeared", [], None),
    )
    matches = []

    async def deferred_match(snapshot):
        matches.append(snapshot.level)
        events.append({"type": "augment_confirm", "best_guess_id": None})

    deps.try_stat_delta_match = deferred_match
    watcher_checks = Mock(return_value=("disappeared", [], None))
    deps.run_watcher_check = watcher_checks

    await poll_tick(state, deps, 10.0)
    assert not state.scan_window_open
    assert state.confirmation_pending
    assert state.awaiting_stat_delta
    assert state.chosen_augments == []
    assert matches == []

    for tick in range(1, 5):
        await poll_tick(state, deps, 10.0 + tick * 2)

    assert matches == [3]
    assert state.confirmation_pending
    assert not state.awaiting_stat_delta
    assert state.chosen_augments == []
    assert [event["type"] for event in events].count("augment_confirm") == 1
    watcher_checks.assert_called_once()


@pytest.mark.asyncio
async def test_a3_level_change_while_confirmation_pending_does_not_reopen_scan():
    state, deps, _events = make_harness(
        [{"tick": i} for i in range(3)],
        [make_snapshot(level=3), make_snapshot(level=7), make_snapshot(level=7)],
        ocr=True,
        watcher_result=("disappeared", [], None),
    )
    async def deferred_match(_snapshot):
        pass

    deps.try_stat_delta_match = deferred_match
    await poll_tick(state, deps, 10.0)
    await poll_tick(state, deps, 12.0)
    await poll_tick(state, deps, 14.0)
    assert state.confirmation_pending
    assert not state.scan_window_open
    assert state.chosen_augments == []


@pytest.mark.asyncio
async def test_c4_due_level_is_not_an_offer():
    state, deps, events = make_harness(
        [{"tick": 1}], [make_snapshot()], ocr=True,
        watcher_result=("no_augments", [], None),
    )
    await poll_tick(state, deps, 42.0)
    assert state.scan_window_open
    assert state.offer_state == "pending"
    assert not state.chosen_augments


@pytest.mark.asyncio
async def test_c4_confirmed_title_offer_has_explicit_visible_ws_state():
    state, deps, events = make_harness(
        [{"tick": 1}], [make_snapshot()], ocr=True,
        watcher_result=("detected", ["en"], [
            {"slot": "left", "id": "en", "name": "En Passant", "confidence": 98},
            {"slot": "centre", "id": None, "name": None, "confidence": 0},
            {"slot": "right", "id": None, "name": None, "confidence": 0},
        ]),
    )
    await poll_tick(state, deps, 42.0)
    assert state.offer_state == "present"
    assert events[0]["offer_state"] == "present"
    assert events[0]["status"] == "detected"
    assert state.chosen_augments == []


@pytest.mark.asyncio
async def test_c4_all_unknown_titles_are_uncertain_not_gone_or_picked():
    state, deps, events = make_harness(
        [{"tick": 1}], [make_snapshot()], ocr=True,
        watcher_result=("detected", [], [
            {"slot": "left", "id": None, "name": None, "confidence": 0},
            {"slot": "centre", "id": None, "name": None, "confidence": 0},
            {"slot": "right", "id": None, "name": None, "confidence": 0},
        ]),
    )
    await poll_tick(state, deps, 42.0)
    assert state.offer_state == "uncertain"
    assert state.scan_window_open
    assert not state.confirmation_pending
    assert not state.chosen_augments
    assert events[0]["offer_state"] == "uncertain"


@pytest.mark.asyncio
async def test_c4_verified_offer_occlusion_suspends_without_clearing_or_choosing():
    state, deps, events = make_harness(
        [{"tick": 1}], [make_snapshot()], ocr=True,
        watcher_result=("occluded", [], None),
    )
    state.scan_window_open = True
    state.offer_lifecycle.open()
    state.set_ocr_phase("detected")
    await poll_tick(state, deps, 42.0)
    assert state.offer_state == "suspended"
    assert state.ocr_stale is True
    assert state.scan_window_open
    assert not state.chosen_augments
    assert events[0]["offer_state"] == "suspended"


@pytest.mark.asyncio
async def test_c4_legacy_verified_disappearance_never_auto_selects_a_card():
    state, deps, events = make_harness(
        [{"tick": 1}], [make_snapshot()], ocr=True,
        watcher_result=("disappeared", [], None),
    )
    await poll_tick(state, deps, 42.0)
    assert state.offer_state == "gone"
    assert not state.scan_window_open
    assert state.confirmation_pending
    assert state.chosen_augments == []
    assert events[0]["status"] == "disappeared"
    assert events[0]["offer_state"] == "gone"

@pytest.mark.asyncio
async def test_c4b_pending_title_change_hides_unverified_old_offer_without_pick():
    state, deps, events = make_harness(
        [{"tick": 1}, {"tick": 2}],
        [make_snapshot(), make_snapshot()],
        ocr=True,
        watcher_result=("transition", [], None),
    )
    await poll_tick(state, deps, 42.0)
    assert state.scan_window_open
    assert state.offer_state == "pending"
    await poll_tick(state, deps, 43.0)
    assert state.offer_state == "pending"
    assert not state.confirmation_pending
    assert not state.chosen_augments


@pytest.mark.asyncio
async def test_c4b_transition_after_valid_offer_sends_uncertain_without_clearing_picks():
    state, deps, events = make_harness(
        [{"tick": 1}, {"tick": 2}],
        [make_snapshot(), make_snapshot()],
        ocr=True,
        watcher_result=("transition", [], None),
    )
    state.scan_window_open = True
    state.offer_lifecycle.open()
    state.offer_lifecycle.observe("detected", identified=3)
    state.augment_choices[:] = ["en", "bind", "kill"]
    await poll_tick(state, deps, 44.0)
    assert state.offer_state == "uncertain"
    assert state.scan_window_open
    assert state.augment_choices == ["en", "bind", "kill"]
    assert state.chosen_augments == []
    assert any(e.get("status") == "transition" and
               e.get("offer_state") == "uncertain" for e in events)
