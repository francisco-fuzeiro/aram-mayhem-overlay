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
@pytest.mark.xfail(strict=True, reason="AUD-03a: passive level-up stat change falsely enters augment pick inference")
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
@pytest.mark.xfail(strict=True, reason="AUD-03d: taking damage must not close the OCR offer eligibility window")
async def test_aud03d_damage_must_not_close_ocr_window():
    state, deps, events = make_harness(
        [{"tick": 1}, {"tick": 2}],
        [make_snapshot(), make_snapshot(hp=0.75)],
    )
    await poll_tick(state, deps, 10.0)
    assert state.scan_window_open
    await poll_tick(state, deps, 12.0)
    assert state.scan_window_open
