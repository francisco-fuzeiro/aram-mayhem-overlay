"""The report names the running code version so a stale process is obvious."""
from backend import feature_diagnostics as fd


def test_report_shows_code_version_of_the_session(tmp_path):
    log = tmp_path / "events.jsonl"
    log.write_text(
        '{"timestamp":"t1","event":"session_start","code":"abc1234"}\n'
        '{"timestamp":"t2","event":"session_start"}\n', encoding="utf-8")
    report = fd.build_report(tmp_path)
    assert report["code"] is None
    assert "Running code: unknown (restart ARAM Oracle)" in fd.render_markdown(report)
    log.write_text('{"timestamp":"t1","event":"session_start","code":"965b6bf"}\n',
                   encoding="utf-8")
    assert "Running code: 965b6bf" in fd.render_markdown(fd.build_report(tmp_path))


def test_session_start_sha_is_whitelisted_and_validated():
    from backend.diagnostic_events import _clean
    assert _clean("session_start", {"code": "965b6bf"}) == {"code": "965b6bf"}
    assert _clean("session_start", {"code": "C:/Users/x"}) == {}
