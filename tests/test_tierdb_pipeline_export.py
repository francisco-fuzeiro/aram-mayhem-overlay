"""F6 build pipeline, overlay export, live kill switch (synthetic data)."""
import json

import pytest

from backend import preferences
from backend.tierdb.augment_tiers import AugmentTierConfig
from backend.tierdb.champion_tiers import ChampionTierConfig
from backend.tierdb.export import FORBIDDEN_KEYS, export_run
from backend.tierdb.pipeline import MultiSourceError, run_build
from backend.tierdb.runtime import (
    TierListProvider,
    load_empirical_tiers_enabled,
    save_empirical_tiers_enabled,
)
from backend.tierdb.store import Observation, SnapshotMeta, SourceMeta, TierStore

SRC = SourceMeta(name="aramhex", url="https://example.invalid", license="CC-BY-NC-4.0",
                 attribution="Synthetic fixture attribution", commercial_ok=False)
CHAMPS = ["ahri", "garen", "lux", "jinx"]
AUGS = {"1001": "gold", "1002": "gold", "1003": "gold", "1004": "silver", "1005": "prismatic"}
FAST = dict(aug_config=AugmentTierConfig(draws=100), champ_config=ChampionTierConfig(draws=100))


def _ingest(store, source=SRC, sha="c" * 64):
    obs = []
    for i, c in enumerate(CHAMPS):
        obs.append(Observation(scope="champion", metric="win", champion_id=c,
                               wins=5000 + 100 * i, n=10000))
        for j, a in enumerate(sorted(AUGS)):
            if (i + j) % 4 == 0:
                continue  # some pairs without data -> fallback levels
            obs.append(Observation(scope="champ_aug", metric="win", champion_id=c,
                                   augment_id=a, wins=500 + 20 * j, n=1000))
    return store.ingest(source, SnapshotMeta(patch="16.23", region="test", sha256=sha), obs,
                        augments={a: (a, r) for a, r in AUGS.items()})


@pytest.fixture()
def store(tmp_path):
    s = TierStore(tmp_path / "t.sqlite")
    _ingest(s)
    yield s
    s.close()


ROLES = {"ahri": "mage", "lux": "mage", "garen": "fighter", "jinx": "marksman"}


def test_build_writes_full_run(store):
    run_id = run_build(store, "16.23", ROLES, **FAST)
    con = store.connection
    n_aug = con.execute("SELECT COUNT(*) FROM augment_tier WHERE run_id=?", (run_id,)).fetchone()[0]
    n_champ = con.execute("SELECT COUNT(*) FROM champion_tier WHERE run_id=?", (run_id,)).fetchone()[0]
    assert n_aug == len(CHAMPS) * len(AUGS)
    assert n_champ == len(CHAMPS)
    weights = json.loads(con.execute("SELECT weights_json FROM tier_run WHERE id=?",
                                     (run_id,)).fetchone()[0])
    assert weights["augments"]["win"] == 50 and weights["champions"]["win"] == 50
    sources = con.execute("SELECT sources_json FROM augment_tier WHERE run_id=? LIMIT 1",
                          (run_id,)).fetchone()[0]
    assert "aramhex" in sources


def test_two_win_sources_for_one_patch_are_refused(store):
    other = SourceMeta(name="other", url="https://example.invalid/2", license="CC-BY-4.0",
                       attribution="x", commercial_ok=True)
    _ingest(store, source=other, sha="d" * 64)
    with pytest.raises(MultiSourceError):
        run_build(store, "16.23", ROLES, **FAST)


def test_commercial_build_excludes_nc_source(store):
    with pytest.raises(ValueError, match="no win data"):
        run_build(store, "16.23", ROLES, commercial_only=True, **FAST)


