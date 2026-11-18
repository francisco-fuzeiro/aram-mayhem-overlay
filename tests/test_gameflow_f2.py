"""M3/F2 read-only Gameflow state and LCDA active-player regression tests."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.collectors import lcu
from backend.collectors.lcda import parse_game_snapshot
from backend.models import GamePhase
from backend.api.server import GameState
import json
from unittest.mock import Mock


def make_snapshot():
    return SimpleNamespace(
        level=3, is_dead=False, health_pct=1.0,
        champion_stats={}, augment_choices=[], chosen_augments=[],
        purchased_items=[], build_style="Balanced",
    )


def make_harness(raw_values, snapshots):
    state = GameState()
    state.ws_clients.add(object())
    state.pipeline = None
    messages = []
    raw = iter(raw_values)
    parsed = iter(snapshots)

    async def fake_thread(fn):
        return fn()

    async def broadcast(msg):
        messages.append(json.loads(msg))

    deps = SimpleNamespace(
        get_raw_game_data=lambda: next(raw),
        parse_game_snapshot=lambda *_args: next(parsed),
        read_champ_select_payload=lambda: None,
        ocr_available=lambda: False,
        screen_watcher=SimpleNamespace(reset=Mock()),
        to_thread=fake_thread,
        broadcast=broadcast,
        try_stat_delta_match=lambda snapshot: None,
        serialize_result=lambda *args: {},
        static_data=object(),
    )
    return state, deps, messages
from backend.api.server import poll_tick


@pytest.mark.parametrize(("phase", "expected"), [
    ("None", "client_idle"), ("Lobby", "client_idle"),
    ("ChampSelect", "champ_select"), ("GameStart", "loading"),
    ("InProgress", "live_data_unavailable"),
    ("EndOfGame", "post_game"), ("WaitingForStats", "post_game"),
])
def test_gameflow_states_are_explicit(phase, expected):
    from backend.api.match_lifecycle import classify_status
    assert classify_status(phase, "http_404", was_in_game=False) == expected


def test_lcu_gameflow_read_is_read_only(monkeypatch):
    session = __import__('unittest.mock', fromlist=['MagicMock']).MagicMock()
    session.base_url = "https://127.0.0.1:1234"
    session.get.return_value = Mock(status_code=200, json=lambda: "ChampSelect")
    monkeypatch.setattr(lcu, "get_lcu_session", lambda: session)
    assert lcu.read_gameflow_phase() == "ChampSelect"
    assert session.get.call_args.args[0].endswith("/lol-gameflow/v1/gameflow-phase")


def test_active_player_prefers_riot_id_over_same_summoner_name():
    raw = {
        "activePlayer": {
            "riotId": "Actual#TAG", "summonerName": "Duplicated", "level": 6,
        },
        "allPlayers": [
            {"riotId": "Other#TAG", "summonerName": "Duplicated",
             "championName": "Annie", "team": "ORDER", "items": []},
            {"riotId": "Actual#TAG", "summonerName": "OtherDisplay",
             "championName": "Jinx", "team": "ORDER", "items": []},
        ],
        "gameData": {"gameTime": 60},
    }
    snapshot = parse_game_snapshot(raw, GamePhase.IN_GAME)
    assert snapshot.champion_id == "jinx"


@pytest.mark.asyncio
async def test_loading_then_multiple_404_then_recovery_keeps_match():
    state, deps, messages = make_harness(
        [None, None, None, None, {"tick": 1}],
        [make_snapshot()],
    )
    phases = iter(("ChampSelect", "GameStart", "InProgress", "InProgress", "InProgress"))
    deps.read_gameflow_phase = lambda: next(phases)
    for tick in range(5):
        await poll_tick(state, deps, float(tick * 2))
    statuses = [m["status"] for m in messages if m.get("type") == "status"]
    assert statuses == [
        "champ_select", "loading", "live_data_unavailable",
        "live_data_unavailable", "in_game",
    ]


@pytest.mark.asyncio
async def test_pipeline_none_reports_champion_unresolved():
    state, deps, messages = make_harness([{"tick": 1}], [make_snapshot()])
    state.pipeline = Mock(run=Mock(return_value=None))
    deps.read_gameflow_phase = lambda: "InProgress"
    await poll_tick(state, deps, 5)
    assert any(m.get("type") == "status" and m.get("status") == "champion_unresolved"
               for m in messages)
