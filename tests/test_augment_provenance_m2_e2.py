"""M2/E2 tests-first: explicit model coverage and contribution origin."""

import json

import pytest

from backend.models import AugmentData, AugmentTier, StatVector
from backend.static_data import loader


@pytest.mark.parametrize("name", [
    "Impassable", "Tooth Fairy", "Shark Bait", "Get Jinxed",
])
def test_known_zero_signal_augments_are_not_modelled(name):
    contribution = loader._parse_description_to_stats("", name)
    augment = AugmentData("test", name, AugmentTier.GOLD, "", contribution)
    assert not augment.modelled
    assert augment.provenance == "none"


def test_nonzero_manual_vector_is_modelled_and_zero_vector_is_not():
    known = AugmentData("a", "Known", AugmentTier.GOLD, "", StatVector(ap=0.8))
    empty = AugmentData("b", "Empty", AugmentTier.GOLD, "", StatVector())
    assert known.modelled is True
    assert empty.modelled is False


def test_name_hint_description_keywords_and_override_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(loader, "_get_dd_version", lambda: "e2-fixture")
    overrides = tmp_path / "overrides.json"
    overrides.write_text(json.dumps({
        "503": {"contribution": {"ap": 0.7}},
        "504": {"contribution": {"hp": 0.0}},
    }), encoding="utf-8")
    monkeypatch.setattr(loader, "AUG_OVERRIDE_FILE", overrides)

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if url == loader.CD_AUGMENTS_URL:
            return Response([
                {"id": 501, "name": "Blunt Force", "nameTRA": "Blunt Force", "augmentSmallIconPath": "/Kiwi/test", "rarity": "kGold"},
                {"id": 502, "name": "Description Card", "nameTRA": "Description Card", "augmentSmallIconPath": "/Kiwi/test", "rarity": "kGold"},
                {"id": 503, "name": "Override Card", "nameTRA": "Override Card", "augmentSmallIconPath": "/Kiwi/test", "rarity": "kGold"},
                {"id": 504, "name": "Empty Override Card", "nameTRA": "Empty Override Card", "augmentSmallIconPath": "/Kiwi/test", "rarity": "kGold"},
                {"id": 505, "name": "Shark Bait", "nameTRA": "Shark Bait", "augmentSmallIconPath": "/Kiwi/test", "rarity": "kGold"},
            ])
        if url == loader.CD_ARENA_DESC_URL:
            return Response({"augments": [
                {"name": "Description Card", "desc": "Gain attack damage."},
            ]})
        raise AssertionError(url)

    monkeypatch.setattr(loader.requests, "get", fake_get)
    first = loader._load_augments()
    assert first["501"].provenance == "curated"  # S1 table (24/11) beats the name hint
    assert first["502"].provenance == "description_keywords"
    assert first["503"].provenance == "override"
    assert first["504"].provenance == "override"
    assert first["505"].provenance == "none"
    assert [first[k].modelled for k in ("501", "502", "503", "504", "505")] == [
        True, True, True, False, False,
    ]

    cache_path = tmp_path / f"augments_v{loader._AUGMENT_CACHE_SCHEMA}_e2-fixture.json"
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cached["501"]["provenance"] == "curated"
    assert cached["502"]["provenance"] == "description_keywords"
    assert cached["505"]["modelled"] is False

    calls.clear()
    second = loader._load_augments()
    assert calls == []
    assert {
        k: (v.modelled, v.provenance)
        for k, v in first.items()
    } == {
        k: (v.modelled, v.provenance)
        for k, v in second.items()
    }


def test_coverage_report_counts_match_catalog_without_inventing_signal():
    data = loader.StaticData()
    data._augments = {
        "a": AugmentData("a", "A", AugmentTier.GOLD, "",
                         StatVector(ad=0.4)),
        "b": AugmentData("b", "B", AugmentTier.GOLD, "", StatVector()),
        "c": AugmentData("c", "C", AugmentTier.GOLD, "",
                         StatVector(ap=0.2), provenance="description_keywords"),
    }
    report = data.augment_coverage_report()
    assert report["total"] == 3
    assert report["modelled"] == 2
    assert report["unmodelled"] == 1
    assert sum(report["by_provenance"].values()) == report["total"]
    assert report["by_provenance"]["description_keywords"] == 1
