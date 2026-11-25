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


@pytest.mark.parametrize("content", [
    'RIOT_API_KEY: "RGAPI-abc-123"\n', "RIOT_API_KEY=RGAPI-abc-123\n",
    "  RIOT_API_KEY = 'RGAPI-abc-123'  \n", "OTHER=1\nRGAPI-abc-123\n",
    "export RIOT_API_KEY=RGAPI-abc-123\n"])
def test_key_from_local_env_file_formats(tmp_path, monkeypatch, content):
    monkeypatch.delenv("RIOT_API_KEY", raising=False)
    f = tmp_path / ".env"
    f.write_text(content)
    monkeypatch.setenv("RIOT_ENV_FILE", str(f))
    assert riot_prior.api_key_from_env() == "RGAPI-abc-123"


def test_key_file_missing_or_empty_gives_clear_error(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("RIOT_API_KEY", raising=False)
    monkeypatch.setenv("RIOT_ENV_FILE", str(tmp_path / "missing.env"))
    with pytest.raises(SystemExit, match="RIOT_ENV_FILE"):
        riot_prior.api_key_from_env()
    (tmp_path / "e.env").write_text("\n")
    monkeypatch.setenv("RIOT_ENV_FILE", str(tmp_path / "e.env"))
    with pytest.raises(SystemExit, match="no RIOT_API_KEY"):
        riot_prior.api_key_from_env()


def test_key_only_from_environment(monkeypatch):
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


def test_collect_snowballs_saves_aggregates_only(tmp_path, monkeypatch):
    from scripts import collect_aram_damage_prior as col
    monkeypatch.setattr(riot_prior, "PRIOR_FILE", tmp_path / "agg.json")
    monkeypatch.setattr(riot_prior, "SEEN_FILE", tmp_path / "seen.txt")

    class Fake:
        requests = 0

        def get_json(self, url):
            self.requests += 1
            if "/league/v4/" in url:
                return [{"puuid": "seed-puuid", "summonerName": "Seed"}]
            if "/ids?" in url:
                return ["EUW1_9", "EUW1_8"]
            mid = url.rsplit("/", 1)[-1]
            return _match(mid, ["Lux"] * 10)

    agg = riot_prior.Aggregates()
    agg.save = lambda: riot_prior.Aggregates.save(agg, tmp_path / "agg.json",
                                                   tmp_path / "seen.txt")
    out = col.collect(Fake(), "euw1", 2, agg)
    assert out["new_matches"] == 2
    text = (tmp_path / "agg.json").read_text() + (tmp_path / "seen.txt").read_text()
    for secret in ("puuid", "Seed", "EUW1_9", "Name"):
        assert secret not in text
    again = riot_prior.Aggregates.load(tmp_path / "agg.json", tmp_path / "seen.txt")
    assert again.seen("EUW1_9") and again.matches == 2
    assert riot_prior.load_prior(tmp_path / "agg.json")["lux"]["n"] == 20


def test_probe_reports_statuses_and_stores_nothing():
    from scripts import collect_aram_damage_prior as col

    class Fake:
        requests = 0

        def get_json(self, url):
            if "/league/v4/" in url:
                return [{"puuid": "zz-secret"}]
            if "queue=450" in url:
                return ["EUW1_5"]
            return None

        def request(self, url):
            if "queue=2400" in url:
                return 200, []
            return 200, _match("EUW1_5", ["Lux"] * 10)

    out = col.probe(Fake(), "euw1")
    assert out["aram450"]["has_damage"] and out["aram450"]["has_heal_shield"]
    assert out["mayhem2400"] == {"ids_status": 200, "ids_listed": 0}
    assert "zz-secret" not in str(out) and "EUW1_5" not in str(out)


def test_client_returns_403_status_without_raising_on_request():
    client = riot_prior.RiotClient("k", get=lambda u, headers, timeout: _Resp(403),
                                   sleep=lambda s: None, min_interval=0)
    assert client.request("https://x")[0] == 403
    with pytest.raises(SystemExit):
        client.get_json("https://x")
