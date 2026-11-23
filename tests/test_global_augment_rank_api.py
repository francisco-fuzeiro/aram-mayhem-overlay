"""Offline Settings tier-list endpoint must not need a live League match."""
import pytest
from fastapi import HTTPException

from backend.api import server
from backend.models import AugmentData, AugmentTier, ChampionMeta, StatVector
from backend.static_data.loader import StaticData


def test_offline_endpoint_uses_loaded_catalog_not_game_state_or_player_history(monkeypatch):
    sd = StaticData()
    sd._champions = {
        "lux": ChampionMeta("lux", "Lux", StatVector(ap=0.9), role="mage"),
    }
    sd._augments = {
        "good": AugmentData("good", "Strong", AugmentTier.GOLD, "",
                            StatVector(ap=0.7), provenance="override"),
        "unknown": AugmentData("unknown", "Unknown", AugmentTier.GOLD, "",
                               StatVector(), provenance="none"),
        "silver": AugmentData("silver", "Silver", AugmentTier.SILVER, "",
                              StatVector(ap=1.0), provenance="override"),
    }
    monkeypatch.setattr(server, "static_data", sd)
    monkeypatch.setattr(server.game_state, "match_id", None)
    monkeypatch.setattr("backend.storage.db.get_all_personal_winrates",
                        lambda _: (_ for _ in ()).throw(AssertionError("history used")))
    result = server.get_augment_tier_list(champion_id="lux", rarity=2)
    assert result["context"] == "baseline"
    assert result["champion_id"] == "lux"
    assert result["catalog_count"] == 2
    assert result["assessed_count"] == 1
    assert result["unrated_count"] == 1
    assert result["grade_calibrated"] is False
    assert [(row["rank"], row["augment_id"]) for row in result["rows"]] == [(1, "good")]
    assert result["rows"][0]["scope"] == "same_rarity_modelled_catalog"
    assert result["rows"][0]["grade"] is None
    assert result["unrated"] == [{"augment_id": "unknown", "augment_name": "Unknown"}]
    assert all("ranking_value" not in row and "win_rate" not in row
               for row in result["rows"])
    assert server.get_augment_tier_list(champion_id="lux", rarity=1)["catalog_count"] == 1


def test_unknown_champion_and_empty_catalog_reject_instead_of_fabricating_tier(monkeypatch):
    sd = StaticData()
    monkeypatch.setattr(server, "static_data", sd)
    with pytest.raises(HTTPException) as exc:
        server.get_augment_tier_list(champion_id="missing", rarity=2)
    assert exc.value.status_code == 404
    sd._champions["lux"] = ChampionMeta("lux", "Lux",
                                         StatVector(ap=0.8), role="mage")
    with pytest.raises(HTTPException) as exc:
        server.get_augment_tier_list(champion_id="lux", rarity=2)
    assert exc.value.status_code == 503
