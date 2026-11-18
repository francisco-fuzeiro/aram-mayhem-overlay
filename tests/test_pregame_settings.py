"""Regression coverage for out-of-game Settings and local feedback.

All tests use mock game state and temporary files. They do not prove
Windows shell integration, live OCR, or in-game item behavior.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import backend.diagnostics as diagnostics_module
from backend import preferences
from backend.api import server
from backend.models import GamePhase, GameSnapshot


def test_preferences_round_trip_and_survive_new_state(tmp_path):
    path = tmp_path / "prefs" / "preferences.json"
    assert preferences.load_build_style(path) == "Balanced"
    preferences.save_build_style("Survival", path)
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "build_style": "Survival",
        "overlay": dict(preferences.DEFAULT_OVERLAY),
    }
    assert preferences.load_build_style(path) == "Survival"
    assert not path.with_name("preferences.json.tmp").exists()


@pytest.mark.parametrize("content", [
    "not json", "null", "[]", '{"build_style": "Cheat"}',
    '{"build_style": 2}',
])
def test_invalid_saved_preferences_fall_back_to_balanced(tmp_path, content):
    path = tmp_path / "preferences.json"
    path.write_text(content, encoding="utf-8")
    assert preferences.load_build_style(path) == "Balanced"


def test_preference_does_not_write_invalid_style(tmp_path):
    path = tmp_path / "preferences.json"
    with pytest.raises(ValueError):
        preferences.save_build_style("Cheat", path)
    assert not path.exists()


def test_reset_between_matches_keeps_selected_style():
    state = server.GameState()
    state.build_style = "Damage"
    state.chosen_augments = ["aug"]
    state.reset()
    assert state.build_style == "Damage"
    assert state.chosen_augments == []


@pytest.mark.asyncio
async def test_rest_setting_is_persisted_and_broadcast(monkeypatch, tmp_path):
    path = tmp_path / "preferences.json"
    monkeypatch.setattr(preferences, "PREFERENCES_FILE", path)
    state = server.GameState()
    monkeypatch.setattr(server, "game_state", state)
    broadcast = AsyncMock()
    monkeypatch.setattr(server, "_broadcast", broadcast)

    reply = await server.update_preferences(
        server.BuildPreferenceRequest(build_style="Utility")
    )
    assert reply == {"build_style": "Utility", "saved": True}
    assert (await server.get_preferences())["build_style"] == "Utility"
    assert preferences.load_build_style(path) == "Utility"
    broadcast.assert_awaited_once()
    assert json.loads(broadcast.await_args.args[0]) == {
        "type": "preferences_updated", "build_style": "Utility",
    }


@pytest.mark.asyncio
async def test_rest_rejects_invalid_style_without_disk_or_broadcast(
    monkeypatch, tmp_path,
):
    path = tmp_path / "preferences.json"
    monkeypatch.setattr(preferences, "PREFERENCES_FILE", path)
    state = server.GameState()
    monkeypatch.setattr(server, "game_state", state)
    broadcast = AsyncMock()
    monkeypatch.setattr(server, "_broadcast", broadcast)
    with pytest.raises(HTTPException) as error:
        await server.update_preferences(
            server.BuildPreferenceRequest(build_style="Unknown")
        )
    assert error.value.status_code == 422
    assert state.build_style == "Balanced"
    assert not path.exists()
    broadcast.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_preference_disk_write_leaves_live_style_unchanged(monkeypatch):
    state = server.GameState()
    monkeypatch.setattr(server, "game_state", state)

    def fail_write(_style):
        raise OSError("disk full")

    monkeypatch.setattr(preferences, "save_build_style", fail_write)
    broadcast = AsyncMock()
    monkeypatch.setattr(server, "_broadcast", broadcast)
    with pytest.raises(HTTPException) as error:
        await server.update_preferences(
            server.BuildPreferenceRequest(build_style="Damage")
        )
    assert error.value.status_code == 500
    assert state.build_style == "Balanced"
    broadcast.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_pipeline_uses_updated_style_on_next_poll(monkeypatch):
    state = server.GameState()
    state.ws_clients.add(object())
    styles = []

    class RecordingPipeline:
        def run(self, snapshot):
            styles.append(snapshot.build_style)
            return object()

    state.pipeline = RecordingPipeline()
    monkeypatch.setattr(server, "game_state", state)
    monkeypatch.setattr(server, "get_raw_game_data", lambda: {"fixture": True})
    monkeypatch.setattr(
        server, "parse_game_snapshot",
        lambda _raw, _phase: GameSnapshot(
            game_id="fixture", phase=GamePhase.IN_GAME, champion_id="jinx",
            augment_choices=[], chosen_augments=[], purchased_items=[],
            current_gold=0, game_time=0.0, enemy_champion_ids=[],
        ),
    )
    monkeypatch.setattr(
        server, "_serialize_result",
        lambda _result, _static_data, snapshot: {
            "type": "update", "build_style": snapshot.build_style,
        },
    )
    outgoing = []
    async def capture(message):
        outgoing.append(json.loads(message))
    monkeypatch.setattr(server, "_broadcast", capture)

    async def stop_after_one_poll(_interval):
        raise StopPolling()
    class StopPolling(BaseException):
        pass

    monkeypatch.setattr(server.asyncio, "sleep", stop_after_one_poll)
    for style in ("Balanced", "Damage"):
        state.build_style = style
        with pytest.raises(StopPolling):
            await server._poll_game_loop(interval=0.01)
    assert styles == ["Balanced", "Damage"]
    assert [msg["build_style"] for msg in outgoing] == styles


@pytest.mark.asyncio
async def test_report_contains_written_feedback_in_local_json(monkeypatch, tmp_path):
    from backend import github_reporter
    state = server.GameState()
    state.last_known_level = 7
    monkeypatch.setattr(server, "game_state", state)
    monkeypatch.setattr(server, "_last_bug_report_time", 0.0)
    monkeypatch.setattr(diagnostics_module, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(github_reporter, "post_issue", lambda *_args: None)

    result = await server.create_bug_report(
        server.BugReportRequest(description="  Missing augment scores  ")
    )
    saved = tmp_path / result["filename"]
    assert saved.exists()
    payload = json.loads(saved.read_text(encoding="utf-8"))
    assert payload["user_description"] == "Missing augment scores"
    assert payload["game_state"]["last_known_level"] == 7
    assert result["github_url"] is None

    with pytest.raises(HTTPException) as error:
        await server.create_bug_report(
            server.BugReportRequest(description="Another report")
        )
    assert error.value.status_code == 429


@pytest.mark.asyncio
async def test_report_failure_returns_error_and_allows_retry(monkeypatch, tmp_path):
    from backend import github_reporter
    state = server.GameState()
    monkeypatch.setattr(server, "game_state", state)
    monkeypatch.setattr(server, "_last_bug_report_time", 0.0)
    monkeypatch.setattr(diagnostics_module, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(github_reporter, "post_issue", lambda *_args: None)
    original = server.diagnostics.generate_report

    def fail_save(**_kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(server.diagnostics, "generate_report", fail_save)
    with pytest.raises(HTTPException) as error:
        await server.create_bug_report(
            server.BugReportRequest(description="Should not claim success")
        )
    assert error.value.status_code == 500
    assert server._last_bug_report_time == 0.0
    monkeypatch.setattr(server.diagnostics, "generate_report", original)
    result = await server.create_bug_report(
        server.BugReportRequest(description="Retry worked")
    )
    assert (tmp_path / result["filename"]).exists()


def test_settings_only_outside_overlay_and_qt_tray_has_open_action():
    root = Path(__file__).resolve().parent.parent
    overlay_html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    overlay_js = (root / "frontend" / "app.js").read_text(encoding="utf-8")
    settings_html = (root / "frontend" / "settings.html").read_text(encoding="utf-8")
    window_py = (root / "backend" / "overlay" / "window.py").read_text(encoding="utf-8")
    assert 'id="preferred-build"' not in overlay_html
    assert 'id="btn-submit-feedback"' not in overlay_html
    assert 'id="btn-bug-report"' not in overlay_html
    assert "bindFeedback()" not in overlay_js
    assert "bindBugReport()" not in overlay_js
    assert 'id="preferred-build"' in settings_html
    assert 'id="feedback-description"' in settings_html
    assert 'menu.addAction("Open Settings")' in window_py
    assert 'webbrowser.open(url, new=2)' in window_py
    assert "VK_O = 0x4F" in window_py and "VK_H = 0x48" in window_py
    assert "WA_TranslucentBackground" in window_py
