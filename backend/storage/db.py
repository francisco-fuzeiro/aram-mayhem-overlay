import json
import logging
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger("aram-oracle.db")

DB_PATH = Path.home() / ".aram-oracle" / "oracle.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id              TEXT PRIMARY KEY,
    champion_id     TEXT NOT NULL,
    augments        TEXT NOT NULL,
    items           TEXT NOT NULL,
    win             INTEGER,
    game_time_secs  INTEGER,
    kills           INTEGER DEFAULT 0,
    deaths          INTEGER DEFAULT 0,
    assists         INTEGER DEFAULT 0,
    played_at       TEXT NOT NULL,
    submitted       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS augment_stats (
    augment_id  TEXT NOT NULL,
    champion_id TEXT NOT NULL,
    games       INTEGER DEFAULT 0,
    wins        INTEGER DEFAULT 0,
    PRIMARY KEY (augment_id, champion_id)
);

-- All 10 players of each finished local Mayhem game (owner decision 23/11).
-- Local-only and never submitted: no names, PUUIDs, summoner IDs or match IDs;
-- `game` is a salted local hash of the match id.
CREATE TABLE IF NOT EXISTS participants (
    game                TEXT NOT NULL,
    slot                INTEGER NOT NULL,
    duration            INTEGER NOT NULL,
    team                INTEGER,
    champion_id         TEXT NOT NULL,
    win                 INTEGER,
    augments            TEXT NOT NULL,
    items               TEXT NOT NULL,
    damage_to_champions INTEGER,
    heal_shield         INTEGER,
    heal_total          INTEGER,
    kills               INTEGER,
    deaths              INTEGER,
    assists             INTEGER,
    is_self             INTEGER DEFAULT 0,
    imported_at         TEXT NOT NULL,
    PRIMARY KEY (game, slot)
);

CREATE TABLE IF NOT EXISTS local_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

MIN_GAME_SECS = 300  # shorter games are remakes
_PARTICIPANT_FIELDS = (
    "game", "duration", "team", "champion_id", "win", "augments", "items",
    "damage_to_champions", "heal_shield", "heal_total", "kills", "deaths",
    "assists", "is_self",
)


def init_db(db_path: Path | None = None) -> None:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with _connect(path) as con:
            con.executescript(SCHEMA)
    except sqlite3.Error as e:
        logger.error("Failed to initialize database at %s: %s", path, e, exc_info=True)


