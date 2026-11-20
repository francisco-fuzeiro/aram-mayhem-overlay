"""Derive mutually exclusive item families from patch-specific Data Dragon passives.

Only an *identically named* passive shared by two or more verified final items
creates a family. This is a conservative advisory rule, not proof of the
Mayhem shop's undocumented "Limited to 1" restrictions.
"""
from __future__ import annotations

import html
import re
from collections import defaultdict


NON_EXCLUSIVE_EFFECTS = frozenset({"Grievous Wounds", "ACTIVE", "Active"})
EXCLUSIVE_GROUP_ALIASES = {"Awe": "Manaflow"}

_PASSIVE = re.compile(r"<passive(?:\s[^>]*)?>(.*?)</passive>", flags=re.I | re.S)
_TAG = re.compile(r"<[^>]+>")


def exclusive_groups(final_items: dict[str, dict]) -> dict[str, frozenset[str]]:
    """Group final item IDs by shared Data Dragon passive names.

    `final_items` must already contain ONLY the patch-verified final pool.
    The raw DD description carries named <passive> elements; strip incidental
    trailing colons, HTML markup and whitespace, then merge known aliases.
    Do not infer effects or exclusivity from free-text item descriptions.
    """
    groups: dict[str, set[str]] = defaultdict(set)
    for item_id, data in final_items.items():
        if not isinstance(data, dict):
            continue
        description = data.get("description")
        if not isinstance(description, str):
            continue
        for raw_name in _PASSIVE.findall(description):
            name = " ".join(html.unescape(_TAG.sub(" ", raw_name)).strip().rstrip(":").split())
            if not name or name in NON_EXCLUSIVE_EFFECTS:
                continue
            canonical = EXCLUSIVE_GROUP_ALIASES.get(name, name)
            groups[canonical].add(str(item_id))

    return {
        name: frozenset(ids)
        for name, ids in groups.items()
        if len(ids) >= 2
    }
