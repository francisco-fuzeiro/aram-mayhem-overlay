"""P0-C: dedicated, independent visual watcher for the Stat Anvil popup.

The popup is detected ONLY from the League window: a separate ScreenWatcher
instance (its own two-read temporal gate, never the augment watcher's state)
reads the card title slots against the real shard titles of the pinned patch
catalogue. A voucher purchase merely opens a bounded attention window so the
capture runs at the right time; it never creates, completes or scores cards.
No screenshots, OCR text or crops are stored by this module.
"""
from __future__ import annotations

from backend.collectors.anvil_voucher import voucher_tier
from backend.collectors.slot_title_ocr import SLOTS

ANVIL_WINDOW_S = 150.0   # attention window after a voucher edge (no proof)
ABSENT_TICKS_TO_CLOSE = 2

_watcher = None


def anvil_watcher():
    """Lazily build the separate watcher so imports stay side-effect free."""
    global _watcher
    if _watcher is None:
        from backend.collectors.screen_ocr import ScreenWatcher
        _watcher = ScreenWatcher(skip_ocr_without_cards=True)
    return _watcher


def attention(previous: object, counts: object) -> tuple[bool, str | None]:
    """Should the popup be watched now, and which voucher tier hints it?

    Vouchers are redeemed later in the shop, and redeeming (a stack going
    DOWN) is when the popup appears; so watch while one is held and right
    after one is spent. This is timing only, never evidence of an offer.
    """
    if not isinstance(counts, dict):
        return False, None
    prev = previous if isinstance(previous, dict) else {}
    spent = tuple(sorted(k for k, v in prev.items() if counts.get(k, 0) < v))
    if spent:
        return True, voucher_tier(spent)
    held = tuple(sorted(k for k, v in counts.items() if v > 0))
    return (True, voucher_tier(held)) if held else (False, None)


def slot_ids(matches) -> list[str | None] | None:
    """Ordered slot ids from a SlotMatches result; None if unreadable."""
    slots = getattr(matches, "slots", None)
    if not isinstance(slots, dict):
        return None
    out = []
    for slot in SLOTS:
        value = slots.get(slot)
        out.append(value[0] if isinstance(value, tuple) and value else None)
    return out


def run_anvil_check(title_names: dict[str, str]) -> tuple[str, list[str | None] | None]:
    """One synchronous observation (call through asyncio.to_thread)."""
    watcher = anvil_watcher()
    action, matches = watcher.check(title_names)
    if action == "detected":
        return action, slot_ids(matches)
    if action == "unchanged":
        return action, slot_ids(watcher.current_slots)
    return action, None
