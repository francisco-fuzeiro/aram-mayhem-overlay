"""Patch-pinned Stat Anvil catalogue built from the real public game bin.

P0-A evidence (2026-11-23): on patch 16.23 CommunityDragon publishes the Stat
Anvil shards under their real name,
``game/maps/modespecificdata/statanvils.bin.json`` (37 ``AnvilData`` rows:
14 Silver, 14 Gold, 8 Prismatic, 1 mixed). The 16.22 hashed path
``game/unknown/507cdd64276919f5.bin.json`` 404s on 16.23 because the file was
renamed, exactly as the MIT ARAM Mayhem Tracker predicted. Titles come from the
public ``lol.stringtable.json`` of the same patch.

The runtime catalogue (``data/anvils/stat_anvils_<patch>.json``) is generated
offline by ``scripts/build_stat_anvil_catalog.py`` and loaded only when its patch
equals the game data patch. Entries that are disabled, untitled, unknown or
ambiguous are rejected with a reason instead of guessed. Nothing here proves a
shard was offered: that needs a visible popup (``backend.engine.stat_anvil_offer``).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from backend.static_data.anvil_public_catalog import TIERS, AnvilCatalogError

CATALOG_SCHEMA = 1
SOURCE_PATH = "game/maps/modespecificdata/statanvils.bin.json"
STRINGTABLE_PATH = "game/{locale}/data/menu/en_us/lol.stringtable.json"
TIER_ORDER = ("silver", "gold", "prismatic")
_PATCH = re.compile(r"^\d{2}\.\d{1,2}$")

# DataValues name -> canonical stat. "pct" variants are chosen when the raw
# value is a fraction (< 1): e.g. Silver MinHP=110 flat, Prismatic MinHP=0.15.
_STAT_NAMES = {
    "MinAD": ("ad", "ad"),
    "MinAP": ("ap", "ap"),
    "MinAH": ("ah", "ah"),
    "MinAS": ("as", "as"),
    "MinAR": ("armor", "armor"),
    "MinArmor": ("armor", "armor"),
    "MinMR": ("mr", "mr"),
    "MinHP": ("hp", "hp_pct"),
    "MinCritChance": ("crit", "crit"),
    "MinCritDamage": ("crit_damage", "crit_damage"),
    "MinLethality": ("lethality", "armor_pen_pct"),
    "MinMPen": ("mpen", "mpen_pct"),
    "MinHS": ("heal_shield", "heal_shield"),
    "MinMS": ("ms", "ms"),
    "MinTenacity": ("tenacity", "tenacity"),
    "MeleeOmnivamp": ("omnivamp", "omnivamp"),
    "RangedOmnivamp": ("omnivamp_ranged", "omnivamp_ranged"),
    # Size changes are side effects of HP/MS shards, never scored stats.
    "SizeGain": ("size", "size"),
    "SizeMod": ("size", "size"),
}
SIDE_EFFECT_STATS = frozenset({"size", "omnivamp_ranged"})


@dataclass(frozen=True)
class StatAnvil:
    id: str
    tier: str
    title: str
    stats: tuple[tuple[str, float], ...]  # canonical stat -> display value
    kind: str

    def stat_map(self) -> dict[str, float]:
        return dict(self.stats)


def canonical_stats(kind: str, raw_values: Mapping[str, float]) -> dict[str, float]:
    """Map DataValues to canonical display stats; unknown names raise."""
    out: dict[str, float] = {}
    for name, raw in raw_values.items():
        if name not in _STAT_NAMES:
            raise AnvilCatalogError(f"unmapped shard stat {name}")
        if type(raw) not in (int, float) or not math.isfinite(raw):
            raise AnvilCatalogError("non-numeric shard stat")
        flat, pct = _STAT_NAMES[name]
        fraction = abs(raw) < 1
        stat = pct if fraction else flat
        shown = round(raw * 100, 1) if fraction else round(float(raw), 1)
        if stat in out:
            raise AnvilCatalogError("duplicate canonical shard stat")
        out[stat] = shown
    return out


def _raw_values(doc: Mapping[str, object], row: Mapping[str, object]) -> dict[str, float]:
    spell = doc.get(row.get("RootSpell")) if isinstance(row.get("RootSpell"), str) else None
    data = (spell or {}).get("mSpell", {}).get("DataValues") if isinstance(spell, dict) else None
    if not isinstance(data, list) or not data:
        raise AnvilCatalogError("missing RootSpell.mSpell.DataValues")
    return {d["name"]: d["values"][0] for d in data
            if isinstance(d, dict) and isinstance(d.get("values"), list) and d["values"]}


def _clean_title(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    title = re.sub(r"<[^>]{0,150}>", "", value).strip()
    return title if 0 < len(title) <= 64 else None


def build_catalog(doc: object, strings: Mapping[str, str], *, patch: str,
                  source: Mapping[str, object]) -> dict:
    """Pure: one real public bin + same-patch strings -> pinned catalogue."""
    if not isinstance(patch, str) or not _PATCH.fullmatch(patch):
        raise AnvilCatalogError("patch must be major.minor")
    if not isinstance(doc, dict):
        raise AnvilCatalogError("invalid game bin")
    rows = {row.get("AugmentNameId"): row for row in doc.values()
            if isinstance(row, dict) and row.get("__type") == "AnvilData"}
    raw_total = len(rows)
    raw_tiers = {t: 0 for t in TIER_ORDER}
    for row in rows.values():
        codes = row.get("AnvilTypes") or []
        if len(set(codes)) == 1 and codes[0] in TIERS:
            raw_tiers[TIERS[codes[0]]] += 1
    entries, rejected = [], []
    for ident in sorted(i for i in rows if isinstance(i, str)):
        row = rows[ident]
        codes = row.get("AnvilTypes") or []
        tier = TIERS.get(codes[0]) if codes and len(set(codes)) == 1 else None
        name_key = row.get("NameTra")
        title = _clean_title(strings.get(name_key.lower())) if isinstance(name_key, str) else None
        reason, stats = None, {}
        if row.get("Enabled") is False:
            reason = "disabled_in_game_bin"
        elif not ident.startswith("ARAM_"):
            reason = "unexpected_id"
        elif tier is None:
            reason = "mixed_or_unknown_tier"
        elif title is None:
            reason = "title_missing"
        else:
            try:
                stats = canonical_stats(str(name_key), _raw_values(doc, row))
                if not any(k not in SIDE_EFFECT_STATS for k in stats):
                    reason = "no_scored_stat"
            except AnvilCatalogError as exc:
                reason = f"stats_rejected: {exc}"
        if reason is not None:
            rejected.append({"id": ident, "tier": tier, "reason": reason})
            continue
        entries.append({"id": ident, "tier": tier, "title": title,
                        "kind": "+".join(stats), "stats": stats})
    entries.sort(key=lambda e: (TIER_ORDER.index(e["tier"]), e["id"]))
    tiers = {t: sum(e["tier"] == t for e in entries) for t in TIER_ORDER}
    return {
        "schema": CATALOG_SCHEMA, "patch": patch,
        "source": dict(source),
        "raw_anvil_data": raw_total, "raw_tiers": raw_tiers,
        "total": len(entries), "tiers": tiers,
        "entries": entries, "rejected": sorted(rejected, key=lambda r: r["id"]),
    }


def validate_catalog(data: object, *, expected_patch: str) -> list[StatAnvil]:
    """Fail closed: wrong patch, empty tier, duplicates or bad rows raise."""
    if not isinstance(data, dict) or data.get("schema") != CATALOG_SCHEMA:
        raise AnvilCatalogError("unknown Stat Anvil catalogue schema")
    if data.get("patch") != expected_patch:
        raise AnvilCatalogError("Stat Anvil catalogue patch mismatch")
    source = data.get("source")
    if not isinstance(source, dict) or source.get("path") != SOURCE_PATH \
            or not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256", ""))):
        raise AnvilCatalogError("Stat Anvil catalogue lacks exact verified source")
    rows = data.get("entries")
    if not isinstance(rows, list):
        raise AnvilCatalogError("Stat Anvil catalogue has no entries")
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise AnvilCatalogError("malformed Stat Anvil entry")
        ident, tier, title, stats = (row.get(k) for k in ("id", "tier", "title", "stats"))
        if (not isinstance(ident, str) or not ident.startswith("ARAM_")
                or tier not in TIER_ORDER or _clean_title(title) != title
                or not isinstance(stats, dict) or not stats or ident in seen):
            raise AnvilCatalogError("invalid or duplicate Stat Anvil entry")
        for stat, value in stats.items():
            if (stat not in {v for pair in _STAT_NAMES.values() for v in pair}
                    or type(value) not in (int, float) or not math.isfinite(value)):
                raise AnvilCatalogError("invalid Stat Anvil stat")
        seen.add(ident)
        result.append(StatAnvil(
            id=ident, tier=tier, title=title,
            stats=tuple(sorted((k, float(v)) for k, v in stats.items())),
            kind=str(row.get("kind", "")),
        ))
    for tier in TIER_ORDER:
        if not any(s.tier == tier for s in result):
            raise AnvilCatalogError(f"Stat Anvil catalogue has no {tier} shards")
    return result


def catalog_path(app_root: Path, patch: str) -> Path:
    return app_root / "data" / "anvils" / f"stat_anvils_{patch}.json"


def load_catalog(app_root: Path, patch: str) -> list[StatAnvil]:
    path = catalog_path(app_root, patch)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AnvilCatalogError("Stat Anvil catalogue unavailable for patch") from exc
    return validate_catalog(data, expected_patch=patch)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
