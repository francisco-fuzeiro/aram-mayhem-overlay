"""M3/F3: match identity, authoritative end and debounced LCDA miss regressions."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.api.server import GameState, poll_tick
from backend.collectors.lcda import LCDAResult


def snapshot(champion="jinx", game_time=50, game_id="unknown"):
    return SimpleNamespace(
        champion_id=champion, game_id=game_id, game_time=game_time,
        level=1, is_dead=False, champion_stats={}, augment_choices=[],
        chosen_augments=[], purchased_items=[], build_style="Balanced",
        current_gold=400,
    )


def rig(readings):
    """Readings: (time, LCDA status, Gameflow phase, game ID, champion, gameTime)."""
    rows = iter(readings)
    state = GameState()
    state.ws_clients.add(object())
    events = []
    current = {}

    def next_lcda():
        row = next(rows)
        current["row"] = row
        status = row[1]
        return LCDAResult(status, {"gameData": {"gameTime": row[5]}} if status == "ok" else None)

    async def send(message):
        events.append(json.loads(message))

    async def fake_thread(fn):
        return fn()

    deps = SimpleNamespace(
        get_raw_game_data=next_lcda,
        read_gameflow=lambda: SimpleNamespace(
            phase=current["row"][2], game_id=current["row"][3],
        ),
        parse_game_snapshot=lambda _raw, _phase: snapshot(
            current["row"][4], current["row"][5],
        ),
        read_champ_select_payload=lambda: None,
        to_thread=fake_thread, broadcast=send,
        ocr_available=lambda: False,
        screen_watcher=SimpleNamespace(reset=Mock()),
        serialize_result=lambda _r, _d, snap: {
            "type": "update", "game_time": snap.game_time,
            "build_state": {"champion_id": snap.champion_id},
        },
        static_data=object(),
    )
    return state, deps, events


@pytest.mark.asyncio
@pytest.mark.parametrize("times", [
    [10, 12],          # one LCDA miss
    [10, 12, 14],      # two LCDA misses
    [10, 11, 12, 15],  # three misses without 6 elapsed seconds
])
async def test_temporary_misses_preserve_confirmed_augments(times):
    rows = [(times[0], "ok", "InProgress", "123", "jinx", 50)]
    rows += [(t, "http_404", None, "123", "jinx", 50) for t in times[1:]]
    state, deps, events = rig(rows)
    await poll_tick(state, deps, times[0])
    state.chosen_augments = ["confirmed-a"]
    for t in times[1:]:
        await poll_tick(state, deps, t)
    assert state.chosen_augments == ["confirmed-a"]
    assert not any(e.get("type") == "game_ended" for e in events)
    assert state.had_game_last_tick
    assert not state.post_game


@pytest.mark.asyncio
async def test_three_misses_spanning_six_seconds_end_without_active_gameflow():
    rows = [
        (10, "ok", "InProgress", "123", "jinx", 50),
        (12, "http_404", None, None, "jinx", 50),
        (15, "timeout", None, None, "jinx", 50),
        (18, "refused", None, None, "jinx", 50),
    ]
    state, deps, messages = rig(rows)
    for row in rows:
        await poll_tick(state, deps, row[0])
    assert [m["type"] for m in messages].count("game_ended") == 1
    assert not state.had_game_last_tick
    assert state.post_game
    assert state.chosen_augments == []


@pytest.mark.asyncio
async def test_gameflow_active_prevents_timeout_based_game_end():
    rows = [
        (10, "ok", "InProgress", "123", "jinx", 50),
        (12, "http_404", "InProgress", "123", "jinx", 50),
        (15, "timeout", "InProgress", "123", "jinx", 50),
        (19, "http_404", "InProgress", "123", "jinx", 50),
    ]
    state, deps, messages = rig(rows)
    for row in rows:
        await poll_tick(state, deps, row[0])
    assert not any(m.get("type") == "game_ended" for m in messages)
    assert state.had_game_last_tick


@pytest.mark.asyncio
async def test_recovery_resets_misses_and_keeps_augments():
    rows = [
        (10, "ok", "InProgress", "123", "jinx", 50),
        (12, "http_404", None, None, "jinx", 50),
        (14, "timeout", None, None, "jinx", 50),
        (15, "ok", "InProgress", "123", "jinx", 58),
        (18, "http_404", None, None, "jinx", 58),
        (20, "http_404", None, None, "jinx", 58),
        (22, "http_404", None, None, "jinx", 58),
    ]
    state, deps, messages = rig(rows)
    for row in rows[:1]:
        await poll_tick(state, deps, row[0])
    state.chosen_augments = ["picked"]
    for row in rows[1:]:
        await poll_tick(state, deps, row[0])
    assert state.chosen_augments == ["picked"]
    assert not any(m.get("type") == "game_ended" for m in messages)


@pytest.mark.asyncio
async def test_authoritative_end_is_immediate_and_resets_game_state():
    rows = [
        (10, "ok", "InProgress", "123", "jinx", 50),
        (12, "http_404", "EndOfGame", "123", "jinx", 50),
    ]
    state, deps, messages = rig(rows)
    await poll_tick(state, deps, 10)
    state.chosen_augments = ["picked"]
    state.augment_choices = ["card"]
    await poll_tick(state, deps, 12)
    assert any(m.get("type") == "game_ended" for m in messages)
    assert state.chosen_augments == []
    assert state.augment_choices == []


@pytest.mark.asyncio
async def test_changed_gameflow_id_starts_clean_without_champ_select():
    rows = [
        (10, "ok", "InProgress", "123", "neeko", 90),
        (12, "ok", "InProgress", "456", "jinx", 3),
    ]
    state, deps, messages = rig(rows)
    await poll_tick(state, deps, 10)
    state.chosen_augments = ["old"]
    state.augment_choices = ["old-offer"]
    await poll_tick(state, deps, 12)
    assert state.chosen_augments == []
    assert state.augment_choices == []
    updates = [m for m in messages if m.get("type") == "status" and m.get("state") == "in_game"]
    assert updates[-1]["match_id"] != updates[0]["match_id"]
    assert state.match_id is not None


@pytest.mark.asyncio
async def test_fallback_game_time_regression_starts_new_match():
    rows = [
        (10, "ok", None, None, "neeko", 155),
        (12, "ok", None, None, "jinx", 2),
    ]
    state, deps, messages = rig(rows)
    await poll_tick(state, deps, 10)
    state.chosen_augments = ["old"]
    await poll_tick(state, deps, 12)
    assert state.chosen_augments == []
    assert len({m["match_id"] for m in messages if m.get("type") == "status" and m.get("state") == "in_game"}) == 2


@pytest.mark.asyncio
async def test_back_to_back_games_no_five_minute_postgame_hold():
    rows = [
        (10, "ok", "InProgress", "100", "neeko", 60),
        (11, "http_404", "EndOfGame", "100", "neeko", 60),
        (13, "ok", "InProgress", "200", "jinx", 1),
    ]
    state, deps, messages = rig(rows)
    await poll_tick(state, deps, 10)
    state.chosen_augments = ["old"]
    await poll_tick(state, deps, 11)
    await poll_tick(state, deps, 13)
    assert state.had_game_last_tick
    assert not state.post_game
    assert not state.chosen_augments
    assert any(m.get("state") == "in_game" for m in messages if m.get("type") == "status")
