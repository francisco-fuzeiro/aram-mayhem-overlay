"""Synthetic RED/GREEN tests only. Live proof must come from the direct HTTP report."""
import pytest
import requests

from scripts.anvil_source_exact_probe import inspect_direct_public_source
from tests.test_p0_anvil_public_source import _fixture


def test_direct_public_path_can_prove_all_three_rarities(monkeypatch):
    data = _fixture()
    data["{spell_p}"] = {"__type": "SpellObject", "mSpell": {
        "DataValues": [{"name": "MinHP", "values": [100.0] * 7}]}}
    data["{shard_p}"] = {"__type": "AnvilData",
        "AugmentNameId": "ARAM_PrisStatAnvil_HP",
        "NameTra": "CHERRY_PrisStatAnvil_HP_Name",
        "AnvilTypes": [9], "RootSpell": "{spell_p}"}
    class Response:
        status_code = 200
        content = b'{"synthetic":true}'
        def raise_for_status(self): pass
        def json(self): return data
    urls = []
    def get(url, timeout):
        urls.append(url)
        return Response()
    monkeypatch.setattr(requests, "get", get)
    report = inspect_direct_public_source("16.23")
    assert urls == ["https://raw.communitydragon.org/16.23/game/unknown/507cdd64276919f5.bin.json"]
    assert report["http_status"] == 200
    assert report["raw_anvil_data"] == 6  # Includes excluded Random
    assert report["raw_rarity_singletons"] == {
        "silver": 2, "gold": 3, "prismatic": 1,
    }
    assert report["parser_total"] == 5
    assert report["parser_tiers"] == {
        "silver": 1, "gold": 3, "prismatic": 1,
    }
    assert report["source_verified"] is True
    assert report["live_popup_verified"] is False


def test_404_queries_exact_patch_index_never_promotes_guessed_path(monkeypatch):
    class Response:
        def __init__(self, status, obj):
            self.status_code = status
            self.obj = obj
            self.content = b""
        def raise_for_status(self): pass
        def json(self): return self.obj
    urls = []
    def get(url, timeout):
        urls.append(url)
        if "/json/" in url:
            return Response(200, [
                {"name": "507cdd64276919f5.bin", "type": "file"},
                {"name": "different.bin.json", "type": "file"},
            ])
        return Response(404, {})
    monkeypatch.setattr(requests, "get", get)
    report = inspect_direct_public_source("16.23")
    assert report["http_status"] == 404
    assert report["index_status"] == "checked"
    assert report["exact_filename_in_index"] is False
    assert report["index_named_candidates"] == ["507cdd64276919f5.bin"]
    assert report["source_verified"] is False
    assert len(urls) == 2


def test_unverified_source_or_incomplete_rarity_abstains(monkeypatch):
    class Response:
        status_code = 200
        content = b'{"synthetic":true}'
        def raise_for_status(self): pass
        def json(self): return _fixture()
    monkeypatch.setattr(requests, "get", lambda url, timeout: Response())
    report = inspect_direct_public_source("16.23")
    assert report["raw_anvil_data"] == 5
    assert report["parser_tiers"]["prismatic"] == 0
    assert report["source_verified"] is False


def test_invalid_patch_rejected_before_network(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *_a, **_kw:
                        pytest.fail("Unsafe patch should not perform request"))
    from backend.static_data.anvil_public_catalog import AnvilCatalogError
    with pytest.raises(AnvilCatalogError):
        inspect_direct_public_source("../private")
