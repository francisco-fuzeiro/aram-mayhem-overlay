"""RED-first contracts for V1.1d private manual labeling (no OCR)."""
import csv
import hashlib
from pathlib import Path

import pytest
from PIL import Image

from benchmarks.ocr_v11d.label_core import save_confirmed_frame, title_suggestions


def specimen():
    image = Image.new("RGB", (120, 60), (180, 10, 70))
    for x in range(120):
        for y in range(60):
            image.putpixel((x, y), ((x * 3) % 256, (y * 4) % 256, (x + y) % 256))
    return image


def choose(slot="left", rect=(0, 0, 35, 25), expected="Donation", category="title"):
    return {"slot": slot, "rect": rect, "expected": expected,
            "category": category, "rarity": "Silver", "two_line": False}


def store(tmp_path, *, image=None, choices=None, **kw):
    return save_confirmed_frame(
        image or specimen(), choices if choices is not None else [choose()],
        tmp_path / "private", repository=tmp_path / "checkout",
        catalog={"Donation", "Blunt Force", "Erosion"},
        frozen_hashes=set(), session=kw.pop("session", "session001"),
        frame=kw.pop("frame", "frame001"), offer=kw.pop("offer", "offer001"),
        split=kw.pop("split", "development"),
        confirmed=kw.pop("confirmed", True),
        context=kw.pop("context", {"scene": "offer", "focus": "game",
                                   "opgg": "unknown", "dpi": "unknown",
                                   "reroll": "none"}),
        **kw)


def read_rows(root):
    with (root / "private" / "human_labels.csv").open(encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def test_must_confirm_human_truth_before_any_persistence(tmp_path):
    with pytest.raises(ValueError, match="confirmation"):
        store(tmp_path, confirmed=False)
    assert not (tmp_path / "private" / "human_labels.csv").exists()


def test_three_cards_share_one_frame_and_keep_true_slot_and_context(tmp_path):
    selections = [
        choose("left", (0, 0, 30, 20), "Donation"),
        choose("centre", (40, 0, 70, 20), "Blunt Force"),
        choose("right", (80, 0, 110, 20), "Erosion"),
    ]
    assert store(tmp_path, choices=selections, context={"scene": "reroll", "focus": "game",
                  "opgg": "yes", "dpi": "125", "reroll": "right"}) == 3
    rows = read_rows(tmp_path)
    assert {x["slot"] for x in rows} == {"left", "centre", "right"}
    assert {x["source_frame"] for x in rows} == {"frame001"}
    assert {x["expected"] for x in rows} == {"Donation", "Blunt Force", "Erosion"}
    assert all(x["privacy_approved"] == "yes" and x["reroll"] == "right"
               and x["scene"] == "reroll" for x in rows)
    assert all((tmp_path / "private" / x["file"]).is_file() for x in rows)


def test_rejects_unverified_or_non_catalog_title_and_unsafe_crop(tmp_path):
    with pytest.raises(ValueError, match="catalog"):
        store(tmp_path, choices=[choose(expected="Donati0n")])
    with pytest.raises(ValueError, match="rectangle"):
        store(tmp_path, choices=[choose(rect=(-1, 0, 35, 25))])
    with pytest.raises(ValueError, match="title"):
        store(tmp_path, choices=[choose(expected="Donation", category="dialog")])
    assert not (tmp_path / "private" / "human_labels.csv").exists()


def test_rejects_duplicates_and_same_frame_slot(tmp_path):
    store(tmp_path)
    with pytest.raises(ValueError, match="duplicate"):
        store(tmp_path, frame="frame002")
    with pytest.raises(ValueError, match="frame"):
        store(tmp_path, choices=[choose(rect=(40, 0, 75, 25))])
    assert len(read_rows(tmp_path)) == 1


def test_rejects_session_leakage_and_existing_frozen_image(tmp_path):
    store(tmp_path)
    with pytest.raises(ValueError, match="session"):
        store(tmp_path, split="holdout", frame="frame002",
              choices=[choose(rect=(40, 0, 75, 25))])
    png_file = tmp_path / "private" / read_rows(tmp_path)[0]["file"]
    with pytest.raises(ValueError, match="frozen"):
        save_confirmed_frame(specimen(), [choose()], tmp_path / "other",
            repository=tmp_path / "checkout", catalog={"Donation"},
            frozen_hashes={hashlib.sha256(png_file.read_bytes()).hexdigest()},
            session="session002", frame="frame002", offer="offer002",
            split="holdout", confirmed=True)
    assert len(read_rows(tmp_path)) == 1


def test_negative_samples_require_blank_title_and_do_not_create_ocr(tmp_path):
    assert store(tmp_path, choices=[choose(expected="", category="no_offer")],
                 context={"scene": "no_offer", "focus": "alt_tab",
                          "opgg": "no", "dpi": "100", "reroll": "none"}) == 1
    row = read_rows(tmp_path)[0]
    assert row["category"] == "no_offer" and row["expected"] == ""
    assert row["focus"] == "alt_tab" and row["scene"] == "no_offer"


def test_labels_cannot_live_inside_repository(tmp_path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    with pytest.raises(ValueError, match="outside"):
        save_confirmed_frame(specimen(), [choose()], checkout / "data",
            repository=checkout, catalog={"Donation"}, frozen_hashes=set(),
            session="session001", frame="frame001", offer="offer001",
            split="development", confirmed=True)


def test_suggestions_only_return_catalog_values_and_are_bounded():
    titles = ["Donation", "Blunt Force", "Erosion"]
    assert title_suggestions("blunt", titles) == ["Blunt Force"]
    assert title_suggestions("", titles, limit=2) == ["Blunt Force", "Donation"]
    assert title_suggestions("not-in-catalog", titles) == []
