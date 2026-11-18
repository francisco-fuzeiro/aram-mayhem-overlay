"""Build-style input/output contract for the local overlay protocol."""

from backend.api.server import _parse_snapshot, _serialize_result
from backend.models import BuildState, GamePhase, PipelineResult
from backend.static_data.loader import StaticData


def test_manual_snapshot_accepts_requested_build_style():
    snapshot = _parse_snapshot({
        "game_id": "fixture",
        "champion_id": "lux",
        "build_style": "Survival",
    })
    assert snapshot.build_style == "Survival"


def test_update_serialization_includes_selected_build_style():
    state = BuildState(champion_id="lux", selected_style="Utility")
    result = PipelineResult(
        phase=GamePhase.IN_GAME,
        recommendations=[],
        build_state=state,
        suggest_reroll=False,
    )
    payload = _serialize_result(result, StaticData())
    assert payload["type"] == "update"
    assert payload["build_state"]["selected_style"] == "Utility"


class FakeWebSocket:
    def __init__(self, messages):
        self.messages = list(messages)
        self.replies = []

    async def accept(self):
        return None

    async def receive_text(self):
        from starlette.websockets import WebSocketDisconnect
        if not self.messages:
            raise WebSocketDisconnect()
        return self.messages.pop(0)

    async def send_text(self, message):
        import json
        self.replies.append(json.loads(message))


import json
import pytest
from backend.api import server


@pytest.mark.asyncio
async def test_websocket_build_style_changes_only_user_preference(monkeypatch):
    monkeypatch.setattr(server.game_state, "build_style", "Balanced")
    socket = FakeWebSocket([json.dumps({
        "type": "set_build_style", "style": "Damage",
    })])
    await server.game_ws(socket)
    assert server.game_state.build_style == "Damage"
    assert socket.replies == [{
        "type": "ack", "action": "set_build_style", "style": "Damage",
    }]


@pytest.mark.asyncio
async def test_websocket_rejects_invalid_build_style(monkeypatch):
    monkeypatch.setattr(server.game_state, "build_style", "Balanced")
    socket = FakeWebSocket([json.dumps({
        "type": "set_build_style", "style": "Cheat",
    })])
    await server.game_ws(socket)
    assert server.game_state.build_style == "Balanced"
    assert socket.replies == [{"error": "invalid build style"}]
