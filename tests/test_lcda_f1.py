"""M3/F1 LCDA classification and non-blocking poll regression tests."""
import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from backend.collectors import lcda
from backend.api.server import GameState, poll_tick


@pytest.mark.parametrize(("code", "expected"), [(404, "http_404"), (503, "error")])
def test_lcda_http_status_classification(monkeypatch, code, expected):
    response = Mock(status_code=code)
    response.json.return_value = {"gameData": {}}
    monkeypatch.setattr(lcda.SESSION, "get", lambda *a, **kw: response)
    status, payload = lcda.get_raw_game_data()
    assert (status, payload) == (expected, None)


def test_lcda_success_returns_explicit_payload(monkeypatch):
    data = {"activePlayer": {"level": 3}}
    response = Mock(status_code=200)
    response.json.return_value = data
    monkeypatch.setattr(lcda.SESSION, "get", lambda *a, **kw: response)
    assert lcda.get_raw_game_data() == ("ok", data)


@pytest.mark.parametrize(("exception", "expected"), [
    (requests.Timeout(), "timeout"),
    (requests.ConnectionError("Connection refused"), "refused"),
    (requests.RequestException("other"), "error"),
    (ValueError("bad json"), "bad_json"),
])
def test_lcda_failures_are_classified_without_payload(monkeypatch, exception, expected):
    def broken(*args, **kwargs):
        raise exception
    monkeypatch.setattr(lcda.SESSION, "get", broken)
    assert lcda.get_raw_game_data() == (expected, None)


def test_lcda_non_object_json_rejected(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = []
    monkeypatch.setattr(lcda.SESSION, "get", lambda *a, **kw: response)
    assert lcda.get_raw_game_data() == ("bad_json", None)


@pytest.mark.asyncio
async def test_slow_lcda_does_not_block_unrelated_async_work():
    state = GameState()
    state.ws_clients.add(object())
    started = asyncio.Event()
    loop = asyncio.get_running_loop()

    def slow_fetch():
        loop.call_soon_threadsafe(started.set)
        time.sleep(0.16)
        return ("http_404", None)

    events = []

    async def send(payload):
        events.append(json.loads(payload))

    deps = SimpleNamespace(
        get_raw_game_data=slow_fetch,
        to_thread=asyncio.to_thread,
        read_champ_select_payload=lambda: None,
        broadcast=send,
    )
    task = asyncio.create_task(poll_tick(state, deps, 1.0))
    await asyncio.wait_for(started.wait(), timeout=1)
    # A responsive event loop can serve another task while LCDA blocks its worker.
    await asyncio.wait_for(asyncio.sleep(0.01), timeout=0.08)
    assert not task.done()
    await task
