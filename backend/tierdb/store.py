"""Local tier-list database: per-value provenance for third-party and local data.

Design: `audit/tierdb/DESENHO_TIERDB_2026-11-23.md` (project files). Every
observation carries its source, snapshot (patch, window, SHA-256) and sample
size. Nothing is fabricated: a value without a positive sample size is
rejected, and a whole batch is rejected atomically if any value is invalid.

The database lives on the user's machine, never in the Git checkout.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCOPES = {
    # scope: (needs champion, needs role, needs augment)
    "champion": (True, False, False),
    "champ_aug": (True, False, True),
    "role_aug": (False, True, True),
    "global_aug": (False, False, True),
}

# Item scopes: (needs item_id, needs augment_id, needs ordered items)
ITEM_SCOPES = {
    "champ_item": (True, False, False),        # finished item held at game end
    "champ_item_base": (False, False, False),  # denominator for champ_item/champ_core
    "champ_boots": (True, False, False),
    "champ_boots_base": (False, False, False),
    "champ_core": (False, False, True),        # first three legendaries, in order
    "champ_aug_item": (True, True, False),     # first legendary with an augment
    "champ_aug_item_base": (False, True, False),
}

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    url           TEXT NOT NULL,
    license       TEXT NOT NULL,
    attribution   TEXT NOT NULL,
    commercial_ok INTEGER NOT NULL CHECK (commercial_ok IN (0, 1))
);

CREATE TABLE IF NOT EXISTS snapshot (
    id                      INTEGER PRIMARY KEY,
    source_id               INTEGER NOT NULL REFERENCES source(id),
    patch                   TEXT NOT NULL,
    region                  TEXT NOT NULL,
    queue                   INTEGER,
    window_start            TEXT,
    window_end              TEXT,
    fetched_at              TEXT NOT NULL,
    sha256                  TEXT NOT NULL,
    row_count               INTEGER NOT NULL,
    metric_definitions_json TEXT NOT NULL,
    UNIQUE (source_id, sha256)
);

CREATE TABLE IF NOT EXISTS observation (
    id          INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES snapshot(id) ON DELETE CASCADE,
    scope       TEXT NOT NULL,
    champion_id TEXT,
    role        TEXT,
    augment_id  TEXT,
    metric      TEXT NOT NULL,
    value       REAL,
    wins        INTEGER,
    n           INTEGER NOT NULL CHECK (n > 0),
    low_sample  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_obs_lookup
    ON observation (metric, champion_id, augment_id);

CREATE TABLE IF NOT EXISTS item_observation (
    id          INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES snapshot(id) ON DELETE CASCADE,
    scope       TEXT NOT NULL,
    champion_id TEXT NOT NULL,
    item_id     TEXT,
    augment_id  TEXT,
    items_json  TEXT,
    ordered     INTEGER NOT NULL DEFAULT 0,
    value       REAL,
    wins        INTEGER NOT NULL,
    n           INTEGER NOT NULL CHECK (n > 0),
    low_sample  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_item_obs ON item_observation (scope, champion_id);

CREATE TABLE IF NOT EXISTS item_tier (
    run_id      INTEGER NOT NULL REFERENCES tier_run(id) ON DELETE CASCADE,
    champion_id TEXT NOT NULL,
    item_id     TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('final', 'boots')),
    score       REAL, score_p20 REAL, score_p80 REAL,
    rank        INTEGER, tie_group INTEGER, tier TEXT,
    level       TEXT NOT NULL, confidence TEXT NOT NULL,
    PRIMARY KEY (run_id, champion_id, kind, item_id)
);

CREATE TABLE IF NOT EXISTS reference_build (
    run_id      INTEGER NOT NULL REFERENCES tier_run(id) ON DELETE CASCADE,
    champion_id TEXT NOT NULL,
    slot        INTEGER NOT NULL,  -- 1..6 items, 0 = boots
    item_id     TEXT NOT NULL,
    source      TEXT NOT NULL CHECK (source IN ('core', 'tier', 'stat', 'boots')),
    PRIMARY KEY (run_id, champion_id, slot)
);

CREATE TABLE IF NOT EXISTS champion_stat_demand (
    run_id      INTEGER NOT NULL REFERENCES tier_run(id) ON DELETE CASCADE,
    champion_id TEXT NOT NULL,
    stat        TEXT NOT NULL,
    weight      REAL NOT NULL,
    source      TEXT NOT NULL CHECK (source IN ('builds', 'role')),
    PRIMARY KEY (run_id, champion_id, stat)
);

CREATE TABLE IF NOT EXISTS item_info (
    snapshot_id INTEGER NOT NULL REFERENCES snapshot(id) ON DELETE CASCADE,
    item_id     TEXT NOT NULL,
    category    TEXT NOT NULL,
    types_json  TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, item_id)
);

CREATE TABLE IF NOT EXISTS augment_info (
    snapshot_id INTEGER NOT NULL REFERENCES snapshot(id) ON DELETE CASCADE,
    augment_id  TEXT NOT NULL,
    name        TEXT NOT NULL,
    rarity      TEXT NOT NULL CHECK (rarity IN ('silver', 'gold', 'prismatic')),
    PRIMARY KEY (snapshot_id, augment_id)
);

CREATE TABLE IF NOT EXISTS quarantine (
    id          INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES snapshot(id) ON DELETE CASCADE,
    raw_name    TEXT NOT NULL,
    reason      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tier_run (
    id                INTEGER PRIMARY KEY,
    patch             TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    code_sha          TEXT,
    weights_json      TEXT NOT NULL,
    thresholds_json   TEXT NOT NULL,
    snapshot_ids_json TEXT NOT NULL,
    seed              INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS augment_tier (
    run_id      INTEGER NOT NULL REFERENCES tier_run(id) ON DELETE CASCADE,
    champion_id TEXT NOT NULL,
    rarity      TEXT NOT NULL,
    augment_id  TEXT NOT NULL,
    score       REAL,
    score_p20   REAL,
    score_p80   REAL,
    rank        INTEGER,
    tie_group   INTEGER,
    tier        TEXT,
    level       TEXT NOT NULL,
    confidence  TEXT NOT NULL,
    n_eff       REAL NOT NULL DEFAULT 0,
    sources_json TEXT NOT NULL,
    rank_all    INTEGER,
    PRIMARY KEY (run_id, champion_id, augment_id)
);

CREATE TABLE IF NOT EXISTS champion_tier (
    run_id          INTEGER NOT NULL REFERENCES tier_run(id) ON DELETE CASCADE,
    champion_id     TEXT NOT NULL,
    score           REAL,
    components_json TEXT NOT NULL,
    rank            INTEGER,
    tie_group       INTEGER,
    tier            TEXT,
    confidence      TEXT NOT NULL,
    n               INTEGER NOT NULL DEFAULT 0,
    potential       TEXT CHECK (potential IN ('very_low', 'low', 'medium', 'high', 'very_high')),
    PRIMARY KEY (run_id, champion_id)
);
"""


