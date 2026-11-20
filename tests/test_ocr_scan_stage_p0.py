"""P0 offline scan-stage diagnosis: no stored images, OCR strings or player data.

A detected Tesseract binary is not proof a Mayhem offer was recognized.
"""
from itertools import count

from PIL import Image

from backend.api import server
from backend.collectors import screen_ocr, slot_title_ocr
from backend.collectors.league_window import LeagueWindow
from backend.collectors.window_capture import CaptureProof
from backend.diagnostic_events import _clean


WINDOW = LeagueWindow(7, 8, 31, 2552, 1384, True)
NAMES = {"1": "En Passant", "2": "Ravenous Bind", "3": "It's Killing Time"}


_PROOF_TIMES = count(10)


def proven(region, game=WINDOW):
    return screen_ocr.RegionCapture(
        region, CaptureProof("wgc", game.hwnd, game.rect, float(next(_PROOF_TIMES)), "other"), "ok",
    )


def test_ocr_scan_stage_distinguishes_executable_from_missing_game_window(monkeypatch):
    watcher = screen_ocr.ScreenWatcher()
    assert watcher.last_scan_stage == "not_scanned"
    monkeypatch.setattr(screen_ocr, "is_available", lambda: False)
    assert watcher.check(NAMES)[0] == "unavailable"
    assert watcher.last_scan_stage == "ocr_unavailable"
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: None)
    assert watcher.check(NAMES)[0] == "unavailable"
    assert watcher.last_scan_stage == "game_window_unavailable"
    watcher.reset()
    assert watcher.last_scan_stage == "not_scanned"


def test_ocr_scan_stage_separates_capture_failure_and_geometry(monkeypatch):
    watcher = screen_ocr.ScreenWatcher()
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: WINDOW)
    monkeypatch.setattr(screen_ocr, "capture_augment_region", lambda *_a, **_k:
                        screen_ocr.RegionCapture(None, None, "invalid_frame"))
    assert watcher.check(NAMES)[0] == "capture_unavailable"
    assert watcher.last_scan_stage == "capture_invalid"
    invalid = LeagueWindow(7, 8, 31, 1608, 1031, False)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: invalid)
    monkeypatch.setattr(screen_ocr, "capture_augment_region", lambda *_a, **_k:
                        proven(Image.new("RGB", (1120, 280)), invalid))
    assert watcher.check(NAMES)[0] == "unavailable"
    assert watcher.last_scan_stage == "geometry_unsupported"


def test_ocr_scan_stage_distinguishes_unreadable_text_from_verified_offer(monkeypatch):
    watcher = screen_ocr.ScreenWatcher(sleep_fn=lambda _: None)
    region = screen_ocr.get_augment_region(2544, 1353)
    strip = Image.new("RGB", (int(2544 * (region[2] - region[0])), int(1353 * (region[3] - region[1]))))
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: WINDOW)
    monkeypatch.setattr(screen_ocr, "capture_augment_region", lambda *_a, **_k: proven(strip))
    monkeypatch.setattr(slot_title_ocr, "recognize_title_slot", lambda *_a: None)
    assert watcher.check(NAMES)[0] == "no_augments"
    assert watcher.last_scan_stage == "titles_unidentified"
    watcher.reset()
    matches = {"left": ("1", "En Passant", 100), "centre": ("2", "Ravenous Bind", 100), "right": ("3", "It's Killing Time", 100)}
    monkeypatch.setattr(slot_title_ocr, "recognize_title_slot", lambda slot, *_a: matches[slot])
    action, result = watcher.check(NAMES)
    assert action == "detected"
    assert [r[0] for r in result] == ["1", "2", "3"]
    assert watcher.last_scan_stage == "titles_detected"


def test_ocr_stage_event_schema_never_accepts_arbitrary_paths_or_text():
    record = _clean("ocr_scan_stage", {"stage": "titles_unidentified", "raw_text": "private account", "path": "C:/private"})
    assert record == {"stage": "titles_unidentified"}
    assert _clean("ocr_scan_stage", {"stage": "C:/private"}) == {}


def test_ocr_status_includes_stage_and_scan_trigger_not_private_ocr(monkeypatch):
    monkeypatch.setattr(server.ocr_capture, "readiness_status", lambda: {
        "available": True, "reason": "ready", "next_step": "Dependency only",
    })
    monkeypatch.setattr(server.screen_watcher, "_last_scan_stage", "titles_unidentified")
    monkeypatch.setattr(server, "game_state", server.GameState())
    response = server.ocr_status()
    assert response["scan_stage"] == "titles_unidentified"
    assert response["scan_window_open"] is False
    assert "raw_text" not in str(response)
    monkeypatch.setattr(server.screen_watcher, "_last_scan_stage", "C:/private")
    assert server.ocr_status()["scan_stage"] == "not_scanned"

