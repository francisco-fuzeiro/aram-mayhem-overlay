"""Conservative ARAM Mayhem item availability from patch-matched public sources.

The ARAM map flag and two public catalogs do not prove the live Mayhem shop.
Unknown, inconsistent or differently versioned evidence is never eligible.
"""
from __future__ import annotations

import html
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ITEM_POLICY_VERSION = "item_pool_v5"  # v5: DD omits "from" on base components
ARAM_MAP_ID = "12"
_SHOP_ID_PATTERN = re.compile(r"(?:\d{4}|12\d{4})")
_REWARD_ID_PATTERN = re.compile(r"22\d{4}")
_EXCLUDED_SHOP_TAGS = frozenset({"Consumable", "Trinket", "Jungle"})
FINAL_ITEM_MIN_COST = 1600
TIER2_BOOTS_MIN_COST = 900
BASIC_BOOTS_ID = "1001"
POOL_CLASSES = frozenset({"final", "component", "boots_tier1", "boots_tier2"})
RECOMMENDABLE_CLASSES = frozenset({"final", "boots_tier2"})
ITEM_CLASSES = frozenset({
    "final", "component", "boots_tier1", "boots_tier2",
    "augment_reward", "conditional", "mode_variant", "not_on_aram_map",
    "not_purchasable", "consumable_trinket", "unknown",
})
ItemClass = Literal[
    "final", "component", "boots_tier1", "boots_tier2",
    "augment_reward", "conditional", "mode_variant", "not_on_aram_map",
    "not_purchasable", "consumable_trinket", "unknown",
]


@dataclass(frozen=True)
class ItemPoolMeta:
    policy_version: str
    ddragon_version: str
    cdragon_patch: str
    cdragon_sha256: str
    cdragon_fetched_at: str
    overrides_version: str
    availability: Literal["verified_two_source", "unknown"]


def patch_of(ddragon_version: str) -> str:
    """Extract exact major.minor; invalid/unknown versions never match."""
    match = re.fullmatch(r"(\d+)\.(\d+)\.\d+", str(ddragon_version))
    if not match:
        raise ValueError("invalid Data Dragon version")
    return f"{match.group(1)}.{match.group(2)}"


def cdragon_matches(dd_version: str, content_version: str) -> bool:
    try:
        patch = patch_of(dd_version)
    except ValueError:
        return False
    return isinstance(content_version, str) and bool(
        re.match(rf"^{re.escape(patch)}\.\d+(?:[+.-]|$)", content_version)
    )


