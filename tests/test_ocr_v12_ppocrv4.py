"""V1.2 opt-in PP-OCRv4 contracts; no game capture, network or user data."""
import hashlib

import numpy as np
import pytest
from PIL import Image, ImageDraw

from backend.collectors import slot_title_ocr
from backend.collectors import ppocr_v4


CATALOG = {
    "1001": "En Passant",
    "1002": "Ravenous Bind",
    "1003": "It's Killing Time",
}


def test_v4_model_requires_exact_pinned_digest_and_size(tmp_path, monkeypatch):
    model = tmp_path / "ppocrv4.onnx"
    model.write_bytes(b"untrusted")
    with pytest.raises(ValueError, match="integrity"):
        ppocr_v4.verify_model(model)
    monkeypatch.setattr(ppocr_v4, "MODEL_SHA256", hashlib.sha256(b"trusted").hexdigest())
    monkeypatch.setattr(ppocr_v4, "MODEL_BYTES", 7)
    model.write_bytes(b"trusted")
    assert ppocr_v4.verify_model(model) == model
    model.write_bytes(b"trusteD")
    with pytest.raises(ValueError, match="integrity"):
        ppocr_v4.verify_model(model)


def test_v4_line_splitting_rejects_empty_and_keeps_two_lines():
    img = Image.new("RGB", (120, 70), "black")
    assert ppocr_v4.split_title_lines(img) == []
    draw = ImageDraw.Draw(img)
    draw.rectangle((15, 12, 80, 23), fill="white")
    draw.rectangle((17, 40, 100, 51), fill="white")
    lines = ppocr_v4.split_title_lines(img)
    assert len(lines) == 2
    assert all(line.width > 0 and line.height > 0 for line in lines)


def test_v4_ctc_rejects_wrong_dictionary_width_without_guessing():
    logits = np.array([
        [0.01, 0.90, 0.04, 0.05],
        [0.01, 0.92, 0.04, 0.03],
        [0.95, 0.02, 0.02, 0.01],
        [0.01, 0.02, 0.96, 0.01],
    ], dtype=np.float32)
    text, confidence = ppocr_v4.decode_ctc(logits, ["A", "B"])
    assert text == "AB"
    assert confidence > 0.9
    with pytest.raises(ValueError, match="decoder"):
        ppocr_v4.decode_ctc(logits[:, :3], ["A", "B"])
    with pytest.raises(ValueError, match="decoder"):
        ppocr_v4.decode_ctc(np.zeros((2, 2, 4), dtype=np.float32), ["A", "B"])


def test_v4_opt_in_respects_strict_match_and_no_unsafe_secondary_guess(monkeypatch):
    monkeypatch.setenv("ARAM_ORACLE_OCR_ENGINE", "ppocrv4")
    monkeypatch.setattr(ppocr_v4, "recognize_text", lambda _im: "En Passant")
    monkeypatch.setattr(slot_title_ocr.pytesseract, "image_to_string",
                        lambda *_a, **_k: pytest.fail("Tesseract cannot overrule valid v4"))
    crop = Image.new("RGB", (340, 90))
    assert slot_title_ocr.recognize_title_slot("left", crop, CATALOG)[0] == "1001"
    monkeypatch.setattr(ppocr_v4, "recognize_text", lambda _im: "unrelated dialogue")
    assert slot_title_ocr.recognize_title_slot("left", crop, CATALOG) is None


def test_v4_missing_runtime_falls_back_to_existing_tesseract(monkeypatch):
    monkeypatch.setenv("ARAM_ORACLE_OCR_ENGINE", "ppocrv4")
    monkeypatch.setattr(ppocr_v4, "recognize_text", lambda _im: None)
    monkeypatch.setattr(slot_title_ocr.pytesseract, "image_to_string",
                        lambda *_a, **_k: "Ravenous Bind")
    assert slot_title_ocr.recognize_title_slot(
        "centre", Image.new("RGB", (340, 90)), CATALOG
    )[0] == "1002"


def test_v4_slot_identity_and_duplicate_fail_closed(monkeypatch):
    monkeypatch.setenv("ARAM_ORACLE_OCR_ENGINE", "ppocrv4")
    crops = {
        "left": Image.new("RGB", (340, 90), (255, 0, 0)),
        "centre": Image.new("RGB", (340, 90), (0, 255, 0)),
        "right": Image.new("RGB", (340, 90), (0, 0, 255)),
    }
    names = {(255, 0, 0): "unrecognized", (0, 255, 0): "Ravenous Bind",
             (0, 0, 255): "It's Killing Time"}
    monkeypatch.setattr(ppocr_v4, "recognize_text",
                        lambda image: names[image.getpixel((0, 0))])
    result = slot_title_ocr.recognize_title_slots(crops, CATALOG)
    assert result.slots["left"] is None
    assert result.slots["centre"][0] == "1002"
    assert result.slots["right"][0] == "1003"
    names[(255, 0, 0)] = "Ravenous Bind"
    result = slot_title_ocr.recognize_title_slots(crops, CATALOG)
    assert result.slots["left"] is None
    assert result.slots["centre"] is None
    assert result.slots["right"][0] == "1003"


def test_tesseract_remains_default(monkeypatch):
    monkeypatch.delenv("ARAM_ORACLE_OCR_ENGINE", raising=False)
    monkeypatch.setattr(slot_title_ocr.pytesseract, "image_to_string",
                        lambda *_a, **_k: "En Passant")
    monkeypatch.setattr(ppocr_v4, "recognize_text",
                        lambda _im: pytest.fail("v4 must be opt-in"))
    assert slot_title_ocr.recognize_title_slot(
        "left", Image.new("RGB", (340, 90)), CATALOG
    )[0] == "1001"
