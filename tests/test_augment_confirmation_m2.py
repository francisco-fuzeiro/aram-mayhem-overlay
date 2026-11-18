"""M2/A3 regressions: disappeared offers must never auto-confirm an augment."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from backend.api import server
from backend.models import AugmentTier


@pytest.fixture
def pending_offer(monkeypatch):
    state = server.GameState()
    state.scan_window_open = False
    state.confirmation_pending = True
    state.scan_window_level = 3
    state.stat_snapshot_before = {"attackDamage": 100.0}
    state.stat_snapshot_level_before = 3
    state.stat_snapshot_items_before = ("1001",)
    state.augment_choices = ["a", "b", "c"]

    augments = {
        aid: SimpleNamespace(id=aid, name="card " + aid, tier=AugmentTier.GOLD)
        for aid in state.augment_choices
    }
    all_augments = Mock(side_effect=AssertionError(
        "A missing OCR offer must never search the entire augment catalog"
    ))
    static_data = SimpleNamespace(
        get_augment=lambda aid: augments.get(aid),
        get_stat_anvil=lambda aid: None,
        all_augments=all_augments,
    )
    broadcast = AsyncMock()
    events = []
    monkeypatch.setattr(server, "game_state", state)
    monkeypatch.setattr(server, "static_data", static_data)
    monkeypatch.setattr(server, "_broadcast", broadcast)
    monkeypatch.setattr(server, "screen_watcher", SimpleNamespace(reset=Mock()))
    monkeypatch.setattr(server, "event_log", SimpleNamespace(
        emit=lambda event, **fields: events.append((event, fields))
    ))
    matcher = Mock(return_value=(augments["a"], 0.95))
    monkeypatch.setattr(server, "match_augment", matcher)
    return state, static_data, broadcast, matcher, events


def snapshot(*, level=3, items=("1001",), ad=145.0):
    return SimpleNamespace(
        level=level, purchased_items=list(items),
        champion_stats={"attackDamage": ad},
    )


@pytest.mark.asyncio
async def test_a3_high_confidence_match_is_only_a_hint_not_a_pick(pending_offer):
    state, _static, broadcast, matcher, events = pending_offer
    await server._try_stat_delta_match(snapshot())

    assert state.chosen_augments == []
    assert state.chosen_stat_anvils == []
    assert state.augment_choices == ["a", "b", "c"]
    assert state.confirmation_pending
    assert not state.scan_window_open
    broadcast.assert_awaited_once()
    message = json.loads(broadcast.await_args.args[0])
    assert message["type"] == "augment_confirm"
    assert [c["id"] for c in message["candidates"]] == ["a", "b", "c"]
    assert message["best_guess_id"] == "a"
    assert not any(event == "augment_confirmation" and fields.get("method") == "automatic"
                   for event, fields in events)
    assert not any(event == "augment_inference" and fields.get("result") == "auto"
                   for event, fields in events)
    matcher.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", [
    {"level": 4},
    {"items": ("1001", "3089")},
])
async def test_a3_level_or_inventory_change_disables_likely_hint(pending_offer, changed):
    state, _static, broadcast, matcher, _events = pending_offer
    await server._try_stat_delta_match(snapshot(**changed))

    assert state.chosen_augments == []
    assert state.confirmation_pending
    assert json.loads(broadcast.await_args.args[0])["best_guess_id"] is None
    matcher.assert_not_called()


@pytest.mark.asyncio
async def test_a3_missing_baseline_metadata_fails_closed(pending_offer):
    state, _static, broadcast, matcher, _events = pending_offer
    state.stat_snapshot_items_before = None
    await server._try_stat_delta_match(snapshot())

    assert state.chosen_augments == []
    assert json.loads(broadcast.await_args.args[0])["best_guess_id"] is None
    matcher.assert_not_called()


@pytest.mark.asyncio
async def test_a3_unobserved_offer_never_guesses_from_whole_catalog(pending_offer):
    state, data, broadcast, matcher, _events = pending_offer
    state.augment_choices.clear()
    await server._try_stat_delta_match(snapshot())

    message = json.loads(broadcast.await_args.args[0])
    assert message["type"] == "augment_confirm"
    assert message["candidates"] == []
    assert message["best_guess_id"] is None
    assert state.chosen_augments == []
    data.all_augments.assert_not_called()
    matcher.assert_not_called()


@pytest.mark.asyncio
async def test_a3_stat_anvil_is_never_automatically_chosen(pending_offer):
    state, data, broadcast, matcher, _events = pending_offer
    data.get_stat_anvil = lambda aid: object() if aid == "a" else None
    await server._try_stat_delta_match(snapshot())

    assert state.chosen_stat_anvils == []
    assert state.chosen_augments == []
    assert json.loads(broadcast.await_args.args[0])["best_guess_id"] == "a"
    matcher.assert_called_once()


@pytest.mark.asyncio
async def test_a3_no_premature_prompt_without_verified_disappearance(pending_offer):
    state, _static, broadcast, matcher, _events = pending_offer
    state.confirmation_pending = False
    state.scan_window_open = True
    await server._try_stat_delta_match(snapshot())

    broadcast.assert_not_awaited()
    matcher.assert_not_called()
    assert state.chosen_augments == []
    assert state.scan_window_open


@pytest.mark.asyncio
async def test_a3_explicit_manual_choice_resolves_pending_state(pending_offer, monkeypatch):
    state, data, _broadcast, _matcher, events = pending_offer
    state.awaiting_stat_delta = True
    state.delta_wait_ticks = 1

    class Socket:
        def __init__(self):
            self.sent = []
            self.pending = [json.dumps({"type": "choose_augment", "augment_id": "b"})]

        async def accept(self):
            pass

        async def receive_text(self):
            if self.pending:
                return self.pending.pop(0)
            raise server.WebSocketDisconnect()

        async def send_text(self, message):
            self.sent.append(json.loads(message))

    client = Socket()
    await server.game_ws(client)
    assert state.chosen_augments == ["b"]
    assert state.chosen_stat_anvils == []
    assert not state.confirmation_pending
    assert not state.awaiting_stat_delta
    assert state.delta_wait_ticks == 0
    assert state.augment_choices == []
    assert state.stat_snapshot_before == {}
    assert client.sent == [{
        "type": "ack", "action": "choose_augment",
        "chosen_augments": ["b"],
    }]
    assert ("augment_confirmation", {"method": "manual", "kind": "augment"}) in events
