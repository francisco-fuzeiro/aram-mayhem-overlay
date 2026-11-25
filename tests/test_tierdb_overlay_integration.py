"""Tier DB wired to the overlay API: offers, champion select, Settings switch."""
import json
import threading

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.tierdb import service as tier_service
from backend.tierdb.runtime import TierListProvider, save_empirical_tiers_enabled

EXPORT = {
    "schema_version": 1, "patch": "16.23", "run_id": 1,
    "generated_at": "2026-11-23T00:00:00+00:00",
    "sources": [{"name": "aramhex", "license": "CC-BY-NC-4.0",
                 "attribution": "Synthetic attribution", "url": "https://example.invalid"}],
    "augment_columns": ["augment_id", "rank", "tie_group", "tier", "level", "confidence"],
    "augments": {"ahri": {
        "gold": [["1001", 1, 1, "S", "champion", "high"],
                 ["1002", 2, 1, "A", "champion", "high"],
                 ["1003", 3, 3, "B", "role", "medium"],
                 ["1009", None, None, None, "none", "none"]],
        "silver": [["2001", 1, 1, "C", "curated", "heuristic"]],
    }},
    "champion_columns": ["champion_id", "rank", "tie_group", "tier", "confidence", "potential"],
    "champions": [["ahri", 1, 1, "S", "high", "very_high"],
                  ["garen", 2, 2, "B", "high", "low"]],
}


@pytest.fixture()
def tiers(tmp_path, monkeypatch):
    export = tmp_path / "tierlist.json"
    export.write_text(json.dumps(EXPORT), encoding="utf-8")
    prefs = tmp_path / "tierlist_preferences.json"
    svc = tier_service.TierListService(
        export_path=export, preferences_path=prefs, db_path=tmp_path / "t.sqlite")
    monkeypatch.setattr(server, "tier_service", svc)
    return svc, prefs


def test_provider_adds_group_span_and_totals(tmp_path):
    export = tmp_path / "tierlist.json"
    export.write_text(json.dumps(EXPORT), encoding="utf-8")
    p = TierListProvider(export, enabled=lambda: True)
    entry = p.augment_tier("ahri", "1002")
    assert entry["rank_total"] == 3  # ranked gold rows only
    assert (entry["tie_group"], entry["tie_end"]) == (1, 2)
    assert p.augment_tier("ahri", "1009")["level"] == "none"
    champ = p.champion_tier("ahri")
    assert champ["rank_total"] == 2 and champ["potential"] == "very_high"


def test_offer_payload_carries_tiers_for_visible_ids(tiers):
    svc, prefs = tiers
    payload = server._augment_tier_payload("ahri", ["1001", "1003", "unknown"])
    assert payload["tiers_enabled"] is True
    assert set(payload["augment_tiers"]) == {"1001", "1003"}
    assert payload["augment_tiers"]["1003"]["level"] == "role"
    for entry in payload["augment_tiers"].values():
        assert not set(entry) & {"wins", "games", "n", "win_rate", "score"}
    save_empirical_tiers_enabled(False, prefs)
    off = server._augment_tier_payload("ahri", ["1001"])
    assert off == {"tiers_enabled": False, "augment_tiers": {}}


def test_offer_ids_are_collected_from_recommendations_and_slots():
    ids = server._visible_augment_ids(
        [{"augment_id": "1001"}],
        {"offers": [{"slots": {"left": {"augment_id": "1002"},
                               "centre": {"augment_id": None},
                               "right": {"augment_id": "1003"}}}]},
    )
    assert ids == ["1001", "1002", "1003"]


def test_champion_select_candidates_get_strength_and_potential(tiers):
    svc, prefs = tiers
    result = {"type": "champ_select",
              "candidates": [{"id": "ahri", "name": "Ahri"}, {"id": "lux", "name": "Lux"}]}
    server._annotate_champion_candidates(result)
    ahri, lux = result["candidates"]
    # Owner decision 24/11: rank 1 of the list is OP (top 5).
    assert ahri["mayhem"] == {"strength": "OP", "potential": "very_high", "rank": 1,
                              "rank_total": 2, "tie_group": 1, "tie_end": 1,
                              "confidence": "high"}
    assert lux["mayhem"] is None
    save_empirical_tiers_enabled(False, prefs)
    server._annotate_champion_candidates(result)
    assert result["candidates"][0]["mayhem"] is None


def test_settings_endpoints_toggle_and_report_status(tiers):
    svc, prefs = tiers
    client = TestClient(server.app)
    status = client.get("/api/tierlist").json()
    assert status["enabled"] is True and status["available"] is True
    assert status["patch"] == "16.23"
    assert status["sources"][0]["attribution"] == "Synthetic attribution"
    assert client.put("/api/tierlist", json={"enabled": False}).json()["enabled"] is False
    assert client.get("/api/tierlist").json()["enabled"] is False
    assert client.put("/api/tierlist", json={"enabled": "yes"}).status_code == 422


def test_update_endpoint_runs_once_in_background(tiers, monkeypatch):
    svc, _ = tiers
    gate = threading.Event()
    calls = []

    def fake_update(**kwargs):
        calls.append(kwargs)
        gate.wait(5)
        return {"patch": "16.23", "run_id": 2}

    monkeypatch.setattr(tier_service, "update_tierlist", fake_update)
    monkeypatch.setattr(server, "static_data", object())
    client = TestClient(server.app)
    first = client.post("/api/tierlist/update").json()
    second = client.post("/api/tierlist/update").json()
    assert first["started"] is True and second["started"] is False
    gate.set()
    svc.wait(5)
    assert len(calls) == 1
    assert client.get("/api/tierlist").json()["last_update"]["run_id"] == 2


def test_update_failure_is_reported_not_raised(tiers, monkeypatch):
    svc, _ = tiers

    def boom(**kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(tier_service, "update_tierlist", boom)
    svc.start_update(static_data=None)
    svc.wait(5)
    assert "network down" in svc.status()["last_error"]


def test_needs_update_when_missing_or_old(tmp_path):
    svc = tier_service.TierListService(
        export_path=tmp_path / "missing.json", preferences_path=tmp_path / "p.json",
        db_path=tmp_path / "t.sqlite")
    assert svc.needs_update(max_age_hours=72) is True


def test_owner_2411_champion_select_is_ordered_by_tier_list(tmp_path, monkeypatch):
    export = tmp_path / "tierlist.json"
    export.write_text(json.dumps(EXPORT), encoding="utf-8")
    svc = tier_service.TierListService(export_path=export,
                                       preferences_path=tmp_path / "p.json",
                                       db_path=tmp_path / "t.sqlite")
    monkeypatch.setattr(server, "tier_service", svc)
    result = {"candidates": [{"id": "zzz", "name": "NoData", "score": 9.9},
                             {"id": "ahri", "name": "Ahri", "score": 1.0}]}
    server._annotate_champion_candidates(result)
    assert [c["name"] for c in result["candidates"]] == ["Ahri", "NoData"]
