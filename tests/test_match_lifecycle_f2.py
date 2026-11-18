"""M3/F2: explicit read-only LCU Gameflow and status transitions."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.api.server import GameState, poll_tick
from backend.collectors.lcda import LCDAResult, parse_game_snapshot
from backend.models import GamePhase


def _fake_snapshot(champion_id="jinx"):
    return SimpleNamespace(
        champion_id=champion_id, level=1, is_dead=False, champion_stats={},
        augment_choices=[], chosen_augments=[], purchased_items=[],
        current_gold=200, game_time=50.0, build_style="Balanced",
    )


def _harness(phase_values, raw_values, *, champ_select_payload=None, pipeline=None):
    state = GameState()
    state.ws_clients.add(object())
    state.pipeline = pipeline
    output = []
    phases = iter(phase_values)
    raws = iter(raw_values)

    async def fake_thread(fn):
        return fn()

    async def broadcast(message):
        output.append(json.loads(message))

    def champ_select():
        return champ_select_payload if output == [] or any(
            msg.get("state") == "champ_select" for msg in output
        ) else None

    deps = SimpleNamespace(
        read_gameflow=lambda: SimpleNamespace(phase=next(phases), game_id=None),
        read_champ_select_payload=champ_select,
        get_raw_game_data=lambda: next(raws),
        parse_game_snapshot=lambda _raw, _phase: _fake_snapshot(),
        ocr_available=lambda: False,
        screen_watcher=SimpleNamespace(reset=Mock()),
        to_thread=fake_thread,
        broadcast=broadcast,
        serialize_result=lambda *_: {"type": "update", "build_state": {}},
        static_data=object(),
    )
    return state, deps, output


@pytest.mark.asyncio
async def test_champ_select_loading_three_404_then_lcda_recovery():
    phases = ["ChampSelect", "GameStart", "InProgress", "InProgress", "InProgress", "InProgress"]
    results = [LCDAResult("http_404") for _ in range(5)] + [
        LCDAResult("ok", {"gameData": {}})
    ]
    state, deps, messages = _harness(
        phases, results, champ_select_payload={"type": "champ_select", "candidates": []},
    )
    for i in range(6):
        await poll_tick(state, deps, 10.0 + i * 2)
    statuses = [msg["state"] for msg in messages if msg.get("type") == "status"]
    assert statuses[0] == "champ_select"
    assert "loading" in statuses
    assert statuses[-1] == "in_game"
    assert "post_game" not in statuses
    assert not any(msg.get("type") == "game_ended" for msg in messages)


@pytest.mark.asyncio
async def test_known_client_idle_phase_does_not_claim_game_active():
    state, deps, messages = _harness(["Lobby"], [LCDAResult("http_404")])
    await poll_tick(state, deps, 3.0)
    assert {"type": "status", "state": "client_idle"} in messages


@pytest.mark.asyncio
async def test_gameflow_active_but_temporary_lcda_failure_is_not_end():
    state, deps, messages = _harness(
        ["InProgress", "InProgress"],
        [LCDAResult("ok", {"gameData": {}}), LCDAResult("timeout")],
    )
    await poll_tick(state, deps, 10.0)
    await poll_tick(state, deps, 12.0)
    assert any(msg.get("state") == "live_data_unavailable" for msg in messages)
    assert not any(msg.get("type") == "game_ended" for msg in messages)


@pytest.mark.asyncio
async def test_pipeline_none_explicitly_reports_unresolved_champion():
    state, deps, messages = _harness(
        ["InProgress"], [LCDAResult("ok", {"gameData": {}})],
        pipeline=SimpleNamespace(run=lambda _snap: None),
    )
    await poll_tick(state, deps, 11.0)
    assert any(msg.get("type") == "status"
               and msg.get("state") == "champion_unresolved" for msg in messages)


def test_active_player_matches_riot_id_before_legacy_name():
    raw = {
        "activePlayer": {"riotId": "Actual#TAG", "summonerName": "old"},
        "allPlayers": [
            {"riotId": "Other#TAG", "summonerName": "old",
             "championName": "Neeko", "team": "CHAOS", "items": [{"itemID": 1001}]},
            {"riotId": "Actual#TAG", "summonerName": "renamed",
             "championName": "Jinx", "team": "ORDER", "items": [{"itemID": 3006}]},
        ],
        "gameData": {"gameTime": 40},
    }
    snapshot = parse_game_snapshot(raw, GamePhase.IN_GAME)
    assert snapshot.champion_id == "jinx"
    assert snapshot.purchased_items == ["3006"]


def test_active_player_can_fallback_to_summoner_name():
    raw = {
        "activePlayer": {"summonerName": "legacy"},
        "allPlayers": [{"summonerName": "legacy", "championName": "Jinx"}],
        "gameData": {},
    }
    assert parse_game_snapshot(raw, GamePhase.IN_GAME).champion_id == "jinx"


def test_gameflow_reader_uses_get_only_and_never_exposes_lcu_credentials(monkeypatch):
    from backend.collectors import lcu

    urls = []
    class FakeLCU:
        base_url = "https://127.0.0.1:12345"
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, **kw):
            urls.append(url)
            if url.endswith("/gameflow-phase"):
                return SimpleNamespace(status_code=200, json=lambda: "GameStart")
            return SimpleNamespace(status_code=200, json=lambda: {"gameId": 42})
    monkeypatch.setattr(lcu, "get_lcu_session", lambda: FakeLCU())
    info = lcu.read_gameflow()
    assert info.phase == "GameStart"
    assert info.game_id == "42"
    assert urls
    assert all(url.startswith(FakeLCU.base_url + "/lol-gameflow/v1/") for url in urls)