def load_item_overrides(path: Path | None = None) -> dict:
    """Validate the entire manually reviewed override file before use.

    Every forced class must identify its source and reason. Invalid data
    raises rather than silently making an item available.
    """
    import json

    path = Path(path) if path is not None else Path(__file__).with_name("item_overrides.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("version"), str) or not data["version"].strip():
        raise ValueError("item override version is required")
    forced = data.get("force_class")
    if not isinstance(forced, dict):
        raise ValueError("force_class must be an object")
    for item_id, item in forced.items():
        if not isinstance(item_id, str) or not re.fullmatch(r"\d{4,6}", item_id):
            raise ValueError("invalid item override identifier")
        if not isinstance(item, dict) or item.get("class") not in ITEM_CLASSES:
            raise ValueError("invalid item override class")
        # Reviewed overrides may remove unsafe shop offers, never create
        # purchase entitlement absent from both source catalogs.
        if item["class"] in POOL_CLASSES:
            raise ValueError("item overrides may only exclude shop items")
        if any(not isinstance(item.get(key), str) or not item[key].strip()
               for key in ("reason", "source")):
            raise ValueError("item override requires a reason and a source")
    return data


def classify_item(item_id: str, dd: dict, cd: dict | None, overrides: dict) -> ItemClass:
    """Classify using explicit precedence; never infer access from a price.

    Source recipe consistency is checked by the loader on full raw records.
    Compact audit fixtures carry recipe counts only and are classified here.
    """
    # Reward IDs are never ordinary shop items, even if an unsanitized
    # caller supplies a manual promotion rule. A reward acquired in game
    # remains recognizable through the full catalog, not recommended to buy.
    if _REWARD_ID_PATTERN.fullmatch(item_id):
        return "augment_reward"
    override = overrides.get("force_class", {}).get(item_id)
    if override is not None:
        if not isinstance(override, dict) or override.get("class") not in ITEM_CLASSES:
            raise ValueError("invalid forced item class")
        if any(not isinstance(override.get(k), str) or not override[k].strip()
               for k in ("reason", "source")):
            raise ValueError("forced class requires reason and source")
        if override["class"] in POOL_CLASSES:
            raise ValueError("item overrides may only exclude shop items")
        return override["class"]
    if cd is None:
        return "unknown"
    if dd.get("maps", {}).get(ARAM_MAP_ID) is not True:
        return "not_on_aram_map"
    if not _SHOP_ID_PATTERN.fullmatch(item_id):
        return "mode_variant"
    # Some CDragon items carry a currency *cost* without a currency name.
    # A missing, malformed or negative cost cannot prove a zero-cost shop
    # path. These metadata values do not prove that an in-game quest is done.
    currency_cost = cd.get("requiredBuffCurrencyCost")
    if type(currency_cost) is not int or currency_cost < 0:
        return "unknown"
    if (dd.get("requiredChampion") or dd.get("requiredAlly")
            or cd.get("requiredChampion") or cd.get("requiredAlly")
            or cd.get("requiredBuffCurrencyName")
            or currency_cost > 0
            or cd.get("specialRecipe", 0)):
        return "conditional"
    tags = set(dd.get("tags") or ())
    if tags & _EXCLUDED_SHOP_TAGS:
        return "consumable_trinket"
    # Absence of an optional Data Dragon inStore key means True; missing
    # required CommunityDragon shop fields mean we do not know availability.
    if "inStore" not in cd or "displayInItemSets" not in cd:
        return "unknown"
    gold = dd.get("gold") or {}
    if not (gold.get("purchasable") is True
            and dd.get("inStore", True) is not False
            and not dd.get("hideFromAll")
            and cd["inStore"] is True
            and cd["displayInItemSets"] is True):
        return "not_purchasable"
    total = gold.get("total")
    if not isinstance(total, (int, float)) or total < 0:
        return "unknown"
    if "Boots" in tags:
        if item_id == BASIC_BOOTS_ID:
            return "boots_tier1"
        if total >= TIER2_BOOTS_MIN_COST and dd.get("from"):
            return "boots_tier2"
        return "component"
    if not dd.get("into") and total >= FINAL_ITEM_MIN_COST:
        return "final"
    return "component"


def sources_agree(dd: dict, cd: dict) -> bool:
    """Price and direct recipes must agree as multisets, including repeats."""
    gold = dd.get("gold")
    if not isinstance(gold, dict) or type(gold.get("total")) is not int:
        return False
    if type(cd.get("priceTotal")) is not int or cd["priceTotal"] != gold["total"]:
        return False
    for dd_key, cd_key in (("from", "from"), ("into", "to")):
        # Data Dragon omits "into" for terminal items; CDragon explicitly
        # publishes "to": []. Only this DD-side omission denotes empty.
        # A missing CD "to"/"from", null, or mismatching recipe stays unsafe.
        # Likewise DD omits "from" on every base component (Long Sword 1036,
        # 16.23.1) while CDragon publishes "from": []. Omitted means empty,
        # so it can only ever match an explicitly empty CD recipe.
        left = dd.get(dd_key, [])
        right = cd.get(cd_key)
        if not isinstance(left, list) or not isinstance(right, list):
            return False
        try:
            if Counter(str(v) for v in left) != Counter(str(v) for v in right):
                return False
        except (TypeError, ValueError):
            return False
    return True


ITEM_PROPERTY_NAMES = frozenset({
    "armor", "magic_resist", "health", "lifesteal", "omnivamp",
    "anti_heal", "armor_pen", "magic_pen", "tenacity", "shield", "cleanse",
})


def item_properties(dd: dict) -> frozenset[str]:
    """Derive B5 item properties solely from Data Dragon stats and text.

    No manually maintained item-ID lists or inferred conditional ownership.
    HTML markup is removed before testing complete text terms.
    """
    stats = dd.get("stats") or {}
    if not isinstance(stats, dict):
        stats = {}
    raw_description = dd.get("description") or ""
    description = html.unescape(re.sub(r"<[^>]*>", " ", str(raw_description)))
    properties = set()
    for source, target in (
        ("FlatArmorMod", "armor"),
        ("FlatSpellBlockMod", "magic_resist"),
        ("FlatHPPoolMod", "health"),
        ("PercentLifeStealMod", "lifesteal"),
    ):
        value = stats.get(source)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            properties.add(target)
    for phrase, target in (
        ("Omnivamp", "omnivamp"),
        ("Magic Penetration", "magic_pen"),
        ("Tenacity", "tenacity"),
        ("Shield", "shield"),
        ("Quicksilver", "cleanse"),
    ):
        if phrase in description:
            properties.add(target)
    if re.search(r"\bWounds\b", description):
        properties.add("anti_heal")
    if "Armor Penetration" in description or "Lethality" in description:
        properties.add("armor_pen")
    return frozenset(properties)
