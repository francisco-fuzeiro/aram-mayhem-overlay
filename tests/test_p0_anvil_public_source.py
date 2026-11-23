"""P0: public, patch-scoped AnvilData source, not a live popup.

These synthetic fixtures exercise the structure found in public CommunityDragon
AnvilData/spell bins; no game or account access is required.
"""
from backend.static_data.anvil_public_catalog import (
    AnvilCatalogError, parse_public_bins, match_verified_shard_offer,
    parse_public_stringtable, summarize_anvil_source,
)
import pytest


def _fixture():
    return {
        "{spell_s}": {"__type": "SpellObject", "mSpell": {"DataValues": [
            {"name": "MinAR", "values": [12.0] * 7}]}},
        "{spell_g}": {"__type": "SpellObject", "mSpell": {"DataValues": [
            {"name": "MinAR", "values": [45.0] * 7}]}},
        "{spell_ap}": {"__type": "SpellObject", "mSpell": {"DataValues": [
            {"name": "MinAP", "values": [.50] * 7}]}},
        "{spell_ad}": {"__type": "SpellObject", "mSpell": {"DataValues": [
            {"name": "MinAD", "values": [35.0] * 7}]}},
        "{shard_s}": {"__type": "AnvilData",
            "AugmentNameId": "ARAM_StatAnvil_AR",
            "NameTra": "CHERRY_StatAnvil_AR_Name", "AnvilTypes": [0],
            "RootSpell": "{spell_s}"},
        "{shard_g}": {"__type": "AnvilData",
            "AugmentNameId": "ARAM_GoldStatAnvil_AR",
            "NameTra": "CHERRY_GoldStatAnvil_AR_Name", "AnvilTypes": [8],
            "RootSpell": "{spell_g}"},
        "{shard_ap}": {"__type": "AnvilData",
            "AugmentNameId": "ARAM_GoldStatAnvil_AP",
            "NameTra": "CHERRY_GoldStatAnvil_AP_Name", "AnvilTypes": [8],
            "RootSpell": "{spell_ap}"},
        "{shard_ad}": {"__type": "AnvilData",
            "AugmentNameId": "ARAM_GoldStatAnvil_AD",
            "NameTra": "CHERRY_GoldStatAnvil_AD_Name", "AnvilTypes": [8],
            "RootSpell": "{spell_ad}"},
        "{excluded}": {"__type": "AnvilData",
            "AugmentNameId": "ARAM_StatAnvil_Random",
            "NameTra": "CHERRY_Random", "AnvilTypes": [0],
            "RootSpell": "{spell_s}"},
        "{unrelated}": {"__type": "AugmentData", "AugmentNameId": "OTHER"},
    }


def test_public_bins_resolve_spell_tier_and_exclude_unavailable_shards():
    shards = parse_public_bins([_fixture()])
    assert len(shards) == 4
    assert "ARAM_StatAnvil_Random" not in {s.item_id for s in shards}
    assert {(s.tier, s.kind, s.values) for s in shards} >= {
        ("silver", "MinAR", (12.0,)), ("gold", "MinAR", (45.0,)),
        ("gold", "MinAP", (50.0,)), ("gold", "MinAD", (35.0,)),
    }
    assert all(s.name_key.startswith("cherry_") for s in shards)
    report = summarize_anvil_source(shards, "16.23")
    assert report["patch"] == "16.23"
    assert report["tiers"] == {"silver": 1, "gold": 3, "prismatic": 0}
    assert report["live_popup_verified"] is False
    assert report["rankings_verified"] is False


def test_public_bin_conflict_or_missing_spell_never_creates_a_shard():
    doc = _fixture()
    doc["{shard_g}"]["RootSpell"] = "{missing}"
    with pytest.raises(AnvilCatalogError):
        parse_public_bins([doc])
    doc = _fixture()
    doc["{shard_s}"]["AnvilTypes"] = [12345]
    with pytest.raises(AnvilCatalogError):
        parse_public_bins([doc])


