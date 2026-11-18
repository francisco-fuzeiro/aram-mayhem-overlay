"""Regressions for desktop-overlay startup and WebSocket broadcasting."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.api import server


@pytest.mark.asyncio
async def test_broadcast_from_inside_state_lock_does_not_deadlock(monkeypatch):
    """OCR and stat confirmation broadcast while holding game_state.lock."""
    fake = type("FakeSocket", (), {})()
    fake.send_text = AsyncMock()
    monkeypatch.setattr(server.game_state, "ws_clients", {fake})

    async def send_with_lock():
        async with server.game_state.lock:
            await server._broadcast('{"type": "test"}')

    await asyncio.wait_for(send_with_lock(), timeout=1.0)
    fake.send_text.assert_awaited_once_with('{"type": "test"}')


@pytest.mark.asyncio
async def test_broadcast_removes_disconnected_clients(monkeypatch):
    fake = type("FakeSocket", (), {})()
    fake.send_text = AsyncMock(side_effect=ConnectionError("disconnected"))
    monkeypatch.setattr(server.game_state, "ws_clients", {fake})
    await asyncio.wait_for(server._broadcast("test"), timeout=1.0)
    assert fake not in server.game_state.ws_clients


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
