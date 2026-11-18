"""Regressions for desktop-overlay startup and WebSocket broadcasting."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.api import server


@pytest.mark.asyncio
async def test_broadcast_is_enqueued_without_socket_io_under_state_lock(monkeypatch):
    """Even a legacy caller under the lock only queues; sender runs later."""
    state = server.GameState()
    sent = asyncio.Event()
    fake = type("FakeSocket", (), {})()

    async def send(payload):
        assert not state.lock.locked()
        assert payload == '{"type": "test"}'
        sent.set()

    fake.send_text = AsyncMock(side_effect=send)
    state.ws_clients.add(fake)
    monkeypatch.setattr(server, "game_state", state)

    async with state.lock:
        await server._broadcast('{"type": "test"}')
        fake.send_text.assert_not_awaited()

    try:
        await asyncio.wait_for(sent.wait(), timeout=1.0)
        fake.send_text.assert_awaited_once_with('{"type": "test"}')
    finally:
        sender = state.ws_send_tasks.get(fake)
        if sender:
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)


@pytest.mark.asyncio
async def test_broadcast_removes_disconnected_clients(monkeypatch):
    state = server.GameState()
    attempted = asyncio.Event()
    fake = type("FakeSocket", (), {})()

    async def fail(_message):
        attempted.set()
        raise ConnectionError("disconnected")

    fake.send_text = AsyncMock(side_effect=fail)
    state.ws_clients.add(fake)
    monkeypatch.setattr(server, "game_state", state)

    await asyncio.wait_for(server._broadcast("test"), timeout=1.0)
    await asyncio.wait_for(attempted.wait(), timeout=1.0)
    await asyncio.sleep(0)
    assert fake not in state.ws_clients


def test_overlay_server_only_listens_on_loopback():
    from backend.overlay import __main__ as overlay
    with patch("uvicorn.run") as run:
        overlay._start_server()
    assert run.call_args.kwargs["host"] == "127.0.0.1"


def test_asgi_lifespan_initializes_database(monkeypatch, tmp_path):
    """Server init must work even when launched without backend.main."""
    from starlette.testclient import TestClient
    db_path = tmp_path / "oracle.db"
    from backend.storage import db
    monkeypatch.setattr(server, "init_db", lambda: db.init_db(db_path))
    monkeypatch.setattr(server.static_data, "load", lambda: None)
    with patch.object(server, "_poll_game_loop", new_callable=AsyncMock):
        with TestClient(server.app):
            assert db_path.exists()
