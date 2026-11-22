"""RED-first unit tests of benchmark integrity, not fabricated OCR success."""
import hashlib
import pytest
from benchmarks.ocr_v11.runner import (
    verify_asset, validate_cases, validate_output_dimensions, classify, assert_predictions,
)

def test_file_missing_fail_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        verify_asset(tmp_path / "missing.png", "0" * 64)

def test_corrupt_sha_fail_closed(tmp_path):
    p = tmp_path / "crop.png"
    p.write_bytes(b"image")
    with pytest.raises(ValueError, match="sha"):
        verify_asset(p, "0" * 64)

def test_missing_model_fail_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        verify_asset(tmp_path / "model.onnx", "0" * 64)

def test_corrupt_model_fail_closed(tmp_path):
    p = tmp_path / "model.onnx"
    p.write_bytes(b"fake")
    with pytest.raises(ValueError, match="sha"):
        verify_asset(p, "0" * 64)

def test_asset_valid_size_and_sha(tmp_path):
    p = tmp_path / "image.png"
    p.write_bytes(b"trusted")
    verify_asset(p, hashlib.sha256(b"trusted").hexdigest(), 7)
    with pytest.raises(ValueError, match="size"):
        verify_asset(p, hashlib.sha256(b"trusted").hexdigest(), 8)

def test_case_counts_are_exact():
    cases = ([{"category": "title"}] * 19
             + [{"category": "dialog"}] * 2
             + [{"category": "no_offer"}] * 5)
    assert validate_cases(cases) == {"title":19, "dialog":2, "no_offer":5}
    with pytest.raises(ValueError, match="count"):
        validate_cases(cases[:-1])

def test_decoder_version_rejects_wrong_dimensions():
    validate_output_dimensions("v4", 6625, 6623)
    validate_output_dimensions("v5", 437, 436)
    with pytest.raises(ValueError, match="decoder"):
        validate_output_dimensions("v5", 438, 436)
    with pytest.raises(ValueError, match="version"):
        validate_output_dimensions("v6", 437, 436)

def test_wrong_nonnull_is_not_counted_as_correct():
    assert classify("Donation", "Goliath", "title") == "wrong_id"
    assert classify("Donation", None, "title") == "false_rejection"
    assert classify("Donation", "Donation", "title") == "correct"
    with pytest.raises(AssertionError, match="classification"):
        assert_predictions([{"expected":"Donation", "actual":"Goliath", "category":"title", "status":"correct"}])

def test_negative_false_positive_and_correct_rejection():
    assert classify(None, "Donation", "dialog") == "false_positive"
    assert classify(None, None, "no_offer") == "correct_rejection"
    with pytest.raises(AssertionError, match="classification"):
        assert_predictions([{"expected":None,"actual":"Donation","category":"dialog","status":"correct_rejection"}])
