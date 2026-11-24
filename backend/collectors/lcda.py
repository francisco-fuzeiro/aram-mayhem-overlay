import errno
from dataclasses import dataclass
from typing import Literal

import requests
import urllib3
from backend.diagnostic_events import events as event_log
from backend.models import GameSnapshot, GamePhase, EnemyState
from backend.collectors.anvil_voucher import count_anvil_vouchers

# League's Live Client Data API uses a self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LCDA_BASE = "https://127.0.0.1:2999/liveclientdata"
SESSION = requests.Session()
SESSION.verify = False

# Champions whose LCDA display name normalizes differently from the data key
_CHAMPION_ALIASES = {
    "nunu&willump": "nunu",
    "dr.mundo": "drmundo",
    "wukong": "monkeyking",
    "renataglasc": "renata",
}


def _normalize_champion_name(raw: str) -> str:
    """Normalize an LCDA champion name to match champions.json keys."""
    key = raw.lower().replace(" ", "").replace("'", "")
    return _CHAMPION_ALIASES.get(key, key)


def _riot_identity(player: dict) -> str | None:
    """Riot ID from the current LCDA payload, with no guessed identity."""
    if not isinstance(player, dict):
        return None
    rid = player.get("riotId")
    if isinstance(rid, str) and rid.strip():
        return rid.strip().casefold()
    if isinstance(rid, dict):
        name, tag = rid.get("gameName"), rid.get("tagLine")
    else:
        name, tag = player.get("riotIdGameName"), player.get("riotIdTagLine")
    if isinstance(name, str) and isinstance(tag, str) and name and tag:
        return f"{name}#{tag}".casefold()
    return None


def _is_main_inventory_item(item: dict) -> bool:
    """Count only slots 0–5 towards a six-slot build.

    Live Client Data API reports the trinket/poro slot as slot 6. The
    fallback for Poro-Snax protects older data mocks with no slot field.
    This must not infer any hidden items or discount regular item slots.
    """
    if not isinstance(item, dict) or item.get("itemID") is None:
        return False
    if str(item["itemID"]) == "2052":
        return False
    slot = item.get("slot")
    return not (isinstance(slot, int) and (slot < 0 or slot >= 6))


LCDAStatus = Literal["ok", "http_404", "timeout", "refused", "bad_json", "error"]


@dataclass(frozen=True)
class LCDAResult:
    """A transport result; unavailable data is never mistaken for an empty game."""

    status: LCDAStatus
    payload: dict | None = None


def _result(status: LCDAStatus, payload: dict | None = None) -> LCDAResult:
    """Only bounded status enums reach the diagnostic journal."""
    if status == "ok":
        event_log.transition("lcda", status="available", error_class="none")
    elif status == "http_404":
        event_log.transition("lcda", status="unavailable", error_class="http_404")
    else:
        event_log.transition("lcda", status="error", error_class=(
            status if status in ("timeout", "refused", "bad_json") else "request"
        ))
    return LCDAResult(status, payload if status == "ok" else None)


def _is_connection_refused(error: BaseException) -> bool:
    """Unwrap requests/urllib3 exception causes without logging exception text."""
    pending = [error]
    visited: set[int] = set()
    while pending and len(visited) < 16:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        if isinstance(current, OSError) and getattr(current, "errno", None) in (
            errno.ECONNREFUSED, 10061, 111,
        ):
            return True
        for value in (
            getattr(current, "__cause__", None),
            getattr(current, "__context__", None),
            getattr(current, "reason", None),
            *getattr(current, "args", ()),
        ):
            if isinstance(value, BaseException):
                pending.append(value)
    return False


def get_raw_game_data() -> LCDAResult:
    """Fetch LCDA on a worker thread (caller responsibility), return typed status."""
    try:
        response = SESSION.get(f"{LCDA_BASE}/allgamedata", timeout=1)
    except requests.Timeout:
        return _result("timeout")
    except requests.ConnectionError as error:
        return _result("refused" if _is_connection_refused(error) else "error")
    except requests.RequestException:
        return _result("error")
    except Exception:
        # Unexpected network/adapter failures never fabricate a game.
        return _result("error")

    if response.status_code == 404:
        return _result("http_404")
    if response.status_code != 200:
        return _result("error")
    try:
        raw = response.json()
    except (ValueError, TypeError):
        return _result("bad_json")
    if not isinstance(raw, dict):
        return _result("bad_json")
    return _result("ok", raw)

