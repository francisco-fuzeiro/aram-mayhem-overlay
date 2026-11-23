"""Per-feature diagnostics: one end-to-end match test must say which feature failed."""
import json

import pytest
from fastapi.testclient import TestClient

from backend import diagnostic_events, feature_diagnostics as fd
from backend.api import server
from backend.tierdb import service as tier_service
from backend.tierdb.runtime import TierListProvider, save_empirical_tiers_enabled
from tests.test_tierdb_overlay_integration import EXPORT


class Sink:
    def __init__(self):
        self.records = []

    def transition(self, event, **fields):
        self.records.append((event, fields))
        return True

    emit = transition

    def of(self, feature):
        return [f for e, f in self.records if e == "feature" and f["feature"] == feature]


@pytest.fixture()
def sink(monkeypatch):
    s = Sink()
    monkeypatch.setattr(fd, "events", s)
    return s


@pytest.fixture()
def tiers(tmp_path, monkeypatch):
    export = tmp_path / "tierlist.json"
    export.write_text(json.dumps(EXPORT), encoding="utf-8")
    svc = tier_service.TierListService(export_path=export,
                                       preferences_path=tmp_path / "p.json",
                                       db_path=tmp_path / "t.sqlite")
    monkeypatch.setattr(server, "tier_service", svc)
    return svc


def test_registry_ids_are_dotted_and_reasons_whitelisted():
    for feature in fd.FEATURES:
        area, _, name = feature.partition(".")
        assert area and name and feature == feature.lower()
    clean = diagnostic_events._clean("feature", {
        "feature": "tierdb.offer_tiers", "status": "ok", "reason": "tiers_attached",
        "count": 3, "path": "C:/Users/x"})
    assert clean == {"feature": "tierdb.offer_tiers", "status": "ok",
                     "reason": "tiers_attached", "count": 3}
    assert fd.record("tierdb.unknown", "ok", "tiers_attached") is False
    assert fd.record("tierdb.offer_tiers", "ok", "Ahri free text") is False


