"""Real pinned PP-OCRv4 through the product slot matching entrypoint.

Only original reviewed retrospective title bands and no-offer negatives.
Windows/Linux CI verification is not League or independent holdout evidence.
Run with ARAM_ORACLE_V12_REAL_MODEL_TEST=1 and a verified local model.
"""
import json
import os
from pathlib import Path

import pytest
from PIL import Image

from backend.collectors.ppocr_v4 import default_model_path, verify_model
from backend.collectors.slot_title_ocr import recognize_title_slot, strict_match_title


FIXTURES = Path(__file__).parent / "fixtures"
BANDS = FIXTURES / "ocr_titles"
CASES = []
for group in ("1440p", "snips"):
    payload = json.loads((BANDS / group / "ground_truth.json").read_text(encoding="utf8"))
    for case in payload["cases"]:
        CASES.append((group + "/" + case["file"], case["expected_name"],
                      case.get("slot") or "centre"))
for image in sorted((BANDS / "no_offer").glob("*.png")):
    slot = next((s for s in ("left", "centre", "right") if "_" + s + "_" in image.name),
                "centre")
    CASES.append(("no_offer/" + image.name, None, slot))


@pytest.fixture(scope="module")
def enabled_v4():
    if os.environ.get("ARAM_ORACLE_V12_REAL_MODEL_TEST") != "1":
        pytest.skip("V1.2 real pinned-model test is opt-in for separate CI job")
    pytest.importorskip("onnxruntime")
    verify_model(default_model_path())
    payload = json.loads(
        (FIXTURES / "expected_mayhem_catalog_2026-11-20.json").read_text(
            encoding="utf8"
        )
    )
    assert payload["count"] == len(payload["catalog"]) == 328
    previous = os.environ.get("ARAM_ORACLE_OCR_ENGINE")
    os.environ["ARAM_ORACLE_OCR_ENGINE"] = "ppocrv4"
    try:
        yield payload["catalog"]
    finally:
        if previous is None:
            os.environ.pop("ARAM_ORACLE_OCR_ENGINE", None)
        else:
            os.environ["ARAM_ORACLE_OCR_ENGINE"] = previous


@pytest.mark.parametrize("file,expected,slot", CASES,
                         ids=[c[0] for c in CASES])
def test_pinned_v4_original_card_ids_or_safe_negative(
    file, expected, slot, enabled_v4
):
    catalog = enabled_v4
    with Image.open(BANDS / file) as source:
        result = recognize_title_slot(slot, source.convert("RGB"), catalog)
    expected_match = strict_match_title(expected, catalog) if expected else None
    actual_id = result[0] if result is not None else None
    expected_id = expected_match[0] if expected_match else None
    assert actual_id == expected_id, (
        f"{file}: canonical ID incorrect or unsafe negative accepted"
    )


def test_all_frozen_originals_accounted():
    assert len(CASES) == 26
    assert sum(expected is not None for _, expected, _ in CASES) == 19
    assert sum(expected is None for _, expected, _ in CASES) == 7
