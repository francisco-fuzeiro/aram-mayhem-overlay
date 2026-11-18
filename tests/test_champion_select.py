"""Champion-select read-only payload tests (no live League client needed)."""
from unittest.mock import patch

from backend.collectors import lcu
from backend.engine.champion_select import summarize_champion_select
from backend.models import ChampionMeta, StatVector


CHAMPIONS = {
    "lux": ChampionMeta("lux", "Lux", StatVector(ap=0.9, cdr=0.8), role="mage"),
    "jinx": ChampionMeta("jinx", "Jinx", StatVector(ad=0.9, crit=0.9), role="marksman"),
    "alistar": ChampionMeta("alistar", "Alistar", StatVector(hp=0.9, hard_cc=0.8), role="tank"),
}
IDS = {"99": "lux", "222": "jinx", "12": "alistar"}


def get_champion(alias):
    return CHAMPIONS.get(alias)


def test_reads_bench_and_current_champion_without_player_identifiers():
    draft = {
        "localPlayerCellId": 1,
        "myTeam": [
            {"cellId": 1, "championId": 99, "summonerId": 12345, "name": "private"},
            {"cellId": 2, "championId": 222, "summonerId": 67890},
        ],
        "benchChampions": [{"championId": 12}, {"championId": 12}, {"championId": 0}],
    }
    result = summarize_champion_select(draft, IDS, get_champion)
    assert result["type"] == "champ_select"
    assert {x["name"] for x in result["candidates"]} == {"Lux", "Alistar"}
    assert next(x for x in result["candidates"] if x["name"] == "Lux")["current"]
    assert next(x for x in result["candidates"] if x["name"] == "Alistar")["score"] > \
        next(x for x in result["candidates"] if x["name"] == "Lux")["score"]
    assert "private" not in str(result)
    assert "12345" not in str(result)
    assert "win rate" not in str(result).lower() or "not" in str(result).lower()


def test_missing_champion_catalog_is_explicit_not_fabricated():
    draft = {"benchChampions": [{"championId": 99}, {"championId": 9876}]}
    result = summarize_champion_select(draft, IDS, get_champion)
    assert len(result["candidates"]) == 1
    assert result["skipped_ids"] == ["9876"]


def test_draft_with_no_champions_returns_empty_choices():
    assert summarize_champion_select({}, IDS, get_champion)["candidates"] == []
    assert summarize_champion_select(None, IDS, get_champion)["error"] == "invalid_draft"


def test_numeric_champion_ids_are_mapped_via_read_only_client_assets():
    class FakeResponse:
        status_code = 200

        def json(self):
            return [
                {"id": 99, "alias": "Lux", "name": "Lux"},
                {"id": 222, "alias": "Jinx", "name": "Jinx"},
                {"id": 0, "alias": "none"},
                {"id": 123, "name": "missing alias"},
            ]

    class FakeSession:
        base_url = "https://127.0.0.1:12345"

        def get(self, url, timeout):
            assert url.endswith("/lol-game-data/assets/v1/champion-summary.json")
            assert timeout == 2
            return FakeResponse()

    assert lcu.get_champion_id_map(FakeSession()) == {"99": "lux", "222": "jinx"}


def test_api_debug_endpoint_reports_unavailable_without_lcu(monkeypatch):
    from backend.api import server
    monkeypatch.setattr(server, "read_champ_select", lambda: None)
    assert server.champ_select_status()["type"] == "champ_select_unavailable"


def test_api_debug_endpoint_uses_team_fit(monkeypatch):
    from backend.api import server
    monkeypatch.setattr(server, "read_champ_select",
                        lambda: ({"benchChampions": [{"championId": 99}]}, IDS))
    with patch.object(server.static_data, "get_champion", side_effect=get_champion):
        response = server.champ_select_status()
    assert response["candidates"][0]["name"] == "Lux"
    assert response["method"] == "experimental_team_fit"
