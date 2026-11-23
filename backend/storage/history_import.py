"""Read-only import of the player's own finished ARAM Mayhem matches.

Adapted conceptually from zp96-cmd/mayhem-overlay/src/main/history.js
(MIT-declared; credit in THIRD_PARTY_NOTICES.md). No account identifiers,
tokens or raw match data are returned by this module or sent externally.
"""
import logging
import re
import time

import requests

from backend.collectors.lcu import get_lcu_session, get_champion_id_map
from backend.storage.db import (
    game_exists, participants_exist, record_game, record_participants,
)

logger = logging.getLogger("aram-oracle.history")

MAYHEM_QUEUE_ID = 2400
_AUGMENT_KEY = re.compile(r"^playerAugment(\d+)$", re.IGNORECASE)


def extract_augments(stats: dict) -> list[str]:
    """Extract non-empty augment IDs in pick order from match statistics."""
    entries = []
    for key, value in (stats or {}).items():
        match = _AUGMENT_KEY.match(str(key))
        if match and isinstance(value, int) and value > 0:
            entries.append((int(match.group(1)), str(value)))
    return [value for _, value in sorted(entries)]


def extract_items(stats: dict) -> list[str]:
    """Extract positive item IDs in client slot order."""
    return [
        str(stats[f"item{slot}"])
        for slot in range(7)
        if isinstance(stats.get(f"item{slot}"), int)
        and stats[f"item{slot}"] > 0
    ]


def _int_or_none(value) -> int | None:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def extract_participants(detail: dict, aliases: dict, own_puuid: str | None) -> list[dict]:
    """All players of one game as anonymous stat rows (no names or account IDs).

    `heal_shield` is healing + shielding on teammates when the client reports it,
    else None; `heal_total` (includes self-healing) is kept as the fallback.
    """
    own_id = None
    if own_puuid:
        for item in detail.get("participantIdentities") or []:
            if isinstance(item, dict) and (item.get("player") or {}).get("puuid") == own_puuid:
                own_id = item.get("participantId")
                break
    rows = []
    for p in detail.get("participants") or []:
        if not isinstance(p, dict):
            continue
        champion = aliases.get(str(p.get("championId", 0)))
        stats = p.get("stats") or {}
        if not champion or not isinstance(stats, dict):
            continue
        win = stats.get("win")
        heals = _int_or_none(stats.get("totalHealsOnTeammates"))
        shields = _int_or_none(stats.get("totalDamageShieldedOnTeammates"))
        rows.append({
            "champion_id": champion,
            "team": _int_or_none(p.get("teamId")),
            "win": bool(win) if isinstance(win, (bool, int)) else None,
            "is_self": own_id is not None and p.get("participantId") == own_id,
            "augments": extract_augments(stats),
            "items": extract_items(stats),
            "damage_to_champions": _int_or_none(stats.get("totalDamageDealtToChampions")),
            "heal_shield": None if heals is None and shields is None
            else (heals or 0) + (shields or 0),
            "heal_total": _int_or_none(stats.get("totalHeal")),
            "kills": _int_or_none(stats.get("kills")),
            "deaths": _int_or_none(stats.get("deaths")),
            "assists": _int_or_none(stats.get("assists")),
        })
    return rows


def _get_json(session: requests.Session, endpoint: str) -> dict | None:
    try:
        response = session.get(f"{session.base_url}{endpoint}", timeout=3)
        if response.status_code != 200:
            return None
        data = response.json()
        return data if isinstance(data, dict) else None
    except (requests.RequestException, ValueError):
        return None


def _own_participant(match: dict, puuid: str) -> dict | None:
    """Match our PUUID to a participant; never assume the first player is us."""
    identities = match.get("participantIdentities") or []
    own_id = None
    for item in identities:
        if isinstance(item, dict) and (item.get("player") or {}).get("puuid") == puuid:
            own_id = item.get("participantId")
            break
    if own_id is None:
        return None
    for participant in match.get("participants") or []:
        if isinstance(participant, dict) and participant.get("participantId") == own_id:
            return participant
    return None


