"""M1/P0.1: deterministic, in-memory regression harness for one poll tick.

Strict expected failures preserve documented AUD defects until M2/M3 changes.
No League client, Tesseract, screenshot or Windows session is required.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.api.server import GameState, poll_tick


def make_snapshot(level=3, *, dead=False, hp=1.0, attack_damage=100.0):
    return SimpleNamespace(
        level=level,
        is_dead=dead,
        health_pct=hp,
        champion_stats={"attackDamage": attack_damage, "maxHealth": 1000.0},
        augment_choices=[],
        chosen_augments=[],
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
@pytest.mark.xfail(strict=True, reason="AUD-07: first transient LCDA miss sends game_ended prematurely")
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
    assert state.scan_window_open
    assert state.awaiting_stat_delta
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
