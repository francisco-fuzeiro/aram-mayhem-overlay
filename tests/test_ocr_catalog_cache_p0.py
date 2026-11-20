"""P0 regressions: a transient Mayhem catalog outage must not become permanent.

These fixtures contain synthetic catalog records only; no game screenshots,
player data, or invented IDs for production use.
"""

import json

import requests

from backend.static_data import loader


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(loader, "_get_dd_version", lambda: "offline-test")
    return tmp_path / f"augments_v{loader._AUGMENT_CACHE_SCHEMA}_offline-test.json"


def _healthy_response(url, **_kwargs):
    if url == loader.CD_AUGMENTS_URL:
        return _Response([{"id": 90001, "name": "Fixture Title", "rarity": "kGold"}])
    if url == loader.CD_ARENA_DESC_URL:
        return _Response({"augments": []})
    raise AssertionError("unexpected source")


def test_failed_catalog_download_does_not_persist_an_empty_cache(tmp_path, monkeypatch):
    path = _setup(tmp_path, monkeypatch)

    def unavailable(url, **_kwargs):
        if url == loader.CD_AUGMENTS_URL:
            raise requests.ConnectionError("offline")
        return _Response({"augments": []})

    monkeypatch.setattr(loader.requests, "get", unavailable)
    assert loader._load_augments() == {}
    assert not path.exists(), "A network outage must not poison the patch cache"

    monkeypatch.setattr(loader.requests, "get", _healthy_response)
    assert "90001" in loader._load_augments()
    assert path.exists()


def test_existing_empty_cache_is_refetched_when_source_recovers(tmp_path, monkeypatch):
    path = _setup(tmp_path, monkeypatch)
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(loader.requests, "get", _healthy_response)
    assert "90001" in loader._load_augments()
    assert "90001" in json.loads(path.read_text(encoding="utf-8"))


def test_empty_successful_source_response_is_not_cached(tmp_path, monkeypatch):
    path = _setup(tmp_path, monkeypatch)

    def empty_source(url, **_kwargs):
        if url == loader.CD_AUGMENTS_URL:
            return _Response([])
        return _Response({"augments": []})

    monkeypatch.setattr(loader.requests, "get", empty_source)
    assert loader._load_augments() == {}
    assert not path.exists()


def test_nonempty_catalog_still_uses_existing_patch_cache(tmp_path, monkeypatch):
    path = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(loader.requests, "get", _healthy_response)
    assert "90001" in loader._load_augments()
    assert path.exists()

    def unexpected_request(url, **_kwargs):
        raise AssertionError("Valid patch cache must be reused")

    monkeypatch.setattr(loader.requests, "get", unexpected_request)
    assert "90001" in loader._load_augments()