def test_public_stringtable_matches_name_key_only_not_tier():
    shards = parse_public_bins([_fixture()])
    names = parse_public_stringtable({"entries": {
        "cherry_goldstatanvil_ar_name": "Armor Shard",
        "cherry_goldstatanvil_ap_name": "Ability Power Shard",
    }}, shards)
    assert names["ARAM_GoldStatAnvil_AR"] == "Armor Shard"
    assert names["ARAM_GoldStatAnvil_AP"] == "Ability Power Shard"
    assert "ARAM_StatAnvil_AR" not in names


def test_only_values_plus_stat_key_resolve_gold_offer_no_tier_guess():
    shards = parse_public_bins([_fixture()])
    matched = match_verified_shard_offer(shards, [
        ("MinAR", (45.0,)), ("MinAP", (50.0,)), ("MinAD", (35.0,)),
    ])
    assert matched is not None
    assert {s.tier for s in matched} == {"gold"}
    assert {s.item_id for s in matched} == {
        "ARAM_GoldStatAnvil_AR", "ARAM_GoldStatAnvil_AP",
        "ARAM_GoldStatAnvil_AD",
    }
    assert match_verified_shard_offer(shards, [
        ("MinAR", ()), ("MinAP", (50.0,)), ("MinAD", (35.0,)),
    ]) is None
    assert match_verified_shard_offer(shards, [
        ("MinAR", (12.0,)), ("MinAP", (50.0,)), ("MinAD", (35.0,)),
    ]) is None
    assert match_verified_shard_offer(shards, [
        ("MinAR", (45.0,)), ("MinAR", (45.0,)), ("MinAD", (35.0,)),
    ]) is None


def test_no_borrowed_competitor_rankings_or_screenshot_published():
    shards = parse_public_bins([_fixture()])
    report = summarize_anvil_source(shards, "16.23")
    assert "player" not in repr(report).lower()
    assert "win_rate" not in repr(report)
    assert report["rankings_verified"] is False
    assert report["live_popup_verified"] is False


def test_patch_pinned_public_source_opt_in_only_and_no_local_writes(monkeypatch):
    import requests
    from scripts.stat_anvil_catalog_report import public_patch_report
    called = []
    fixture = _fixture()

    class Response:
        def __init__(self, status, data=None):
            self.status_code = status
            self.data = data
        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError("remote request failed")
        def json(self):
            return self.data

    def fetch(url, timeout):
        called.append((url, timeout))
        assert url.startswith("https://raw.communitydragon.org/16.23/")
        if "map12.bin.json" in url or "statanvils.bin.json" in url:
            # Historical 16.22 layout: named path absent, hashed path present.
            return Response(404)
        if "507cdd64276919f5.bin.json" in url:
            return Response(200, fixture)
        if "lol.stringtable.json" in url:
            return Response(200, {"entries": {
                "cherry_goldstatanvil_ar_name": "Armor Shard",
                "cherry_goldstatanvil_ap_name": "Ability Power Shard",
            }})
        raise AssertionError("unapproved network URL")
    monkeypatch.setattr(requests, "get", fetch)
    report = public_patch_report("16.23", locale="en_us")
    assert report["total"] == 4
    assert report["public_bins"] == ["507cdd64276919f5.bin.json"]
    assert report["titles_found"] == 2
    assert report["titles_missing"] == 2
    assert report["live_popup_verified"] is False
    assert report["rankings_verified"] is False
    assert len(called) == 4


def test_bad_patch_or_locale_never_reaches_network(monkeypatch):
    import requests
    from scripts.stat_anvil_catalog_report import public_patch_report
    monkeypatch.setattr(requests, "get", lambda *args, **kw:
                        pytest.fail("network must not be used"))
    with pytest.raises(AnvilCatalogError):
        public_patch_report("16.23/../../private")
    with pytest.raises(AnvilCatalogError):
        public_patch_report("16.23", locale="this-is-not-a-locale")
