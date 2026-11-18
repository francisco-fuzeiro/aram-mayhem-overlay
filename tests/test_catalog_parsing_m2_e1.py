"""M2/E1 red-first regressions for false catalog hints and cache reuse."""

import json

from backend.static_data import loader


def test_upgrade_has_no_ad_from_partial_keyword():
    stats = loader._parse_description_to_stats("", "Upgrade Stormsurge")
    assert stats.ad == 0.0


def test_donation_has_no_hp_from_incorrect_name_hint():
    stats = loader._parse_description_to_stats("", "Donation")
    assert stats.hp == 0.0


def test_keywords_match_whole_words_and_keep_real_matches():
    description = "Attack damage, ability haste, slow, and magic penetration."
    stats = loader._parse_description_to_stats(description, "Unknown")
    assert stats.ad > 0.0
    assert stats.cdr > 0.0
    assert stats.soft_cc > 0.0
    assert stats.pen > 0.0
    assert loader._parse_description_to_stats("Upgraded equipment", "").ad == 0.0
    assert loader._parse_description_to_stats("Shadowy", "").ad == 0.0


def test_old_schema_augment_cache_is_not_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(loader, "_get_dd_version", lambda: "test-patch")
    old_file = tmp_path / "augments_test-patch.json"
    old_file.write_text(json.dumps({
        "old": {"name": "Old Data", "tier": 2, "description": "",
                "contribution": {"ad": 0.8}}
    }), encoding="utf-8")

    class Response:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    def fake_get(url, **kwargs):
        if url == loader.CD_AUGMENTS_URL:
            return Response([{"id": 9001, "name": "Valid Card", "rarity": "kGold"}])
        if url == loader.CD_ARENA_DESC_URL:
            return Response({"augments": []})
        raise AssertionError(f"Unexpected request: {url}")

    monkeypatch.setattr(loader.requests, "get", fake_get)
    results = loader._load_augments()
    assert "old" not in results
    assert "9001" in results
    assert old_file.exists()
    assert (tmp_path / f"augments_v{loader._AUGMENT_CACHE_SCHEMA}_test-patch.json").exists()
