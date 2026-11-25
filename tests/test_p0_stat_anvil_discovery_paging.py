"""P0 public-patch bin scanner must support non-overlapping bounded batches.

Synthetic responses prove that after owner's 80/471 scan we can inspect
80..279 and 280..470 without repeating 0..79. They do NOT prove any
real 16.23 Stat Anvil source exists.
"""
from __future__ import annotations

import json
import pytest

from scripts.stat_anvil_catalog_report import discover_patch_anvil_bins
from backend.static_data.anvil_public_catalog import AnvilCatalogError
from tests.test_p0_stat_anvil_discovery import _bin_with_three_tiers


def _mock_300_bin_index(monkeypatch, *, populated_index: int = 150):
    import requests
    hits = []
    listed = [
        {"name": f"mayhem-{i:03d}.bin.json", "type": "file", "size": 5000}
        for i in range(300)
    ]
    class Response:
        def __init__(self, payload):
            self.payload = payload
            self.content = json.dumps(payload).encode("utf-8")
            self.status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return self.payload

    def get(url, timeout):
        assert url.startswith("https://raw.communitydragon.org/")
        if url == "https://raw.communitydragon.org/json/16.23/game/":
            return Response(listed)
        assert url.startswith("https://raw.communitydragon.org/16.23/game/")
        hits.append(url.rsplit("/", 1)[-1])
        name = url.rsplit("/", 1)[-1]
        payload = (_bin_with_three_tiers()
                   if name == f"mayhem-{populated_index:03d}.bin.json"
                   else {"entry": {"__type": "NotAnvilData"}})
        return Response(payload)

    monkeypatch.setattr(requests, "get", get)
    return hits


def test_second_batch_finds_source_without_repeating_first_80(monkeypatch):
    hits = _mock_300_bin_index(monkeypatch)
    result = discover_patch_anvil_bins("16.23", start_index=80, max_bins=200)
    assert result["candidate_bin_files"] == 300
    assert result["scan_start_index"] == 80
    assert result["scan_stop_index_exclusive"] == 280
    assert result["scan_window_complete"] is True
    assert result["scan_complete"] is False  # offset 0..79 was not scanned now
    assert len(hits) == 200
    assert "mayhem-000.bin.json" not in hits
    assert "mayhem-079.bin.json" not in hits
    assert "mayhem-080.bin.json" in hits
    assert result["source_paths"] == ["game/mayhem-150.bin.json"]
    assert result["total"] == 3
    assert result["tiers"] == {"silver": 1, "gold": 1, "prismatic": 1}
    assert result["source_verified"] is True
    assert result["live_popup_verified"] is False


def test_last_batch_covers_remainder_and_zero_is_not_absence(monkeypatch):
    hits = _mock_300_bin_index(monkeypatch)
    result = discover_patch_anvil_bins("16.23", start_index=280, max_bins=200)
    assert result["candidate_bin_files"] == 300
    assert result["scan_start_index"] == 280
    assert result["scan_stop_index_exclusive"] == 300
    assert result["scan_window_complete"] is True
    assert len(hits) == 20
    assert hits[0] == "mayhem-280.bin.json"
    assert hits[-1] == "mayhem-299.bin.json"
    assert result["total"] == 0
    assert result["source_verified"] is False
    assert result["scan_complete"] is False


def test_offset_outside_catalogue_never_misreports_full_scan(monkeypatch):
    hits = _mock_300_bin_index(monkeypatch)
    result = discover_patch_anvil_bins("16.23", start_index=350, max_bins=200)
    assert result["scan_start_index"] == 350
    assert result["scan_stop_index_exclusive"] == 350
    assert result["bin_files_inspected"] == 0
    assert result["source_verified"] is False
    assert result["scan_complete"] is False
    assert hits == []


def test_invalid_offsets_fail_before_any_network(monkeypatch):
    import requests
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs:
                        pytest.fail("invalid offset reached public network"))
    for invalid in (-1, 10001, True, 1.5):
        with pytest.raises(AnvilCatalogError):
            discover_patch_anvil_bins("16.23", start_index=invalid)


def test_real_keyword_false_positives_cannot_validate_anvils():
    from scripts.stat_anvil_catalog_report import summarize_public_anvil_references
    tft = summarize_public_anvil_references("game/gameplay.bin.json", {
        "TFT": {"name": "TFT17_MarketOffering_ComponentAnvil"}})
    cherry = summarize_public_anvil_references(
        "game/maps/modespecificdata/cherry.bin.json", {
            "DustToDiamonds": {"DataValues": [
                {"name": "AnvilsGranted", "values": [1]}]}})
    assert tft["top_level_anvil_data"] == 0
    assert cherry["top_level_anvil_data"] == 0
    assert not tft["catalogue_verified"]
    assert not cherry["catalogue_verified"]
