"""M5/P0.4: privacy-safe, locally prepared OCR truth fixtures.

Synthetic pixels in these tests exercise plumbing only. They are not League
samples, title-position calibration, or evidence of OCR recognition accuracy.
"""
import json
from pathlib import Path

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from scripts.prepare_ocr_fixtures import prepare_fixture_case, main


SLOTS = ("left", "centre", "right")


def input_triplet(tmp_path: Path, *, size=(340, 85), pixels=None):
    """Create synthetic card-title crops with deliberately private metadata."""
    paths = {}
    pixels = pixels or [(160, 42, 50), (42, 160, 50), (50, 42, 160)]
    for slot, rgb in zip(SLOTS, pixels):
        path = tmp_path / f"card_{slot}_synthetic.png"
        metadata = PngInfo()
        metadata.add_text("private-screen-text", "PRIVATE ACCOUNT / OCR RAW TEXT")
        Image.new("RGB", size, rgb).save(path, pnginfo=metadata)
        paths[slot] = path
    return paths


def test_three_title_crops_truth_and_zero_embedded_metadata(tmp_path):
    sources = input_triplet(tmp_path)
    out = tmp_path / "fixtures" / "ocr"
    created = prepare_fixture_case(
        sources=sources,
        truth={"left": "aug_123", "centre": None, "right": "mayhem:456"},
        case_id="offer-1440p-01", output_dir=out,
    )
    assert set(created) == {"left", "centre", "right", "truth"}
    assert {p.name for p in out.iterdir()} == {
        "offer-1440p-01.left.png", "offer-1440p-01.centre.png",
        "offer-1440p-01.right.png", "offer-1440p-01.truth.json",
    }
    assert json.loads(created["truth"].read_text("utf-8")) == {
        "left": "aug_123", "centre": None, "right": "mayhem:456",
    }
    for slot, expected_colour in zip(SLOTS, [(160, 42, 50), (42, 160, 50), (50, 42, 160)]):
        with Image.open(created[slot]) as cropped:
            assert cropped.format == "PNG"
            assert cropped.size == (340, 85)
            assert cropped.mode == "RGB"
            assert cropped.getpixel((0, 0)) == expected_colour
            assert not cropped.info
        assert "PRIVATE ACCOUNT" not in created[slot].read_bytes().decode("latin-1")
    # The input debug images are never modified or copied alongside the fixture.
    assert len(list(out.iterdir())) == 4


def test_unknown_slots_are_explicit_null_not_guess_ids(tmp_path):
    output = prepare_fixture_case(
        sources=input_triplet(tmp_path), truth=dict.fromkeys(SLOTS),
        case_id="dialog-left-1080p-02", output_dir=tmp_path / "out",
    )
    truth = json.loads(output["truth"].read_text("utf-8"))
    assert truth == dict.fromkeys(SLOTS)


@pytest.mark.parametrize("case_id", [
    "../private", "a/b", "A-Upper", "contains spaces", ".hidden",
    "root\\file", "a" * 81, "",
])
def test_case_id_cannot_create_paths_or_encode_personal_text(tmp_path, case_id):
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        prepare_fixture_case(
            sources=input_triplet(tmp_path), truth=dict.fromkeys(SLOTS),
            case_id=case_id, output_dir=out,
        )
    assert not out.exists()


@pytest.mark.parametrize("bad_id", [
    "text with spaces", "../secret", "<script>", "a" * 81, "", 42,
])
def test_invalid_truth_ids_rejected_without_file_writes(tmp_path, bad_id):
    out = tmp_path / "out"
    truth = {"left": bad_id, "centre": None, "right": "123"}
    with pytest.raises(ValueError):
        prepare_fixture_case(
            sources=input_triplet(tmp_path), truth=truth,
            case_id="offer-1440p-02", output_dir=out,
        )
    assert not out.exists()


