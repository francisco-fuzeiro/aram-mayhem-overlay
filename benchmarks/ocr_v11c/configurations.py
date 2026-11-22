"""Shared pinned V1.1c research-only challenger configuration.

RapidOCR v4 and adaptive direct v4 use the same SHA-pinned model weights.
This helper only selects the separately tested preprocessing wrapper.
"""
from __future__ import annotations

from benchmarks.ocr_v11b.controlled import AblationRecognizer


def adaptive_v4(fixed_direct_v4):
    """BGR/OpenCV/ceil/adaptive recognition width, same fixed v4 decoder."""
    return AblationRecognizer(
        fixed_direct_v4,
        color="bgr",
        resize="cv2",
        rounding="ceil",
        dynamic_width=True,
    )
