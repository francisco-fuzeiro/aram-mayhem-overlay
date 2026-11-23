"""Offline ARAM (queue 450) damage prior from Riot match-v5 (owner decision 23/11).

Key only from RIOT_API_KEY; only per-champion aggregates are stored locally
(no PUUIDs, names or match ids); rate limits respected.
"""
import json

import pytest

from backend.tierdb import riot_prior
from backend.tierdb.impact import ImpactConfig, augment_impact


def _match(mid, champs, dur=1200, version="16.23.1.1", queue=450):
    return {"metadata": {"matchId": mid, "participants": [f"p-{mid}-{i}" for i in range(10)]},
            "info": {"queueId": queue, "gameDuration": dur, "gameVersion": version,
                     "participants": [
                         {"puuid": f"p-{mid}-{i}", "riotIdGameName": f"Name{i}",
                          "championName": c, "totalDamageDealtToChampions": 20000 + 1000 * i,
                          "totalHealsOnTeammates": 100, "totalDamageShieldedOnTeammates": 50}
                         for i, c in enumerate(champs)]}}


def test_aggregate_keeps_only_champion_stats():
    agg = riot_prior.Aggregates()
    agg.add_match(_match("EUW1_1", ["Jinx"] * 5 + ["MonkeyKing"] * 5))
    agg.add_match(_match("EUW1_1", ["Jinx"] * 10))            # duplicate: ignored
    agg.add_match(_match("EUW1_2", ["Jinx"] * 10, dur=200))   # remake: ignored
    agg.add_match(_match("EUW1_3", ["Jinx"] * 10, queue=420))  # not ARAM: ignored
    data = agg.to_json()
    text = json.dumps(data)
    for secret in ("p-EUW1", "Name", "EUW1_1"):
        assert secret not in text
    jinx = data["champions"]["16.23"]["jinx"]
    assert jinx["n"] == 5 and data["matches"] == 1
    assert jinx["dmg_per_min_mean"] == pytest.approx((20000 + 1000 * 2) / 20)
    assert jinx["heal_shield_per_min_mean"] == pytest.approx(150 / 20)
    assert "monkeyking" in data["champions"]["16.23"]


def test_key_only_from_environment(monkeypatch):
    monkeypatch.delenv("RIOT_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        riot_prior.api_key_from_env()
    monkeypatch.setenv("RIOT_API_KEY", "RGAPI-test")
    assert riot_prior.api_key_from_env() == "RGAPI-test"


class _Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}

    def json(self):
        return self._body


def test_client_backs_off_on_429_and_never_puts_key_in_url():
    calls, sleeps = [], []
    responses = [_Resp(429, headers={"Retry-After": "2"}), _Resp(200, {"ok": 1})]

    def fake_get(url, headers, timeout):
        calls.append((url, headers))
        return responses.pop(0)

    client = riot_prior.RiotClient("RGAPI-secret", get=fake_get, sleep=sleeps.append,
                                   min_interval=0)
    assert client.get_json("https://europe.api.riotgames.com/x") == {"ok": 1}
    assert sleeps and sleeps[0] >= 2
    assert all("RGAPI-secret" not in url for url, _ in calls)
    assert calls[0][1]["X-Riot-Token"] == "RGAPI-secret"


def test_prior_sets_baseline_for_champion_without_local_games():
    # Local history has too few games of this champion for its own baseline;
    # the scaled 450 prior lets its augments still be compared.
    rows = [{"champion_id": "jinx", "augments": [a], "duration": 1200,
             "damage_to_champions": d, "heal_shield": 0, "heal_total": 0, "win": 1}
            for a, d in [("a", 20000)] * 3 + [("b", 30000)] * 3]
    cfg = ImpactConfig(min_games=3)
    assert augment_impact(rows, config=cfg) == {}
    prior = {"jinx": {"n": 500, "dmg_per_min_mean": 1250.0, "dmg_per_min_sd": 250.0,
                      "heal_shield_per_min_mean": 0.0, "heal_shield_per_min_sd": 0.0}}
    out = augment_impact(rows, config=cfg, prior=prior)
    assert out[("jinx", "b")]["impact"] > out[("jinx", "a")]["impact"]
