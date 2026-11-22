"""F0: expose matcher acceptance/rejection causes without preserving OCR text."""
from backend.collectors import slot_title_ocr as matcher


def test_title_matcher_reports_per_slot_acceptance_and_uncertainty(monkeypatch):
    events = []
    monkeypatch.setattr(
        matcher, "emit_f0_trace",
        lambda *args, **kwargs: events.append((args, kwargs)),
        raising=False,
    )
    catalog = {"10001": "Stalwart Guard", "10002": "Mystic Siphon"}
    assert matcher.strict_match_title(
        "Stalwart Guard", catalog, trace_slot="left"
    )[0] == "10001"
    assert events[-1] == (
        ("augment", "matching", "accepted", "title_matched"),
        {"source": "ocr", "slot": "left", "similarity": 100, "augment_id": "10001"},
    )
    assert matcher.strict_match_title("??", catalog, trace_slot="centre") is None
    assert events[-1][0] == ("augment", "matching", "unknown", "title_short")
    assert events[-1][1]["slot"] == "centre"
    assert matcher.strict_match_title(
        "Totally Different Title", catalog, trace_slot="right"
    ) is None
    assert events[-1][0] == (
        "augment", "matching", "rejected", "below_threshold"
    )
    assert matcher.strict_match_title(
        "Stalwart Guard", {}, trace_slot="left"
    ) is None
    assert events[-1][0] == (
        "augment", "matching", "unknown", "catalog_empty"
    )


def test_strict_matcher_remains_90_8_and_rejects_ambiguous_title(monkeypatch):
    events = []
    monkeypatch.setattr(
        matcher, "emit_f0_trace",
        lambda *args, **kwargs: events.append((args, kwargs)),
        raising=False,
    )
    assert matcher.MATCH_THRESHOLD == 90
    assert matcher.MIN_MARGIN == 8
    assert matcher.strict_match_title(
        "Unseen Force", {"10001": "Unseen Force", "10002": "Unseen Forces"},
        trace_slot="right",
    ) is None
    assert events[-1][0] == (
        "augment", "matching", "rejected", "insufficient_margin"
    )
