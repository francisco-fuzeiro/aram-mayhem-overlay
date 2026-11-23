"""Per-feature diagnostics and the post-session report.

Each feature records ``(feature, status, reason[, count])`` into the existing
whitelisted local journal (``events.jsonl``). After one test match,
``python -m backend.feature_diagnostics`` says per feature: ok / failed /
skipped / not fired, and why. Only registry enums and small counts are
stored: no names, Riot IDs, paths, OCR text or win rates.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from backend.diagnostic_events import default_log_dir, events
from backend.feature_registry import FEATURES, REASONS, STATUSES, UI_FEATURES, allowed_outcome

__all__ = ["FEATURES", "UI_FEATURES", "record", "session_start", "build_report",
           "render_markdown", "main"]


def _valid(feature, status, reason, count) -> bool:
    return (allowed_outcome(feature, status, reason) and
            (count is None or (type(count) is int and 0 <= count <= 1000)))


def record(feature: str, status: str, reason: str, count: int | None = None) -> bool:
    """Record a feature outcome; consecutive duplicates are suppressed. Never raises."""
    if not _valid(feature, status, reason, count):
        return False
    fields = {"feature": feature, "status": status, "reason": reason}
    if count is not None:
        fields["count"] = count
    try:
        return bool(events.transition("feature", **fields))
    except Exception:  # diagnostics must never break the feature itself
        return False


def session_start() -> bool:
    try:
        return bool(events.emit("session_start"))
    except Exception:
        return False


def _read_records(log_dir: Path) -> list[dict]:
    files = sorted(log_dir.glob("events.jsonl.*"),
                   key=lambda p: -int(p.suffix[1:]) if p.suffix[1:].isdigit() else 0)
    files.append(log_dir / "events.jsonl")
    out = []
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict):
                out.append(rec)
    return out


def build_report(log_dir: Path | None = None) -> dict:
    """Summarise the last session (records after the last ``session_start``)."""
    records = _read_records(Path(log_dir) if log_dir is not None else default_log_dir())
    starts = [i for i, r in enumerate(records) if r.get("event") == "session_start"]
    session = records[starts[-1] + 1:] if starts else records
    started_at = records[starts[-1]].get("timestamp") if starts else None
    features = []
    for feature, (expected, description) in FEATURES.items():
        rows = [r for r in session if r.get("event") == "feature" and
                r.get("feature") == feature]
        reasons = Counter(f"{r.get('status')}/{r.get('reason')}" for r in rows)
        statuses = {r.get("status") for r in rows}
        verdict = ("not_fired" if not rows else "ok" if "ok" in statuses
                   else "failed" if "failed" in statuses else "skipped")
        last = rows[-1] if rows else None
        features.append({
            "feature": feature, "description": description, "expected": expected,
            "verdict": verdict, "reasons": dict(reasons),
            "last": None if last is None else {
                k: last.get(k) for k in ("timestamp", "status", "reason", "count")},
        })
    return {"session_started_at": started_at, "features": features}


_LABEL = {"ok": "OK", "failed": "FAILED", "skipped": "SKIPPED", "not_fired": "NOT FIRED"}


def render_markdown(report: dict) -> str:
    lines = ["# Feature report (last session)", "",
             f"Session start: {report.get('session_started_at') or 'unknown'}", "",
             "| Feature | Verdict | Expected | Reasons (status/reason: times) |",
             "| --- | --- | --- | --- |"]
    for f in report["features"]:
        verdict = _LABEL[f["verdict"]]
        if f["expected"] and f["verdict"] in ("not_fired", "failed"):
            verdict = "**" + verdict + "**"
        reasons = ", ".join(f"{k}: {v}" for k, v in sorted(f["reasons"].items())) or "-"
        lines.append(f"| `{f['feature']}` | {verdict} | {'yes' if f['expected'] else 'no'} "
                     f"| {reasons} |")
    lines += ["", "Only enumerated ids and counts are logged: safe to paste in a chat or issue."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.feature_diagnostics",
                                     description=__doc__.splitlines()[0])
    parser.add_argument("--log-dir", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    report = build_report(args.log_dir)
    text = json.dumps(report, indent=2) if args.json else render_markdown(report)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
