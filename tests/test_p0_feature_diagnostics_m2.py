"""P0 per-feature diagnostics RED: one-match-ready decisions, no user data.

No client, OCR screenshots, Riot calls or uncontrolled Mayhem. Tests pin closed
status/reason tuples at the actual parser/cache, build, and Voucher decision paths.
"""
import json
from types import SimpleNamespace

import pytest

from backend import feature_diagnostics as fd
from backend.static_data import loader
from backend.api.server import poll_tick
from tests.test_poll_tick_m1 import make_harness, make_snapshot


def _capture(monkeypatch):
    received = []
    monkeypatch.setattr(
        fd, "record",
        lambda feature, status, reason, count=None:
        received.append((feature, status, reason, count)) or True,
    )
    return received


def test_diagnostic_registry_has_all_current_p0_decisions():
    from backend.feature_registry import FEATURES, UI_FEATURES
    assert {"augment.stats_parser", "augment.cache_schema",
            "build.next_item", "anvil.voucher_purchase",
            "anvil.offer_detected", "anvil.offer_render"}.issubset(FEATURES)
    assert "anvil.offer_render" in UI_FEATURES


def test_parser_emits_modelled_and_unmodelled_without_raw_text(monkeypatch):
    got = _capture(monkeypatch)
    from backend.static_data.loader import _parse_description_to_stats_with_provenance
    unsupported, _ = _parse_description_to_stats_with_provenance(
        "Gain 30% Movement Speed.", "Synthetic Speed")
    supported, _ = _parse_description_to_stats_with_provenance(
        "Gain 30% Attack Speed.", "Synthetic AS")
    assert unsupported.hp == 0
    assert supported.attack_speed > 0
    assert ("augment.stats_parser", "skipped", "unmodelled", None) in got
    assert ("augment.stats_parser", "ok", "modelled", None) in got


def test_current_augment_cache_emits_exact_verdict(monkeypatch, tmp_path):
    got = _capture(monkeypatch)
    monkeypatch.setattr(loader, "_get_dd_version", lambda: "16.23.1")
    monkeypatch.setattr(loader, "CACHE_DIR", tmp_path)
    cache = tmp_path / "augments_v5_16.23.1.json"
    cache.write_text(json.dumps({"fixture": {"id": "fixture"}}), encoding="utf-8")
    monkeypatch.setattr(loader, "_parse_augment_cache", lambda _: {"fixture": object()})
    assert loader._load_augments()
    assert ("augment.cache_schema", "ok", "current", None) in got


def test_build_decision_records_concrete_exclusion(monkeypatch):
    got = _capture(monkeypatch)
    from backend.workflow.pipeline import _record_next_item_decision
    verified = SimpleNamespace(availability="verified_two_source")
    _record_next_item_decision(SimpleNamespace(
        next_item_id="3031", slot_blocked=False,
        build_unavailable_reason=None), verified)
    _record_next_item_decision(SimpleNamespace(
        next_item_id="3031", slot_blocked=True,
        build_unavailable_reason=None), verified)
    _record_next_item_decision(SimpleNamespace(
        next_item_id=None, slot_blocked=False,
        build_unavailable_reason="inventory_unknown"), verified)
    _record_next_item_decision(SimpleNamespace(
        next_item_id=None, slot_blocked=False,
        build_unavailable_reason=None), None)
    assert got == [
        ("build.next_item", "ok", "ranked", None),
        ("build.next_item", "skipped", "slot_blocked", None),
        ("build.next_item", "skipped", "inventory_unknown", None),
        ("build.next_item", "skipped", "unverified", None),
    ]


@pytest.mark.asyncio
async def test_real_poll_observer_emits_voucher_edge_but_no_fake_popup(monkeypatch):
    got = _capture(monkeypatch)
    frames = [make_snapshot(level=1) for _ in range(3)]
    for frame, vouchers in zip(frames, ({}, {"220008": 1}, {"220008": 1})):
        frame.anvil_vouchers = vouchers
    state, deps, messages = make_harness(
        [{"tick": i} for i in range(3)], frames, ocr=True)
    for i in range(3):
        await poll_tick(state, deps, float(i + 10))
    assert state.anvil_voucher_purchase_events == 1
    assert ("anvil.voucher_purchase", "ok", "positive_edge", 1) in got
    assert ("anvil.offer_detected", "skipped", "popup_unverified", None) in got
    assert not any(row[0] == "anvil.offer_detected" and row[1] == "ok" for row in got)
    assert state.augment_choices == []
    assert not any(msg.get("type") == "ocr_result" and
                   msg.get("status") == "detected" for msg in messages)


def test_reasons_closed_and_private_keys_rejected():
    from backend.feature_registry import FEATURES, REASONS
    from backend.diagnostic_events import _clean
    assert "build.next_item" in FEATURES
    assert "ranked" in REASONS
    assert _clean("feature", {
        "feature": "build.next_item", "status": "ok", "reason": "ranked",
        "path": "PRIVATE_PATH", "riot_id": "PRIVATE_ID",
        "ocr_text": "PRIVATE_TEXT",
    }) == {"feature": "build.next_item", "status": "ok", "reason": "ranked"}
