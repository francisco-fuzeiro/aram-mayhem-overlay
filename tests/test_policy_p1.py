"""PG: offline Riot-policy guardrails across the actual HTTP/WS surfaces."""

from pathlib import Path
import inspect
import re
from types import SimpleNamespace

from fastapi.testclient import TestClient
from backend.api import server
from backend.config import Config
from backend.models import (
    AugmentRecommendation, BuildState, GamePhase, PipelineResult,
)
from backend.overlay import window

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_AUGMENT_KEYS = {"win_rate", "winrate", "wins", "wr"}


def _assert_no_augment_win_stats(value):
    """Inspect every nested key, not just the top-level recommendations."""
    if isinstance(value, dict):
        assert not (set(value) & FORBIDDEN_AUGMENT_KEYS), value
        for child in value.values():
            _assert_no_augment_win_stats(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _assert_no_augment_win_stats(child)


def _recommendation_result():
    # Deliberately hostile nested evidence: must never escape via the API.
    return PipelineResult(
        phase=GamePhase.IN_GAME,
        recommendations=[AugmentRecommendation(
            augment_id="aug-test", augment_name="Fixture Augment",
            score=7.5, label=("Utility", "Team"), core_items=[],
            explanation="Situational trade-offs", confidence=0.6,
            components={"synergy": 5.0, "wins": 12,
                        "evidence": {"wr": 0.75, "win_rate": 0.75}},
        )],
        build_state=BuildState(champion_id="test"),
        suggest_reroll=False,
        enemy_analysis={"metrics": [{"winrate": 0.55, "context": "visible"}]},
    )


def test_http_augments_never_expose_prohibited_win_statistics():
    with TestClient(server.app) as client:
        for route in ("/api/augments/search?q=fixture", "/api/static-names"):
            response = client.get(route)
            assert response.status_code == 200
            _assert_no_augment_win_stats(response.json())


def test_serialized_update_redacts_nested_win_statistics():
    result = server._serialize_result(_recommendation_result(), server.static_data)
    _assert_no_augment_win_stats(result)
    assert result["recommendations"][0]["score"] == 7.5
    assert result["recommendations"][0]["components"]["synergy"] == 5.0


def test_websocket_snapshot_redacts_nested_win_statistics(monkeypatch):
    state = server.GameState()
    state.pipeline = SimpleNamespace(run=lambda _snapshot: _recommendation_result())
    monkeypatch.setattr(server, "game_state", state)
    with TestClient(server.app) as client:
        with client.websocket_connect("/ws/game") as ws:
            ws.send_json({"type": "snapshot", "data": {"phase": "in_game"}})
            update = ws.receive_json()
    assert update["type"] == "update"
    _assert_no_augment_win_stats(update)
    assert update["recommendations"][0]["score"] == 7.5


def test_lcu_match_history_opt_in_is_disabled_by_default():
    assert Config().get("lcu_history_enabled") is False


def test_http_history_import_denied_without_explicit_opt_in(monkeypatch):
    from backend.storage import history_import
    called = []
    monkeypatch.setattr(history_import, "sync_recent_mayhem_games",
                        lambda: called.append(True))
    monkeypatch.setattr(server.config, "_data", {
        **server.config._data, "lcu_history_enabled": False,
    })
    with TestClient(server.app) as client:
        response = client.post("/api/history/import")
    assert response.status_code == 403
    assert called == []


def test_http_history_import_only_when_explicitly_enabled(monkeypatch):
    from backend.storage import history_import
    called = []
    monkeypatch.setattr(history_import, "sync_recent_mayhem_games",
                        lambda: called.append(True) or {
                            "status": "ok", "imported": 0, "inspected": 0,
                        })
    monkeypatch.setattr(server.config, "_data", {
        **server.config._data, "lcu_history_enabled": True,
    })
    with TestClient(server.app) as client:
        response = client.post("/api/history/import")
    assert response.status_code == 200
    assert called == [True]


def test_click_position_hints_are_disabled_and_no_lbutton_poll_occurs():
    assert window.PICK_CLICK_HINTS_ENABLED is False
    source = inspect.getsource(window.OverlayWindow._poll_interaction_hotkey) \
        if window.PYQT_AVAILABLE else (
            ROOT / "backend/overlay/window.py"
        ).read_text(encoding="utf-8")
    assert "VK_LBUTTON" not in source
    assert "GetAsyncKeyState(0x01)" not in source


def test_frontend_has_no_imperative_augment_selection_language():
    for path in ("frontend/app.js", "frontend/index.html",
                 "frontend/settings.html"):
        text = (ROOT / path).read_text(encoding="utf-8")
        assert not re.search(r"\b(?:pick\s+this|you\s+must|choose\s+this)\b",
                             text, re.IGNORECASE), path


def test_riot_notice_and_original_mit_attribution_are_present():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    about = (ROOT / "frontend/settings.html").read_text(encoding="utf-8")
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "isn't endorsed by Riot Games" in readme
    assert "isn't endorsed by Riot Games" in about
    assert "Copyright (c) 2025 fabs133" in license_text
    assert "fabs133/league-aram-builder" in notices
    assert "THIRD_PARTY_NOTICES.md" in readme
