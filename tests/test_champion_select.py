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
    assert all(isinstance(c["score"], float) and 0.0 <= c["score"] <= 10.0 for c in result["candidates"])
    assert all(round(c["score"], 1) == c["score"] for c in result["candidates"])
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
    assert response["method"] == "composite_v1"


def test_role_fit_tiers_use_ten_point_scale():
    draft = {
        "localPlayerCellId": 1,
        "myTeam": [
            {"cellId": 1, "championId": 99},
            {"cellId": 2, "championId": 222},
        ],
        "benchChampions": [{"championId": 12}],
    }
    result = summarize_champion_select(draft, IDS, get_champion)
    for candidate in result["candidates"]:
        score = candidate["score"]
        tier = candidate["tier"]
        assert 0 <= score <= 10
        expected = "S" if score >= 7.5 else "A" if score >= 7.0 else "B" if score >= 6.5 else "C"
        assert tier == expected
    assert "0.0" in result["notice"] and "10.0" in result["notice"]


def test_champion_composite_uses_personal_record_when_available():
    draft = {
        "localPlayerCellId": 1,
        "myTeam": [
            {"cellId": 1, "championId": 99},
            {"cellId": 2, "championId": 222},
        ],
        "benchChampions": [{"championId": 12}],
    }
    no_history = summarize_champion_select(draft, IDS, get_champion)
    with_history = summarize_champion_select(
        draft, IDS, get_champion,
        record_lookup=lambda champ: (80, 100) if champ == "lux" else None,
    )
    before = next(c for c in no_history["candidates"] if c["name"] == "Lux")
    after = next(c for c in with_history["candidates"] if c["name"] == "Lux")
    assert after["score"] > before["score"]
    assert after["confidence"] > 0
    assert after["sample_size"] == 100
    assert after["evidence_source"] == "personal_history"
    assert before["sample_size"] == 0
    assert before["components"]["performance"] is None


def test_champion_composite_depends_on_team_even_with_same_win_evidence():
    roster = {"benchChampions": [{"championId": 99}]}
    one = dict(roster, myTeam=[{"championId": 222}])  # No mage yet
    two = dict(roster, myTeam=[{"championId": 99}])  # Already has a mage
    lookup = lambda _: (70, 100)
    rating_a = summarize_champion_select(one, IDS, get_champion, record_lookup=lookup)
    rating_b = summarize_champion_select(two, IDS, get_champion, record_lookup=lookup)
    assert rating_a["method"] == "composite_v1"
    assert rating_b["method"] == "composite_v1"
    assert rating_a["candidates"][0]["score"] != rating_b["candidates"][0]["score"]
    assert rating_a["candidates"][0]["sample_size"] == 100
    assert rating_b["candidates"][0]["sample_size"] == 100


# F1.1 RED: the F0 diagnostic correctly rejects these drafts, but the
# production candidate builder must also abstain, not choose the last row.
def test_f1_duplicate_local_cell_fails_closed_without_losing_bench():
    draft = {
        "localPlayerCellId": 4,
        "myTeam": [
            {"cellId": 4, "championId": 99},
            {"cellId": 4, "championId": 222},
        ],
        "benchChampions": [{"championId": 12}],
    }
    result = summarize_champion_select(draft, IDS, get_champion)
    assert result["current_status"] == "unresolved"
    assert result["current_champion_id"] is None
    assert not any(row["current"] for row in result["candidates"])
    assert "Alistar" in {row["name"] for row in result["candidates"]}


def test_f1_unknown_or_unmapped_local_champion_abstains_but_keeps_bench():
    base = {"localPlayerCellId": 4,
            "myTeam": [{"cellId": 4, "championId": 99}],
            "benchChampions": [{"championId": 222}]}
    for draft, aliases in [
        ({**base, "localPlayerCellId": None}, IDS),
        ({**base, "localPlayerCellId": 8}, IDS),
        ({**base, "localPlayerCellId": True}, IDS),
        ({**base, "localPlayerCellId": "4"}, IDS),
        ({**base, "myTeam": [{"cellId": 4, "championId": 0}]}, IDS),
        ({**base, "myTeam": [{"cellId": 4, "championId": 9876}]}, IDS),
        (base, {}),
    ]:
        result = summarize_champion_select(draft, aliases, get_champion)
        assert result["current_status"] == "unresolved"
        assert result["current_champion_id"] is None
        assert not any(row["current"] for row in result["candidates"])
    assert "Jinx" in {r["name"] for r in summarize_champion_select(
        {**base, "localPlayerCellId": None}, IDS, get_champion
    )["candidates"]}


def test_f1_swap_updates_local_identity_without_ranking_as_identity():
    base = {"localPlayerCellId": 4,
            "myTeam": [{"cellId": 4, "championId": 99}],
            "benchChampions": [{"championId": 222}, {"championId": 12}]}
    first = summarize_champion_select(base, IDS, get_champion)
    swapped = summarize_champion_select(
        {**base, "myTeam": [{"cellId": 4, "championId": 222}],
         "benchChampions": [{"championId": 99}, {"championId": 12}]},
        IDS, get_champion)
    assert first["current_status"] == "confirmed"
    assert first["current_champion_id"] == "lux"
    assert swapped["current_status"] == "confirmed"
    assert swapped["current_champion_id"] == "jinx"
    assert [c["id"] for c in first["candidates"] if c["current"]] == ["lux"]
    assert [c["id"] for c in swapped["candidates"] if c["current"]] == ["jinx"]


def test_f1_catalog_lookup_failure_does_not_claim_current():
    draft = {"localPlayerCellId": 4,
             "myTeam": [{"cellId": 4, "championId": 99}],
             "benchChampions": [{"championId": 222}]}
    result = summarize_champion_select(
        draft, IDS, lambda alias: None if alias == "lux" else get_champion(alias))
    assert result["current_status"] == "unresolved"
    assert result["current_champion_id"] is None
    assert not any(row["current"] for row in result["candidates"])
    assert [r["name"] for r in result["candidates"]] == ["Jinx"]


def test_f1_ambiguous_self_rows_must_not_be_scored_as_confirmed_allies():
    # Both entries have our local cell. They cannot simultaneously be
    # confirmed teammates. Keeping the bench is independent of this fact.
    draft = {
        "localPlayerCellId": 4,
        "myTeam": [
            {"cellId": 4, "championId": 99},
            {"cellId": 4, "championId": 222},
        ],
        "benchChampions": [{"championId": 99}, {"championId": 12}],
    }
    empty_team = {**draft, "myTeam": []}
    actual = summarize_champion_select(draft, IDS, get_champion)
    reference = summarize_champion_select(empty_team, IDS, get_champion)
    assert actual["current_status"] == "unresolved"
    assert not any(row["current"] for row in actual["candidates"])
    assert {c["id"]: c["score"] for c in actual["candidates"]} == {
        c["id"]: c["score"] for c in reference["candidates"]
    }
