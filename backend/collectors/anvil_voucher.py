"""Observation-only Anvil Voucher purchase edge from the player's LCDA inventory.

Item IDs are public already-observed Riot catalogue IDs, not invented Anvil
choices. A voucher delta does NOT prove that an Anvil popup is visually present
or that an OCR title can be mapped to a stat selection.
"""
from __future__ import annotations

# Public 16.23 items.json: all three are "Redeem during a Shopping Phase to
# gain a Stat Anvil!" (220010 "Prismatic Stat Voucher" was missing before).
# Tier per voucher is a HINT for title-ambiguous offers only: 220009/220010
# are named Gold/Prismatic [Certo]; 220008 "Anvil Voucher" = Silver [Provavel].
VOUCHER_TIERS = {"220008": "silver", "220009": "gold", "220010": "prismatic"}
STAT_ANVIL_VOUCHER_IDS = frozenset(VOUCHER_TIERS)


def voucher_tier(bought: object) -> str | None:
    """Single tier of a voucher edge, else None (none or several kinds)."""
    if not isinstance(bought, (list, tuple)):
        return None
    tiers = {VOUCHER_TIERS[b] for b in bought if b in VOUCHER_TIERS}
    return tiers.pop() if len(tiers) == 1 else None


def count_anvil_vouchers(items: object) -> dict[str, int] | None:
    """Read the observed local inventory, including a possible special slot.

    None means unavailable/invalid source, never an observed empty inventory.
    Presence with omitted 'count' is one observed stack, not a guessed purchase.
    """
    if not isinstance(items, list):
        return None
    counts: dict[str, int] = {}
    for item in items:
        if not isinstance(item, dict):
            return None
        raw_id = item.get("itemID")
        if type(raw_id) not in (str, int):
            continue
        identifier = str(raw_id)
        if identifier not in STAT_ANVIL_VOUCHER_IDS:
            continue
        stack = item.get("count", 1)
        slot = item.get("slot")
        if (type(stack) is not int or stack <= 0 or
                (slot is not None and (type(slot) is not int or slot < 0))):
            return None
        counts[identifier] = counts.get(identifier, 0) + stack
    return counts


class AnvilVoucherPurchaseObserver:
    """Require two consecutive valid inventory observations in one session.

    Start/reconnect mid-match only establishes a baseline. No scan, identity,
    pick confirmation or score may be produced by this pure observer.
    """

    def __init__(self) -> None:
        self._previous: dict[str, int] | None = None

    def reset(self) -> None:
        self._previous = None

    def observe(self, counts: dict[str, int] | None) -> tuple[str, ...]:
        if (not isinstance(counts, dict)
                or any(key not in STAT_ANVIL_VOUCHER_IDS
                       or type(value) is not int or value <= 0
                       for key, value in counts.items())):
            self.reset()
            return ()
        bought = () if self._previous is None else tuple(
            sorted(key for key, amount in counts.items()
                   if amount > self._previous.get(key, 0))
        )
        self._previous = dict(counts)
        return bought
