"""Strict public Stat Anvil source decoder (no game or account access).

CommunityDragon's patch-specific game bins contain AnvilData entries and their
RootSpell DataValues. Names live in the game's public per-locale string table.
The ordinary cherry-augments.json does NOT contain these shard choices.

Independent design informed by public MIT project:
https://github.com/Sygnano/aram-mayhem-tracker
Source details are reimplemented here; no screenshots, ratings or runtime
input/gameplay automation are imported. This parser does NOT prove that any
shard was offered to a player.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Mapping

TIERS = {0: "silver", 8: "gold", 9: "prismatic"}
_EXCLUDED = frozenset((
    "ARAM_StatAnvil_Random",
    "ARAM_GoldStatAnvil_Random",
    "ARAM_StatAnvil_Pristine",
))
_PATCH = re.compile(r"^\d{2}\.\d{1,2}$")
_STAT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_MAX_SHARDS = 256


class AnvilCatalogError(ValueError):
    """Reject inconsistent public metadata rather than invent a choice."""


@dataclass(frozen=True)
class PublicStatAnvil:
    item_id: str
    tier: str
    kind: str
    values: tuple[float, ...]
    name_key: str


def _display_number(value: float) -> float:
    shown = value * 100 if abs(value) < 1 else value
    return float(Decimal(str(shown)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP,
    ))


def _read_shard(doc: Mapping[str, object], row: dict) -> tuple[PublicStatAnvil, ...]:
    item_id = row.get("AugmentNameId")
    if (not isinstance(item_id, str) or not item_id.startswith("ARAM_")
            or len(item_id) > 128):
        raise AnvilCatalogError("invalid public shard id")
    if item_id in _EXCLUDED or row.get("Enabled") is False:
        # Riot marks non-offerable rows (Random, Pristine) Enabled=false;
        # honour that generically so a new disabled row is never offered.
        return ()
    codes = row.get("AnvilTypes")
    if not isinstance(codes, list) or not codes:
        raise AnvilCatalogError("AnvilData lacks a tier")
    if any(type(code) is not int or code not in TIERS for code in codes):
        raise AnvilCatalogError("unknown AnvilData tier code")
    tiers = tuple(TIERS[code] for code in dict.fromkeys(codes))
    spell_ref = row.get("RootSpell")
    spell = doc.get(spell_ref) if isinstance(spell_ref, str) else None
    if not isinstance(spell, dict):
        raise AnvilCatalogError("missing RootSpell")
    mspell = spell.get("mSpell")
    data = mspell.get("DataValues") if isinstance(mspell, dict) else None
    if not isinstance(data, list) or not data:
        raise AnvilCatalogError("missing shard DataValues")
    names, values = [], []
    for stat in data:
        if not isinstance(stat, dict):
            raise AnvilCatalogError("malformed DataValues")
        name = stat.get("name")
        vals = stat.get("values")
        if (not isinstance(name, str) or not _STAT_NAME.fullmatch(name)
                or not isinstance(vals, list) or not vals):
            raise AnvilCatalogError("invalid shard stat")
        first = vals[0]
        if (type(first) not in (int, float) or not math.isfinite(first)
                or abs(first) > 100_000
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       or abs(v - first) > 0.000001 for v in vals)):
            raise AnvilCatalogError("dynamic/unverified shard stat")
        names.append(name)
        values.append(_display_number(float(first)))
    if len(set(names)) != len(names):
        raise AnvilCatalogError("duplicate shard stat")
    name_key = row.get("NameTra")
    if not isinstance(name_key, str) or not name_key or len(name_key) > 256:
        raise AnvilCatalogError("missing public shard title key")
    return tuple(
        PublicStatAnvil(
            item_id=item_id, tier=tier, kind="+".join(names),
            values=tuple(values), name_key=name_key.lower(),
        ) for tier in tiers
    )


def parse_public_bins(documents: Iterable[object]) -> list[PublicStatAnvil]:
    """Extract only Riot-defined AnvilData; conflicting duplicate IDs fail.

    All documents must be from the same patch. Caller must pin that patch.
    Missing or malformed public data cannot create fake offered options.
    """
    found: dict[tuple[str, str], PublicStatAnvil] = {}
    for doc in documents:
        if not isinstance(doc, dict):
            raise AnvilCatalogError("invalid game bin")
        for row in doc.values():
            if not isinstance(row, dict) or row.get("__type") != "AnvilData":
                continue
            for shard in _read_shard(doc, row):
                key = (shard.item_id, shard.tier)
                previous = found.get(key)
                if previous is not None and previous != shard:
                    raise AnvilCatalogError("conflicting shard sources")
                found[key] = shard
                if len(found) > _MAX_SHARDS:
                    raise AnvilCatalogError("excessive shard source rows")
    return sorted(found.values(), key=lambda s: (
        ("silver", "gold", "prismatic").index(s.tier), s.item_id,
    ))


def parse_public_stringtable(
    table: object, shards: Iterable[PublicStatAnvil],
) -> dict[str, str]:
    """Allowlisted title lookup only; a title alone never verifies the tier."""
    if not isinstance(table, dict) or not isinstance(table.get("entries"), dict):
        raise AnvilCatalogError("invalid game string table")
    entries = table["entries"]
    result: dict[str, str] = {}
    for shard in shards:
        value = entries.get(shard.name_key)
        if not isinstance(value, str):
            continue
        title = re.sub(r"<[^>]{0,150}>", "", value).strip()
        if title and len(title) <= 256:
            result[shard.item_id] = title
    return result


def match_verified_shard_offer(
    shards: Iterable[PublicStatAnvil],
    cards: object,
) -> tuple[PublicStatAnvil, ...] | None:
    """Identify a COMPLETE offer from independently verified kind/value pairs.

    This is a pure post-OCR decision: it does not detect screen visibility or
    trust a voucher purchase. Incomplete, conflicting or unknown cards abstain.
    A four-card layout is structurally supported but is NOT native-verified.
    """
    if not isinstance(cards, (list, tuple)) or len(cards) not in (3, 4):
        return None
    catalog = list(shards)
    results = []
    observed_kinds = set()
    for card in cards:
        if not isinstance(card, (list, tuple)) or len(card) != 2:
            return None
        kind, measured = card
        if (not isinstance(kind, str) or kind in observed_kinds
                or not isinstance(measured, (list, tuple)) or not measured):
            return None
        observed_kinds.add(kind)
        if any(type(v) not in (int, float) or not math.isfinite(v)
               for v in measured):
            return None
        candidates = [
            s for s in catalog
            if s.kind == kind and len(s.values) == len(measured)
            and all(abs(abs(actual) - abs(float(read))) <= 0.05
                    for actual, read in zip(s.values, measured))
        ]
        if len(candidates) != 1:
            return None
        results.append(candidates[0])
    if len({r.tier for r in results}) != 1:
        return None
    return tuple(results)


def summarize_anvil_source(
    shards: Iterable[PublicStatAnvil], patch: str,
) -> dict:
    if not isinstance(patch, str) or not _PATCH.fullmatch(patch):
        raise AnvilCatalogError("public patch must be major.minor")
    items = list(shards)
    return {
        "patch": patch, "total": len(items),
        "tiers": {
            tier: sum(s.tier == tier for s in items)
            for tier in ("silver", "gold", "prismatic")
        },
        "live_popup_verified": False,
        "rankings_verified": False,
        "warnings": (
            ["NO PUBLIC STAT ANVILS FOUND; abstain from recommendations"]
            if not items else
            ["Source identities are public; live popup layout and values remain unverified"]
        ),
    }
