"""M3/F1: classified LCDA transport and non-blocking polling regressions."""
import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.collectors import lcda
from backend.api.server import GameState, poll_tick


@pytest.mark.parametrize("http_status, expected", [(200, "ok"), (404, "http_404"), (503, "error")])
def test_lcda_http_status_contract(monkeypatch, http_status, expected):
    response = SimpleNamespace(status_code=http_status, json=lambda: {
        "activePlayer": {"summonerName": "private-identity"}, "gameData": {}
    })
    monkeypatch.setattr(lcda.SESSION, "get", lambda *a, **kw: response)
    result = lcda.get_raw_game_data()
    assert result.status == expected
    assert result.payload is not None if expected == "ok" else result.payload is None
    assert isinstance(result.payload, dict) if expected == "ok" else True


@pytest.mark.parametrize("exc, expected", [
    (lcda.requests.Timeout("secret request URL"), "timeout"),
    (lcda.requests.ConnectionError(ConnectionRefusedError(111, "connection refused")), "refused"),
    (lcda.requests.ConnectionError("generic link failure"), "error"),
    (lcda.requests.RequestException("secret token"), "error"),
])
def test_lcda_errors_are_classified_without_leaking_payloads(monkeypatch, exc, expected):
    def fail(*args, **kwargs):
        raise exc
    monkeypatch.setattr(lcda.SESSION, "get", fail)
    result = lcda.get_raw_game_data()
    assert result.status == expected
    assert result.payload is None


@pytest.mark.parametrize("json_result", [
    ValueError("secret JSON"), [], "not an object", None,
])
def test_bad_json_is_distinct_from_network_failure(monkeypatch, json_result):
    def parse():
        if isinstance(json_result, Exception):
            raise json_result
        return json_result
    monkeypatch.setattr(lcda.SESSION, "get", lambda *a, **kw: SimpleNamespace(
        status_code=200, json=parse,
    ))
    result = lcda.get_raw_game_data()
    assert result.status == "bad_json"
    assert result.payload is None


@pytest.mark.asyncio
async def test_lcda_slow_request_does_not_block_other_async_tasks(monkeypatch):
    # A 100-ms wall-clock race is not a concurrency contract on loaded Windows
    # runners. Explicitly hold the LCDA worker until the event loop handles a
    # separate coroutine. Use generous timeouts only to bound a deadlock.
    worker_started = threading.Event()
    release_worker = threading.Event()
    loop_thread = threading.get_ident()

    def slow_fetch():
        assert threading.get_ident() != loop_thread, "LCDA must leave the event loop"
        worker_started.set()
        if not release_worker.wait(timeout=10):
            raise AssertionError("LCDA test worker was not released")
        return lcda.LCDAResult("http_404", None)

    state = GameState()
    state.ws_clients.add(object())
    outputs = []

    async def send(message):
        outputs.append(json.loads(message))

    deps = SimpleNamespace(
        get_raw_game_data=slow_fetch,
        to_thread=asyncio.to_thread,
        read_champ_select_payload=lambda: None,
        broadcast=send,
    )
    tick = asyncio.create_task(poll_tick(state, deps, 1.0))
    try:
        started = await asyncio.wait_for(
            asyncio.to_thread(worker_started.wait, 5.0), timeout=6.0,
        )
        assert started, "LCDA worker never started"

        heartbeat = asyncio.Event()

        async def other_websocket_task():
            await asyncio.sleep(0)
            heartbeat.set()

        other = asyncio.create_task(other_websocket_task())
        await asyncio.wait_for(heartbeat.wait(), timeout=5.0)
        assert not tick.done(), "LCDA worker must not block independent tasks"
        await other
    finally:
        release_worker.set()
        await asyncio.wait_for(tick, timeout=6.0)
    assert any(x.get("type") == "no_game" for x in outputs)


@pytest.mark.asyncio
async def test_poll_tick_consumes_typed_success(monkeypatch):
    state = GameState()
    state.ws_clients.add(object())
    snapshot = SimpleNamespace(
        level=1, is_dead=False, champion_stats={}, chosen_augments=[],
        augment_choices=[], purchased_items=[], build_style="Balanced",
    )
    deps = SimpleNamespace(
        get_raw_game_data=lambda: lcda.LCDAResult("ok", {"gameData": {}}),
        to_thread=asyncio.to_thread,
        parse_game_snapshot=lambda raw, phase: snapshot,
        screen_watcher=SimpleNamespace(reset=Mock()),
        ocr_available=lambda: False,
        broadcast=lambda msg: asyncio.sleep(0),
        static_data=object(),
    )
    await poll_tick(state, deps, 5.0)
    assert state.had_game_last_tick
