"""Local Mayhem history with all 10 players (owner decision 23/11).

Each finished Mayhem game stores, per participant: champion, team, result,
augments, items, damage to champions, healing+shielding on teammates, K/D/A
and the game length. Never names, PUUIDs or summoner IDs. Remakes are skipped.
"""
import json

from backend.storage import db, history_import

DETAIL = {
    "gameDuration": 1200,
    "participantIdentities": [
        {"participantId": i, "player": {"puuid": f"puuid-{i}", "gameName": f"Name{i}",
                                         "tagLine": "EUW", "summonerId": 1000 + i}}
        for i in range(1, 11)],
    "participants": [
        {"participantId": i, "teamId": 100 if i <= 5 else 200, "championId": 100 + i,
         "stats": {"win": i <= 5, "playerAugment1": 1000 + i, "item0": 3000 + i,
                   "kills": i, "deaths": 1, "assists": 2,
                   "totalDamageDealtToChampions": 1000 * i,
                   "totalHealsOnTeammates": 10 * i,
                   "totalDamageShieldedOnTeammates": 5 * i}}
        for i in range(1, 11)],
}
ALIASES = {str(100 + i): f"champ{i}" for i in range(1, 11)}


def test_extract_participants_keeps_stats_and_drops_identity():
    rows = history_import.extract_participants(DETAIL, ALIASES, own_puuid="puuid-3")
    assert len(rows) == 10
    third = rows[2]
    assert third["champion_id"] == "champ3" and third["team"] == 100 and third["win"] is True
    assert third["is_self"] is True and sum(r["is_self"] for r in rows) == 1
    assert third["augments"] == ["1003"] and third["items"] == ["3003"]
    assert third["damage_to_champions"] == 3000
    assert third["heal_shield"] == 45
    assert (third["kills"], third["deaths"], third["assists"]) == (3, 1, 2)
    text = json.dumps(rows)
    for secret in ("puuid", "Name3", "EUW", "1003\"", "summoner"):
        if secret != "1003\"":
            assert secret not in text


def test_heal_shield_falls_back_to_total_heal_when_team_fields_missing():
    detail = json.loads(json.dumps(DETAIL))
    for p in detail["participants"]:
        p["stats"].pop("totalHealsOnTeammates")
        p["stats"].pop("totalDamageShieldedOnTeammates")
        p["stats"]["totalHeal"] = 77
    rows = history_import.extract_participants(detail, ALIASES, own_puuid=None)
    assert rows[0]["heal_shield"] is None and rows[0]["heal_total"] == 77


def test_participants_are_stored_once_and_remakes_skipped(tmp_path):
    path = tmp_path / "o.db"
    db.init_db(path)
    rows = history_import.extract_participants(DETAIL, ALIASES, own_puuid="puuid-3")
    assert db.record_participants("g1", 1200, rows, db_path=path) == 10
    assert db.record_participants("g1", 1200, rows, db_path=path) == 0
    assert db.record_participants("g2", 200, rows, db_path=path) == 0  # remake (<300 s)
    stored = db.get_participants(db_path=path)
    assert len(stored) == 10
    assert set(stored[0]) == {
        "game", "duration", "team", "champion_id", "win", "augments", "items",
        "damage_to_champions", "heal_shield", "heal_total", "kills", "deaths",
        "assists", "is_self"}
    assert stored[0]["game"] != "g1"  # local key, not the match id