def record_game(
    game_id: str,
    champion_id: str,
    augments: list[str],
    items: list[str],
    win: bool | None,
    game_time_secs: int,
    kda: dict,
    db_path: Path | None = None,
) -> None:
    path = db_path or DB_PATH
    try:
        with _connect(path) as con:
            # Importers may encounter the same game repeatedly. Avoid
            # inflating augment sample counts on a second sync.
            previous = con.execute(
                "SELECT win FROM games WHERE id=?", (game_id,)
            ).fetchone()
            if previous is not None:
                # Permit backfilling a previously unknown result only.
                if previous[0] is not None or win is None:
                    return
            con.execute(
                """INSERT OR REPLACE INTO games
                   VALUES (?,?,?,?,?,?,?,?,?,?,0)""",
                (
                    game_id, champion_id,
                    json.dumps(augments), json.dumps(items),
                    int(win) if win is not None else None,
                    game_time_secs,
                    kda.get("kills", 0),
                    kda.get("deaths", 0),
                    kda.get("assists", 0),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            if win is not None:
                for aug_id in augments:
                    con.execute("""
                        INSERT INTO augment_stats (augment_id, champion_id, games, wins)
                        VALUES (?, ?, 1, ?)
                        ON CONFLICT(augment_id, champion_id) DO UPDATE SET
                            games = games + 1,
                            wins  = wins  + excluded.wins
                    """, (aug_id, champion_id, int(win)))
    except sqlite3.Error as e:
        logger.error("Failed to record game %s: %s", game_id, e, exc_info=True)


def game_exists(game_id: str, db_path: Path | None = None) -> bool:
    """Return whether an imported game was already stored."""
    try:
        with _connect(db_path or DB_PATH) as con:
            return con.execute(
                "SELECT 1 FROM games WHERE id=?", (game_id,)
            ).fetchone() is not None
    except sqlite3.Error:
        return False


def get_champion_record(
    champion_id: str, db_path: Path | None = None,
) -> tuple[int, int] | None:
    """Return (wins, games) for the user's known, finished games on a champion.

    No matches are fabricated. Games with unknown outcome are excluded.
    """
    try:
        with _connect(db_path or DB_PATH) as con:
            row = con.execute(
                """SELECT COALESCE(SUM(CASE WHEN win = 1 THEN 1 ELSE 0 END), 0),
                          COUNT(*)
                   FROM games
                   WHERE champion_id = ? AND win IN (0, 1)""",
                (champion_id,),
            ).fetchone()
        return (int(row[0]), int(row[1])) if row and row[1] else None
    except sqlite3.Error:
        return None


def get_personal_winrate(
    champion_id: str, augment_id: str, db_path: Path | None = None,
) -> tuple[int, int] | None:
    """Returns (wins, games) or None if no data."""
    path = db_path or DB_PATH
    try:
        with _connect(path) as con:
            row = con.execute(
                """SELECT wins, games FROM augment_stats
                   WHERE augment_id=? AND champion_id=?""",
                (augment_id, champion_id),
            ).fetchone()
        return (row[0], row[1]) if row else None
    except sqlite3.Error as e:
        logger.error("Failed to get winrate for %s/%s: %s", champion_id, augment_id, e)
        return None


def get_all_personal_winrates(
    champion_id: str, db_path: Path | None = None,
) -> dict[str, tuple[int, int]]:
    """Returns {augment_id: (wins, games)} for all augments on a champion."""
    path = db_path or DB_PATH
    try:
        with _connect(path) as con:
            rows = con.execute(
                "SELECT augment_id, wins, games FROM augment_stats WHERE champion_id=?",
                (champion_id,),
            ).fetchall()
        return {row[0]: (row[1], row[2]) for row in rows}
    except sqlite3.Error as e:
        logger.error("Failed to get winrates for %s: %s", champion_id, e)
        return {}


def get_unsubmitted_games(db_path: Path | None = None) -> list[dict]:
    path = db_path or DB_PATH
    try:
        with _connect(path) as con:
            rows = con.execute(
                "SELECT * FROM games WHERE submitted=0 AND win IS NOT NULL"
            ).fetchall()
        columns = [
            "id", "champion_id", "augments", "items", "win", "game_time_secs",
            "kills", "deaths", "assists", "played_at", "submitted",
        ]
        return [dict(zip(columns, row)) for row in rows]
    except sqlite3.Error as e:
        logger.error("Failed to get unsubmitted games: %s", e)
        return []


def mark_submitted(game_ids: list[str], db_path: Path | None = None) -> None:
    path = db_path or DB_PATH
    try:
        with _connect(path) as con:
            con.executemany(
                "UPDATE games SET submitted=1 WHERE id=?",
                [(gid,) for gid in game_ids],
            )
    except sqlite3.Error as e:
        logger.error("Failed to mark games submitted: %s", e)


def _local_salt(con: sqlite3.Connection) -> str:
    con.executescript(SCHEMA)
    row = con.execute("SELECT value FROM local_meta WHERE key='game_salt'").fetchone()
    if row:
        return row[0]
    import secrets
    salt = secrets.token_hex(16)
    con.execute("INSERT INTO local_meta(key, value) VALUES ('game_salt', ?)", (salt,))
    return salt


def _game_key(con: sqlite3.Connection, game_id: str) -> str:
    import hashlib
    return hashlib.sha256(f"{_local_salt(con)}:{game_id}".encode()).hexdigest()[:16]


def participants_exist(game_id: str, db_path: Path | None = None) -> bool:
    try:
        with _connect(db_path or DB_PATH) as con:
            key = _game_key(con, str(game_id))
            return con.execute("SELECT 1 FROM participants WHERE game=? LIMIT 1",
                               (key,)).fetchone() is not None
    except sqlite3.Error:
        return False


def record_participants(game_id: str, duration: int, rows: list[dict],
                        db_path: Path | None = None) -> int:
    """Store all players of one game once; returns rows inserted (0 for remakes)."""
    if not rows or int(duration or 0) < MIN_GAME_SECS:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    try:
        with _connect(db_path or DB_PATH) as con:
            key = _game_key(con, str(game_id))
            if con.execute("SELECT 1 FROM participants WHERE game=? LIMIT 1",
                           (key,)).fetchone():
                return 0
            con.executemany(
                "INSERT INTO participants (game, slot, duration, team, champion_id, win,"
                " augments, items, damage_to_champions, heal_shield, heal_total, kills,"
                " deaths, assists, is_self, imported_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(key, i, int(duration), r.get("team"), r["champion_id"],
                  None if r.get("win") is None else int(bool(r["win"])),
                  json.dumps(list(r.get("augments") or [])),
                  json.dumps(list(r.get("items") or [])),
                  r.get("damage_to_champions"), r.get("heal_shield"),
                  r.get("heal_total"), r.get("kills"), r.get("deaths"),
                  r.get("assists"), int(bool(r.get("is_self"))), now)
                 for i, r in enumerate(rows)],
            )
            return len(rows)
    except sqlite3.Error as e:
        logger.error("Failed to record participants: %s", e)
        return 0


def get_participants(db_path: Path | None = None) -> list[dict]:
    """All stored participant rows, oldest import first (for temporal holdouts)."""
    try:
        with _connect(db_path or DB_PATH) as con:
            con.executescript(SCHEMA)
            rows = con.execute(
                "SELECT " + ", ".join(_PARTICIPANT_FIELDS) +
                " FROM participants ORDER BY imported_at, rowid").fetchall()
    except sqlite3.Error as e:
        logger.error("Failed to read participants: %s", e)
        return []
    out = []
    for row in rows:
        d = dict(zip(_PARTICIPANT_FIELDS, row))
        d["augments"] = json.loads(d["augments"] or "[]")
        d["items"] = json.loads(d["items"] or "[]")
        d["win"] = None if d["win"] is None else bool(d["win"])
        d["is_self"] = bool(d["is_self"])
        out.append(d)
    return out


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)
