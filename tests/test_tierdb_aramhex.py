"""F2 AramHex importer.

Fixtures are SYNTHETIC: tiny made-up numbers written in the real AramHex
layout (verified on 2026-11-23 against czgreat/aramhex-data 16.23/normal).
They are not real statistics.
"""
import hashlib
import json

import pytest

from backend.tierdb.aramhex import (
    AramhexFormatError,
    LicenseError,
    ingest_aramhex,
    load_aramhex_dataset,
)
from backend.tierdb.store import TierStore

ALIASES = {"1": "annie", "10": "kayle"}


def _write_dataset(directory, *, mode="normal", license_="CC BY-NC 4.0",
                   corrupt=None, extra_hero=False):
    directory.mkdir(parents=True, exist_ok=True)
    heroes = {
        "1": {"games": 1000, "wins": 500, "win_rate": 0.5, "pick_rate": 0.01,
              "rank": 2, "name": "x", "title": "y", "low_sample": False},
        "10": {"games": 2000, "wins": 1100, "win_rate": 0.55, "pick_rate": 0.02,
               "rank": 1, "name": "x", "title": "y", "low_sample": False},
    }
    if extra_hero:
        heroes["999"] = {"games": 10, "wins": 5, "win_rate": 0.5, "pick_rate": 0.0,
                         "rank": 3, "name": "x", "title": "y", "low_sample": True}
    hero_augments = {
        "1": {
            "1001": {"games": 300, "wins": 180, "win_rate": 0.6, "low_sample": True},
            "1337": {"games": 50, "wins": 10, "win_rate": 0.2, "low_sample": True},
            "4242": {"games": 40, "wins": 20, "win_rate": 0.5, "low_sample": True},
        },
        "10": {
            "1001": {"games": 400, "wins": 200, "win_rate": 0.5, "low_sample": True},
            "1002": {"games": 500, "wins": 300, "win_rate": 0.6, "low_sample": True},
        },
    }
    augments = {
        "1001": {"name": "a", "rarity": "prismatic"},
        "1002": {"name": "b", "rarity": "gold"},
        "1337": {"name": "c", "rarity": "silver"},
    }
    payloads = {
        "heroes.json": json.dumps(heroes).encode(),
        "hero_augments.json": json.dumps(hero_augments).encode(),
        "augments.json": json.dumps(augments).encode(),
    }
    files = {}
    for name, data in payloads.items():
        (directory / name).write_bytes(data)
        # Real meta.json format (verified 16.23/normal): name -> sha256 string.
        files[name] = hashlib.sha256(data).hexdigest()
    if corrupt:
        (directory / corrupt).write_bytes(payloads[corrupt] + b" ")
    meta = {
        "schema_version": 1,
        "patch": "16.23",
        "mode": mode,
        "license": license_,
        "low_sample_threshold": 3000,
        "excluded_augments": {"1337": "quest augment replaced on completion"},
        "regions": ["r1", "r2"],
        "regions_combined": True,
        "snapshot_at": "2026-11-20T08:00:00+08:00",
        "window": {"start": "2026-11-19T07:05:34+08:00",
                   "end_exclusive": "2026-11-20T08:00:00+08:00"},
        "augment_exposure": "held at game end, deduplicated per player",
        "matches": {"collected": 10, "valid": 9},
        "files": files,
    }
    (directory / "meta.json").write_text(json.dumps(meta))
    return directory


def test_parses_champion_and_pair_observations(tmp_path):
    ds = load_aramhex_dataset(_write_dataset(tmp_path / "d"), ALIASES)
    assert ds.snapshot.patch == "16.23"
    assert ds.snapshot.window_start.startswith("2026-11-19")
    assert len(ds.snapshot.sha256) == 64
    assert ds.source.license == "CC-BY-NC-4.0"
    assert ds.source.commercial_ok is False
    assert "aramhex-data" in ds.source.attribution

    champs = {o.champion_id: o for o in ds.observations if o.scope == "champion"}
    assert champs["kayle"].wins == 1100 and champs["kayle"].n == 2000
    pairs = {(o.champion_id, o.augment_id): o for o in ds.observations if o.scope == "champ_aug"}
    assert pairs[("annie", "1001")].wins == 180
    assert pairs[("annie", "1001")].low_sample is True
    assert ds.augments["1002"] == ("b", "gold")


def test_excluded_and_unknown_augments_are_quarantined_not_dropped(tmp_path):
    ds = load_aramhex_dataset(_write_dataset(tmp_path / "d"), ALIASES)
    ids = {(o.champion_id, o.augment_id) for o in ds.observations if o.scope == "champ_aug"}
    assert ("annie", "1337") not in ids
    assert ("annie", "4242") not in ids
    reasons = " | ".join(f"{name}: {reason}" for name, reason in ds.quarantine)
    assert "1337" in reasons and "excluded" in reasons
    assert "4242" in reasons and "rarity" in reasons


def test_unmapped_champion_is_quarantined(tmp_path):
    ds = load_aramhex_dataset(_write_dataset(tmp_path / "d", extra_hero=True), ALIASES)
    assert all(o.champion_id != "999" for o in ds.observations)
    assert any("999" in name for name, _ in ds.quarantine)


def test_sha_mismatch_is_rejected(tmp_path):
    directory = _write_dataset(tmp_path / "d", corrupt="hero_augments.json")
    with pytest.raises(AramhexFormatError, match="SHA-256"):
        load_aramhex_dataset(directory, ALIASES)


def test_file_missing_from_manifest_is_rejected(tmp_path):
    directory = _write_dataset(tmp_path / "d")
    meta = json.loads((directory / "meta.json").read_text())
    del meta["files"]["heroes.json"]
    (directory / "meta.json").write_text(json.dumps(meta))
    with pytest.raises(AramhexFormatError, match="heroes.json"):
        load_aramhex_dataset(directory, ALIASES)


def test_event_mode_rejected_by_default(tmp_path):
    directory = _write_dataset(tmp_path / "d", mode="first-prismatic")
    with pytest.raises(AramhexFormatError, match="mode"):
        load_aramhex_dataset(directory, ALIASES)


def test_unexpected_license_is_rejected(tmp_path):
    directory = _write_dataset(tmp_path / "d", license_="All rights reserved")
    with pytest.raises(LicenseError):
        load_aramhex_dataset(directory, ALIASES)


def test_commercial_mode_excludes_non_commercial_source(tmp_path):
    store = TierStore(tmp_path / "t.sqlite")
    with pytest.raises(LicenseError):
        ingest_aramhex(store, _write_dataset(tmp_path / "d"), ALIASES, app_mode="commercial")
    assert store.observations(patch="16.23") == []
    store.close()


def test_ingest_stores_rarity_and_is_idempotent(tmp_path):
    store = TierStore(tmp_path / "t.sqlite")
    directory = _write_dataset(tmp_path / "d")
    first = ingest_aramhex(store, directory, ALIASES)
    second = ingest_aramhex(store, directory, ALIASES)
    assert first == second
    assert store.augment_rarities("16.23") == {"1001": "prismatic", "1002": "gold"}
    assert len(store.observations(patch="16.23", scope="champ_aug")) == 3
    quarantined = store.connection.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
    assert quarantined == 2
    store.close()
