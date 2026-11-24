"""Overlay export: tiers, ranks, tie groups, levels and confidence only.

Win rates, wins, games, sample sizes, scores and lifts never leave the local
database (owner rule: the overlay never shows win rates).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from backend.tierdb.store import TierStore

EXPORT_SCHEMA_VERSION = 1
FORBIDDEN_KEYS = frozenset({
    "wins", "games", "n", "n_eff", "win_rate", "winrate", "wr", "score",
    "score_p20", "score_p80", "lift", "delta", "components",
})
AUGMENT_COLUMNS = ("augment_id", "rank", "tie_group", "tier", "level", "confidence",
                   "rank_all")
ITEM_COLUMNS = ("item_id", "rank", "tie_group", "tier", "level", "confidence")
CHAMPION_COLUMNS = ("champion_id", "rank", "tie_group", "tier", "confidence",
                    "potential")


def export_run(store: TierStore, run_id: int, path: Path | str) -> dict:
    con = store.connection
    patch, snapshot_ids = con.execute(
        "SELECT patch, snapshot_ids_json FROM tier_run WHERE id=?", (run_id,)).fetchone()
    snapshot_ids = json.loads(snapshot_ids)
    marks = ",".join("?" * len(snapshot_ids))
    sources = [
        {"name": r[0], "license": r[1], "attribution": r[2], "url": r[3]}
        for r in con.execute(
            f"""SELECT DISTINCT src.name, src.license, src.attribution, src.url
                FROM snapshot s JOIN source src ON src.id = s.source_id
                WHERE s.id IN ({marks}) ORDER BY src.name""", snapshot_ids)
    ]
    augments: dict[str, dict[str, list]] = {}
    for row in con.execute(
        """SELECT champion_id, rarity, augment_id, rank, tie_group, tier, level, confidence,
                  rank_all
           FROM augment_tier WHERE run_id=?
           ORDER BY champion_id, rarity, rank IS NULL, rank, augment_id""", (run_id,)):
        augments.setdefault(row[0], {}).setdefault(row[1], []).append(list(row[2:]))
    champions = [
        list(r) for r in con.execute(
            """SELECT champion_id, rank, tie_group, tier, confidence, potential
               FROM champion_tier WHERE run_id=? ORDER BY rank""", (run_id,))
    ]
    items: dict[str, dict] = {}
    for row in con.execute(
        """SELECT champion_id, kind, item_id, rank, tie_group, tier, level, confidence
           FROM item_tier WHERE run_id=?
           ORDER BY champion_id, kind, rank IS NULL, rank, item_id""", (run_id,)):
        entry = items.setdefault(row[0], {"final": [], "boots": [], "reference": [],
                                         "boots_reference": None, "stat_demand": {},
                                         "fate": {}})
        entry[row[1]].append(list(row[2:]))
    for champion, slot, iid in con.execute(
            "SELECT champion_id, slot, item_id FROM reference_build WHERE run_id=? "
            "ORDER BY champion_id, slot", (run_id,)):
        if champion not in items:
            continue
        if slot == 0:
            items[champion]["boots_reference"] = iid
        else:
            items[champion]["reference"].append(iid)
    for champion, stat, weight in con.execute(
            "SELECT champion_id, stat, weight FROM champion_stat_demand WHERE run_id=?",
            (run_id,)):
        if champion in items:
            items[champion]["stat_demand"][stat] = round(weight, 4)
    for champion, aug, iid in con.execute(
            f"""SELECT champion_id, augment_id, item_id FROM item_observation
                WHERE scope='champ_aug_item' AND snapshot_id IN ({marks})
                ORDER BY champion_id, augment_id, n DESC""", snapshot_ids):
        if champion in items:
            items[champion]["fate"].setdefault(aug, []).append(iid)
    doc = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "patch": patch,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "augment_columns": list(AUGMENT_COLUMNS),
        "augments": augments,
        "champion_columns": list(CHAMPION_COLUMNS),
        "champions": champions,
        "item_columns": list(ITEM_COLUMNS),
        "items": items,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)
    return doc
