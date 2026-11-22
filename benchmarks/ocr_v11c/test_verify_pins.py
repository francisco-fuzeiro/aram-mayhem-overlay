"""Fail-closed pinned research dependency validation (no model inference)."""
from __future__ import annotations

import pytest

from benchmarks.ocr_v11c.verify_pins import check_pins


def test_all_exact_pinned_versions_pass():
    assert check_pins(["numpy==1.26.4", "Pillow==11.1.0"],
                      installed={"numpy": "1.26.4", "pillow": "11.1.0"}) == []


def test_mismatched_and_missing_packages_fail_closed():
    errors = check_pins(["numpy==1.26.4", "Pillow==11.1.0", "psutil==6.1.1"],
                        installed={"numpy": "2.0.0", "pillow": "11.1.0"})
    assert len(errors) == 2
    assert any("numpy" in e and "2.0.0" in e for e in errors)
    assert any("psutil" in e and "missing" in e for e in errors)


@pytest.mark.parametrize("pins", [
    [], ["numpy"], ["numpy>1.26"], ["numpy=="], ["==1.0"],
    ["numpy==1.26.4==unexpected"], ["numpy==1.26.4", "NumPy==2.0.0"],
])
def test_invalid_pins_do_not_bypass_check(pins):
    with pytest.raises(ValueError):
        check_pins(pins, installed={"numpy": "1.26.4"})


def test_hyphen_and_underscore_normalization_is_exact():
    assert check_pins(["opencv-python-headless==4.10.0.84"],
                      installed={"opencv_python_headless": "4.10.0.84"}) == []
