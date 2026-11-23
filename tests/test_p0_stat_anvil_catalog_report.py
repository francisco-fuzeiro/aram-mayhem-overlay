"""P0: read-only stat-anvil source-coverage audit, NOT popup identification."""
import json

from scripts.stat_anvil_catalog_report import inspect_cache, format_report


def test_public_augment_cache_tier_zero_is_only_unverified_candidates(tmp_path):
    source = tmp_path / "augments_v5_16.23.1.json"
    source.write_text(json.dumps({
        "300005": {"name": "Synthetic Silver Candidate", "tier": 0},
        "300006": {"name": "Synthetic Gold Candidate", "tier": 0},
        "300007": {"name": "Synthetic Augment", "tier": 2},
    }), encoding="utf-8")
    original = source.read_bytes()
    result = inspect_cache(source)
    assert result["valid"] is True
    assert result["total_rows"] == 3
    assert result["tier_zero_rows"] == 2
    assert result["verified_stat_options"] is False
    assert len(result["candidate_titles"]) == 2
    assert "NOT verified" in format_report([result])
    assert source.read_bytes() == original


def test_missing_or_corrupt_cache_fail_closed(tmp_path):
    missing = inspect_cache(tmp_path / "augments_v5_missing.json")
    assert missing["valid"] is False
    assert missing["tier_zero_rows"] == 0
    invalid = tmp_path / "augments_v5_bad.json"
    invalid.write_text('{"not-a-cache": 4}', encoding="utf-8")
    result = inspect_cache(invalid)
    assert result["valid"] is False
    assert result["verified_stat_options"] is False


def test_empty_tier_zero_catalog_never_promotes_anvils(tmp_path):
    source = tmp_path / "augments_v5_16.23.1.json"
    source.write_text(json.dumps({
        "300007": {"name": "Synthetic Gold", "tier": 2},
    }), encoding="utf-8")
    result = inspect_cache(source)
    assert result["valid"] is True
    assert result["tier_zero_rows"] == 0
    assert result["candidate_titles"] == []
    assert any("NO TIER-ZERO" in x for x in result["warnings"])
