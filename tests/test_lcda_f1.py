"""M3/F1: LCDA result classification and non-blocking polling regressions."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from backend.collectors import lcda
from backend.api.server import GameState, poll_tick
from tests.test_poll_tick_m1 import make_harness


@pytest.mark.parametrize("status_code,expected", [(404, "http_404"), (503, "http_error")])
def test_lcda_http_classes(monkeypatch, status_code, expected):
    monkeypatch.setattr(lcda.SESSION, "get", lambda *a, **kw: SimpleNamespace(status_code=status_code))
    result = lcda.get_raw_game_data()
    assert result.status == expected
    assert result.payload is None


def test_lcda_success(monkeypatch):
    payload = {"gameData": {"gameTime": 12}}
    monkeypatch.setattr(lcda.SESSION, "get", lambda *a, **kw: SimpleNamespace(status_code=200, json=lambda: payload))
    result = lcda.get_raw_game_data()
    assert result.status == "ok"
    assert result.payload == payload


@pytest.mark.parametrize("error,expected", [
    (requests.Timeout(), "timeout"),
    (requests.ConnectionError("Connection refused"), "refused"),
    (requests.ConnectionError("unreachable"), "connection_error"),
    (requests.RequestException("other"), "request_error"),
])
def test_lcda_network_classes(monkeypatch, error, expected):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(lcda.SESSION, "get", fail)
    result = lcda.get_raw_game_data()
    assert result.status == expected
    assert result.payload is None


def test_lcda_bad_json(monkeypatch):
    def invalid():
        raise json.JSONDecodeError("invalid", "{", 0)
    monkeypatch.setattr(lcda.SESSION, "get", lambda *a, **kw: SimpleNamespace(status_code=200, json=invalid))
    assert lcda.get_raw_game_data().status == "bad_json"


@pytest.mark.asyncio
async def test_lcda_slow_does_not_block_other_tasks():
    state, deps, _ = make_harness([None], [])
    started = asyncio.Event()
    release = asyncio.Event()
    # A real worker thread must keep the event loop free while LCDA is blocked.
    from threading import Event
    worker_started = Event()
    worker_release = Event()
    def slow_lcda():
        worker_started.set()
        worker_release.wait(timeout=2)
        return None
    deps.get_raw_game_data = slow_lcda
    deps.to_thread = asyncio.to_thread
    task = asyncio.create_task(poll_tick(state, deps, 1.0))
    try:
        await asyncio.wait_for(asyncio.to_thread(worker_started.wait, 1), timeout=1.5)
        assert worker_started.is_set()
        await asyncio.wait_for(asyncio.sleep(0), timeout=0.1)
        assert not task.done()
    finally:
        worker_release.set()
        await task
