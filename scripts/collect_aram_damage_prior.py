"""Collect a per-champion damage prior from normal ARAM (queue 450), offline.

Owner decision 23/11. Run in a terminal, never from the overlay:

    PowerShell:  $env:RIOT_API_KEY = "RGAPI-..."   (this terminal only)
                 py -3.11 -m scripts.collect_aram_damage_prior --platform euw1 --matches 300

Seeds are players from public ranked ladders (league-v4); their recent ARAM
match ids come from match-v5 and each match adds its players to an in-memory
queue. PUUIDs live only in memory for this run. Only per-champion aggregates are
written, to ~/.aram-oracle/riot_prior/ (outside the repo). Re-running resumes
and never counts a match twice. Prints counts only.
"""
from __future__ import annotations

import argparse
import random
from collections import deque

from backend.tierdb.riot_prior import (
    ARAM_QUEUE, PRIOR_FILE, REGION, Aggregates, RiotClient, api_key_from_env,
)

SEED_TIERS = (("GOLD", "I"), ("PLATINUM", "II"), ("EMERALD", "III"), ("DIAMOND", "IV"),
              ("SILVER", "I"))


def collect(client: RiotClient, platform: str, target: int, agg: Aggregates,
            save_every: int = 25, max_players: int = 5000) -> dict:
    region = REGION[platform]
    queue: deque[str] = deque()
    queued: set[str] = set()
    for tier, div in SEED_TIERS:
        entries = client.get_json(f"https://{platform}.api.riotgames.com/lol/league/v4/"
                                  f"entries/RANKED_SOLO_5x5/{tier}/{div}?page=1") or []
        sample = [e.get("puuid") for e in entries if isinstance(e, dict) and e.get("puuid")]
        random.shuffle(sample)
        for p in sample[:20]:
            if p not in queued:
                queued.add(p); queue.append(p)
    added = players = 0
    while queue and added < target:
        puuid = queue.popleft()
        players += 1
        ids = client.get_json(f"https://{region}.api.riotgames.com/lol/match/v5/matches/"
                              f"by-puuid/{puuid}/ids?queue={ARAM_QUEUE}&count=20") or []
        for mid in ids:
            if added >= target:
                break
            if not isinstance(mid, str) or agg.seen(mid):
                continue
            match = client.get_json(f"https://{region}.api.riotgames.com/lol/match/v5/"
                                    f"matches/{mid}")
            if not match or not agg.add_match(match):
                continue
            added += 1
            for p in (match.get("metadata") or {}).get("participants") or []:
                if len(queued) < max_players and p not in queued:
                    queued.add(p); queue.append(p)
            if added % save_every == 0:
                agg.save()
                print(f"  {added}/{target} matches, {client.requests} requests")
    agg.save()
    champs = len({c for p in agg.to_json()["champions"].values() for c in p})
    return {"new_matches": added, "total_matches": agg.matches, "champions": champs,
            "players_visited": players, "requests": client.requests}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--platform", default="euw1", choices=sorted(REGION))
    parser.add_argument("--matches", type=int, default=300)
    args = parser.parse_args()
    client = RiotClient(api_key_from_env())
    result = collect(client, args.platform, max(1, args.matches), Aggregates.load())
    print(result)
    print(f"Saved locally: {PRIOR_FILE}")


if __name__ == "__main__":
    main()
