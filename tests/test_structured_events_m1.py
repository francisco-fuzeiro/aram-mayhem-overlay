"""M1/P0.3 privacy and retention contract for structured diagnostics."""
import json
import queue
import time
from pathlib import Path
from unittest.mock import Mock, AsyncMock
from types import SimpleNamespace
import inspect

import pytest

from backend.diagnostic_events import StructuredEventLogger, default_log_dir
from backend.collectors import lcda
from backend.api import server


def records(directory: Path) -> list[dict]:
    output = []
    for path in sorted(directory.glob("events.jsonl*")):
        output.extend(json.loads(line) for line in path.read_text("utf-8").splitlines())
    return output


def test_structured_json_is_whitelisted_and_excludes_identifiers(tmp_path):
    logger = StructuredEventLogger(tmp_path)
    assert logger.start()
    assert logger.emit(
        "ocr_recognition", outcome="detected", count=3, confidence=91,
        summonerName="private-player", screenshot="/private/desktop.png",
        augment_name="private-text", raw="SECRET",
    )
    assert logger.emit("lcda", status="error", error_class="timeout", token="secret")
    assert not logger.emit("arbitrary", raw="secret")
    logger.stop()
    saved = records(tmp_path)
    assert len(saved) == 2
    assert saved[0]["count"] == 3
    assert saved[1]["error_class"] == "timeout"
    assert all(set(row) <= {"timestamp", "event", "status", "error_class", "outcome", "count", "confidence"} for row in saved)
    assert "private-player" not in str(saved)
    assert "desktop.png" not in str(saved)
    assert "SECRET" not in str(saved)


def test_lcda_transitions_are_deduplicated(tmp_path):
    journal = StructuredEventLogger(tmp_path)
    journal.start()
    assert journal.transition("lcda", status="available", error_class="none")
    assert not journal.transition("lcda", status="available", error_class="none")
    assert journal.transition("lcda", status="error", error_class="timeout")
    journal.stop()
    assert [(row["status"], row["error_class"]) for row in records(tmp_path)] == [
        ("available", "none"), ("error", "timeout"),
    ]


def test_log_rotation_has_hard_file_count_and_bounded_size(tmp_path):
    journal = StructuredEventLogger(tmp_path, max_bytes=256, backups=2)
    journal.start()
    for i in range(70):
        journal.emit("ocr_window", state="opened", reason="level_due", level=i)
    journal.stop()
    files = list(tmp_path.glob("events.jsonl*"))
    assert 1 <= len(files) <= 3
    assert all(path.stat().st_size <= 256 for path in files)
    assert records(tmp_path)


def test_full_queue_drops_immediately_without_disk_io(tmp_path):
    journal = StructuredEventLogger(tmp_path, queue_size=1)
    journal._running = True  # simulate a stalled writer, never create a thread
    journal._queue.put_nowait("occupied")
    started = time.perf_counter()
    assert not journal.emit("lcda", status="available", error_class="none")
    assert time.perf_counter() - started < 0.2
    assert journal.dropped == 1
    assert list(tmp_path.iterdir()) == []  # pytest creates tmp_path itself


def test_logging_is_inert_until_started(tmp_path):
    journal = StructuredEventLogger(tmp_path)
    assert not journal.emit("lcda", status="available", error_class="none")
    assert list(tmp_path.iterdir()) == []  # pytest creates tmp_path itself
    assert not str(default_log_dir()).endswith("data/screenshots")


def test_default_path_is_outside_git_tree():
    assert default_log_dir().name == "logs"
    assert default_log_dir().parent.name.lower() in ("aram-oracle", "aramoracle")


def test_auto_and_manual_ocr_never_save_screenshots(monkeypatch):
    watched = {}
    class Watcher:
        def check(self, names, *, save):
            watched["watcher_save"] = save
            return "no_augments", None
    monkeypatch.setattr(server, "screen_watcher", Watcher())
    def detect(names, *, save):
        watched["manual_save"] = save
        return []
    monkeypatch.setattr(server, "detect_augments", detect)
    server._run_watcher_check()
    server._run_ocr_scan_manual()
    assert watched == {"watcher_save": False, "manual_save": False}


