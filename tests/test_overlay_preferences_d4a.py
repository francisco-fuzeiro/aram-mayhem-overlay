"""D4a schema, migration, API and restart persistence tests.

No Qt renderer, real League window or Tesseract dependency is required.
"""
import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend import preferences
from backend.api import server


def example_overlay(**changes):
    return {**preferences.DEFAULT_OVERLAY, **changes}


def test_defaults_without_file(tmp_path):
    saved = preferences.load_preferences(tmp_path / "missing.json")
    assert saved == {
        "schema_version": 1, "build_style": "Balanced",
        "overlay": example_overlay(),
    }
    saved["overlay"]["opacity"] = 0.5
    assert preferences.DEFAULT_OVERLAY["opacity"] == 0.92


def test_legacy_v0_migrates_on_write_and_retains_build_style(tmp_path):
    path = tmp_path / "preferences.json"
    path.write_text('{"build_style": "Survival"}', encoding="utf-8")
    assert preferences.load_preferences(path)["overlay"] == example_overlay()
    assert json.loads(path.read_text(encoding="utf-8")) == {"build_style": "Survival"}
    preferences.save_overlay_preferences(example_overlay(scale=1.25), path)
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "build_style": "Survival",
        "overlay": example_overlay(scale=1.25),
    }
    assert not path.with_name(path.name + ".tmp").exists()


def test_legacy_explicit_version_zero_and_style_only_update(tmp_path):
    path = tmp_path / "preferences.json"
    path.write_text('{"schema_version": 0, "build_style": "Damage"}', encoding="utf-8")
    preferences.save_build_style("Utility", path)
    assert preferences.load_preferences(path)["build_style"] == "Utility"
    assert preferences.load_preferences(path)["overlay"] == example_overlay()


def test_overlay_survives_build_style_update_and_simulated_restart(tmp_path):
    path = tmp_path / "preferences.json"
    overlay = example_overlay(anchor="bottom_left", offset_x=-100, offset_y=320,
                              opacity=0.55, scale=1.4)
    preferences.save_overlay_preferences(overlay, path)
    preferences.save_build_style("Damage", path)
    reloaded = preferences.load_preferences(path)  # fresh read, not in-memory state
    assert reloaded["overlay"] == overlay
    assert reloaded["build_style"] == "Damage"


@pytest.mark.parametrize("bad", [
    {"anchor": "center"}, {"anchor": ""}, {"anchor": None},
    {"offset_x": -501}, {"offset_y": 501}, {"offset_x": 3.5},
    {"offset_y": True}, {"opacity": 0.39}, {"opacity": 1.01},
    {"opacity": float("nan")}, {"opacity": float("inf")},
    {"opacity": "0.8"}, {"scale": 0.74}, {"scale": 1.51},
    {"scale": float("-inf")}, {"scale": None},
    {"extra": 2},
])
def test_rejects_invalid_overlay_without_writing(tmp_path, bad):
    path = tmp_path / "preferences.json"
    with pytest.raises(ValueError):
        preferences.save_overlay_preferences(example_overlay(**bad), path)
    assert not path.exists()


@pytest.mark.parametrize("payload", [None, [], {}, {"anchor": "top_right"}])
def test_rejects_incomplete_or_malformed_overlay(payload):
    with pytest.raises(ValueError):
        preferences.validate_overlay(payload)


def test_corrupted_saved_fields_fall_back_individually(tmp_path):
    path = tmp_path / "prefs.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "build_style": "Utility",
        "overlay": {
            "anchor": "garbage", "offset_x": 120,
            "offset_y": False, "opacity": 0.8, "scale": "huge",
        },
    }), encoding="utf-8")
    loaded = preferences.load_preferences(path)
    assert loaded == {
        "schema_version": 1, "build_style": "Utility",
        "overlay": example_overlay(offset_x=120, opacity=0.8),
    }


@pytest.mark.parametrize("value", [
    "not json", "null", "[]", '{"schema_version": 99, "build_style": "Damage"}',
    '{"schema_version": true, "build_style": "Damage"}',
])
def test_bad_or_unknown_schema_loads_safe_defaults(tmp_path, value):
    path = tmp_path / "prefs.json"
    path.write_text(value, encoding="utf-8")
    assert preferences.load_preferences(path) == {
        "schema_version": 1, "build_style": "Balanced", "overlay": example_overlay(),
    }


