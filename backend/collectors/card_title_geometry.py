"""M5/C1: pure, client-relative crop geometry for three Mayhem card titles.

Calibrated on a real observed League windowed client: 2544x1353 physical
pixels at desktop origin (8,31). Full letter padding was visually reviewed
against two independent captures of a three-card offer and a centre reroll.

This module neither observes the desktop nor recognises game text. 1080p is
a proportional extrapolation awaiting live Windows acceptance. Unsupported
ratios fail closed instead of silently borrowing 16:9 geometry.
"""
from __future__ import annotations


# Physical client geometry and reviewed padded title-only boxes: x,y,w,h.
_OBSERVED_WIDTH = 2544
_OBSERVED_HEIGHT = 1353
_OBSERVED_BANDS = (
    ("left", (643, 490, 340, 90)),
    ("centre", (1100, 490, 340, 90)),
    ("right", (1567, 490, 340, 90)),
)

# League can report a non-16:9 client viewport in a nominally 16:9
# windowed desktop mode (measured: 2544/1353 = 1.8803).
# Do not accept 16:10, ultrawide or tiny windows as calibrated.
_MIN_RATIO = 1.70
_MAX_RATIO = 1.96
_MIN_WIDTH = 960
_MIN_HEIGHT = 540


def title_bands_from_client_rect(
    client_rect: tuple[int, int, int, int],
) -> dict[str, tuple[int, int, int, int]] | None:
    """Return ordered title rectangles (client-relative x,y,w,h), or None.

    The input rectangle is physical desktop (left,top,right,bottom). Only its
    width and height affect crops: offsets and signed origins must not.
    No screen access, HWND dependency, OCR or platform-specific calls.
    """
    if not isinstance(client_rect, (tuple, list)) or len(client_rect) != 4:
        return None
    if any(not isinstance(value, int) or isinstance(value, bool) for value in client_rect):
        return None
    left, top, right, bottom = client_rect
    width, height = right - left, bottom - top
    if width < _MIN_WIDTH or height < _MIN_HEIGHT:
        return None
    ratio = width / height
    if not _MIN_RATIO <= ratio <= _MAX_RATIO:
        return None

    result = {}
    for slot, (x, y, w, h) in _OBSERVED_BANDS:
        scaled = (
            round(x * width / _OBSERVED_WIDTH),
            round(y * height / _OBSERVED_HEIGHT),
            round(w * width / _OBSERVED_WIDTH),
            round(h * height / _OBSERVED_HEIGHT),
        )
        sx, sy, sw, sh = scaled
        if (sx < 0 or sy < 0 or sw < 80 or sh < 20
                or sx + sw > width or sy + sh > height):
            return None
        result[slot] = scaled
    return result