def test_transition_dedup_is_per_feature(tmp_path):
    log = diagnostic_events.StructuredEventLogger(tmp_path)
    log.start()
    for _ in range(3):
        log.transition("feature", feature="tierdb.offer_tiers", status="ok",
                       reason="tiers_attached", count=3)
        log.transition("feature", feature="tierdb.champselect_tiers", status="ok",
                       reason="annotated", count=5)
    log.stop()
    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def _write(dirpath, records):
    dirpath.mkdir(parents=True, exist_ok=True)
    with open(dirpath / "events.jsonl", "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps({"timestamp": "2026-11-23T20:00:00+00:00", **r}) + "\n")


def test_report_covers_last_session_and_flags_missing_features(tmp_path):
    _write(tmp_path, [
        {"event": "session_start"},
        {"event": "feature", "feature": "tierdb.load", "status": "failed",
         "reason": "export_missing"},
        {"event": "session_start"},
        {"event": "feature", "feature": "tierdb.load", "status": "ok", "reason": "loaded",
         "count": 172},
        {"event": "feature", "feature": "tierdb.offer_tiers", "status": "failed",
         "reason": "champion_not_in_tierlist"},
        {"event": "feature", "feature": "tierdb.offer_tiers", "status": "ok",
         "reason": "tiers_attached", "count": 3},
        {"event": "feature", "feature": "tierdb.champselect_tiers", "status": "skipped",
         "reason": "tiers_off"},
    ])
    report = fd.build_report(tmp_path)
    by = {f["feature"]: f for f in report["features"]}
    assert set(by) == set(fd.FEATURES)
    assert by["tierdb.load"]["verdict"] == "ok"
    assert by["tierdb.load"]["reasons"] == {"ok/loaded": 1}  # earlier session ignored
    assert by["tierdb.offer_tiers"]["verdict"] == "ok"
    assert by["tierdb.offer_tiers"]["reasons"]["failed/champion_not_in_tierlist"] == 1
    assert by["tierdb.champselect_tiers"]["verdict"] == "skipped"
    assert by["tierdb.offer_render"]["verdict"] == "not_fired"
    assert by["tierdb.offer_render"]["expected"] is True
    text = fd.render_markdown(report)
    assert "tierdb.offer_render" in text and "NOT FIRED" in text
    assert str(tmp_path) not in text


def test_report_without_log_is_all_not_fired(tmp_path):
    report = fd.build_report(tmp_path / "none")
    assert {f["verdict"] for f in report["features"]} == {"not_fired"}


def test_cli_writes_report(tmp_path, capsys):
    _write(tmp_path, [{"event": "session_start"},
                      {"event": "feature", "feature": "tierdb.load", "status": "ok",
                       "reason": "loaded", "count": 2}])
    out = tmp_path / "report.md"
    assert fd.main(["--log-dir", str(tmp_path), "--out", str(out)]) == 0
    assert "tierdb.load" in out.read_text(encoding="utf-8")


def test_offer_tiers_are_diagnosed(tiers, sink):
    server._augment_tier_payload("ahri", ["1001", "1003"])
    assert sink.of("tierdb.offer_tiers")[-1] == {
        "feature": "tierdb.offer_tiers", "status": "ok", "reason": "tiers_attached", "count": 2}
    server._augment_tier_payload("zed", ["1001"])
    assert sink.of("tierdb.offer_tiers")[-1]["reason"] == "champion_not_in_tierlist"
    assert sink.of("tierdb.offer_tiers")[-1]["status"] == "failed"
    server._augment_tier_payload("ahri", [])
    assert sink.of("tierdb.offer_tiers")[-1]["reason"] == "no_visible_augments"
    server._augment_tier_payload(None, ["1001"])
    assert sink.of("tierdb.offer_tiers")[-1]["reason"] == "no_champion"
    save_empirical_tiers_enabled(False, tiers.preferences_path)
    server._augment_tier_payload("ahri", ["1001"])
    assert sink.of("tierdb.offer_tiers")[-1] == {
        "feature": "tierdb.offer_tiers", "status": "skipped", "reason": "tiers_off"}


def test_offer_tiers_without_export_is_a_failure(tmp_path, monkeypatch, sink):
    svc = tier_service.TierListService(export_path=tmp_path / "missing.json",
                                       preferences_path=tmp_path / "p.json",
                                       db_path=tmp_path / "t.sqlite")
    monkeypatch.setattr(server, "tier_service", svc)
    server._augment_tier_payload("ahri", ["1001"])
    assert sink.of("tierdb.offer_tiers")[-1]["reason"] == "export_missing"
    assert sink.of("tierdb.load")[-1] == {"feature": "tierdb.load", "status": "failed",
                                         "reason": "export_missing"}


def test_provider_load_reports_invalid_and_loaded(tmp_path, sink):
    path = tmp_path / "tierlist.json"
    path.write_text("{broken", encoding="utf-8")
    TierListProvider(path, enabled=lambda: True).champion_tier("ahri")
    assert sink.of("tierdb.load")[-1]["reason"] == "export_invalid"
    path.write_text(json.dumps(EXPORT), encoding="utf-8")
    TierListProvider(path, enabled=lambda: True).champion_tier("ahri")
    assert sink.of("tierdb.load")[-1] == {"feature": "tierdb.load", "status": "ok",
                                         "reason": "loaded", "count": 2}


def test_champion_select_is_diagnosed(tiers, sink):
    server._annotate_champion_candidates({"candidates": [{"id": "ahri"}, {"id": "lux"}]})
    assert sink.of("tierdb.champselect_tiers")[-1] == {
        "feature": "tierdb.champselect_tiers", "status": "ok", "reason": "annotated", "count": 1}
    server._annotate_champion_candidates({"candidates": [{"id": "lux"}]})
    assert sink.of("tierdb.champselect_tiers")[-1]["reason"] == "no_candidate_in_tierlist"
    server._annotate_champion_candidates({"candidates": []})
    assert sink.of("tierdb.champselect_tiers")[-1]["reason"] == "no_candidates"


@pytest.mark.parametrize("exc,reason", [
    (ConnectionError("down"), "network"),
    (__import__("backend.tierdb.aramhex", fromlist=["x"]).AramhexFormatError("bad"),
     "bad_dataset"),
    (ValueError("no win data"), "build_failed"),
    (KeyError("x"), "unexpected"),
])
def test_update_failures_are_classified(tiers, sink, monkeypatch, exc, reason):
    def boom(**kwargs):
        raise exc
    monkeypatch.setattr(tier_service, "update_tierlist", boom)
    monkeypatch.setattr(tier_service, "static_inputs", lambda sd: ({}, {}))
    tiers.start_update(static_data=None)
    tiers.wait(5)
    assert sink.of("tierdb.update")[-1] == {"feature": "tierdb.update", "status": "failed",
                                           "reason": reason}


def test_switch_and_ui_acks(tiers, sink):
    client = TestClient(server.app)
    client.put("/api/tierlist", json={"enabled": False})
    assert sink.of("tierdb.switch")[-1] == {"feature": "tierdb.switch", "status": "ok",
                                           "reason": "disabled"}
    assert server._handle_feature_ack({"type": "feature_ack", "feature": "tierdb.offer_render",
                                       "status": "ok", "reason": "rendered", "count": 3})
    assert sink.of("tierdb.offer_render")[-1]["count"] == 3
    # Browser may only report UI features, never server-side ones.
    assert not server._handle_feature_ack({"feature": "tierdb.load", "status": "ok",
                                           "reason": "loaded"})
    assert not server._handle_feature_ack({"feature": "tierdb.offer_render", "status": "ok",
                                           "reason": "C:/Users/someone"})


def test_report_endpoint(tmp_path, monkeypatch):
    _write(tmp_path, [{"event": "session_start"}])
    monkeypatch.setattr(fd, "default_log_dir", lambda: tmp_path)
    body = TestClient(server.app).get("/api/diagnostics/features").json()
    assert {f["feature"] for f in body["features"]} == set(fd.FEATURES)
