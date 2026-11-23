"""I1: AramHex item, boots, core build and Weapon of Fate import (synthetic data)."""
import hashlib
import json

import pytest

from backend.tierdb.aramhex import AramhexFormatError, download_dataset, ingest_aramhex
from backend.tierdb.store import ItemObservation, ProvenanceError, TierStore
from tests.test_tierdb_aramhex import _write_dataset

ALIASES = {"1": "annie", "10": "kayle"}


def _add_item_files(directory, *, corrupt=None, unknown_hero=False):
    """Mirror the verified 16.23/normal item layout with synthetic numbers."""
    meta_path = directory / "meta.json"
    meta = json.loads(meta_path.read_text())
    payloads = {
        "item_metadata.json": {
            "3118": {"category": "complete_equipment", "types": ["SpellDamage"], "name": "x"},
            "4645": {"category": "complete_equipment", "types": ["SpellDamage"], "name": "x"},
            "3089": {"category": "complete_equipment", "types": ["SpellDamage"], "name": "x"},
            "3020": {"category": "other", "types": ["Boots", "MagicPenetration"], "name": "x"},
            "1001": {"category": "other", "types": ["Boots"], "name": "x"},
            "1026": {"category": "other", "types": ["SpellDamage"], "name": "x"},
        },
        "hero_items.json": {
            "1": {"3118": {"games": 900, "wins": 480, "low_sample": True},
                  "4645": {"games": 600, "wins": 290, "low_sample": True},
                  "3089": {"games": 0, "wins": 0, "low_sample": True}},
            "10": {"3118": {"games": 50, "wins": 25, "low_sample": True}},
        },
        "equipment_recommendation_heroes.json": {
            "1": {"games": 950, "wins": 470}, "10": {"games": 1800, "wins": 900}},
        "hero_item_holdings.json": {
            "1": {"3020": {"games": 700, "wins": 360}, "1001": {"games": 40, "wins": 15},
                  "1026": {"games": 300, "wins": 150}, "3118": {"games": 950, "wins": 500}},
        },
        "equipment_heroes.json": {"1": {"games": 990, "wins": 495}},
        "core_builds.json": {
            "1": [{"games": 400, "wins": 220, "items": ["3118", "4645", "3089"],
                   "ordered": True, "pick": 0.4, "win": 0.55}],
            "10": [],
        },
        "hero_augment_items.json": {
            "1": {"3081": {"baseline": {"games": 1000, "wins": 500},
                           "eligible_total": 80, "eligible_wins": 41,
                           "items": [{"item": "4645", "games": 30, "wins": 17}]}},
        },
    }
    if unknown_hero:
        payloads["hero_items.json"]["999"] = {"3118": {"games": 10, "wins": 5}}
    for name, payload in payloads.items():
        data = json.dumps(payload).encode()
        (directory / name).write_bytes(data)
        meta["files"][name] = hashlib.sha256(data).hexdigest()
        if name == corrupt:
            (directory / name).write_bytes(data + b" ")
    meta_path.write_text(json.dumps(meta))
    return directory


@pytest.fixture()
def store(tmp_path):
    s = TierStore(tmp_path / "t.sqlite")
    yield s
    s.close()


def _rows(store, scope, champion=None):
    return store.item_observations("16.23", scope=scope, champion_id=champion)


