"""P0: exact public 16.23 keyword source probes (no live-game claims)."""
from __future__ import annotations

import pytest

from backend.static_data.anvil_public_catalog import AnvilCatalogError
from scripts.stat_anvil_catalog_report import (
    summarize_public_anvil_references, probe_public_anvil_keyword_paths,
)


def _example():
    return {
        "{normal}": {"__type": "Effect", "Name": "normal"},
        "{spell}": {"__type": "SpellObject", "mSpell": {
            "DataValues": [{"name": "MinAR", "values": [12] * 7}]}},
        "{nested}": {"__type": "MapConfig",
            "anvilSetting": {"objectPath": "ARAM_StatAnvil_AR",
                             "source": "game/unknown/abc123.bin.json"}},
        "{direct}": {"__type": "AnvilData",
                     "AugmentNameId": "ARAM_StatAnvil_AR",
                     "RootSpell": "{spell}", "AnvilTypes": [0],
                     "NameTra": "CHERRY_StatAnvil_AR_Name"},
    }


def test_references_report_exact_public_paths_and_class_counts():
    result = summarize_public_anvil_references(
        "game/maps/modespecificdata/cherry.bin.json", _example())
    assert result["valid_json"]
    assert result["top_level_anvil_data"] == 1
    assert result["nested_anvil_data"] == 0
    assert result["keyword_hit_count"] >= 2
    assert any("anvilSetting" in row["json_path"]
               for row in result["keyword_examples"])
    assert result["catalogue_verified"] is False


def test_nested_anvil_is_reference_only_not_automatically_verified():
    result = summarize_public_anvil_references("game/gameplay.bin.json", {
        "root": {"value": {"__type": "AnvilData",
                            "AugmentNameId": "ARAM_StatAnvil_AR"}},
    })
    assert result["top_level_anvil_data"] == 0
    assert result["nested_anvil_data"] == 1
    assert result["catalogue_verified"] is False


def test_probe_fetches_only_explicit_patch_pinned_public_bins(monkeypatch):
    import requests
    seen = []

    class Response:
        status_code = 200
        content = b'{"root":{"text":"StatAnvil"}}'
        def raise_for_status(self):
            return None
        def json(self):
            return {"root": {"text": "StatAnvil"}}

    def fake_get(url, timeout):
        seen.append((url, timeout))
        assert url.startswith("https://raw.communitydragon.org/16.23/game/")
        return Response()

    monkeypatch.setattr(requests, "get", fake_get)
    report = probe_public_anvil_keyword_paths("16.23", [
        "game/gameplay.bin.json", "game/maps/modespecificdata/cherry.bin.json",
    ])
    assert len(seen) == 2
    assert report["patch"] == "16.23"
    assert report["catalogue_verified"] is False
    assert report["paths"][0]["keyword_hit_count"] == 1
    assert all(row["top_level_anvil_data"] == 0 for row in report["paths"])


def test_probe_denies_url_injection_without_network(monkeypatch):
    import requests
    monkeypatch.setattr(requests, "get", lambda *_a, **_k:
                        pytest.fail("untrusted URL reached network"))
    with pytest.raises(AnvilCatalogError):
        probe_public_anvil_keyword_paths("16.23", [
            "https://example.org/private.bin.json",
        ])
    with pytest.raises(AnvilCatalogError):
        probe_public_anvil_keyword_paths("../latest", [
            "game/gameplay.bin.json",
        ])
    with pytest.raises(AnvilCatalogError):
        probe_public_anvil_keyword_paths("16.23", [
            "game/../gameplay.bin.json",
        ])