@pytest.mark.parametrize("size", [
    (1920, 1080), (1344, 302), (10, 10), (340, 500), (1100, 85),
])
def test_full_desktop_full_augment_strip_and_invalid_geometry_rejected(tmp_path, size):
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        prepare_fixture_case(
            sources=input_triplet(tmp_path, size=size),
            truth=dict.fromkeys(SLOTS), case_id="offer-1440p-03",
            output_dir=out,
        )
    assert not out.exists()


def test_mismatched_band_dimensions_fail_closed_before_persistence(tmp_path):
    sources = input_triplet(tmp_path)
    Image.new("RGB", (600, 100)).save(sources["centre"])
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        prepare_fixture_case(
            sources=sources, truth=dict.fromkeys(SLOTS),
            case_id="offer-1440p-03", output_dir=out,
        )
    assert not out.exists()


def test_duplicate_or_missing_slots_and_reused_source_are_rejected(tmp_path):
    sources = input_triplet(tmp_path)
    out = tmp_path / "out"
    for broken in [
        {"left": sources["left"], "right": sources["right"]},
        {**sources, "extra": sources["right"]},
        {**sources, "centre": sources["left"]},
    ]:
        with pytest.raises(ValueError):
            prepare_fixture_case(
                sources=broken, truth=dict.fromkeys(SLOTS),
                case_id="offer-1440p-03", output_dir=out,
            )
    assert not out.exists()


def test_existing_case_cannot_be_overwritten_or_partially_replaced(tmp_path):
    sources = input_triplet(tmp_path)
    out = tmp_path / "out"
    truth = {"left": "old", "centre": None, "right": None}
    created = prepare_fixture_case(
        sources=sources, truth=truth, case_id="offer-1440p-04", output_dir=out,
    )
    previous = {key: path.read_bytes() for key, path in created.items()}
    with pytest.raises(FileExistsError):
        prepare_fixture_case(
            sources=sources,
            truth={"left": "new", "centre": "new", "right": "new"},
            case_id="offer-1440p-04", output_dir=out,
        )
    assert {key: path.read_bytes() for key, path in created.items()} == previous


def test_invalid_png_rejected_without_persisted_results(tmp_path):
    sources = input_triplet(tmp_path)
    sources["centre"].write_text("not an image", encoding="utf-8")
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        prepare_fixture_case(
            sources=sources, truth=dict.fromkeys(SLOTS),
            case_id="offer-1440p-05", output_dir=out,
        )
    assert not out.exists()


def test_cli_reads_explicit_three_labels_and_writes_four_files(tmp_path):
    images = input_triplet(tmp_path)
    out = tmp_path / "fixtures" / "ocr"
    result = main([
        "--left", str(images["left"]),
        "--centre", str(images["centre"]),
        "--right", str(images["right"]),
        "--left-id", "123", "--centre-id", "unknown", "--right-id", "456",
        "--case-id", "reroll-centre-1440p-01", "--output-dir", str(out),
    ])
    assert result == 0
    assert json.loads((out / "reroll-centre-1440p-01.truth.json").read_text("utf-8")) == {
        "left": "123", "centre": None, "right": "456",
    }


def test_fixture_preparation_is_never_a_live_capture_or_ocr(monkeypatch, tmp_path):
    sources = input_triplet(tmp_path)
    from backend.collectors import screen_ocr
    from backend.collectors import league_window

    monkeypatch.setattr(screen_ocr, "capture_augment_region",
                        lambda *a, **kw: pytest.fail("captured live screen"))
    monkeypatch.setattr(screen_ocr, "extract_text",
                        lambda *a, **kw: pytest.fail("performed OCR"))
    monkeypatch.setattr(league_window, "find_league_window",
                        lambda *a, **kw: pytest.fail("inspected running game"))
    output = prepare_fixture_case(
        sources=sources, truth=dict.fromkeys(SLOTS),
        case_id="offline-1440p-01", output_dir=tmp_path / "out",
    )
    assert len(output) == 4
