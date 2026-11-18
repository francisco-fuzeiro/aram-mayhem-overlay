"""Verify that a finished match cannot leak augment state into the next match."""

import asyncio
import json

import pytest

from backend.api import server


@pytest.mark.asyncio
async def test_game_end_clears_match_only_state_immediately(monkeypatch):
    state = server.GameState()
    state.had_game_last_tick = True
    state.augment_choices = ["stale-offer"]
    state.chosen_augments = ["stale-pick"]
    state.chosen_stat_anvils = ["stale-anvil"]
    state.ocr_last_detected = ["stale-ocr"]
    state.last_known_level = 15
    state.scan_window_open = True
    state.awaiting_stat_delta = True
    state.stat_snapshot_before = {"health": 1000.0}
    state.build_style = "Survival"
    state.overlay_preferences = {"anchor": "bottom_left"}
    state.ocr_enabled = False

    messages = []

    async def capture_broadcast(message):
        messages.append(json.loads(message))

    async def stop_after_tick(_interval):
        raise asyncio.CancelledError()

    monkeypatch.setattr(server, "game_state", state)
    monkeypatch.setattr(server, "get_raw_game_data", lambda: None)
    monkeypatch.setattr(server, "_read_champ_select_payload", lambda: None)
    monkeypatch.setattr(server, "_broadcast", capture_broadcast)
    monkeypatch.setattr(server.asyncio, "sleep", stop_after_tick)

    with pytest.raises(asyncio.CancelledError):
        await server._poll_game_loop(interval=0.01)

    assert messages == [{"type": "game_ended"}]
    assert state.post_game is True
    assert state.had_game_last_tick is False
    assert state.augment_choices == []
    assert state.chosen_augments == []
    assert state.chosen_stat_anvils == []
    assert state.ocr_last_detected == []
    assert state.last_known_level == 0
    assert state.scan_window_open is False
    assert state.awaiting_stat_delta is False
    assert state.stat_snapshot_before == {}
    assert state.build_style == "Survival"
    assert state.overlay_preferences == {"anchor": "bottom_left"}
    assert state.ocr_enabled is False
