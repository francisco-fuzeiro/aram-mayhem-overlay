"""Offline per-champion damage prior from normal ARAM (queue 450) via Riot match-v5.

Owner decision 23/11. Mayhem (2400) is blocked on match-v5, normal ARAM is not.
Run only from scripts/collect_aram_damage_prior.py, never inside the overlay.
The key is read only from the RIOT_API_KEY environment variable and sent only as
the X-Riot-Token header. Only per-champion aggregates (damage to champions/min,
heal+shield on teammates/min, n, patch) are stored, locally; no PUUIDs, names or
match ids (resume uses salted hashes in a separate local file). Not to be
published in the repo until Riot's policy for it is confirmed.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import time
from pathlib import Path

ARAM_QUEUE = 450
MIN_SECS = 300
PRIOR_DIR = Path.home() / ".aram-oracle" / "riot_prior"
PRIOR_FILE = PRIOR_DIR / "aram450_champion_aggregates.json"
SEEN_FILE = PRIOR_DIR / "seen_hashes.txt"

REGION = {
    "euw1": "europe", "eun1": "europe", "tr1": "europe", "ru": "europe", "me1": "europe",
    "na1": "americas", "br1": "americas", "la1": "americas", "la2": "americas",
    "kr": "asia", "jp1": "asia",
    "oc1": "sea", "ph2": "sea", "sg2": "sea", "th2": "sea", "tw2": "sea", "vn2": "sea",
}


def api_key_from_env() -> str:
    key = os.environ.get("RIOT_API_KEY", "").strip()
    if not key:
        raise SystemExit("Set RIOT_API_KEY in this terminal first (never in a file).")
    return key


class RiotClient:
    """Rate-limited GET with backoff. Dev keys: 20/s and 100/2 min -> 1.25 s spacing."""

    def __init__(self, key: str, *, get=None, sleep=time.sleep, min_interval: float = 1.25,
                 max_tries: int = 6):
        if get is None:
            import requests
            get = requests.get
        self._key, self._get, self._sleep = key, get, sleep
        self._min, self._tries, self._last = min_interval, max_tries, 0.0
        self.requests = 0

    def get_json(self, url: str):
        for attempt in range(self._tries):
            wait = self._min - (time.monotonic() - self._last)
            if wait > 0:
                self._sleep(wait)
            self._last = time.monotonic()
            self.requests += 1
            try:
                resp = self._get(url, headers={"X-Riot-Token": self._key}, timeout=10)
            except Exception:  # network error: back off, never echo the request
                self._sleep(min(60, 2 ** attempt))
                continue
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                try:
                    retry = float(resp.headers.get("Retry-After", 0))
                except (TypeError, ValueError):
                    retry = 0.0
                self._sleep(max(retry, 2 ** attempt))
                continue
            if resp.status_code in (401, 403):
                raise SystemExit("Riot API key rejected or expired (HTTP %d)." % resp.status_code)
            if resp.status_code == 404:
                return None
            self._sleep(min(60, 2 ** attempt))
        return None


def _patch(version: str) -> str | None:
    parts = str(version or "").split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 and all(p.isdigit() for p in parts[:2]) else None


def _num(v) -> float:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


class Aggregates:
    """Running sums per (patch, champion); serialises to aggregates only."""

    def __init__(self, data: dict | None = None, seen: set[str] | None = None,
                 salt: str | None = None):
        self._sums: dict[tuple[str, str], list[float]] = {}
        self.matches = 0
        self._seen = set(seen or ())
        self._salt = salt or secrets.token_hex(16)
        for patch, champs in ((data or {}).get("_sums") or {}).items():
            for champ, s in champs.items():
                self._sums[(patch, champ)] = list(s)
        self.matches = int((data or {}).get("matches") or 0)

    def _hash(self, match_id: str) -> str:
        return hashlib.sha256(f"{self._salt}:{match_id}".encode()).hexdigest()[:16]

    def seen(self, match_id: str) -> bool:
        return self._hash(match_id) in self._seen

    def add_match(self, match: dict) -> bool:
        info = (match or {}).get("info") or {}
        mid = ((match or {}).get("metadata") or {}).get("matchId")
        if not mid or self.seen(mid):
            return False
        self._seen.add(self._hash(mid))
        secs = _num(info.get("gameDuration"))
        patch = _patch(info.get("gameVersion"))
        if info.get("queueId") != ARAM_QUEUE or secs < MIN_SECS or not patch:
            return False
        minutes = secs / 60.0
        for p in info.get("participants") or []:
            champ = str(p.get("championName") or "").lower()
            if not champ:
                continue
            d = _num(p.get("totalDamageDealtToChampions")) / minutes
            h = (_num(p.get("totalHealsOnTeammates"))
                 + _num(p.get("totalDamageShieldedOnTeammates"))) / minutes
            s = self._sums.setdefault((patch, champ), [0.0] * 5)
            s[0] += 1; s[1] += d; s[2] += d * d; s[3] += h; s[4] += h * h
        self.matches += 1
        return True

    def to_json(self) -> dict:
        champions: dict[str, dict] = {}
        sums: dict[str, dict] = {}
        for (patch, champ), (n, sd, sd2, sh, sh2) in sorted(self._sums.items()):
            champions.setdefault(patch, {})[champ] = _stats(n, sd, sd2, sh, sh2)
            sums.setdefault(patch, {})[champ] = [n, sd, sd2, sh, sh2]
        return {"source": "riot match-v5 queue 450 (local aggregates only)",
                "matches": self.matches, "champions": champions, "_sums": sums}

    def save(self, path: Path = PRIOR_FILE, seen_path: Path = SEEN_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=1), encoding="utf-8")
        seen_path.write_text("\n".join([self._salt, *sorted(self._seen)]), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = PRIOR_FILE, seen_path: Path = SEEN_FILE) -> "Aggregates":
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        lines = seen_path.read_text(encoding="utf-8").split("\n") if seen_path.exists() else []
        return cls(data, set(lines[1:]), lines[0] if lines else None)


def _stats(n, s, s2, h, h2) -> dict:
    def sd(total, sq):
        if n < 2:
            return 0.0
        return math.sqrt(max(0.0, (sq - total * total / n) / (n - 1)))
    return {"n": int(n), "dmg_per_min_mean": s / n, "dmg_per_min_sd": sd(s, s2),
            "heal_shield_per_min_mean": h / n, "heal_shield_per_min_sd": sd(h, h2)}


def load_prior(path: Path = PRIOR_FILE, patch: str | None = None) -> dict:
    """{champion: stats} for one patch, or all patches pooled. {} when absent."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    pooled: dict[str, list[float]] = {}
    for p, champs in (data.get("_sums") or {}).items():
        if patch and p != patch:
            continue
        for champ, s in champs.items():
            acc = pooled.setdefault(champ, [0.0] * 5)
            for i in range(5):
                acc[i] += s[i]
    return {c: _stats(*s) for c, s in pooled.items() if s[0] > 0}
