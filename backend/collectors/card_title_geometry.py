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


# Field 24/11 (owner screenshot, 2550x1363 client): Mayhem can offer FOUR
# cards. Card pitch is the same as the three-card layout (457/2544 of the
# width); a four-card row is centred, so its cards sit at +-0.5 and +-1.5
# pitches and its gaps at 0 and +-1 pitch, the opposite of three cards.
_PITCH = 457 / _OBSERVED_WIDTH
_STRIP = 20 / _OBSERVED_WIDTH


def layout_probe_strips(
    client_rect: tuple[int, int, int, int],
) -> dict[float, tuple[int, int, int, int]] | None:
    """Narrow client-relative strips (x,y,w,h) at the title height, keyed by
    the offset from the centre in pitches (-1, -0.5, 0, 0.5, 1)."""
    bands = title_bands_from_client_rect(client_rect)
    if bands is None:
        return None
    left, top, right, bottom = client_rect
    width = right - left
    _, y, _, h = bands["centre"]
    half = max(2, round(_STRIP * width / 2))
    out = {}
    for k in (-1.0, -0.5, 0.0, 0.5, 1.0):
        x = round(width / 2 + k * _PITCH * width)
        out[k] = (x - half, y, 2 * half, h)
    return out


def card_count_from_fractions(teal: dict[float, float]) -> int | None:
    """3 or 4 cards from card-background fractions in the probe strips."""
    on = lambda k: teal.get(k, 0.0) >= 0.5   # noqa: E731
    off = lambda k: teal.get(k, 1.0) < 0.3   # noqa: E731
    if on(-0.5) and on(0.5) and off(0.0) and off(-1.0) and off(1.0):
        return 4
    if on(0.0) and on(-1.0) and on(1.0) and off(-0.5) and off(0.5):
        return 3
    return None


FOUR_SLOTS = ("c1", "c2", "c3", "c4")
_FOUR_OFFSETS = (-1.5, -0.5, 0.5, 1.5)


def four_title_bands(
    client_rect: tuple[int, int, int, int],
) -> dict[str, tuple[int, int, int, int]] | None:
    """Title rectangles (client-relative x,y,w,h) of a FOUR-card offer.

    Same title height and band size as the three-card layout; the centres sit
    at +-0.5 and +-1.5 pitches (measured on the owner's 2546x1385 window
    screenshots, 24/11). Fails closed like the three-card bands.
    """
    bands = title_bands_from_client_rect(client_rect)
    if bands is None:
        return None
    left, top, right, bottom = client_rect
    width = right - left
    _, y, w, h = bands["centre"]
    out = {}
    for slot, k in zip(FOUR_SLOTS, _FOUR_OFFSETS):
        x = round(width / 2 + k * _PITCH * width - w / 2)
        if x < 0 or x + w > width:
            return None
        out[slot] = (x, y, w, h)
    return out