def _walk_keys(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk_keys(v)


def test_export_has_no_win_rate_or_sample_size(store, tmp_path):
    run_id = run_build(store, "16.23", ROLES, **FAST)
    doc = export_run(store, run_id, tmp_path / "tierlist.json")
    keys = {k.lower() for k in _walk_keys(doc)} | {c.lower() for c in doc["augment_columns"]}
    assert not keys & FORBIDDEN_KEYS
    text = (tmp_path / "tierlist.json").read_text(encoding="utf-8")
    assert '"wins"' not in text and "win_rate" not in text
    assert doc["sources"][0]["attribution"] == "Synthetic fixture attribution"
    assert doc["patch"] == "16.23"
    assert set(doc["augments"]["ahri"]) == {"gold", "silver", "prismatic"}


def test_provider_kill_switch_is_live(store, tmp_path):
    run_id = run_build(store, "16.23", ROLES, **FAST)
    path = tmp_path / "tierlist.json"
    export_run(store, run_id, path)
    enabled = {"value": True}
    provider = TierListProvider(path, enabled=lambda: enabled["value"])
    row = provider.augment_tier("ahri", "1002")
    assert set(row) == {"rank", "tie_group", "tier", "level", "confidence", "rarity"}
    assert provider.champion_tier("ahri")["tier"] in {"OP", "S", "A", "B", "C", "D", "E"}
    enabled["value"] = False  # no reload, no restart
    assert provider.augment_tier("ahri", "1002") is None
    assert provider.champion_tier("ahri") is None


def test_provider_without_export_is_empty(tmp_path):
    provider = TierListProvider(tmp_path / "missing.json", enabled=lambda: True)
    assert provider.augment_tier("ahri", "1002") is None


def test_tier_switch_defaults_on_and_is_separate_from_overlay_prefs(tmp_path):
    # Own file: the strict overlay preferences contract stays untouched.
    overlay_path, tier_path = tmp_path / "prefs.json", tmp_path / "tierlist_prefs.json"
    assert load_empirical_tiers_enabled(tier_path) is True
    preferences.save_overlay_preferences(dict(preferences.DEFAULT_OVERLAY, opacity=0.5), overlay_path)
    save_empirical_tiers_enabled(False, tier_path)
    assert load_empirical_tiers_enabled(tier_path) is False
    assert preferences.load_preferences(overlay_path)["overlay"]["opacity"] == 0.5
    with pytest.raises(ValueError):
        save_empirical_tiers_enabled("yes", tier_path)
    tier_path.write_text("not json", encoding="utf-8")
    assert load_empirical_tiers_enabled(tier_path) is True  # corrupt -> decided default


def test_cli_ingest_build_export_offline(tmp_path):
    from backend.tierdb.__main__ import main
    from tests.test_tierdb_aramhex import _write_dataset

    dataset = _write_dataset(tmp_path / "ds")
    aliases = tmp_path / "aliases.json"
    aliases.write_text(json.dumps({"1": "annie", "10": "kayle"}))
    db, out = tmp_path / "t.sqlite", tmp_path / "out.json"
    assert main(["--db", str(db), "ingest-aramhex", "--dir", str(dataset),
                 "--aliases", str(aliases)]) == 0
    s = TierStore(db)
    run_id = run_build(s, "16.23", {"annie": "mage", "kayle": "fighter"}, **FAST)
    s.close()
    assert main(["--db", str(db), "export", "--run", str(run_id), "--out", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["sources"][0]["name"] == "aramhex"
    assert "CC BY-NC 4.0" in doc["sources"][0]["attribution"]


def test_leverage_defaults_to_absolute_strength_with_best_offer(store):
    # Holdout 16.22->16.23 (F7): relative lift anti-correlates with winning;
    # absolute E[max of 3] strength keeps the composite within 0.02 of WR-only.
    run_id = run_build(store, "16.23", ROLES, **FAST)
    cfg = json.loads(store.connection.execute(
        "SELECT thresholds_json FROM tier_run WHERE id=?", (run_id,)).fetchone()[0])
    assert cfg["leverage_mode"] == "absolute"
    rel = run_build(store, "16.23", ROLES, leverage_mode="relative", **FAST)
    cfg = json.loads(store.connection.execute(
        "SELECT thresholds_json FROM tier_run WHERE id=?", (rel,)).fetchone()[0])
    assert cfg["leverage_mode"] == "relative"
    with pytest.raises(ValueError):
        run_build(store, "16.23", ROLES, leverage_mode="magic", **FAST)


def test_export_and_provider_carry_strength_and_potential(store, tmp_path):
    run_id = run_build(store, "16.23", ROLES, **FAST)
    doc = export_run(store, run_id, tmp_path / "tierlist.json")
    assert "potential" in doc["champion_columns"]
    provider = TierListProvider(tmp_path / "tierlist.json", enabled=lambda: True)
    row = provider.champion_tier("ahri")
    assert row["tier"] in {"OP", "S", "A", "B", "C", "D", "E"}  # strength
    levels = {"very_low", "low", "medium", "high", "very_high"}
    assert row["potential"] in levels | {None}
    stored = {r[0] for r in store.connection.execute(
        "SELECT potential FROM champion_tier WHERE run_id=?", (run_id,))}
    assert stored <= levels | {None} and stored - {None}
