"""C2 click-hint geometry only. OS mouse monitoring is intentionally absent."""

PICK_CLICK_HINTS_ENABLED = False
CARD_BODY_HALF_WIDTH_H = 0.17
CARD_BODY_TOP_H = -0.28
CARD_BODY_BOTTOM_H = 0.26
SLOTS = ("left", "centre", "right")


def card_body_rects(client_rect, bands, slots=SLOTS) -> dict[str, tuple[int, int, int, int]]:
    """Pure physical-pixel card bodies; excludes areas below the card/reroll."""
    x0, y0, width, height = client_rect
    half_width = round(CARD_BODY_HALF_WIDTH_H * height)
    rectangles = {}
    for slot in slots:
        bx, by, bw, bh = bands[slot]
        cx = x0 + bx + bw // 2
        cy = y0 + by + bh // 2
        rectangles[slot] = (
            cx - half_width,
            cy + round(CARD_BODY_TOP_H * height),
            cx + half_width,
            cy + round(CARD_BODY_BOTTOM_H * height),
        )
    return rectangles


def first_card_click(clicks: list[tuple[int, int, float]], rects, since: float) -> str | None:
    """Pure. First left click at/after the timestamp, if inside one card body.

    The caller must already have opted in through a separately approved policy
    gate. C2 never hooks or polls system mouse buttons.
    """
    for x, y, timestamp in sorted(clicks, key=lambda row: row[2]):
        if timestamp < since:
            continue
        for slot in SLOTS:
            rect = rects.get(slot)
            if rect is not None and rect[0] <= x < rect[2] and rect[1] <= y < rect[3]:
                return slot
        return None
    return None
