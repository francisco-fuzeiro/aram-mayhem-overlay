from dataclasses import dataclass
import requests
import urllib3
from backend.diagnostic_events import events as event_log
from backend.models import GameSnapshot, GamePhase, EnemyState

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


@dataclass(frozen=True)
class LCDAResult:
    """Sanitized LCDA read result; payload exists only for valid JSON objects."""
    status: str
    payload: dict | None = None


def get_raw_game_data() -> LCDAResult:
    """Fetch LCDA synchronously; caller must run this in a worker thread."""
    try:
        response = SESSION.get(f"{LCDA_BASE}/allgamedata", timeout=1)
        if response.status_code != 200:
            status = "http_404" if response.status_code == 404 else "http_error"
            event_log.transition("lcda", status=status, error_class=status)
            return LCDAResult(status)
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("LCDA response is not an object")
        event_log.transition("lcda", status="ok", error_class="none")
        return LCDAResult("ok", payload)
    except requests.Timeout:
        status = "timeout"
    except requests.ConnectionError as exc:
        status = "refused" if "refused" in str(exc).lower() else "connection_error"
    except requests.RequestException:
        status = "request_error"
    except (ValueError, TypeError):
        status = "bad_json"
    except Exception:
        # Unknown failure class; never retain or print payloads or credentials.
        status = "internal_error"
    event_log.transition("lcda", status=status, error_class=status)
    return LCDAResult(status)


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

    active_name = active.get("summonerName", "")
    active_player = next(
        (p for p in all_players if p.get("summonerName") == active_name), {}
    )

    items = [
        str(item["itemID"]) for item in active_player.get("items", [])
        if _is_main_inventory_item(item)
    ]
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

    return GameSnapshot(
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
    )
