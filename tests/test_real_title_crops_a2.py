"""A2 offline regression checks on individually privacy-reviewed real title bands.

The original unmodified ground truths and PNGs come from the archived v3 ZIP.
Snips are not geometry evidence. These checks never capture the game/desktop.
"""
import json
from collections import Counter
from pathlib import Path

import pytest
from PIL import Image

from backend.collectors.slot_title_ocr import _normalize, recognize_title_slot
from backend.static_data.loader import select_mayhem_augments
from tests.conftest import require_tesseract_or_skip


FIXTURES = Path(__file__).parent / "fixtures"
OCR_TITLES = FIXTURES / "ocr_titles"
GROUPS = ("1440p", "snips")


def _ground_truth(group: str) -> dict:
    return json.loads(
        (OCR_TITLES / group / "ground_truth.json").read_text(encoding="utf-8")
    )


def _cases() -> list[tuple[str, dict]]:
    return [
        (group, case)
        for group in GROUPS
        for case in _ground_truth(group)["cases"]
    ]


CASES = _cases()


@pytest.fixture(scope="module")
def tesseract_ready():
    require_tesseract_or_skip()


@pytest.fixture(scope="module")
def mayhem_catalog() -> dict[str, str]:
    data = json.loads(
        (FIXTURES / "expected_mayhem_catalog_2026-11-20.json").read_text(
            encoding="utf-8"
        )
    )
    assert data["count"] == len(data["catalog"]) == 328
    return data["catalog"]


@pytest.mark.parametrize(
    "group,case",
    CASES,
    ids=[f"{group}/{case['file']}" for group, case in CASES],
)
def test_real_title_band_matches_exact_ground_truth(
    group: str, case: dict, tesseract_ready, mayhem_catalog,
):
    """Use real OCR, full-title matching and the original physical slot label."""
    slot = case.get("slot", "centre")
    assert slot in ("left", "centre", "right")
    with Image.open(OCR_TITLES / group / case["file"]) as source:
        match = recognize_title_slot(slot, source.convert("RGB"), mayhem_catalog)
    recognized_name = match[1] if match is not None else None
    assert recognized_name == case["expected_name"], (
        f"{group}/{case['file']}: expected {case['expected_name']!r}, "
        f"recognized {recognized_name!r}"
    )


def test_real_title_names_exist_exactly_once_in_selected_600_row_catalog():
    """Independent from OCR, test actual A1 selection, not just reference JSON."""
    source = json.loads(
        (FIXTURES / "cdragon_cherry_augments_2026-11-20.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(source["rows"]) == 600
    rows = [
        {
            "id": row[0],
            "augmentNameId": row[1],
            "nameTRA": row[2],
            "rarity": row[3],
            "augmentSmallIconPath": "/Kiwi/x" if row[4] else "/Cherry/x",
        }
        for row in source["rows"]
    ]
    selected = select_mayhem_augments(rows)
    assert len(selected) == 328
    normalized_counts = Counter(_normalize(row["nameTRA"]) for row in selected)
    for group, case in CASES:
        expected = case["expected_name"]
        if expected is not None:
            assert normalized_counts[_normalize(expected)] == 1, (
                f"{group}/{case['file']}: {expected!r} absent or duplicated"
            )


def test_real_title_fixture_counts_match_v3_manifest_without_tesseract():
    """MANIFEST: 13 1440p (11 named, 2 null), 8 snips (8 named)."""
    counts = {
        "1440p": (13, 11, 2),
        "snips": (8, 8, 0),
    }
    total = named = negative = 0
    for group, (expected_pngs, expected_names, expected_nulls) in counts.items():
        cases = _ground_truth(group)["cases"]
        actual_files = {path.name for path in (OCR_TITLES / group).glob("*.png")}
        expected_files = {case["file"] for case in cases}
        assert len(cases) == len(expected_files) == expected_pngs
        assert actual_files == expected_files
        names = sum(case["expected_name"] is not None for case in cases)
        nulls = sum(case["expected_name"] is None for case in cases)
        assert (names, nulls) == (expected_names, expected_nulls)
        total += len(actual_files)
        named += names
        negative += nulls
    assert (total, named, negative) == (21, 19, 2)
