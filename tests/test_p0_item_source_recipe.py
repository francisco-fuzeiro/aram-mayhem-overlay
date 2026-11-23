"""P0 #49: real DD omission of terminal into must not zero final items.

Tests-only RED: actual 16.23.1 DD omits 'into' for 104 terminal items;
patch-matched CDragon supplies explicit empty 'to'. Synthetic fixture copies
the same shape. No game data or network.
"""
from copy import deepcopy

from backend.static_data.item_policy import classify_item, sources_agree
from backend.static_data.loader import _load_items
from tests.test_item_pool_b1 import offline_loader, sources


def test_terminal_dd_omits_into_but_cd_explicit_to_empty():
    dd, cd, _ = sources()
    for ident in ("3031", "3089", "3074"):
        row = deepcopy(dd[ident])
        row.pop("into")
        assert cd[ident]["to"] == []
        assert row["from"] == cd[ident]["from"]
        assert sources_agree(row, cd[ident]) is True


def test_all_104_synthetic_finals_stay_verified_without_dd_into():
    dd, cd, _ = sources()
    ids = [ident for ident, row in dd.items()
           if classify_item(ident, row, cd.get(ident), {"force_class": {}})
           == "final"]
    assert len(ids) == 104
    for ident in ids:
        row = deepcopy(dd[ident])
        row.pop("into", None)
        assert sources_agree(row, cd[ident]) is True, ident


def test_recipe_absence_not_generalized_to_unsafe_cd_or_wrong_sources():
    dd, cd, _ = sources()
    row = deepcopy(dd["3031"])
    row.pop("into")
    other = deepcopy(cd["3031"])
    assert other["to"] == []

    del other["to"]
    assert sources_agree(row, other) is False
    other = deepcopy(cd["3031"])
    other["to"] = ["9999"]
    assert sources_agree(row, other) is False
    other = deepcopy(cd["3031"])
    other["priceTotal"] += 1
    assert sources_agree(row, other) is False
    other = deepcopy(cd["3031"])
    other["from"] = ["9999"]
    assert sources_agree(row, other) is False
    row.pop("from")
    assert sources_agree(row, cd["3031"]) is False


def test_item_pool_feature_reason_is_closed_and_privacy_safe(monkeypatch):
    from backend import feature_diagnostics
    from backend.feature_registry import FEATURES

    assert "build.item_pool" in FEATURES
    recorded = []
    monkeypatch.setattr(
        feature_diagnostics.events, "transition",
        lambda event, **fields: recorded.append((event, fields)) or True,
    )
    assert feature_diagnostics.record("build.item_pool", "ok", "final_items", 104)
    assert feature_diagnostics.record("build.item_pool", "failed", "no_final_items", 0)
    assert not feature_diagnostics.record("build.item_pool", "ok", "invented_reason")
    assert recorded == [
        ("feature", {"feature": "build.item_pool", "status": "ok",
                      "reason": "final_items", "count": 104}),
        ("feature", {"feature": "build.item_pool", "status": "failed",
                      "reason": "no_final_items", "count": 0}),
    ]


def test_item_loader_emits_diagnostic_from_verified_catalog(monkeypatch, tmp_path):
    from backend import feature_diagnostics

    observed = []
    monkeypatch.setattr(
        feature_diagnostics, "record",
        lambda feature, status, reason, count=None:
        observed.append((feature, status, reason, count)) or True,
    )
    offline_loader(monkeypatch, tmp_path)
    catalog = _load_items()
    assert catalog.meta.availability == "verified_two_source"
    assert ("build.item_pool", "ok", "final_items", 104) in observed
