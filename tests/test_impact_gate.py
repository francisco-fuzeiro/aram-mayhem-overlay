"""Impact reaches the ±1 tier adjustment only after the holdout says enable."""
from fastapi.testclient import TestClient

from backend.tierdb import impact_holdout
from backend.tierdb.impact_gate import (
    ImpactGate, load_history_enabled, save_history_enabled,
)
from tests.test_impact_holdout import _rows


def test_gate_stays_off_without_enough_history():
    gate = ImpactGate(rows_source=lambda: _rows(5), prior_source=lambda: None)
    assert gate.refresh() == "insufficient_data"
    assert gate.lookup("c0", "s") is None and not gate.enabled


def test_gate_off_when_holdout_keeps_it_off(monkeypatch):
    monkeypatch.setattr(impact_holdout, "evaluate", lambda rows, prior=None: {
        "verdict": "keep_off", "games": 300, "test_rows": 900})
    gate = ImpactGate(rows_source=lambda: _rows(300), prior_source=lambda: None)
    assert gate.refresh() == "keep_off"
    assert gate.lookup("c0", "s") is None


def test_gate_serves_impact_when_enabled(monkeypatch):
    monkeypatch.setattr(impact_holdout, "evaluate", lambda rows, prior=None: {
        "verdict": "enable", "games": 300, "test_rows": 900})
    gate = ImpactGate(rows_source=lambda: _rows(300), prior_source=lambda: None)
    assert gate.refresh() == "enable" and gate.enabled
    assert gate.lookup("c0", "s") > 0 > gate.lookup("c0", "w")
    status = gate.status()
    assert status["impact_active"] is True and "c0" not in str(status)


def test_gate_never_breaks_on_errors():
    def boom():
        raise RuntimeError("db gone")
    gate = ImpactGate(rows_source=boom, prior_source=lambda: None)
    assert gate.refresh() == "failed" and gate.lookup("c0", "s") is None


def test_history_switch_round_trip(tmp_path):
    path = tmp_path / "history.json"
    assert load_history_enabled(path) is False
    save_history_enabled(True, path)
    assert load_history_enabled(path) is True
    save_history_enabled(False, path)
    assert load_history_enabled(path) is False


def test_settings_switch_allows_import(monkeypatch, tmp_path):
    from backend.api import server
    from backend.storage import history_import
    from backend.tierdb import impact_gate as gate_mod
    path = tmp_path / "history.json"
    monkeypatch.setattr(gate_mod, "HISTORY_PREFERENCES_FILE", path)
    monkeypatch.setattr(server, "load_history_enabled", lambda: load_history_enabled(path))
    monkeypatch.setattr(server, "save_history_enabled",
                        lambda v: save_history_enabled(v, path))
    monkeypatch.setattr(server.config, "_data", {
        **server.config._data, "lcu_history_enabled": False})
    monkeypatch.setattr(history_import, "sync_recent_mayhem_games",
                        lambda n: {"status": "ok", "imported": 0, "inspected": 0})
    monkeypatch.setattr(server.impact_gate, "_rows_source", lambda: [])
    with TestClient(server.app) as client:
        assert client.get("/api/history").json()["enabled"] is False
        assert client.post("/api/history/import").status_code == 403
        assert client.put("/api/history", json={"enabled": True}).json() == {"enabled": True}
        out = client.post("/api/history/import").json()
        assert out["status"] == "ok" and out["impact_verdict"] == "insufficient_data"


def test_offer_adjuster_passes_impact_only_when_enabled(monkeypatch):
    from types import SimpleNamespace

    from backend.api import server
    seen = []
    import backend.tierdb.context_adjust as ca
    real = ca.context_adjust

    def spy(*a, **kw):
        seen.append((kw.get("impact"), dict(kw["config"].weights)["impact"]))
        return real(*a, **kw)
    monkeypatch.setattr(ca, "context_adjust", spy)
    sd = SimpleNamespace(get_champion=lambda c: None, get_item=lambda i: None,
                         get_augment=lambda a: None)
    monkeypatch.setattr(server.impact_gate, "verdict", "keep_off")
    server._offer_context_adjuster("c0", [], {}, {}, sd)("s")
    monkeypatch.setattr(server.impact_gate, "verdict", "enable")
    monkeypatch.setattr(server.impact_gate, "_impact", {("c0", "s"): 0.8})
    server._offer_context_adjuster("c0", [], {}, {}, sd)("s")
    assert seen == [(None, 0.0), (0.8, 0.2)]
