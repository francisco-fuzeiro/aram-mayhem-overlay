from pathlib import Path
from dataclasses import dataclass
import os
import subprocess
import sys
import requests


def _find_lockfile() -> Path | None:
    """Find the local League lockfile without assuming the install drive.

    Windows discovery adapted from zp96-cmd/mayhem-overlay's MIT-declared
    src/main/lcu.js (Copyright 2026 Zac Pitts; see THIRD_PARTY_NOTICES.md).
    No client secrets are logged or transmitted.
    """
    candidates = [
        Path(os.environ["ARAM_ORACLE_LCU_LOCKFILE"])
        if os.environ.get("ARAM_ORACLE_LCU_LOCKFILE") else None,
        Path("C:/Riot Games/League of Legends/lockfile"),
        Path("D:/Riot Games/League of Legends/lockfile"),
        Path("C:/Program Files/Riot Games/League of Legends/lockfile"),
        Path.home() / "Library/Application Support/Riot Games/League of Legends/lockfile",
    ]
    for path in candidates:
        if path is not None and path.is_file():
            return path

    # LeagueClientUx.exe may run from a custom location (E:, another folder).
    # Use a fixed PowerShell command (never interpolate user input).
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                [
                    "powershell", "-NoProfile", "-NonInteractive", "-Command",
                    "(Get-Process LeagueClientUx -ErrorAction SilentlyContinue "
                    "| Select-Object -First 1 -ExpandProperty Path)",
                ],
                capture_output=True, text=True, timeout=3,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            executable = result.stdout.strip().splitlines()
            if executable:
                candidate = Path(executable[0]).parent / "lockfile"
                if candidate.is_file():
                    return candidate
        except (OSError, subprocess.SubprocessError):
            pass
    return None

def _parse_lockfile(path: Path) -> dict:
    parts = path.read_text().strip().split(":")
    return {
        "process": parts[0],
        "pid": parts[1],
        "port": parts[2],
        "password": parts[3],
        "protocol": parts[4],
    }


def get_lcu_session() -> requests.Session | None:
    """Returns an authenticated requests.Session for the LCU or None if client not running."""
    lockfile = _find_lockfile()
    if not lockfile:
        return None
    try:
        info = _parse_lockfile(lockfile)
    except (OSError, ValueError, IndexError):
        return None
    session = requests.Session()
    session.verify = False
    session.auth = ("riot", info["password"])
    session.base_url = f"https://127.0.0.1:{info['port']}"
    return session


def get_champ_select_session(lcu: requests.Session) -> dict | None:
    """Returns current champ select session data or None if not in champ select."""
    try:
        r = lcu.get(f"{lcu.base_url}/lol-champ-select/v1/session", timeout=1)
        return r.json() if r.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None


def parse_bench_champions(session_data: dict) -> list[str]:
    """Extract bench champion IDs available for swapping."""
    return [
        str(c.get("championId"))
        for c in session_data.get("benchChampions", [])
    ]


def parse_team_champions(session_data: dict) -> list[str]:
    """Extract the 5 champion IDs on the local team."""
    return [
        str(a.get("championId"))
        for a in session_data.get("myTeam", [])
        if a.get("championId", 0) != 0
    ]


def get_champion_id_map(lcu: requests.Session) -> dict[str, str]:
    """Map numeric champion IDs to Data Dragon aliases (lowercase).

    /lol-game-data/assets/v1/champion-summary.json is a read-only client asset.
    Names are not suitable as IDs because some differ from their aliases.
    """
    try:
        response = lcu.get(
            f"{lcu.base_url}/lol-game-data/assets/v1/champion-summary.json",
            timeout=2,
        )
        if response.status_code != 200:
            return {}
        payload = response.json()
        if not isinstance(payload, list):
            return {}
        return {
            str(champ["id"]): champ["alias"].lower()
            for champ in payload
            if isinstance(champ, dict)
            and isinstance(champ.get("id"), int)
            and isinstance(champ.get("alias"), str)
            and champ["id"] > 0
        }
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return {}


def read_champ_select() -> tuple[dict, dict[str, str]] | None:
    """Read already visible data from the user's current League client.

    Returns None outside champion select. Lockfile credentials and raw
    client session data are never sent to the frontend.
    """
    lcu = get_lcu_session()
    if lcu is None:
        return None
    try:
        with lcu:
            draft = get_champ_select_session(lcu)
            if draft is None:
                return None
            return draft, get_champion_id_map(lcu)
    except requests.RequestException:
        return None


@dataclass(frozen=True)
class GameflowSnapshot:
    """Only read-only phase and match ID, never LCU credentials or raw session."""

    phase: str
    game_id: str | None = None


def read_gameflow() -> GameflowSnapshot | None:
    """Read documented local Gameflow fields; no write requests or inference."""
    session = get_lcu_session()
    if session is None:
        return None
    try:
        with session:
            response = session.get(
                f"{session.base_url}/lol-gameflow/v1/gameflow-phase", timeout=1,
            )
            if response.status_code != 200:
                return None
            phase = response.json()
            if not isinstance(phase, str):
                return None
            game_id = None
            if phase in ("GameStart", "InProgress", "Reconnect", "PreEndOfGame",
                         "WaitingForStats", "EndOfGame"):
                detail = session.get(
                    f"{session.base_url}/lol-gameflow/v1/session", timeout=1,
                )
                if detail.status_code == 200:
                    payload = detail.json()
                    if isinstance(payload, dict):
                        raw_id = payload.get("gameId")
                        if raw_id is None and isinstance(payload.get("gameData"), dict):
                            raw_id = payload["gameData"].get("gameId")
                        if isinstance(raw_id, (int, str)) and str(raw_id).strip() not in ("", "0", "unknown"):
                            game_id = str(raw_id)
            return GameflowSnapshot(phase=phase, game_id=game_id)
    except (requests.RequestException, ValueError, OSError, TypeError):
        return None
