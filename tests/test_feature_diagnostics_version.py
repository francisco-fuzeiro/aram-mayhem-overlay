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


def test_report_times_each_augment_window_by_scan_stage(tmp_path):
    rows = [
        ('2026-11-23T21:00:00+00:00', '"event":"session_start"'),
        ('2026-11-23T21:00:10+00:00', '"event":"ocr_window","state":"opened","reason":"level_due","level":3'),
        ('2026-11-23T21:00:10+00:00', '"event":"ocr_scan_stage","stage":"game_not_focused"'),
        ('2026-11-23T21:00:30+00:00', '"event":"ocr_scan_stage","stage":"titles_verifying"'),
        ('2026-11-23T21:00:33+00:00', '"event":"ocr_scan_stage","stage":"titles_detected"'),
        ('2026-11-23T21:00:40+00:00', '"event":"ocr_window","state":"closed","reason":"cursor_pick","level":3'),
    ]
    (tmp_path / "events.jsonl").write_text(
        "".join('{"timestamp":"%s",%s}\n' % r for r in rows), encoding="utf-8")
    report = fd.build_report(tmp_path)
    w = report["ocr_windows"][0]
    assert w["first_read_s"] == 23.0 and w["stages"]["game_not_focused"] == 20.0
    assert w["closed_reason"] == "cursor_pick"
    md = fd.render_markdown(report)
    assert "| 3 | 23.0 s | game_not_focused: 20.0" in md