def test_future_schema_refuses_overwrite(tmp_path):
    path = tmp_path / "prefs.json"
    raw = '{"schema_version": 2, "build_style": "Damage"}'
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        preferences.save_build_style("Survival", path)
    assert path.read_text(encoding="utf-8") == raw


def test_atomic_write_failure_retains_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "prefs.json"
    preferences.save_build_style("Survival", path)
    original = path.read_text(encoding="utf-8")
    def deny_replace(*_args):
        raise OSError("disk full")
    monkeypatch.setattr(preferences.os, "replace", deny_replace)
    with pytest.raises(OSError):
        preferences.save_overlay_preferences(example_overlay(opacity=0.7), path)
    assert path.read_text(encoding="utf-8") == original
    assert not path.with_name("prefs.json.tmp").exists()


@pytest.mark.asyncio
async def test_fastapi_overlay_write_broadcast_and_restart(monkeypatch, tmp_path):
    path = tmp_path / "preferences.json"
    monkeypatch.setattr(preferences, "PREFERENCES_FILE", path)
    state = server.GameState()
    monkeypatch.setattr(server, "game_state", state)
    broadcast = AsyncMock()
    monkeypatch.setattr(server, "_broadcast", broadcast)
    overlay = example_overlay(anchor="bottom_right", offset_x=-40, scale=1.2)
    response = await server.update_overlay_preferences(overlay)
    assert response == {"schema_version": 1, "overlay": overlay, "saved": True}
    assert (await server.get_preferences())["overlay"] == overlay
    assert json.loads(broadcast.await_args.args[0]) == {
        "type": "preferences_updated", "build_style": "Balanced",
        "overlay": overlay, "schema_version": 1,
    }
    # Simulate a full new process/HTTP state initialized from the same disk.
    monkeypatch.setattr(server, "game_state", server.GameState())
    monkeypatch.setattr(server, "init_db", lambda: None)
    monkeypatch.setattr(server.static_data, "load", lambda: None)
    monkeypatch.setattr(server, "Pipeline", lambda _data: object())
    async def suspended_poll():
        await asyncio.Event().wait()
    monkeypatch.setattr(server, "_poll_game_loop", suspended_poll)
    async with server.lifespan(server.app):
        prefs = await server.get_preferences()
        assert prefs["schema_version"] == 1
        assert prefs["overlay"] == overlay
        assert prefs["build_style"] == "Balanced"
    assert preferences.load_preferences(path)["overlay"] == overlay


@pytest.mark.asyncio
async def test_fastapi_invalid_overlay_rejects_without_state_change(monkeypatch, tmp_path):
    path = tmp_path / "prefs.json"
    monkeypatch.setattr(preferences, "PREFERENCES_FILE", path)
    state = server.GameState()
    monkeypatch.setattr(server, "game_state", state)
    broadcast = AsyncMock()
    monkeypatch.setattr(server, "_broadcast", broadcast)
    for invalid in (example_overlay(opacity=0), example_overlay(offset_x="5"),
                    {"anchor": "top_left"}):
        with pytest.raises(HTTPException) as err:
            await server.update_overlay_preferences(invalid)
        assert err.value.status_code == 422
    assert not path.exists()
    assert state.overlay_preferences == example_overlay()
    broadcast.assert_not_awaited()


@pytest.mark.asyncio
async def test_fastapi_disk_failure_keeps_live_overlay(monkeypatch):
    state = server.GameState()
    monkeypatch.setattr(server, "game_state", state)
    broadcast = AsyncMock()
    monkeypatch.setattr(server, "_broadcast", broadcast)
    def fail_save(_overlay):
        raise OSError("disk unavailable")
    monkeypatch.setattr(preferences, "save_overlay_preferences", fail_save)
    with pytest.raises(HTTPException) as err:
        await server.update_overlay_preferences(example_overlay(opacity=0.6))
    assert err.value.status_code == 500
    assert state.overlay_preferences == example_overlay()
    broadcast.assert_not_awaited()


def test_game_reset_does_not_clear_overlay_preferences():
    state = server.GameState()
    state.overlay_preferences = example_overlay(scale=1.3)
    state.reset()
    assert state.overlay_preferences["scale"] == 1.3
