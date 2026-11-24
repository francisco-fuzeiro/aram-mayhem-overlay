"""Champion tiers pool the previous patch; augments stay on this patch (owner 24/11)."""
import json

from backend.tierdb.augment_tiers import AugmentTierConfig
from backend.tierdb.champion_tiers import ChampionTierConfig
from backend.tierdb.pipeline import run_build
from backend.tierdb.service import previous_dataset
from backend.tierdb.store import Observation, SnapshotMeta, SourceMeta, TierStore

SRC = SourceMeta(name="aramhex", url="https://example.invalid", license="CC-BY-NC-4.0",
                 attribution="Synthetic", commercial_ok=False)
CHAMPS = ["ahri", "garen", "lux", "jinx"]
AUGS = {"1001": "gold", "1002": "gold", "1003": "silver"}
FAST = dict(aug_config=AugmentTierConfig(draws=100), champ_config=ChampionTierConfig(draws=100))
ROLES = {"ahri": "mage", "lux": "mage", "garen": "fighter", "jinx": "marksman"}


def _ingest(store, patch, champ_wins, sha):
    obs = []
    for c, w in zip(CHAMPS, champ_wins):
        obs.append(Observation(scope="champion", metric="win", champion_id=c, wins=w, n=10000))
        for j, a in enumerate(sorted(AUGS)):
            obs.append(Observation(scope="champ_aug", metric="win", champion_id=c,
                                   augment_id=a, wins=480 + 20 * j, n=1000))
    store.ingest(SRC, SnapshotMeta(patch=patch, region="test", sha256=sha), obs,
                 augments={a: (a, r) for a, r in AUGS.items()})


def _tables(store, run_id):
    con = store.connection
    champs = dict(con.execute("SELECT champion_id, rank FROM champion_tier WHERE run_id=?",
                              (run_id,)).fetchall())
    augs = con.execute("SELECT champion_id, augment_id, rank_all, effect_pp FROM augment_tier"
                       " WHERE run_id=? ORDER BY 1, 2", (run_id,)).fetchall()
    return champs, augs


def test_previous_patch_moves_champions_but_not_augments(tmp_path):
    store = TierStore(tmp_path / "t.sqlite")
    _ingest(store, "16.23", [5000, 5050, 5100, 5150], "a" * 64)
    alone = run_build(store, "16.23", ROLES, champion_pool_patches=(), **FAST)
    # A much larger previous patch where the order is reversed.
    _ingest(store, "16.22", [9000, 6000, 4000, 1000], "b" * 64)
    pooled = run_build(store, "16.23", ROLES, **FAST)
    champs_alone, augs_alone = _tables(store, alone)
    champs_pooled, augs_pooled = _tables(store, pooled)
    assert champs_alone["jinx"] == 1 and champs_pooled["ahri"] == 1
    assert augs_alone == augs_pooled
    meta = json.loads(store.connection.execute(
        "SELECT thresholds_json FROM tier_run WHERE id=?", (pooled,)).fetchone()[0])
    assert [p["patch"] for p in meta["champion_pool"]] == ["16.22"]
    store.close()


def test_only_older_patches_are_pooled(tmp_path):
    store = TierStore(tmp_path / "t.sqlite")
    _ingest(store, "16.22", [5000, 5050, 5100, 5150], "a" * 64)
    _ingest(store, "16.23", [9000, 6000, 4000, 1000], "b" * 64)
    run = run_build(store, "16.22", ROLES, **FAST)
    meta = json.loads(store.connection.execute(
        "SELECT thresholds_json FROM tier_run WHERE id=?", (run,)).fetchone()[0])
    assert meta["champion_pool"] == []
    store.close()


def test_previous_dataset_picks_the_newest_older_normal_patch():
    index = {"datasets": [
        {"patch": "16.23", "mode": "first-prismatic", "path": "patches/16.23/first-prismatic"},
        {"patch": "16.23", "mode": "normal", "path": "patches/16.23/normal"},
        {"patch": "16.22", "mode": "normal", "path": "patches/16.22/normal"},
        {"patch": "16.21", "mode": "normal", "path": "patches/16.21-prehotfix/normal"},
        {"patch": "16.20", "mode": "normal", "path": "patches/16.21-pbe/normal",
         "provisional": {"augments": 38}},
        {"patch": "16.21", "mode": "normal", "path": "patches/16.21/normal"},
    ]}
    assert previous_dataset("x", "16.23", fetch_index=lambda: index) == "patches/16.22/normal"
    assert previous_dataset("x", "16.22", fetch_index=lambda: index) == "patches/16.21/normal"
    assert previous_dataset("x", "16.19", fetch_index=lambda: index) is None
