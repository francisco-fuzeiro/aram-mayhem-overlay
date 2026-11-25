"""Field 24/11: is the item shop open? (OCR-free, position-independent).

The owner wants the full build only while the shop is open. The Live Client
API does not expose it, and the shop panel can be DRAGGED anywhere (it stays
where the player left it). So nothing here assumes a position: the frame of
the shop panel is a long gold horizontal border with gold vertical borders at
both of its ends, far wider than any augment/Anvil card (measured on the
owner's screenshots: border 0.96 x client height, sides 0.65 x height; a card
is 0.29 x height wide). Pixels are read in memory only, never stored.
"""
from __future__ import annotations

import numpy as np

POOL = 2                 # 2x2 OR-pooling keeps 1-2 px borders, 4x fewer pixels
MIN_BORDER_H = 0.45      # top border length / client height (HUD scale margin)
MIN_SIDE_OF_BORDER = 0.40  # side border length / top border length
SIDE_SEARCH = 0.01       # of the width, around each border end (corner ornaments)


def _gold(rgb: np.ndarray) -> np.ndarray:
    r = rgb[..., 0].astype(np.int16)
    g = rgb[..., 1].astype(np.int16)
    b = rgb[..., 2].astype(np.int16)
    return (r > 90) & (r - b > 30) & (g > 60) & (r >= g)


def _pool(mask: np.ndarray) -> np.ndarray:
    h, w = (mask.shape[0] // POOL) * POOL, (mask.shape[1] // POOL) * POOL
    m = mask[:h, :w]
    return m.reshape(h // POOL, POOL, w // POOL, POOL).any(axis=(1, 3))


def _longest_run(line: np.ndarray) -> tuple[int, int]:
    """(length, start) of the longest True run in a 1-D boolean array."""
    padded = np.concatenate(([0], line.astype(np.int8), [0]))
    edges = np.flatnonzero(np.diff(padded))
    if edges.size == 0:
        return 0, 0
    starts, ends = edges[0::2], edges[1::2]
    lengths = ends - starts
    i = int(np.argmax(lengths))
    return int(lengths[i]), int(starts[i])


def shop_frame_found(image) -> bool:
    """True when a shop-sized gold frame is visible anywhere in the client."""
    try:
        rgb = np.asarray(image.convert("RGB"))
    except (AttributeError, ValueError, OSError):
        return False
    if rgb.ndim != 3 or rgb.shape[0] < 200 or rgb.shape[1] < 200:
        return False
    mask = _pool(_gold(rgb))
    height = mask.shape[0]
    need = MIN_BORDER_H * height
    # Candidate rows: cheap row sums first, exact runs only where possible.
    for y in np.flatnonzero(mask.sum(axis=1) >= need):
        length, start = _longest_run(mask[y])
        if length < need:
            continue
        side_need = MIN_SIDE_OF_BORDER * length
        reach = max(4, round(SIDE_SEARCH * mask.shape[1]))
        ok = []
        for x_end in (start, start + length - 1):
            lo, hi = max(0, x_end - reach), min(mask.shape[1], x_end + reach + 1)
            ok.append(any(_longest_run(mask[y:, x])[0] >= side_need for x in range(lo, hi)))
        if all(ok):
            return True
    return False


def probe_shop() -> bool | None:
    """One synchronous look (call through asyncio.to_thread); None = unknown."""
    from backend.collectors.screen_ocr import find_league_window
    from backend.collectors.window_capture import capture_league_client
    game = find_league_window()
    if game is None:
        return None
    capture = capture_league_client(game)
    if capture.reason != "ok" or capture.image is None:
        return None
    return shop_frame_found(capture.image)
