"""P0 source-location RED: indexed CDragon files are not gameplay offers.

Observed by owner on Windows current patch 16.23:
map12.bin.json was HTTP 200 but contained ZERO AnvilData rows,
and historical 507c... hashed bin was absent/404. Search public directory
metadata only; do not scan player data or guess shard identities.
"""
from __future__ import annotations

import pytest

from backend.static_data.anvil_public_catalog import AnvilCatalogError
from scripts.stat_anvil_catalog_report import inspect_public_bin_index


def test_patch_index_distinguishes_missing_hash_from_empty_source(monkeypatch):
    import requests
    calls = []

    class Response:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return [
                {"name": "507cdd64276919f5.bin", "type": "file", "size": 31700},
                {"name": "anotherhash.bin.json", "type": "file", "size": 65000},
                {"name": "tiny.bin.json", "type": "file", "size": 15},
                {"name": "irrelevant.png", "type": "file", "size": 66000},
                {"name": "folder", "type": "directory"},
            ]

    def fake(url, timeout):
        calls.append(url)
        assert url == "https://raw.communitydragon.org/json/16.23/game/unknown/"
        assert timeout <= 20
        return Response()

    monkeypatch.setattr(requests, "get", fake)
    found = inspect_public_bin_index("16.23")
    assert len(calls) == 1
    assert found["status"] == "indexed"
    assert found["known_hashed_bin_present"] is False
    assert found["bin_json_count"] == 2
    assert found["possible_public_filenames"] == ["anotherhash.bin.json"]
    assert found["live_popup_verified"] is False
    assert found["catalogue_verified"] is False


def test_patch_index_reports_known_hash_without_promoting_it(monkeypatch):
    import requests

    class Response:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return [{"name": "507cdd64276919f5.bin.json",
                     "type": "file", "size": 66100}]

    monkeypatch.setattr(requests, "get", lambda url, timeout: Response())
    found = inspect_public_bin_index("16.23")
    assert found["known_hashed_bin_present"] is True
    assert found["possible_public_filenames"] == []
    assert found["catalogue_verified"] is False


def test_bad_index_never_guesses_a_bin_or_creates_suggestions(monkeypatch):
    import requests

    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return [{"name": "../../private.bin.json", "size": 66000,
                     "type": "file"}]

    monkeypatch.setattr(requests, "get", lambda url, timeout: Response())
    found = inspect_public_bin_index("16.23")
    assert found["status"] == "indexed"
    assert found["possible_public_filenames"] == []
    assert found["catalogue_verified"] is False
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs:
                        pytest.fail("invalid patch must not access network"))
    with pytest.raises(AnvilCatalogError):
        inspect_public_bin_index("latest/../../private")


def test_index_unavailable_has_closed_reason(monkeypatch):
    import requests

    class Response:
        status_code = 404
        def raise_for_status(self):
            raise requests.HTTPError("404")
    monkeypatch.setattr(requests, "get", lambda url, timeout: Response())
    found = inspect_public_bin_index("16.23")
    assert found["status"] == "index_unavailable"
    assert found["known_hashed_bin_present"] is False
    assert found["possible_public_filenames"] == []
