"""Pure, six-slot physical inventory and deterministic recipe accounting.

Only patch-proven final items (including tier-2 boots) consume build slots.
Components, basic boots and rewards still occupy real inventory slots.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from backend.static_data.item_policy import RECOMMENDABLE_CLASSES

INVENTORY_SLOTS = 6


@dataclass(frozen=True)
class Inventory:
    finals: tuple[str, ...]
    components: tuple[str, ...]
    other: tuple[str, ...]

    @property
    def used_slots(self) -> int:
        return len(self.finals) + len(self.components) + len(self.other)

    @property
    def free_slots(self) -> int:
        return max(0, INVENTORY_SLOTS - self.used_slots)


def build_inventory(raw_ids: list[str], data) -> Inventory:
    """Classify observed, already-filtered main-inventory IDs in slot order."""
    finals: list[str] = []
    components: list[str] = []
    other: list[str] = []
    for raw in raw_ids[:INVENTORY_SLOTS]:
        ident = data.canonical_item_id(raw)
        item = data.get_item(ident)
        category = item.item_class if item is not None else "unknown"
        if category in RECOMMENDABLE_CLASSES:
            finals.append(ident)
        elif category in {"component", "boots_tier1"}:
            components.append(ident)
        else:
            other.append(ident)
    return Inventory(tuple(finals), tuple(components), tuple(other))


def remaining_cost(
    target_id: str, owned_components: Counter[str], data,
) -> tuple[int, Counter[str]]:
    """Cost of a full target minus distinct owned recipe subtrees.

    Walk the direct Data Dragon recipe, including repeated component IDs.
    A single owned copy can be consumed only once; ancestors take priority
    over descendants. The input multiset is not mutated.
    """
    available = Counter({
        str(ident): count for ident, count in owned_components.items()
        if isinstance(count, int) and count > 0
    })
    consumed: Counter[str] = Counter()
    discount = 0

    def walk(ident: str, ancestors: frozenset[str]) -> None:
        nonlocal discount
        item = data.get_item(ident)
        if item is None:
            raise ValueError(f"Unknown recipe component: {ident}")
        if available[ident] > 0:
            available[ident] -= 1
            consumed[ident] += 1
            discount += item.cost
            return
        if ident in ancestors:
            raise ValueError(f"Cyclic item recipe at {ident}")
        for child in item.from_ids:
            walk(str(child), ancestors | {ident})

    target = data.get_item(str(target_id))
    if target is None:
        raise ValueError(f"Unknown target item: {target_id}")
    walk(str(target_id), frozenset())
    return max(0, target.cost - discount), consumed
