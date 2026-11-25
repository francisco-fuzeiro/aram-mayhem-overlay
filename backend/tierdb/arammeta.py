"""Local per-patch snapshot of AramMeta aggregates (evaluation only).

Permission (Lanternko/arammeta issue #61, 25/11): the published aggregates may
be ONE input to our tiers in this non-commercial project, with "Data: AramMeta"
attribution wherever data-backed tiers show, no republishing of the tables, and
only a few requests per patch. Owner decision 25/11: step 1 only, a local
snapshot per patch (tier list once + one file per champion actually played);
it does not feed the tiers until a holdout on the next patch says it helps.

Nothing here is written to the repository; files live under
``~/.aram-oracle/arammeta/<patch>/``.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

BASE = "https://arammeta.com/api"
SNAPSHOT_DIR = Path.home() / ".aram-oracle" / "arammeta"
USER_AGENT = "mayhem-overlay"
CHECK_EVERY_S = 24 * 3600   # tier list: at most one request per day
MIN_GAP_S = 1.0             # between our own requests

_lock = threading.Lock()
_last_request = [0.0]
_tried: set[tuple[str, str]] = set()


def _default_fetch(url: str) -> bytes:
    import requests
    response = requests.get(url, timeout=(10, 30), headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.content


def _get(url: str, fetch) -> bytes:
    wait = MIN_GAP_S - (time.monotonic() - _last_request[0])
    if wait > 0:
        time.sleep(wait)
    _last_request[0] = time.monotonic()
    return fetch(url)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)


def _state_file(root: Path) -> Path:
    return root / "state.json"


def _read_state(root: Path) -> dict:
    try:
        return json.loads(_state_file(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def current_patch(root: Path | None = None) -> str | None:
    return _read_state(root or SNAPSHOT_DIR).get("patch")


def refresh_tier_list(*, root: Path | None = None, fetch=None,
                      now: float | None = None) -> str | None:
    """Fetch tier-list.json at most once a day; keep one copy per patch."""
    root = root or SNAPSHOT_DIR
    fetch = fetch or _default_fetch
    now = time.time() if now is None else now
    with _lock:
        state = _read_state(root)
        if now - float(state.get("checked_at") or 0) < CHECK_EVERY_S and state.get("patch"):
            return state["patch"]
        data = _get(f"{BASE}/tier-list.json", fetch)
        doc = json.loads(data.decode("utf-8"))
        patch = str(doc.get("patch_prefix") or "").strip()
        if not patch or "/" in patch or ".." in patch:
            raise ValueError("AramMeta tier list without a usable patch_prefix")
        target = root / patch / "tier-list.json"
        if not target.exists():
            _write(target, data)
        keys = {str(c.get("alias") or "").lower(): str(k)
                for k, c in (doc.get("champs") or {}).items() if isinstance(c, dict)}
        _write(_state_file(root), json.dumps(
            {"patch": patch, "checked_at": now, "champion_keys": keys}).encode("utf-8"))
        return patch


def ensure_champion(champion_id: str, *, root: Path | None = None, fetch=None) -> bool:
    """One request per champion per patch; True when the file is stored."""
    root = root or SNAPSHOT_DIR
    fetch = fetch or _default_fetch
    with _lock:
        state = _read_state(root)
        patch = state.get("patch")
        key = (state.get("champion_keys") or {}).get(str(champion_id).lower())
        if not patch or not key or not key.isdigit():
            return False
        target = root / patch / "champions" / f"{key}.json"
        if target.exists():
            return True
        if (patch, key) in _tried:      # a failure is not retried this session
            return False
        _tried.add((patch, key))
        data = _get(f"{BASE}/champions/{key}.json", fetch)
        json.loads(data.decode("utf-8"))  # store only valid JSON
        _write(target, data)
        return True


def snapshot_in_background(champion_id: str | None = None) -> None:
    """Best effort, never blocks the overlay or raises."""
    def work():
        try:
            refresh_tier_list()
            if champion_id:
                ensure_champion(champion_id)
        except Exception as exc:  # network, schema change, disk
            logger.info("AramMeta snapshot skipped: %s", type(exc).__name__)
    threading.Thread(target=work, name="arammeta-snapshot", daemon=True).start()
