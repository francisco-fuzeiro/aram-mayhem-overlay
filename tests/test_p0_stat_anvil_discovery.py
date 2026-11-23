"""P0: scan public patch indexes for *real* AnvilData, not fixture-only success.

Fixtures mock public HTTP entirely. A real 16.23 >0 must be separately
obtained by the owner and cannot be claimed from these tests.
"""
import json

import pytest

from backend.static_data.anvil_public_catalog import AnvilCatalogError
from scripts.stat_anvil_catalog_report import discover_patch_anvil_bins


def _bin_with_three_tiers():
    rows = {}
    for tier, code, prefix in (
        ("silver", 0, "ARAM_StatAnvil"),
        ("gold", 8, "ARAM_GoldStatAnvil"),
        ("prismatic", 9, "ARAM_PrisStatAnvil"),
    ):
        rows[f"{{{tier}-spell}}"] = {
            "__type": "SpellObject",
            "mSpell": {"DataValues": [
                {"name": "MinAR", "values": [12.0 + code] * 7},
            ]},
        }
        rows[f"{{{tier}-entry}}"] = {
            "__type": "AnvilData", "AugmentNameId": f"{prefix}_AR",
            "NameTra": f"CHERRY_{tier}_AR_Name",
            "AnvilTypes": [code], "RootSpell": f"{{{tier}-spell}}",
        }
    return rows


def test_scan_indexed_patch_16_23_finds_different_bin_instead_of_map12(monkeypatch):
    import requests
    seen = []
    index = {
        "game/": [
            {"name": "data", "type": "directory"},
            {"name": "unknown", "type": "directory"},
            {"name": "gameplay.mayhem.bin.json", "type": "file", "size": 6000},
        ],
        "game/unknown/": [
            {"name": "tiny.bin.json", "type": "file", "size": 15},
            {"name": "../unsafe.bin.json", "type": "file", "size": 30000},
        ],
        "game/data/": [{"name": "maps", "type": "directory"}],
        "game/data/maps/": [{"name": "shipping", "type": "directory"}],
        "game/data/maps/shipping/": [
            {"name": "map12", "type": "directory"},
            {"name": "map30", "type": "directory"},
        ],
        "game/data/maps/shipping/map12/": [
            {"name": "map12.bin.json", "type": "file", "size": 45000},
        ],
        "game/data/maps/shipping/map30/": [
            {"name": "mayhem.stats.bin.json", "type": "file", "size": 64000},
        ],
    }

    class Response:
        def __init__(self, status, payload):
            self.status_code, self.payload = status, payload
            self.content = json.dumps(payload).encode("utf-8")
            self.headers = {"Content-Length": str(len(self.content))}
        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError("public error")
        def json(self):
            return self.payload

    def fetch(url, timeout, **_):
        seen.append(url)
        assert url.startswith("https://raw.communitydragon.org/")
        assert "/16.23/" in url
        if "/json/16.23/" in url:
            directory = url.split("/json/16.23/")[1]
            return Response(200, index.get(directory, []))
        if url.endswith("mayhem.stats.bin.json"):
            return Response(200, _bin_with_three_tiers())
        return Response(200, {"noAnvil": {"kind": "not an anvil"}})

    monkeypatch.setattr(requests, "get", fetch)
    result = discover_patch_anvil_bins("16.23")
    assert result["patch"] == "16.23"
    assert result["total"] == 3
    assert result["tiers"] == {"silver": 1, "gold": 1, "prismatic": 1}
    assert result["source_paths"] == [
        "game/data/maps/shipping/map30/mayhem.stats.bin.json"
    ]
    assert "game/data/maps/shipping/map30/mayhem.stats.bin.json" in repr(seen)
    assert result["live_popup_verified"] is False
    assert result["source_verified"] is True


def test_empty_patch_never_fabricates_options(monkeypatch):
    import requests

    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return []
    monkeypatch.setattr(requests, "get", lambda url, timeout, **k: Response())
    result = discover_patch_anvil_bins("16.23")
    assert result["total"] == 0
    assert result["source_verified"] is False
    assert result["live_popup_verified"] is False
    assert result["status"] in ("no_source", "scan_incomplete")


def test_invalid_patch_denies_network(monkeypatch):
    import requests
    monkeypatch.setattr(requests, "get",
                        lambda *a, **k: pytest.fail("invalid patch reached network"))
    with pytest.raises(AnvilCatalogError):
        discover_patch_anvil_bins("../16.23")


def test_bounded_discovery_reports_incomplete_not_no_source(monkeypatch):
    import requests

    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return [
                {"name": "gameplay.cherry.bin.json", "type": "file", "size": 2000},
                {"name": "gameplay.mayhem.bin.json", "type": "file", "size": 3000},
                {"name": "data", "type": "directory"},
            ]
    monkeypatch.setattr(requests, "get", lambda url, timeout, **k: Response())
    result = discover_patch_anvil_bins("16.23", max_bins=0)
    assert result["status"] == "scan_incomplete"
    assert result["total"] == 0
    assert result["source_verified"] is False
