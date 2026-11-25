"""Local match-history parsing and privacy checks without a League client."""
from unittest.mock import Mock

from backend.storage import history_import
from backend.storage.db import get_champion_record, init_db, record_game


def test_extract_augments_in_pick_order():
    stats = {
        "playerAugment3": 333, "playerAugment1": 111,
        "playerAugment2": 0, "playerAugment10": 999,
        "playerAugmentOther": 444,
    }
    assert history_import.extract_augments(stats) == ["111", "333", "999"]


def test_extract_items_ignores_empty_and_invalid_slots():
    stats = {"item0": 1001, "item1": 0, "item2": 3001, "item6": "invalid"}
    assert history_import.extract_items(stats) == ["1001", "3001"]


def test_own_participant_must_match_puuid():
    match = {
        "participantIdentities": [
            {"participantId": 1, "player": {"puuid": "another"}},
            {"participantId": 2, "player": {"puuid": "ours"}},
        ],
        "participants": [
            {"participantId": 1, "championId": 99},
            {"participantId": 2, "championId": 222},
        ],
    }
    assert history_import._own_participant(match, "ours")["championId"] == 222
    assert history_import._own_participant(match, "missing") is None


def test_sync_only_own_mayhem_match_and_never_returns_account_ids(monkeypatch):
    class Session:
        base_url = "https://127.0.0.1:87654"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, timeout):
            endpoint = url.split(self.base_url, 1)[-1]
            data = {
                "/lol-summoner/v1/current-summoner": {
                    "puuid": "super-private-puuid",
                },
                "/lol-match-history/v1/products/lol/current-summoner/matches?begIndex=0&endIndex=20": {
                    "games": {"games": [
                        {"gameId": 77, "queueId": 2400, "gameDuration": 700},
                        {"gameId": 88, "queueId": 450},
                    ]},
                },
                "/lol-match-history/v1/games/77": {
                    "gameDuration": 700,
                    "participantIdentities": [
                        {"participantId": 1, "player": {"puuid": "other"}},
                        {"participantId": 2, "player": {"puuid": "super-private-puuid"}},
                    ],
                    "participants": [
                        {"participantId": 1, "championId": 99, "stats": {"win": False}},
                        {"participantId": 2, "championId": 222, "stats": {
                            "win": True,
                            "playerAugment1": 1234,
                            "item0": 3001,
                            "kills": 5, "deaths": 2, "assists": 9,
                        }},
                    ],
                },
            }
            response = Mock()
            response.status_code = 200 if endpoint in data else 404
            response.json.return_value = data.get(endpoint)
            return response

    written = []
    monkeypatch.setattr(history_import, "get_lcu_session", Session)
    monkeypatch.setattr(history_import, "get_champion_id_map", lambda _: {"222": "jinx"})
    monkeypatch.setattr(history_import, "game_exists", lambda _: False)
    monkeypatch.setattr(history_import, "record_game", lambda **kwargs: written.append(kwargs))
    stored = []
    monkeypatch.setattr(history_import, "participants_exist", lambda _: False)
    monkeypatch.setattr(history_import, "record_participants",
                        lambda gid, dur, rows: stored.append((dur, rows)) or len(rows))

    result = history_import.sync_recent_mayhem_games()
    assert result == {"status": "ok", "imported": 1, "inspected": 1, "listed": 2}
    assert len(written) == 1
    assert written[0]["champion_id"] == "jinx"
    assert written[0]["augments"] == ["1234"]
    assert written[0]["items"] == ["3001"]
    assert written[0]["win"] is True
    assert "super-private-puuid" not in str(result)
    assert "super-private-puuid" not in str(written)
    assert len(stored) == 1 and len(stored[0][1]) == 1  # other champion unknown
    assert "puuid" not in str(stored)


def test_champion_record_counts_only_finished_known_results(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    record_game("1", "lux", [], [], True, 600, {}, db_path=path)
    record_game("2", "lux", [], [], False, 600, {}, db_path=path)
    record_game("3", "lux", [], [], None, 600, {}, db_path=path)
    record_game("4", "jinx", [], [], True, 600, {}, db_path=path)
    assert get_champion_record("lux", db_path=path) == (1, 2)
    assert get_champion_record("unknown", db_path=path) is None


class _PagedSession:
    base_url = "https://127.0.0.1:1"

    def __init__(self, total, ignore_indices=False):
        self.total, self.ignore, self.calls = total, ignore_indices, []

    def get(self, url, timeout):
        endpoint = url.split(self.base_url, 1)[-1]
        self.calls.append(endpoint)
        q = dict(kv.split("=") for kv in endpoint.split("?", 1)[1].split("&"))
        beg, end = (0, 20) if self.ignore else (int(q["begIndex"]), int(q["endIndex"]))
        games = [{"gameId": i} for i in range(beg, min(end, self.total))]
        response = Mock(status_code=200)
        response.json.return_value = {"games": {"games": games}}
        return response


def test_match_list_pages_back_until_history_ends():
    s = _PagedSession(total=65)
    out = history_import._list_matches(s, 1000, pause=0)
    assert [g["gameId"] for g in out] == list(range(65))
    assert len(s.calls) == 4


def test_match_list_stops_when_client_ignores_indices():
    s = _PagedSession(total=500, ignore_indices=True)
    out = history_import._list_matches(s, 1000, pause=0)
    assert len(out) == 20 and len(s.calls) == 2


def test_match_list_respects_max_games():
    s = _PagedSession(total=500)
    assert len(history_import._list_matches(s, 50, pause=0)) == 50
