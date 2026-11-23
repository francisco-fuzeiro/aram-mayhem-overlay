"""P0: an offline item-pool report must expose, not hide, empty real caches.

Pure synthetic cache fixtures: no League, network, real user files or tier DB.
"""
import json
from scripts.item_pool_report import inspect_cache, format_report


def _write_cache(path, policy, classes):
    data = {
        "schema": 5,
        "meta": {"policy_version": policy, "ddragon_version": "16.23.1",
                 "cdragon_patch": "16.23.8406595", "availability": "verified_two_source",
                 "cdragon_sha256": "a" * 64},
        "classes": classes,
        "items": {key: {"name": "Synthetic", "item_class": cat}
                  for key, cat in classes.items()},
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def test_read_only_report_exposes_empty_final_pool_and_old_policy(tmp_path):
    cache = tmp_path / "items_v5_16.23.1.json"
    _write_cache(cache, "item_pool_v2",
                 {"1001": "unknown", "3006": "boots_tier2",
                  "3074": "unknown", "220008": "augment_reward"})
    original = cache.read_bytes()
    report = inspect_cache(cache)
    assert report["classes"]["final"] == 0
    assert report["recommendable_count"] == 1
    assert report["policy_version"] == "item_pool_v2"
    assert report["policy_current"] is False
    assert report["warnings"]
    assert "source-conflict details" in format_report([report])
    assert cache.read_bytes() == original


def test_report_current_policy_counts_final_without_claiming_mayhem_shop(tmp_path):
    cache = tmp_path / "items_v5_16.23.1.json"
    _write_cache(cache, "item_pool_v3",
                 {"3074": "final", "3006": "boots_tier2",
                  "1036": "component", "220009": "augment_reward"})
    report = inspect_cache(cache)
    assert report["classes"]["final"] == 1
    assert report["recommendable_count"] == 2
    assert report["policy_current"] is True
    assert "does not prove live Mayhem shop availability" in format_report([report])


def test_report_fails_closed_on_corrupt_cache(tmp_path):
    cache = tmp_path / "items_v5_broken.json"
    cache.write_text('{"meta": {"policy_version": "item_pool_v3"}}', encoding="utf-8")
    report = inspect_cache(cache)
    assert report["valid"] is False
    assert report["recommendable_count"] == 0
