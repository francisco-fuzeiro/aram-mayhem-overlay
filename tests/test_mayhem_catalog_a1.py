"""A1 offline regressions for Mayhem-only augments and distinct OCR titles.

Reference catalog fixtures are versioned public catalog metadata, not user captures.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.collectors.slot_title_ocr import _normalize, strict_match_title
from backend.static_data import loader
from backend.api import server


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def cherry_rows():
    source = json.loads(
        (FIXTURES / "cdragon_cherry_augments_2026-11-20.json").read_text(encoding="utf-8")
    )
    assert source["fields"] == ["id", "augmentNameId", "nameTRA", "rarity", "kiwiIcon"]
    assert len(source["rows"]) == 600
    return [
        {
            "id": row[0],
            "augmentNameId": row[1],
            "nameTRA": row[2],
            "rarity": row[3],
            "augmentSmallIconPath": "/Kiwi/x" if row[4] else "/Cherry/x",
        }
        for row in source["rows"]
    ]


def test_catalog_matches_exact_328_row_reference(cherry_rows):
    expected = json.loads(
        (FIXTURES / "expected_mayhem_catalog_2026-11-20.json").read_text(encoding="utf-8")
    )
    selected = loader.select_mayhem_augments(cherry_rows)
    actual = {str(row["id"]): row["nameTRA"] for row in selected}
    assert expected["count"] == len(expected["catalog"]) == len(selected) == 328
    assert actual == expected["catalog"]
    assert [int(row["id"]) for row in selected] == sorted(int(row["id"]) for row in selected)
    assert len({_normalize(row["nameTRA"]) for row in selected}) == 328


def test_catalog_keeps_real_mayhem_ids_and_drops_bad_duplicates(cherry_rows):
    selected = {
        str(row["id"]): row["nameTRA"]
        for row in loader.select_mayhem_augments(cherry_rows)
    }
    assert {key: selected[key] for key in ("1041", "1004", "1149", "1329", "1361")} == {
        "1041": "Goliath",
        "1004": "Back To Basics",
        "1149": "Impassable",
        "1329": "Biggest Snowball Ever",
        "1361": "Icathia's Fall",
    }
    for excluded in ("393", "1424", "3176"):
        assert excluded not in selected
    # The ARAM_ prefix is not a reliable selection criterion.
    assert selected["3004"] == "Get Jinxed"
    assert selected["2083"] == "Tooth Fairy"


def test_catalog_uses_id_or_kiwi_and_rejects_bad_ids():
    assert loader._is_mayhem_augment({"id": 1000, "augmentSmallIconPath": ""})
    assert loader._is_mayhem_augment({"id": "396", "augmentSmallIconPath": "/Kiwi/test"})
    assert not loader._is_mayhem_augment({"id": "396", "augmentSmallIconPath": "/Cherry/test"})
    assert not loader._is_mayhem_augment({"id": "invalid", "augmentSmallIconPath": "/Kiwi/test"})
    assert not loader._is_mayhem_augment({"id": None, "augmentSmallIconPath": "/Kiwi/test"})


def test_catalog_dedup_prefers_mayhem_id_then_lowest_numeric_id():
    rows = [
        {"id": 20, "nameTRA": "  Foo--Bar  ", "augmentSmallIconPath": "/Kiwi/x"},
        {"id": 1002, "nameTRA": "Foo Bar", "augmentSmallIconPath": ""},
        {"id": 1001, "nameTRA": "foo bar", "augmentSmallIconPath": ""},
        {"id": 1432, "nameTRA": "???", "augmentSmallIconPath": "/Kiwi/x"},
        {"id": 2000, "nameTRA": "     ", "augmentSmallIconPath": ""},
    ]
    assert [(int(row["id"]), row["nameTRA"]) for row in loader.select_mayhem_augments(rows)] == [
        (1001, "foo bar"),
    ]


@pytest.mark.parametrize("title,aid", [
    ("Goliath", "1041"),
    ("Back To Basics", "1004"),
    ("Impassable", "1149"),
    ("Biggest Snowball Ever", "1329"),
    ("Icathia's Fall", "1361"),
])
def test_strict_match_ignores_same_title_ids_in_unfiltered_600_rows(cherry_rows, title, aid):
    names = {str(row["id"]): row["nameTRA"] for row in cherry_rows}
    assert strict_match_title(title, names) == (aid, title, 100)


def test_strict_match_keeps_distinct_name_margin_and_threshold():
    names = {"104": "Scoped Weapons", "105": "Scopier Weapons"}
    assert strict_match_title("Scoped Weapons", names) == ("104", "Scoped Weapons", 100)
    assert strict_match_title("Unrecognizable Card Text", names) is None


def test_strict_match_same_normalized_title_prefers_lowest_mayhem_id():
    names = {"12": "Test--Card", "1005": "TEST CARD", "1003": "Test Card"}
    assert strict_match_title("test card", names) == ("1003", "Test Card", 100)


def test_cache_schema_is_incremented_to_prevent_reusing_arena_data():
    assert loader._AUGMENT_CACHE_SCHEMA == 4


def test_shared_server_title_catalog_augments_take_precedence(monkeypatch):
    monkeypatch.setattr(server.static_data, "_stat_anvils", {
        "1": SimpleNamespace(name="Anvil"),
        "2": SimpleNamespace(name="Old"),
    })
    monkeypatch.setattr(server.static_data, "_augments", {
        "2": SimpleNamespace(name="Mayhem Preferred"),
        "3": SimpleNamespace(name="Goliath"),
    })
    expected = {"1": "Anvil", "2": "Mayhem Preferred", "3": "Goliath"}
    assert server._ocr_title_catalog() == expected

    received = []
    monkeypatch.setattr(server, "detect_augments", lambda names, *, save: received.append(names) or [])
    monkeypatch.setattr(server.screen_watcher, "check", lambda names, *, save: (received.append(names) or "unchanged", []))
    monkeypatch.setattr(server.event_log, "emit", lambda *args, **kwargs: None)
    server._run_ocr_scan_manual()
    server._run_watcher_check()
    assert received == [expected, expected]


def test_loader_persists_only_the_328_selected_mayhem_source_rows(
    tmp_path, monkeypatch, cherry_rows,
):
    """Exercise the actual loader path, not only the pure selection helper."""
    monkeypatch.setattr(loader, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(loader, "_get_dd_version", lambda: "a1-fixture")

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_get(url, **_kwargs):
        if url == loader.CD_AUGMENTS_URL:
            return Response(cherry_rows)
        if url == loader.CD_ARENA_DESC_URL:
            return Response({"augments": []})
        raise AssertionError("unexpected catalog source")

    monkeypatch.setattr(loader.requests, "get", fake_get)
    loaded = loader._load_augments()
    cache = json.loads(
        (tmp_path / "augments_v4_a1-fixture.json").read_text(encoding="utf-8")
    )
    expected = json.loads(
        (FIXTURES / "expected_mayhem_catalog_2026-11-20.json").read_text(encoding="utf-8")
    )["catalog"]
    assert {identifier: row["name"] for identifier, row in cache.items()} == expected
    assert set(expected).issubset(set(loaded))
    assert "393" not in cache