PAGE_SIZE = 20
MAX_HISTORY_GAMES = 1000
PAGE_PAUSE_SECS = 0.3


def _list_matches(session, max_games: int, pause: float) -> list[dict] | None:
    """Page the local client's match list (begIndex/endIndex) going back in time.

    Stops at max_games, on an empty page, or when a page brings no new game ids
    (i.e. the client ignores the indices). Only the loopback League Client API.
    """
    seen: set = set()
    out: list[dict] = []
    for beg in range(0, max_games, PAGE_SIZE):
        end = min(beg + PAGE_SIZE, max_games)
        response = _get_json(
            session,
            f"/lol-match-history/v1/products/lol/current-summoner/matches"
            f"?begIndex={beg}&endIndex={end}",
        )
        page = ((response or {}).get("games") or {}).get("games")
        if not isinstance(page, list):
            return out if beg else None
        fresh = [g for g in page if isinstance(g, dict) and g.get("gameId") not in seen]
        if not fresh:
            break
        for g in fresh:
            seen.add(g.get("gameId"))
        out.extend(fresh)
        if len(page) < end - beg:
            break
        if pause > 0:
            time.sleep(pause)
    return out[:max_games]


def sync_recent_mayhem_games(max_games: int = 40, pause: float = PAGE_PAUSE_SECS) -> dict:
    """Import up to max_games (<= 1000) recent games, using local LCU data only.

    The return value deliberately excludes account identifiers and match IDs.
    No network calls are made beyond the loopback League Client API.
    """
    max_games = max(1, min(int(max_games), MAX_HISTORY_GAMES))
    session = get_lcu_session()
    if session is None:
        return {"status": "client_unavailable", "imported": 0, "inspected": 0}

    imported = 0
    inspected = 0
    listed = 0
    with session:
        summoner = _get_json(session, "/lol-summoner/v1/current-summoner")
        puuid = summoner.get("puuid") if summoner else None
        if not isinstance(puuid, str) or not puuid:
            return {"status": "identity_unavailable", "imported": 0, "inspected": 0}

        matches = _list_matches(session, max_games, pause)
        if matches is None:
            return {"status": "history_unavailable", "imported": 0, "inspected": 0}
        listed = len(matches)
        aliases = get_champion_id_map(session)

        for summary in matches:
            if not isinstance(summary, dict):
                continue
            if summary.get("queueId") != MAYHEM_QUEUE_ID and str(
                summary.get("gameMode", "")
            ).upper() != "MAYHEM":
                continue
            inspected += 1
            game_id = summary.get("gameId")
            if not isinstance(game_id, int) or game_id <= 0:
                continue
            own_done = game_exists(str(game_id))
            if own_done and participants_exist(str(game_id)):
                continue
            detail = _get_json(session, f"/lol-match-history/v1/games/{game_id}")
            if not detail:
                logger.debug("Game details missing for an otherwise eligible match")
                continue
            duration = int(detail.get("gameDuration") or summary.get("gameDuration") or 0)
            record_participants(str(game_id), duration,
                                extract_participants(detail, aliases, puuid))
            if own_done:
                continue
            participant = _own_participant(detail, puuid)
            if participant is None:
                continue

            champion_id = aliases.get(str(participant.get("championId", 0)))
            stats = participant.get("stats") or {}
            if not champion_id or not isinstance(stats, dict):
                continue
            win = stats.get("win")
            if not isinstance(win, (bool, int)) or int(win) not in (0, 1):
                continue

            record_game(
                game_id=str(game_id),
                champion_id=champion_id,
                augments=extract_augments(stats),
                items=extract_items(stats),
                win=bool(win),
                game_time_secs=duration,
                kda={k: stats.get(k, 0) for k in ("kills", "deaths", "assists")},
            )
            imported += 1

    return {"status": "ok", "imported": imported, "inspected": inspected,
            "listed": listed}