class ProvenanceError(ValueError):
    """A value or snapshot lacks the provenance the tier DB requires."""


@dataclass(frozen=True)
class SourceMeta:
    name: str
    url: str
    license: str
    attribution: str
    commercial_ok: bool


@dataclass(frozen=True)
class SnapshotMeta:
    patch: str
    region: str
    sha256: str
    queue: int | None = None
    window_start: str | None = None
    window_end: str | None = None
    metric_definitions: dict = field(default_factory=dict)
    fetched_at: str | None = None
    row_count: int = 0


@dataclass(frozen=True)
class Observation:
    scope: str
    metric: str
    n: int | None
    champion_id: str | None = None
    role: str | None = None
    augment_id: str | None = None
    value: float | None = None
    wins: int | None = None
    low_sample: bool = False


@dataclass(frozen=True)
class ItemObservation:
    scope: str
    champion_id: str
    n: int | None
    wins: int | None
    item_id: str | None = None
    augment_id: str | None = None
    items: tuple[str, ...] | None = None
    ordered: bool = False
    value: float | None = None
    low_sample: bool = False


@dataclass(frozen=True)
class StoredItemObservation:
    scope: str
    champion_id: str
    item_id: str | None
    augment_id: str | None
    items: tuple[str, ...] | None
    ordered: bool
    value: float | None
    wins: int
    n: int
    low_sample: bool
    source_name: str
    snapshot_id: int


