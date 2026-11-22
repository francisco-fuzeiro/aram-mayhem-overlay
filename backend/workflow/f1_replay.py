"""Synthetic LCU → production API → polling WebSocket payload replay for F1.

No League, accounts, network or user fixtures are read. Output is safe to
feed into the genuine frontend DOM/WebSocket harness.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

from backend.api import server
from backend.models import ChampionMeta, StatVector


async def run_synthetic_replay() -> list[dict]:
    champions = {
        "fixture_self": ChampionMeta("fixture_self", "Synthetic Self",
                                     StatVector(ad=0.8), role="marksman"),
        "fixture_bench": ChampionMeta("fixture_bench", "Synthetic Bench",
                                      StatVector(ap=0.9), role="mage"),
    }
    aliases = {"222": "fixture_self", "99": "fixture_bench"}
    drafts = [
        {"localPlayerCellId": 9,
         "myTeam": [{"cellId": 9, "championId": 222}],
         "benchChampions": [{"championId": 99}]},
        {"localPlayerCellId": 9,
         "myTeam": [{"cellId": 9, "championId": 99}],
         "benchChampions": [{"championId": 222}]},
        {"localPlayerCellId": 9,
         "myTeam": [{"cellId": 9, "championId": 99},
                    {"cellId": 9, "championId": 222}],
         "benchChampions": [{"championId": 99}, {"championId": 222}]},
        None,
    ]
    state = server.GameState()
    state.ws_clients.add(object())  # production poll checks for subscribers
    seen = []

    async def threaded(fn):
        return fn()

    async def broadcast(payload):
        message = json.loads(payload)
        if message.get("type") == "champ_select":
            seen.append(message)

    deps = SimpleNamespace(
        get_raw_game_data=lambda: None,
        read_gameflow=lambda: SimpleNamespace(phase="ChampSelect"),
        read_champ_select_payload=server._read_champ_select_payload,
        to_thread=threaded, broadcast=broadcast,
    )
    with (patch.object(server.static_data, "get_champion",
                       side_effect=champions.get),
          patch.object(server, "get_champion_record", return_value=None)):
        for draft in drafts:
            with patch.object(server, "read_champ_select",
                              return_value=(draft, aliases) if draft is not None else None):
                await server.poll_tick(state, deps, float(len(seen) + 1))
    return seen


if __name__ == "__main__":
    print(json.dumps({"kind": "synthetic_f1_lcu_backend_ws",
                      "packets": asyncio.run(run_synthetic_replay())},
                     sort_keys=True, separators=(",", ":")))
