"""Resumable AramHex download: per-file cache, mirror fallback, rebuild trigger."""
import hashlib
import json
import os
import time

from backend.tierdb import aramhex
from backend.tierdb.export import BUILD_VERSION
from backend.tierdb.service import TierListService

FILES = {"heroes.json": b"{}", "hero_augments.json": b"{}", "augments.json": b"{}"}


def _meta():
    return json.dumps({"files": {n: hashlib.sha256(b).hexdigest()
                                 for n, b in FILES.items()}}).encode()


def _server(calls, fail_host=None):
    def fetch(url):
        calls.append(url)
        if fail_host and fail_host in url:
            raise ConnectionError("down")
        name = url.rsplit("/", 1)[-1]
        return _meta() if name == "meta.json" else FILES[name]
    return fetch


def test_second_download_reuses_cached_files(tmp_path):
    calls = []
    for run in range(2):
        aramhex.download_dataset("data-v1", "patches/1.0/normal", tmp_path / f"t{run}",
                                 fetch=_server(calls), cache_dir=tmp_path / "cache")
    # 1 meta + 3 files the first time, only meta the second time
    assert len(calls) == 5
    assert (tmp_path / "t1" / "heroes.json").read_bytes() == b"{}"


def test_corrupt_cache_entry_is_downloaded_again(tmp_path):
    calls = []
    cache = tmp_path / "cache"
    aramhex.download_dataset("data-v1", "p", tmp_path / "a", fetch=_server(calls),
                             cache_dir=cache)
    (cache / "data-v1" / "p" / "augments.json").write_bytes(b"bad")
    calls.clear()
    aramhex.download_dataset("data-v1", "p", tmp_path / "b", fetch=_server(calls),
                             cache_dir=cache)
    assert [c.rsplit("/", 1)[-1] for c in calls] == ["meta.json", "augments.json"]
    assert (tmp_path / "b" / "augments.json").read_bytes() == b"{}"


def test_falls_back_to_raw_github_when_cdn_fails(tmp_path):
    calls = []
    aramhex.download_dataset("data-v1", "p", tmp_path / "a",
                             fetch=_server(calls, fail_host="jsdelivr"))
    assert any("raw.githubusercontent" in c for c in calls)
    assert (tmp_path / "a" / "augments.json").exists()


def test_branch_refs_skip_the_cdn(tmp_path):
    calls = []
    aramhex.download_dataset("main", "p", tmp_path / "a", fetch=_server(calls))
    assert not any("jsdelivr" in c for c in calls)


def test_export_from_older_rules_needs_update(tmp_path):
    export = tmp_path / "tierlist.json"
    svc = TierListService(export_path=export, preferences_path=tmp_path / "p.json",
                          db_path=tmp_path / "db.sqlite")
    export.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    assert svc.needs_update()
    export.write_text(json.dumps({"build_version": BUILD_VERSION}), encoding="utf-8")
    assert not svc.needs_update()
    old = time.time() - 4 * 86400
    os.utime(export, (old, old))
    assert svc.needs_update()