def _validate_item_observation(obs: ItemObservation) -> None:
    if obs.scope not in ITEM_SCOPES:
        raise ProvenanceError(f"unknown item scope {obs.scope!r}")
    if not obs.champion_id:
        raise ProvenanceError("item observation requires champion_id")
    if obs.n is None or int(obs.n) <= 0:
        raise ProvenanceError("item value without a positive sample size")
    if obs.wins is None or not 0 <= obs.wins <= obs.n:
        raise ProvenanceError("wins must lie in [0, n]")
    need_item, need_aug, need_items = ITEM_SCOPES[obs.scope]
    for present, needed, label in ((obs.item_id, need_item, "item_id"),
                                   (obs.augment_id, need_aug, "augment_id"),
                                   (obs.items, need_items, "items")):
        if needed and not present:
            raise ProvenanceError(f"scope {obs.scope} requires {label}")
        if not needed and present:
            raise ProvenanceError(f"scope {obs.scope} must not set {label}")


@dataclass(frozen=True)
class StoredObservation:
    scope: str
    metric: str
    n: int
    champion_id: str | None
    role: str | None
    augment_id: str | None
    value: float | None
    wins: int | None
    low_sample: bool
    source_name: str
    snapshot_id: int
    snapshot_sha256: str
    patch: str
    region: str


def _validate_observation(obs: Observation) -> None:
    if obs.scope not in SCOPES:
        raise ProvenanceError(f"unknown scope {obs.scope!r}")
    if not obs.metric:
        raise ProvenanceError("metric is required")
    if obs.n is None or int(obs.n) <= 0:
        raise ProvenanceError(f"{obs.metric} value without a positive sample size")
    need_champ, need_role, need_aug = SCOPES[obs.scope]
    for present, needed, label in (
        (obs.champion_id, need_champ, "champion_id"),
        (obs.role, need_role, "role"),
        (obs.augment_id, need_aug, "augment_id"),
    ):
        if needed and not present:
            raise ProvenanceError(f"scope {obs.scope} requires {label}")
        if not needed and present:
            raise ProvenanceError(f"scope {obs.scope} must not set {label}")
    if obs.metric == "win":
        if obs.wins is None:
            raise ProvenanceError("win metric requires wins")
        if not 0 <= obs.wins <= obs.n:
            raise ProvenanceError("wins must lie in [0, n]")
    elif obs.value is None:
        raise ProvenanceError(f"{obs.metric} value is missing")


def _validate_snapshot(snap: SnapshotMeta) -> None:
    if not snap.patch:
        raise ProvenanceError("snapshot patch is required")
    if not snap.region:
        raise ProvenanceError("snapshot region is required")
    if not _SHA_RE.match(snap.sha256 or ""):
        raise ProvenanceError("snapshot sha256 must be 64 lowercase hex chars")


class TierStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path))
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Additive column migrations for databases created by older builds."""
        cols = {r[1] for r in self.connection.execute("PRAGMA table_info(champion_tier)")}
        if "potential" not in cols:
            with self.connection:
                self.connection.execute("ALTER TABLE champion_tier ADD COLUMN potential TEXT")
        cols = {r[1] for r in self.connection.execute("PRAGMA table_info(augment_tier)")}
        if "rank_all" not in cols:
            with self.connection:
                self.connection.execute("ALTER TABLE augment_tier ADD COLUMN rank_all INTEGER")
        sql = (self.connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='reference_build'").fetchone() or [""])[0]
        if "'stat'" not in sql:
            # Field 23/11: builds may carry a required-stat slot (source 'stat').
            con = self.connection
            con.execute("PRAGMA foreign_keys = OFF")
            with con:
                con.execute("ALTER TABLE reference_build RENAME TO reference_build_old")
                con.executescript(SCHEMA)
                con.execute("INSERT INTO reference_build SELECT * FROM reference_build_old")
                con.execute("DROP TABLE reference_build_old")
            con.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self.connection.close()

    # -- writes -----------------------------------------------------------

    def _source_id(self, source: SourceMeta) -> int:
        con = self.connection
        row = con.execute("SELECT id FROM source WHERE name=?", (source.name,)).fetchone()
        values = (source.url, source.license, source.attribution, int(source.commercial_ok))
        if row:
            con.execute(
                "UPDATE source SET url=?, license=?, attribution=?, commercial_ok=? WHERE id=?",
                (*values, row[0]),
            )
            return row[0]
        cur = con.execute(
            "INSERT INTO source (name, url, license, attribution, commercial_ok) VALUES (?,?,?,?,?)",
            (source.name, *values),
        )
        return cur.lastrowid

    def ingest(
        self,
        source: SourceMeta,
        snapshot: SnapshotMeta,
        observations: list[Observation],
        quarantine: list[tuple[str, str]] | None = None,
        augments: dict[str, tuple[str, str]] | None = None,
    ) -> int:
        """Store one snapshot atomically; return its id.

        Re-ingesting a snapshot with the same SHA-256 from the same source is a
        no-op that returns the existing id.
        """
        _validate_snapshot(snapshot)
        for obs in observations:
            _validate_observation(obs)

        con = self.connection
        with con:
            source_id = self._source_id(source)
            existing = con.execute(
                "SELECT id FROM snapshot WHERE source_id=? AND sha256=?",
                (source_id, snapshot.sha256),
            ).fetchone()
            if existing:
                return existing[0]
            fetched_at = snapshot.fetched_at or datetime.now(timezone.utc).isoformat()
            cur = con.execute(
                """INSERT INTO snapshot (source_id, patch, region, queue, window_start,
                       window_end, fetched_at, sha256, row_count, metric_definitions_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    source_id, snapshot.patch, snapshot.region, snapshot.queue,
                    snapshot.window_start, snapshot.window_end, fetched_at,
                    snapshot.sha256, len(observations),
                    json.dumps(snapshot.metric_definitions, sort_keys=True),
                ),
            )
            snap_id = cur.lastrowid
            con.executemany(
                """INSERT INTO observation (snapshot_id, scope, champion_id, role,
                       augment_id, metric, value, wins, n, low_sample)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                [
                    (snap_id, o.scope, o.champion_id, o.role, o.augment_id, o.metric,
                     o.value, o.wins, int(o.n), int(bool(o.low_sample)))
                    for o in observations
                ],
            )
            con.executemany(
                "INSERT INTO augment_info (snapshot_id, augment_id, name, rarity) VALUES (?,?,?,?)",
                [(snap_id, aid, name, rarity)
                 for aid, (name, rarity) in sorted((augments or {}).items())],
            )
            con.executemany(
                "INSERT INTO quarantine (snapshot_id, raw_name, reason) VALUES (?,?,?)",
                [(snap_id, name, reason) for name, reason in (quarantine or [])],
            )
        return snap_id

    # -- reads ------------------------------------------------------------

    def snapshot(self, snapshot_id: int) -> SnapshotMeta:
        row = self.connection.execute(
            """SELECT patch, region, sha256, queue, window_start, window_end,
                      metric_definitions_json, fetched_at, row_count
               FROM snapshot WHERE id=?""",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            raise KeyError(snapshot_id)
        return SnapshotMeta(
            patch=row[0], region=row[1], sha256=row[2], queue=row[3],
            window_start=row[4], window_end=row[5],
            metric_definitions=json.loads(row[6]), fetched_at=row[7], row_count=row[8],
        )

    def ingest_items(
        self,
        snapshot_id: int,
        observations: list[ItemObservation],
        item_info: dict[str, tuple[str, tuple[str, ...]]] | None = None,
    ) -> int:
        """Attach item observations to a snapshot once; return rows written.

        A snapshot that already has item rows is left unchanged (idempotent);
        a snapshot stored by an older build without items gets them added.
        """
        for obs in observations:
            _validate_item_observation(obs)
        con = self.connection
        with con:
            if con.execute("SELECT 1 FROM item_observation WHERE snapshot_id=? LIMIT 1",
                           (snapshot_id,)).fetchone():
                return 0
            con.executemany(
                """INSERT INTO item_observation (snapshot_id, scope, champion_id, item_id,
                       augment_id, items_json, ordered, value, wins, n, low_sample)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                [(snapshot_id, o.scope, o.champion_id, o.item_id, o.augment_id,
                  json.dumps(list(o.items)) if o.items else None, int(bool(o.ordered)),
                  o.value, int(o.wins), int(o.n), int(bool(o.low_sample)))
                 for o in observations],
            )
            con.executemany(
                "INSERT OR REPLACE INTO item_info (snapshot_id, item_id, category, types_json) "
                "VALUES (?,?,?,?)",
                [(snapshot_id, iid, cat, json.dumps(list(types)))
                 for iid, (cat, types) in sorted((item_info or {}).items())],
            )
        return len(observations)

    def item_observations(self, patch: str, scope: str | None = None,
                          champion_id: str | None = None) -> list[StoredItemObservation]:
        sql = """SELECT o.scope, o.champion_id, o.item_id, o.augment_id, o.items_json,
                        o.ordered, o.value, o.wins, o.n, o.low_sample, src.name, s.id
                 FROM item_observation o
                 JOIN snapshot s ON s.id = o.snapshot_id
                 JOIN source src ON src.id = s.source_id
                 WHERE s.patch = ?"""
        params: list = [patch]
        for column, value in (("o.scope", scope), ("o.champion_id", champion_id)):
            if value is not None:
                sql += f" AND {column} = ?"
                params.append(value)
        return [
            StoredItemObservation(
                scope=r[0], champion_id=r[1], item_id=r[2], augment_id=r[3],
                items=tuple(json.loads(r[4])) if r[4] else None, ordered=bool(r[5]),
                value=r[6], wins=r[7], n=r[8], low_sample=bool(r[9]),
                source_name=r[10], snapshot_id=r[11])
            for r in self.connection.execute(sql + " ORDER BY o.id", params)
        ]

    def item_info(self, patch: str) -> dict[str, tuple[str, tuple[str, ...]]]:
        rows = self.connection.execute(
            """SELECT i.item_id, i.category, i.types_json FROM item_info i
               JOIN snapshot s ON s.id = i.snapshot_id WHERE s.patch = ? ORDER BY s.id""",
            (patch,))
        return {iid: (cat, tuple(json.loads(types))) for iid, cat, types in rows}

    def augment_rarities(self, patch: str) -> dict[str, str]:
        """Augment id -> rarity for every augment described in the patch."""
        rows = self.connection.execute(
            """SELECT a.augment_id, a.rarity FROM augment_info a
               JOIN snapshot s ON s.id = a.snapshot_id
               WHERE s.patch = ? ORDER BY s.id""",
            (patch,),
        )
        return {aid: rarity for aid, rarity in rows}

    def snapshot_ids(self, patch: str) -> list[int]:
        return [r[0] for r in self.connection.execute(
            "SELECT id FROM snapshot WHERE patch=? ORDER BY id", (patch,))]

    def sources(self, commercial_only: bool = False) -> list[SourceMeta]:
        sql = "SELECT name, url, license, attribution, commercial_ok FROM source"
        if commercial_only:
            sql += " WHERE commercial_ok = 1"
        return [
            SourceMeta(name=r[0], url=r[1], license=r[2], attribution=r[3],
                       commercial_ok=bool(r[4]))
            for r in self.connection.execute(sql + " ORDER BY name")
        ]

    def observations(
        self,
        patch: str,
        metric: str | None = None,
        champion_id: str | None = None,
        scope: str | None = None,
        commercial_only: bool = False,
    ) -> list[StoredObservation]:
        sql = """SELECT o.scope, o.metric, o.n, o.champion_id, o.role, o.augment_id,
                        o.value, o.wins, o.low_sample, src.name, s.id, s.sha256,
                        s.patch, s.region
                 FROM observation o
                 JOIN snapshot s ON s.id = o.snapshot_id
                 JOIN source src ON src.id = s.source_id
                 WHERE s.patch = ?"""
        params: list = [patch]
        for column, value in (("o.metric", metric), ("o.champion_id", champion_id),
                              ("o.scope", scope)):
            if value is not None:
                sql += f" AND {column} = ?"
                params.append(value)
        if commercial_only:
            sql += " AND src.commercial_ok = 1"
        sql += " ORDER BY o.id"
        return [
            StoredObservation(
                scope=r[0], metric=r[1], n=r[2], champion_id=r[3], role=r[4],
                augment_id=r[5], value=r[6], wins=r[7], low_sample=bool(r[8]),
                source_name=r[9], snapshot_id=r[10], snapshot_sha256=r[11],
                patch=r[12], region=r[13],
            )
            for r in self.connection.execute(sql, params)
        ]
