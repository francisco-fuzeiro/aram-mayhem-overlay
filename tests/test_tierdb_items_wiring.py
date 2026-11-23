"""I2-I5 wiring: pipeline tables, export without win data, provider, overlay payload."""
import json

import pytest

from backend.api import server
from backend import feature_diagnostics as fd
from backend.models import ChampionMeta, ItemData, StatVector
from backend.tierdb import service as tier_service
from backend.tierdb.aramhex import ingest_aramhex
from backend.tierdb.augment_tiers import AugmentTierConfig
from backend.tierdb.champion_tiers import ChampionTierConfig
from backend.tierdb.export import FORBIDDEN_KEYS, export_run
from backend.tierdb.item_tiers import ItemTierConfig
from backend.tierdb.pipeline import ItemInputs, run_build
from backend.tierdb.runtime import TierListProvider, save_empirical_tiers_enabled
from backend.tierdb.store import TierStore
from tests.test_tierdb_aramhex import _write_dataset
from tests.test_tierdb_items_import import ALIASES, _add_item_files

FAST = dict(aug_config=AugmentTierConfig(draws=50), champ_config=ChampionTierConfig(draws=50),
            item_config=ItemTierConfig(draws=50))
ELIGIBLE = {"3118", "4645", "3089", "6655"}
INPUTS = ItemInputs(eligible=ELIGIBLE, boots_eligible={"3020"}, canonical=lambda x: x,
                    fit={}, item_types=None)


@pytest.fixture()
def built(tmp_path):
    store = TierStore(tmp_path / "t.sqlite")
    ingest_aramhex(store, _add_item_files(_write_dataset(tmp_path / "ds")), ALIASES)
    run_id = run_build(store, "16.23", {"annie": "mage", "kayle": "fighter"},
                       items=INPUTS, **FAST)
    yield store, run_id
    store.close()


def _walk(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v)


def test_pipeline_writes_item_tiers_reference_and_demand(built):
    store, run_id = built
    con = store.connection
    items = {r[0] for r in con.execute(
        "SELECT item_id FROM item_tier WHERE run_id=? AND champion_id='annie' AND kind='final'",
        (run_id,))}
    assert items == ELIGIBLE  # observed eligible + eligible without data
    ref = [r[0] for r in con.execute(
        "SELECT item_id FROM reference_build WHERE run_id=? AND champion_id='annie' "
        "ORDER BY slot", (run_id,))]
    assert ref[:3] == ["3118", "4645", "3089"]
    demand = dict(con.execute(
        "SELECT stat, weight FROM champion_stat_demand WHERE run_id=? AND champion_id='annie'",
        (run_id,)))
    assert max(demand, key=demand.get) == "ap"
    cfg = json.loads(con.execute("SELECT thresholds_json FROM tier_run WHERE id=?",
                                 (run_id,)).fetchone()[0])
    assert cfg["item_config"]["weights"] == {"win": 50, "core": 30, "fit": 20}


def test_pipeline_without_item_inputs_skips_items(tmp_path):
    store = TierStore(tmp_path / "t.sqlite")
    ingest_aramhex(store, _add_item_files(_write_dataset(tmp_path / "ds")), ALIASES)
    run_id = run_build(store, "16.23", {"annie": "mage"}, **FAST)
    assert store.connection.execute(
        "SELECT COUNT(*) FROM item_tier WHERE run_id=?", (run_id,)).fetchone()[0] == 0
    store.close()


def test_export_carries_items_without_win_data(built, tmp_path):
    store, run_id = built
    doc = export_run(store, run_id, tmp_path / "tierlist.json")
    keys = {k.lower() for k in _walk(doc)} | {c.lower() for c in doc["item_columns"]}
    assert not keys & FORBIDDEN_KEYS
    annie = doc["items"]["annie"]
    assert set(annie) >= {"final", "boots", "reference", "boots_reference", "stat_demand",
                          "fate"}
    assert annie["reference"][:3] == ["3118", "4645", "3089"]
    assert annie["fate"] == {"3081": ["4645"]}