def test_items_boots_cores_and_destiny_are_imported(tmp_path, store):
    ds = _add_item_files(_write_dataset(tmp_path / "ds"))
    ingest_aramhex(store, ds, ALIASES)
    finals = {r.item_id: (r.wins, r.n) for r in _rows(store, "champ_item", "annie")}
    assert finals == {"3118": (480, 900), "4645": (290, 600)}  # zero-game rows skipped
    assert [(r.wins, r.n) for r in _rows(store, "champ_item_base", "annie")] == [(470, 950)]
    boots = {r.item_id for r in _rows(store, "champ_boots", "annie")}
    assert boots == {"3020", "1001"}  # only Boots-typed holdings
    assert [(r.wins, r.n) for r in _rows(store, "champ_boots_base", "annie")] == [(495, 990)]
    (core,) = _rows(store, "champ_core", "annie")
    assert core.items == ("3118", "4645", "3089") and core.ordered and core.value == 0.4
    assert _rows(store, "champ_core", "kayle") == []
    (fate,) = _rows(store, "champ_aug_item", "annie")
    assert (fate.augment_id, fate.item_id, fate.wins, fate.n) == ("3081", "4645", 17, 30)
    (base,) = _rows(store, "champ_aug_item_base", "annie")
    assert (base.augment_id, base.wins, base.n) == ("3081", 41, 80)
    assert all(r.source_name == "aramhex" for r in _rows(store, "champ_item"))


def test_item_metadata_is_kept(tmp_path, store):
    ds = _add_item_files(_write_dataset(tmp_path / "ds"))
    ingest_aramhex(store, ds, ALIASES)
    info = store.item_info("16.23")
    assert info["3020"] == ("other", ("Boots", "MagicPenetration"))
    assert info["3118"][0] == "complete_equipment"


def test_dataset_without_item_files_still_imports(tmp_path, store):
    ingest_aramhex(store, _write_dataset(tmp_path / "ds"), ALIASES)
    assert store.item_observations("16.23") == []
    assert store.observations("16.23", scope="champion")


def test_corrupt_item_file_is_refused(tmp_path, store):
    ds = _add_item_files(_write_dataset(tmp_path / "ds"), corrupt="core_builds.json")
    with pytest.raises(AramhexFormatError, match="core_builds.json"):
        ingest_aramhex(store, ds, ALIASES)


def test_unmapped_hero_in_item_tables_is_quarantined(tmp_path, store):
    ds = _add_item_files(_write_dataset(tmp_path / "ds"), unknown_hero=True)
    sid = ingest_aramhex(store, ds, ALIASES)
    reasons = [r[0] for r in store.connection.execute(
        "SELECT raw_name FROM quarantine WHERE snapshot_id=?", (sid,))]
    assert any("999" in r and "item" in r for r in reasons)


def test_reingest_is_idempotent_and_backfills_items(tmp_path, store):
    ds = _write_dataset(tmp_path / "ds")
    first = ingest_aramhex(store, ds, ALIASES)
    assert store.item_observations("16.23") == []
    # Same meta SHA would be a no-op; item files change meta, so build the
    # older-database case directly: items added to an existing snapshot once.
    ds2 = _add_item_files(_write_dataset(tmp_path / "ds2"))
    second = ingest_aramhex(store, ds2, ALIASES)
    third = ingest_aramhex(store, ds2, ALIASES)
    assert second == third and second != first
    assert len(_rows(store, "champ_item", "annie")) == 2


def test_item_observation_requires_provenance(store):
    with pytest.raises(ProvenanceError):
        store.ingest_items(1, [ItemObservation(scope="champ_item", champion_id="annie",
                                               item_id="3118", wins=5, n=0)])
    with pytest.raises(ProvenanceError):
        store.ingest_items(1, [ItemObservation(scope="champ_core", champion_id="annie",
                                               wins=5, n=10, items=())])
    with pytest.raises(ProvenanceError):
        store.ingest_items(1, [ItemObservation(scope="champ_item", champion_id="annie",
                                               wins=11, n=10, item_id="3118")])


def test_download_fetches_listed_item_files(tmp_path):
    src = _add_item_files(_write_dataset(tmp_path / "src"))
    fetched = []

    def fetch(url):
        fetched.append(url.rsplit("/", 1)[-1])
        return (src / url.rsplit("/", 1)[-1]).read_bytes()

    out = download_dataset("data-v20", "patches/16.23/normal", tmp_path / "out", fetch=fetch)
    assert {"core_builds.json", "hero_items.json", "item_metadata.json"} <= set(fetched)
    assert (out / "hero_augment_items.json").exists()
