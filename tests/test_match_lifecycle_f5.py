"""M3/F5: no WebSocket sends under GameState.lock, bounded ordered transport."""
import asyncio
import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.api import server
from backend.api.server import GameState, poll_tick


def snapshot(*, level=1):
    return SimpleNamespace(
        champion_id="jinx", game_id="unknown", game_time=60,
        level=level, is_dead=False, champion_stats={},
        augment_choices=[], chosen_augments=[], purchased_items=[],
        build_style="Balanced", current_gold=400,
    )


def rig(state, *, level=1, ocr=False, watcher=None, broadcaster=None, match=None):
    async def thread(fn):
        return fn()

    async def broadcast(message):
        if broadcaster:
            await broadcaster(message)

    return SimpleNamespace(
        get_raw_game_data=lambda: {"gameData": {"gameTime": 60}},
        read_champ_select_payload=lambda: None,
        parse_game_snapshot=lambda *_args: snapshot(level=level),
        ocr_available=lambda: ocr,
        run_watcher_check=lambda: watcher or ("unchanged", [], None),
        screen_watcher=SimpleNamespace(reset=Mock()),
        to_thread=thread, broadcast=broadcast,
        try_stat_delta_match=match or (lambda _snap: asyncio.sleep(0)),
        serialize_result=lambda _result, _static, snap: {
            "type": "update", "chosen": list(snap.chosen_augments),
        },
        static_data=object(),
    )


@pytest.mark.asyncio
async def test_ocr_message_sent_only_after_releasing_game_state_lock():
    state = GameState()
    state.ws_clients.add(object())
    locked_at_send = []

    async def send(_message):
        locked_at_send.append(state.lock.locked())

    watcher = ("detected", ["observed"], [
        {"id": "observed", "name": "Observed", "confidence": 95},
    ])
    deps = rig(state, level=3, ocr=True, watcher=watcher, broadcaster=send)
    await poll_tick(state, deps, 10.0)
    assert locked_at_send
    assert locked_at_send == [False]


@pytest.mark.asyncio
async def test_stat_delta_confirmation_is_prepared_without_socket_io_under_lock():
    state = GameState()
    state.ws_clients.add(object())
    state.awaiting_stat_delta = True
    state.confirmation_pending = True
    state.delta_wait_ticks = 1
    locked_at_match = []

    async def match(_snapshot):
        locked_at_match.append(state.lock.locked())

    await poll_tick(state, rig(state, match=match), 10.0)
    assert locked_at_match == [False]


class SlowSocket:
    def __init__(self):
        self.started = asyncio.Event()
        self.blocked = asyncio.Event()

    async def send_text(self, _text):
        self.started.set()
        await self.blocked.wait()


class RecordingSocket:
    def __init__(self, *, limit=1):
        self.messages = []
        self.limit = limit
        self.complete = asyncio.Event()

    async def send_text(self, payload):
        self.messages.append(payload)
        if len(self.messages) >= self.limit:
            self.complete.set()


async def stop_sender_tasks(state):
    for task in list(getattr(state, "ws_send_tasks", {}).values()):
        task.cancel()
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_slow_client_does_not_block_fast_client_or_next_broadcast(monkeypatch):
    state = GameState()
    slow, fast = SlowSocket(), RecordingSocket(limit=2)
    state.ws_clients.update({slow, fast})
    monkeypatch.setattr(server, "game_state", state)

    try:
        await asyncio.wait_for(server._broadcast("snapshot-1"), timeout=0.25)
        await asyncio.wait_for(server._broadcast("snapshot-2"), timeout=0.25)
        await asyncio.wait_for(fast.complete.wait(), timeout=0.6)
        assert fast.messages == ["snapshot-1", "snapshot-2"]
        assert slow.started.is_set()
    finally:
        slow.blocked.set()
        await stop_sender_tasks(state)


@pytest.mark.asyncio
async def test_disconnected_client_removed_while_other_receives_ordered_messages(monkeypatch):
    state = GameState()
    good = RecordingSocket(limit=2)
    class Broken:
        async def send_text(self, _payload):
            raise ConnectionError("gone")
    broken = Broken()
    state.ws_clients.update({good, broken})
    monkeypatch.setattr(server, "game_state", state)

    try:
        await server._broadcast("1")
        await server._broadcast("2")
        await asyncio.wait_for(good.complete.wait(), timeout=0.6)
        await asyncio.sleep(0)
        assert good.messages == ["1", "2"]
        assert broken not in state.ws_clients
    finally:
        await stop_sender_tasks(state)


@pytest.mark.asyncio
async def test_concurrent_poll_ticks_are_serialized_and_do_not_overlap_lcda_reads():
    state = GameState()
    state.ws_clients.add(object())
    counters = {"active": 0, "maximum": 0}
    mutex = threading.Lock()

    def fetch():
        with mutex:
            counters["active"] += 1
            counters["maximum"] = max(counters["maximum"], counters["active"])
        time.sleep(0.04)
        with mutex:
            counters["active"] -= 1
        return None

    async def send(_msg):
        return None

    deps = SimpleNamespace(
        get_raw_game_data=fetch, read_champ_select_payload=lambda: None,
        to_thread=asyncio.to_thread, broadcast=send,
    )
    await asyncio.gather(poll_tick(state, deps, 1.0), poll_tick(state, deps, 2.0))
    assert counters["maximum"] == 1


@pytest.mark.asyncio
async def test_snapshot_is_immutable_after_capture_and_sent_without_lock():
    state = GameState()
    state.ws_clients.add(object())
    state.chosen_augments = ["confirmed"]
    state.pipeline = SimpleNamespace(run=lambda _snapshot: object())
    captures = []

    async def send(text):
        assert not state.lock.locked()
        captures.append(json.loads(text))
        if len(captures) == 1:
            async with state.lock:
                state.chosen_augments.append("future")

    deps = rig(state, broadcaster=send)
    await poll_tick(state, deps, 10.0)
    assert captures[0]["chosen"] == ["confirmed"]
    assert state.chosen_augments == ["confirmed", "future"]