def test_provider_items_follow_the_switch(built, tmp_path):
    store, run_id = built
    path = tmp_path / "tierlist.json"
    export_run(store, run_id, path)
    on = {"v": True}
    p = TierListProvider(path, enabled=lambda: on["v"])
    items = p.items("annie")
    assert items["final"]["3118"]["rank_total"] == len(ELIGIBLE)
    assert items["reference"][0] == "3118"
    on["v"] = False
    assert p.items("annie") is None


def _sd():
    class SD:
        _items = {
            "3118": ItemData("3118", "Malignance", 3000, StatVector(ap=1)),
            "4645": ItemData("4645", "Shadowflame", 3000, StatVector(ap=1)),
            "3089": ItemData("3089", "Rabadon", 3600, StatVector(ap=1)),
            "6655": ItemData("6655", "Anti-heal AP", 3000, StatVector(ap=1),
                             properties=frozenset({"anti_heal", "magic_pen"})),
            "3020": ItemData("3020", "Sorcerer's Shoes", 1100, StatVector(), boots=True),
        }
        _augments = {}

        def get_item(self, i):
            return self._items.get(i)

        def get_champion(self, c):
            return ChampionMeta(c, c.title(), StatVector(ap=1), role="mage")

        def get_augment(self, a):
            return None

        exclusive_item_groups = {}
    return SD()


def test_overlay_payload_reference_adapted_and_anvils(built, tmp_path, monkeypatch):
    store, run_id = built
    path = tmp_path / "tierlist.json"
    export_run(store, run_id, path)
    svc = tier_service.TierListService(export_path=path, preferences_path=tmp_path / "p.json",
                                       db_path=tmp_path / "x.sqlite")
    monkeypatch.setattr(server, "tier_service", svc)
    calm = server._mayhem_build_payload("annie", [], [], {}, {}, _sd())
    assert [i["id"] for i in calm["reference"]][:3] == ["3118", "4645", "3089"]
    assert calm["swaps"] == [] and calm["adapted"] == calm["reference"]
    assert calm["anvil_stats"][0]["stat"] == "ap"
    assert calm["anvil_stats"][0]["level"] == "estimate"
    heal = {"enemies_analyzed": 5, "sustain_pressure": 0.8, "healing_items": 3,
            "magic_pressure": 0.8, "physical_pressure": 0.2}
    hot = server._mayhem_build_payload("annie", [], [], heal, {}, _sd())
    assert any(s["in"] == "6655" for s in hot["swaps"])
    assert hot["adapted"][0] == hot["reference"][0]
    assert all(set(s) == {"slot", "out", "in", "out_name", "in_name", "reason"}
               for s in hot["swaps"])
    assert not {k.lower() for k in _walk(hot)} & {"win_rate", "wins", "games", "n"}
    save_empirical_tiers_enabled(False, tmp_path / "p.json")
    assert server._mayhem_build_payload("annie", [], [], {}, {}, _sd()) is None


def test_overlay_payload_is_diagnosed(built, tmp_path, monkeypatch):
    store, run_id = built
    path = tmp_path / "tierlist.json"
    export_run(store, run_id, path)
    svc = tier_service.TierListService(export_path=path, preferences_path=tmp_path / "p.json",
                                       db_path=tmp_path / "x.sqlite")
    monkeypatch.setattr(server, "tier_service", svc)
    seen = []
    monkeypatch.setattr(fd, "record", lambda *a, **k: seen.append(a) or True)
    server._mayhem_build_payload("annie", [], [], {}, {}, _sd())
    assert ("items.reference_build", "ok", "attached") in [s[:3] for s in seen]
    assert ("anvil.stat_estimate", "ok", "estimated") in [s[:3] for s in seen]
    server._mayhem_build_payload("zed", [], [], {}, {}, _sd())
    assert seen[-1][:3] in {("items.reference_build", "failed", "champion_not_in_tierlist"),
                            ("anvil.stat_estimate", "skipped", "no_demand")}


def test_registry_has_item_and_anvil_features():
    from backend.feature_registry import FEATURES, UI_FEATURES, allowed_outcome
    assert {"items.reference_build", "items.build_render", "anvil.stat_estimate"} <= set(FEATURES)
    assert "items.build_render" in UI_FEATURES
    assert allowed_outcome("items.reference_build", "ok", "attached")
