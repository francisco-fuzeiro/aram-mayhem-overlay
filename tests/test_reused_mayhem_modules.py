"""Regression tests for the MIT-declared Mayhem Overlay algorithms adapted to Python."""

from backend.collectors import lcu, screen_ocr
from backend.storage.db import init_db, record_game, get_personal_winrate


def test_ocr_matches_wrapped_augment_title(monkeypatch):
    # The League OCR may split a long augment title into two lines.
    monkeypatch.setattr(screen_ocr, "OCR_AVAILABLE", True)
    matches = screen_ocr.match_augments(
        ["Jeweled", "Gauntlet"],
        {"a1": "Jeweled Gauntlet", "a2": "Goliath", "a3": "Firebrand"},
    )
    assert matches
    assert matches[0] == ("a1", "Jeweled Gauntlet", 100)


def test_ocr_limits_predictions_to_three_cards(monkeypatch):
    monkeypatch.setattr(screen_ocr, "OCR_AVAILABLE", True)
    names = {str(i): f"Augment Name {i}" for i in range(5)}
    matches = screen_ocr.match_augments(
        list(names.values()), names, threshold=90
    )
    assert len(matches) <= 3


def test_custom_lockfile_env_override(monkeypatch, tmp_path):
    path = tmp_path / "lockfile"
    path.write_text("LeagueClient:1234:4444:secret:https")
    monkeypatch.setenv("ARAM_ORACLE_LCU_LOCKFILE", str(path))
    assert lcu._find_lockfile() == path
    parsed = lcu._parse_lockfile(path)
    assert parsed["port"] == "4444"
    assert parsed["password"] == "secret"


def test_duplicate_sync_does_not_inflate_augment_statistics(tmp_path):
    path = tmp_path / "history.db"
    init_db(path)
    for _ in range(3):
        record_game(
            game_id="game1",
            champion_id="lux",
            augments=["augment1"],
            items=["3001"],
            win=True,
            game_time_secs=800,
            kda={},
            db_path=path,
        )
    assert get_personal_winrate("lux", "augment1", db_path=path) == (1, 1)
