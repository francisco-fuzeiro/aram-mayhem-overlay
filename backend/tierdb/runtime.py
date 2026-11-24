"""Live access to the exported tier list, behind an instant kill switch.

Owner decision 2026-11-23: empirical tiers are shown now, without waiting for
Riot's written answer, behind ``empirical_tiers_enabled`` (default on). The
switch is read on every lookup, so turning it off takes effect immediately;
callers then fall back to the curated heuristic.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from backend import feature_diagnostics as diag

logger = logging.getLogger("aram-oracle.tierdb")

TIER_PREFERENCES_FILE = Path.home() / ".aram-oracle" / "tierlist_preferences.json"
DEFAULT_EXPORT_FILE = Path.home() / ".aram-oracle" / "tierlist.json"
DEFAULT_ENABLED = True


def load_empirical_tiers_enabled(path: Path | None = None) -> bool:
    source = path if path is not None else TIER_PREFERENCES_FILE
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return DEFAULT_ENABLED
    except (OSError, ValueError) as exc:
        logger.warning("Unreadable tier preference %s: %s", source, exc)
        return DEFAULT_ENABLED
    value = payload.get("empirical_tiers_enabled") if isinstance(payload, dict) else None
    return value if isinstance(value, bool) else DEFAULT_ENABLED


def save_empirical_tiers_enabled(enabled: bool, path: Path | None = None) -> None:
    if not isinstance(enabled, bool):
        raise ValueError("empirical_tiers_enabled must be a boolean")
    target = path if path is not None else TIER_PREFERENCES_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps({"empirical_tiers_enabled": enabled}) + "\n", encoding="utf-8")
    os.replace(tmp, target)


def _add_spans(entries: list[dict]) -> None:
    """Add ``rank_total`` (ranked rows) and ``tie_end`` (last rank of the group)."""
    ranked = [e for e in entries if e.get("rank") is not None]
    ends: dict = {}
    for e in ranked:
        ends[e["tie_group"]] = max(ends.get(e["tie_group"], 0), e["rank"])
    for e in entries:
        e["rank_total"] = len(ranked)
        e["tie_end"] = ends.get(e.get("tie_group")) if e.get("rank") is not None else None


# Owner decision 24/11: the tier IS the position in the list ("top 5 OP, S up
# to 15"). Bands below S are a proposal: A 16-30, B 31-50, C 51-75, D 76-100,
# E after. Ranking order is unchanged; evidence caps (e.g. curated-only
# augments at most A) still apply so a guess is never shown as OP.
RANK_BANDS = (("OP", 5), ("S", 15), ("A", 30), ("B", 50), ("C", 75), ("D", 100))


def rank_tier(rank, level: str | None = None, fallback: str | None = None) -> str | None:
    if not isinstance(rank, int) or rank < 1:
        return fallback
    tier = next((name for name, last in RANK_BANDS if rank <= last), "E")
    from backend.tierdb.augment_tiers import LEVEL_CAP, TIER_ORDER
    cap = LEVEL_CAP.get(level or "")
    if cap is not None:
        tier = TIER_ORDER[max(TIER_ORDER.index(tier), TIER_ORDER.index(cap))]
    return tier


def _apply_rank_tiers(entries: list[dict]) -> None:
    for e in entries:
        e["score_tier"] = e.get("tier")
        e["tier"] = rank_tier(e.get("rank"), e.get("level"), e.get("tier"))


class TierListProvider:
    def __init__(self, export_path: Path | None = None, enabled=None):
        self.export_path = Path(export_path) if export_path else DEFAULT_EXPORT_FILE
        self._enabled = enabled or load_empirical_tiers_enabled
        self._mtime = None
        self._augments: dict = {}
        self._champions: dict = {}
        self._items: dict = {}
        self.patch: str | None = None
        self.sources: list = []

    def _load(self) -> None:
        try:
            mtime = self.export_path.stat().st_mtime_ns
        except OSError:
            self._augments, self._champions, self._mtime, self._items = {}, {}, None, {}
            diag.record("tierdb.load", "failed", "export_missing")
            return
        if mtime == self._mtime:
            return
        try:
            doc = json.loads(self.export_path.read_text(encoding="utf-8"))
            cols = doc["augment_columns"]
            augments = {}
            for champ, by_rarity in doc["augments"].items():
                for rarity, rows in by_rarity.items():
                    entries = [dict(zip(cols, row)) for row in rows]
                    _add_spans(entries)
                    _apply_rank_tiers(entries)
                    for entry in entries:
                        aid = entry.pop("augment_id")
                        entry["rarity"] = rarity
                        augments[(champ, aid)] = entry
            ccols = doc["champion_columns"]
            entries = [dict(zip(ccols, row)) for row in doc["champions"]]
            _add_spans(entries)
            _apply_rank_tiers(entries)
            champions = {e.pop("champion_id"): e for e in entries}
            icols = doc.get("item_columns") or []
            items = {}
            for champ, entry in (doc.get("items") or {}).items():
                lists = {}
                for kind in ("final", "boots"):
                    rows = [dict(zip(icols, row)) for row in entry.get(kind, [])]
                    _add_spans(rows)
                    lists[kind] = {r.pop("item_id"): r for r in rows}
                items[champ] = {
                    **lists,
                    "reference": list(entry.get("reference") or []),
                    "boots_reference": entry.get("boots_reference"),
                    "stat_demand": dict(entry.get("stat_demand") or {}),
                    "fate": {k: list(v) for k, v in (entry.get("fate") or {}).items()},
                }
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Invalid tier list export %s: %s", self.export_path, exc)
            diag.record("tierdb.load", "failed", "export_invalid")
            return
        self._augments, self._champions, self._mtime = augments, champions, mtime
        self._items = items
        self.patch, self.sources = doc.get("patch"), doc.get("sources", [])
        diag.record("tierdb.load", "ok", "loaded", min(len(champions), 1000))

    @property
    def loaded(self) -> bool:
        return self._mtime is not None

    def augment_tier(self, champion_id: str, augment_id: str) -> dict | None:
        if not self._enabled():
            return None
        self._load()
        entry = self._augments.get((champion_id, str(augment_id)))
        return dict(entry) if entry else None

    def items(self, champion_id: str) -> dict | None:
        """Item/boots tiers, reference build, stat demand and Weapon of Fate items."""
        if not self._enabled():
            return None
        self._load()
        entry = self._items.get(champion_id)
        if not entry:
            return None
        return {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
                for k, v in entry.items()}

    def champion_tier(self, champion_id: str) -> dict | None:
        if not self._enabled():
            return None
        self._load()
        entry = self._champions.get(champion_id)
        return dict(entry) if entry else None