def get_active_player_name() -> str | None:
    try:
        r = SESSION.get(f"{LCDA_BASE}/activeplayer", timeout=1)
        return r.json().get("summonerName") if r.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None


def parse_game_snapshot(raw: dict, phase: GamePhase) -> GameSnapshot:
    """
    Parse raw LCDv2 allgamedata response into a GameSnapshot.
    augment_choices and chosen_augments are not available from LCDv2 directly --
    they must be injected from the overlay event watcher.
    """
    active = raw.get("activePlayer", {})
    all_players = raw.get("allPlayers", [])
    game_data = raw.get("gameData", {})

    active_riot_id = _riot_identity(active)
    active_player = next(
        (p for p in all_players
         if active_riot_id and _riot_identity(p) == active_riot_id),
        {},
    )
    if not active_player:
        # Older LCDA payloads may not expose Riot ID; use the legacy name
        # only when a precise Riot-ID match was unavailable.
        active_name = active.get("summonerName")
        active_player = next(
            (p for p in all_players if active_name and p.get("summonerName") == active_name),
            {},
        )

    items = [
        str(item["itemID"]) for item in active_player.get("items", [])
        if _is_main_inventory_item(item)
    ]
    # Only the uniquely identified active player can supply voucher evidence.
    # Missing player or inventory is unknown, never zero stacks.
    anvil_vouchers = count_anvil_vouchers(active_player.get("items")) if active_player else None
    gold = int(active.get("currentGold", 0))
    game_time = float(game_data.get("gameTime", 0))
    game_id = str(game_data.get("gameId", "unknown"))
    level = int(active.get("level", 1))

    # Full champion stats dict for augment detection via stat deltas
    raw_stats = active.get("championStats", {})
    champion_stats = {
        k: float(v) for k, v in raw_stats.items()
        if isinstance(v, (int, float))
    }
    cur_hp = champion_stats.get("currentHealth", 0.0)
    max_hp = champion_stats.get("maxHealth", 1.0)
    health_pct = cur_hp / max_hp if max_hp > 0 else 1.0

    # Death status from allPlayers entry
    is_dead = bool(active_player.get("isDead", False))

    champion_id = _normalize_champion_name(
        active_player.get("championName", "")
    )

    # Never infer hidden opponents: use only players returned in allgamedata.
    # If the local player cannot be identified, do not guess the teams.
    our_team = active_player.get("team") if active_player else None
    opponents = [
        p for p in all_players
        if our_team is not None and p.get("team") not in (None, our_team)
    ]
    enemies = [
        _normalize_champion_name(p.get("championName", ""))
        for p in opponents if p.get("championName")
    ]
    enemy_states = [
        EnemyState(
            champion_id=_normalize_champion_name(p.get("championName", "")),
            item_ids=[
                str(item["itemID"]) for item in p.get("items", [])
                if _is_main_inventory_item(item)
            ],
            kills=max(0, int((p.get("scores") or {}).get("kills") or 0)),
            deaths=max(0, int((p.get("scores") or {}).get("deaths") or 0)),
        )
        for p in opponents if p.get("championName")
    ]
    allies = [
        _normalize_champion_name(p.get("championName", ""))
        for p in all_players
        if our_team is not None and p.get("team") == our_team
        and p.get("championName")
        and p is not active_player
    ]

    spells_raw = active_player.get("summonerSpells") if active_player else None
    summoner_spells = [
        str(spell.get("displayName"))
        for spell in (spells_raw.values() if isinstance(spells_raw, dict) else ())
        if isinstance(spell, dict) and spell.get("displayName")
    ]
    resource = raw_stats.get("resourceType") if isinstance(raw_stats, dict) else None

    return GameSnapshot(
        summoner_spells=summoner_spells,
        resource_type=str(resource) if isinstance(resource, str) and resource else None,
        game_id=game_id,
        phase=phase,
        champion_id=champion_id,
        augment_choices=[],
        chosen_augments=[],
        purchased_items=items,
        current_gold=gold,
        game_time=game_time,
        enemy_champion_ids=enemies,
        level=level,
        is_dead=is_dead,
        health_pct=health_pct,
        champion_stats=champion_stats,
        ally_champion_ids=allies,
        enemy_states=enemy_states,
        anvil_vouchers=anvil_vouchers,
    )
