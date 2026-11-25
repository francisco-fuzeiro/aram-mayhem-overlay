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


_CODE: list = []


def code_version() -> str | None:
    """Short git commit of the running code, or None (packaged build, no git)."""
    if _CODE:
        return _CODE[0]
    _CODE.append(_git_sha())
    return _CODE[0]


def _git_sha() -> str | None:
    import subprocess
    root = Path(__file__).resolve().parents[1]
    try:
        out = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], cwd=root,
                             capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return None
    sha = out.stdout.strip()
    return sha if out.returncode == 0 and sha else None


def session_start() -> bool:
    try:
        sha = code_version()
        return bool(events.emit("session_start", **({"code": sha} if sha else {})))
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
    code = records[starts[-1]].get("code") if starts else None
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
    return {"session_started_at": started_at, "code": code, "features": features,
            "ocr_windows": _ocr_windows(session)}


def _ts(rec: dict):
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(rec.get("timestamp")))
    except ValueError:
        return None


def _ocr_windows(session: list[dict]) -> list[dict]:
    """Per augment window: seconds to the first read and time per scan stage.

    Only enumerated stages and durations (field 23/11: reads took 23 s to
    minutes; this shows whether the cards were absent, the game unfocused,
    the titles unreadable, ...)."""
    windows, cur, stage, since = [], None, None, None

    def close_stage(t):
        if cur is not None and stage is not None and since is not None and t is not None:
            cur["stages"][stage] = cur["stages"].get(stage, 0.0) + (t - since).total_seconds()

    for rec in session:
        t = _ts(rec)
        ev = rec.get("event")
        if ev == "ocr_window" and rec.get("state") == "opened":
            close_stage(t)
            cur = {"level": rec.get("level"), "opened": t, "first_read_s": None, "stages": {},
                   "ticks": [], "misses": {}}
            windows.append(cur)
            stage, since = None, t
        elif ev == "ocr_window" and rec.get("state") == "closed" and cur is not None:
            close_stage(t)
            cur["closed_reason"] = rec.get("reason")
            cur, stage, since = None, None, None
        elif ev == "ocr_tick" and cur is not None:
            # Field 24/11: how long each watcher tick took, and why captures missed.
            if isinstance(rec.get("total_ms"), int):
                cur["ticks"].append(rec["total_ms"])
            if rec.get("engine") in ("ppocrv4", "tesseract"):
                cur["engine"] = rec["engine"]
            if rec.get("reason"):
                key = f"{rec['reason']}/{rec.get('detail') or 'none'}"
                cur["misses"][key] = cur["misses"].get(key, 0) + 1
        elif ev == "ocr_scan_stage" and cur is not None:
            close_stage(t)
            stage, since = rec.get("stage"), t
            if stage == "titles_detected" and cur["first_read_s"] is None and t is not None:
                cur["first_read_s"] = round((t - cur["opened"]).total_seconds(), 1)
                waiting = sum(v for k, v in cur["stages"].items()
                              if k in ("cards_absent", "not_scanned"))
                # OCR's own share: time after the cards were on screen.
                cur["ocr_s"] = round(max(0.0, cur["first_read_s"] - waiting), 1)
    return [{"level": w["level"], "first_read_s": w["first_read_s"],
             "ocr_s": w.get("ocr_s"),
             "closed_reason": w.get("closed_reason"),
             "engine": w.get("engine"),
             "ticks": len(w["ticks"]),
             "tick_ms_median": (sorted(w["ticks"])[len(w["ticks"]) // 2]
                                if w["ticks"] else None),
             "capture_misses": dict(sorted(w["misses"].items())),
             "stages": {k: round(v, 1) for k, v in sorted(
                 w["stages"].items(), key=lambda kv: -kv[1])}} for w in windows]


_LABEL = {"ok": "OK", "failed": "FAILED", "skipped": "SKIPPED", "not_fired": "NOT FIRED"}


def render_markdown(report: dict) -> str:
    lines = ["# Feature report (last session)", "",
             f"Session start: {report.get('session_started_at') or 'unknown'}",
             f"Running code: {report.get('code') or 'unknown (restart ARAM Oracle)'}", "",
             "| Feature | Verdict | Expected | Reasons (status/reason: times) |",
             "| --- | --- | --- | --- |"]
    for f in report["features"]:
        verdict = _LABEL[f["verdict"]]
        if f["expected"] and f["verdict"] in ("not_fired", "failed"):
            verdict = "**" + verdict + "**"
        reasons = ", ".join(f"{k}: {v}" for k, v in sorted(f["reasons"].items())) or "-"
        lines.append(f"| `{f['feature']}` | {verdict} | {'yes' if f['expected'] else 'no'} "
                     f"| {reasons} |")
    if report.get("ocr_windows"):
        lines += ["", "| Augment window (level) | First read | OCR after cards shown | "
                  "Time per scan stage (s) | Ticks (median ms) | Capture misses | Closed |",
                  "| --- | --- | --- | --- | --- | --- | --- |"]
        for w in report["ocr_windows"]:
            first = "-" if w["first_read_s"] is None else f"{w['first_read_s']} s"
            stages = ", ".join(f"{k}: {v}" for k, v in list(w["stages"].items())[:4]) or "-"
            ocr = "-" if w.get("ocr_s") is None else f"{w['ocr_s']} s"
            ticks = (f"{w.get('ticks', 0)} ({w['tick_ms_median']}, {w.get('engine') or '?'})"
                     if w.get("tick_ms_median") is not None else "-")
            misses = ", ".join(f"{k}: {v}" for k, v in (w.get("capture_misses") or {}).items()) or "-"
            lines.append(f"| {w['level']} | {first} | {ocr} | {stages} | {ticks} | {misses} | "
                         f"{w.get('closed_reason') or '-'} |")
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