def test_lcda_timeout_emits_only_the_error_class(monkeypatch):
    sent = []
    monkeypatch.setattr(lcda, "event_log", type("Sink", (), {
        "transition": lambda self, event, **kw: sent.append((event, kw)),
    })())
    def timeout(*args, **kwargs):
        raise lcda.requests.Timeout("private http URL/token")
    monkeypatch.setattr(lcda.SESSION, "get", timeout)
    assert lcda.get_raw_game_data() is None
    assert sent == [("lcda", {"status": "error", "error_class": "timeout"})]


@pytest.mark.asyncio
async def test_live_poll_tick_records_match_and_ocr_open_close_without_raw_data(monkeypatch):
    emitted = []
    class Sink:
        def emit(self, event, **kw):
            emitted.append((event, kw))
    monkeypatch.setattr(server, "event_log", Sink())
    state = server.GameState()
    state.ws_clients.add(object())
    snapshots = iter((
        SimpleNamespace(level=3, is_dead=False, health_pct=1.0,
                        champion_stats={"attackDamage": 100}, augment_choices=[],
                        chosen_augments=[], build_style="Balanced"),
        SimpleNamespace(level=3, is_dead=False, health_pct=0.6,
                        champion_stats={"attackDamage": 100}, augment_choices=[],
                        chosen_augments=[], build_style="Balanced"),
    ))
    raw = iter(({"game": 1}, {"game": 1}))
    async def background(fn):
        return fn()
    async def broadcast(_msg):
        return None
    deps = SimpleNamespace(
        get_raw_game_data=lambda: next(raw),
        parse_game_snapshot=lambda _raw, _phase: next(snapshots),
        read_champ_select_payload=lambda: None,
        screen_watcher=SimpleNamespace(reset=Mock()),
        to_thread=background, broadcast=broadcast,
        ocr_available=lambda: False, run_watcher_check=lambda: ("unchanged", [], None),
        try_stat_delta_match=background, send_augment_confirm=background,
        static_data=object(), serialize_result=lambda *_: {},
    )
    await server.poll_tick(state, deps, 1.0)
    assert state.scan_window_open
    await server.poll_tick(state, deps, 3.0)
    assert not state.scan_window_open
    assert ("match_transition", {"from_state": "no_game", "to_state": "in_game"}) in emitted
    assert ("ocr_window", {"state": "opened", "reason": "level_due", "level": 3}) in emitted
    assert ("ocr_window", {"state": "closed", "reason": "damage", "level": 3}) in emitted
    assert "attackDamage" not in str(emitted)


@pytest.mark.asyncio
async def test_auto_inference_emits_confirmation_metadata_without_augment_name(monkeypatch):
    emitted = []
    class Sink:
        def emit(self, event, **kw):
            emitted.append((event, kw))
    monkeypatch.setattr(server, "event_log", Sink())
    state = server.GameState()
    state.scan_window_open = True
    state.scan_window_level = 3
    state.stat_snapshot_before = {"attackDamage": 100.0}
    state.augment_choices = ["private-id"]
    monkeypatch.setattr(server, "game_state", state)
    candidate = SimpleNamespace(id="private-id", name="private-augment-name")
    fake_static = SimpleNamespace(
        get_augment=lambda _id: candidate,
        get_stat_anvil=lambda _id: None,
    )
    monkeypatch.setattr(server, "static_data", fake_static)
    monkeypatch.setattr(server, "match_augment", lambda *_: (candidate, 0.93))
    monkeypatch.setattr(server, "screen_watcher", SimpleNamespace(reset=Mock()))
    monkeypatch.setattr(server, "_broadcast", AsyncMock())
    await server._try_stat_delta_match(
        SimpleNamespace(champion_stats={"attackDamage": 130.0})
    )
    assert ("augment_inference", {"result": "auto", "confidence": 0.93}) in emitted
    assert ("augment_confirmation", {"method": "automatic", "kind": "augment"}) in emitted
    assert ("ocr_window", {"state": "closed", "reason": "confirmed", "level": 3}) in emitted
    assert "private-id" not in str(emitted)
    assert "private-augment-name" not in str(emitted)


def test_ocr_screenshot_defaults_are_opt_in_not_automatic():
    from backend.collectors.screen_ocr import ScreenWatcher, detect_augments
    assert inspect.signature(ScreenWatcher.check).parameters["save"].default is False
    assert inspect.signature(detect_augments).parameters["save"].default is False
