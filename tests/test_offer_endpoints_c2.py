"""C2 HTTP and WebSocket contract: no guesses or old epochs enter builds."""

from types import SimpleNamespace
from unittest.mock import Mock
import json

from fastapi.testclient import TestClient

from backend.api import server


def _setup(monkeypatch):
    state = server.GameState()
    monkeypatch.setattr(server, "game_state", state)
    monkeypatch.setattr(server, "screen_watcher", SimpleNamespace(reset=Mock()))
    monkeypatch.setattr(server, "event_log", SimpleNamespace(emit=Mock()))
    monkeypatch.setattr(server, "static_data", SimpleNamespace(
        _augments={"101": object(), "102": object(), "103": object()},
    ))
    first = state.offer_ledger.on_level(3)
    state.offer_ledger.on_verified_titles({
        "left": "101", "centre": "102", "right": "103",
    }, first.epoch)
    state.scan_window_open = True
    return state, first


def test_identify_and_confirm_are_separate_and_fenced(monkeypatch):
    state, offer = _setup(monkeypatch)
    client = TestClient(server.app)
    current = offer.epoch
    not_catalog = client.post("/api/offers/identify", json={
        "offer_id": 1, "epoch": current, "slot": "right", "augment_id": "999",
    })
    assert (not_catalog.status_code, not_catalog.json()["detail"]) == (422, "not_in_catalog")
    stale = client.post("/api/offers/identify", json={
        "offer_id": 1, "epoch": current - 1, "slot": "right", "augment_id": "101",
    })
    assert (stale.status_code, stale.json()["detail"]) == (409, "stale_epoch")
    identified = client.post("/api/offers/identify", json={
        "offer_id": 1, "epoch": current, "slot": "right", "augment_id": "102",
    })
    assert identified.status_code == 409  # already in the centre slot
    identified = client.post("/api/offers/identify", json={
        "offer_id": 1, "epoch": current, "slot": "right", "augment_id": "103",
    })
    assert identified.status_code == 200
    assert state.chosen_augments == []
    wrong = client.post("/api/offers/confirm", json={
        "offer_id": 1, "epoch": current, "augment_id": "999",
    })
    assert wrong.status_code == 409
    assert state.chosen_augments == []
    confirmed = client.post("/api/offers/confirm", json={
        "offer_id": 1, "epoch": current, "augment_id": "102",
    })
    assert confirmed.status_code == 200
    assert confirmed.json()["chosen_augments"] == ["102"]
    assert state.chosen_augments == ["102"]
    assert state.scan_window_open is False
    assert offer.pick_source == "user_confirm"


def test_old_offer_confirm_preserves_current_offer_identity(monkeypatch):
    state, older = _setup(monkeypatch)
    state.offer_ledger.on_titles_unverified()
    newer = state.offer_ledger.on_level(7)
    state.offer_ledger.on_verified_titles({
        "left": "201", "centre": "202", "right": "203",
    }, newer.epoch)
    state.scan_window_open = True
    state.offer_epoch = newer.epoch
    state.ocr_slot_choices = {"left": "201", "centre": "202", "right": "203"}
    current = (newer.epoch, newer.state, state.offer_epoch,
               state.scan_window_open, dict(state.ocr_slot_choices))
    result = TestClient(server.app).post("/api/offers/confirm", json={
        "offer_id": 1, "epoch": older.epoch, "augment_id": "101",
    })
    assert result.status_code == 200
    assert state.chosen_augments == ["101"]
    assert (newer.epoch, newer.state, state.offer_epoch,
            state.scan_window_open, state.ocr_slot_choices) == current


def test_confirm_slot_targets_oldest_unconfirmed_offer(monkeypatch):
    state, older = _setup(monkeypatch)
    state.offer_ledger.on_titles_unverified()
    newer = state.offer_ledger.on_level(7)
    state.offer_ledger.on_verified_titles({
        "left": "201", "centre": "202", "right": "203",
    }, newer.epoch)
    response = TestClient(server.app).post(
        "/api/offers/confirm-slot", json={"slot": "centre"},
    )
    assert response.status_code == 200
    assert response.json()["offer_id"] == older.offer_id
    assert state.chosen_augments == ["102"]
    assert newer.picked_id is None


def test_recovery_invalidates_old_offer_epoch(monkeypatch):
    state = server.GameState()
    monkeypatch.setattr(server, "game_state", state)
    monkeypatch.setattr(server, "screen_watcher", SimpleNamespace(reset=Mock()))
    due = state.offer_ledger.on_level(3)
    old_epoch = due.epoch
    result = TestClient(server.app).post(
        "/api/offers/recover", json={"offer_id": 1},
    )
    assert result.status_code == 200
    assert due.epoch > old_epoch
    assert state.offer_epoch == due.epoch
    assert state.chosen_augments == []
    assert TestClient(server.app).post("/api/offers/confirm", json={
        "offer_id": 1, "epoch": old_epoch, "augment_id": "101",
    }).json()["detail"] == "stale_epoch"


def test_ws_unidentified_choice_cannot_inject_build_augments(monkeypatch):
    state, offer = _setup(monkeypatch)
    state.pipeline = SimpleNamespace(run=lambda _snapshot: None)
    client = TestClient(server.app)
    with client.websocket_connect("/ws/game") as ws:
        ws.send_json({
            "type": "choose_augment", "augment_id": "999",
            "offer_id": offer.offer_id, "epoch": offer.epoch,
        })
        result = ws.receive_json()
        assert result["type"] == "error"
        assert result["error"] == "not_in_offer"
        assert state.chosen_augments == []
        ws.send_json({
            "type": "choose_augment", "augment_id": "101",
            "offer_id": offer.offer_id, "epoch": offer.epoch - 1,
        })
        assert ws.receive_json()["error"] == "stale_epoch"
        assert state.chosen_augments == []
        ws.send_json({
            "type": "choose_augment", "augment_id": "101",
            "offer_id": offer.offer_id, "epoch": offer.epoch,
        })
        result = ws.receive_json()
        assert result["type"] == "ack"
        assert result["chosen_augments"] == ["101"]
