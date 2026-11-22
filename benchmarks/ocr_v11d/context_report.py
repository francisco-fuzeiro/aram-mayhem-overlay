"""Private case-level OCR evidence grouped by human capture context.

Read-only post-processing of the existing V1.1c result and sealed manifest.
Never runs OCR, networks, uploads, accesses the game or guesses labels.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

FIELDS = ("category", "slot", "rarity", "two_line", "scene", "reroll",
          "focus", "opgg", "resolution", "dpi")
STATUSES = frozenset(("correct", "correct_rejection", "wrong_id",
                      "false_positive", "false_rejection"))


def summarize_context(csv_path: Path, manifest_path: Path, report_path: Path) -> dict:
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    by_file = {row["file"]: row for row in rows}
    if len(by_file) != len(rows):
        raise ValueError("duplicate files in private human labels")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    samples = manifest.get("samples", [])
    if not samples or report.get("independent_samples") != len(samples):
        raise ValueError("missing/mismatched evaluated independent sample count")
    joined = []
    for item in samples:
        row = by_file.get(item["file"])
        if not row or row["privacy_approved"] != "yes":
            raise ValueError("missing confirmed CSV provenance")
        keys = ("source_session", "source_frame", "offer_id", "slot",
                "category", "rarity")
        if any(row[k] != item.get(k) for k in keys):
            raise ValueError("CSV/manifest provenance changed after evaluation")
        expected = item.get("expected") or ""
        if row["expected"] != expected or row["two_line"] != str(item["two_line"]).lower():
            raise ValueError("human title/line label changed after evaluation")
        joined.append({k: row.get(k, "unknown") for k in FIELDS})
    result = {"dataset": "approved-local-independent-only",
              "user_device": "UNATTESTED",
              "privacy": "LOCAL_ONLY_NO_UPLOAD",
              "sample_count": len(samples), "engines": {}}
    for engine, data in report.get("summary", {}).items():
        audits = data.get("case_audit_LOCAL_ONLY", [])
        if len(audits) != len(samples):
            raise ValueError("OCR audit length differs from sealed manifest")
        groups = {k: defaultdict(Counter) for k in FIELDS}
        seen = set()
        for audit in audits:
            index = audit["sample_index"]
            status = audit["status"]
            if type(index) is not int or index < 0 or index >= len(samples) or index in seen:
                raise ValueError("invalid/duplicate OCR sample index")
            seen.add(index)
            if status not in STATUSES:
                raise ValueError("unrecognized OCR evidence status")
            context = joined[index]
            for dimension, values in groups.items():
                value = str(context[dimension]).lower() if dimension == "two_line" else str(context[dimension])
                values[value][status] += 1
        result["engines"][engine] = {
            key: {value: dict(counts) for value, counts in sorted(dim.items())}
            for key, dim in groups.items()
        }
    if set(result["engines"]) != {"tesseract", "ppocrv4_split",
                                  "ppocrv4_adaptive_split", "rapidocr_v4_split",
                                  "ppocrv5_en_split"}:
        raise ValueError("expected the five pinned engine configurations")
    return result


def main():
    import argparse
    p = argparse.ArgumentParser(description="PRIVATE OCR scenario grouping; no inference")
    p.add_argument("--labels", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--result", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    from benchmarks.ocr_v11c.evaluate_local import assert_private_paths
    assert_private_paths(Path(__file__).resolve().parents[2],
                         [args.labels, args.manifest, args.result, args.out])
    output = summarize_context(args.labels, args.manifest, args.result)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print("PRIVATE_CONTEXT_BREAKDOWN_READY: " + str(output["sample_count"]), flush=True)


if __name__ == "__main__":
    main()
