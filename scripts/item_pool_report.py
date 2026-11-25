"""Read-only, offline ARAM Oracle item eligibility report.

Run from the repository root, with League CLOSED:
    py -3.11 -m scripts.item_pool_report
    py -3.11 -m scripts.item_pool_report --json

Reads existing local public item metadata caches only. No LCDA, HTTP, writes,
player identifiers or cache refresh. Cache classifications do NOT prove shop access.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from backend.static_data.item_policy import (
    ITEM_CLASSES, ITEM_POLICY_VERSION, RECOMMENDABLE_CLASSES,
)

_CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cache"


def inspect_cache(path: Path) -> dict:
    """Summarize existing classification evidence; never promote an item."""
    result = {
        "file": path.name, "valid": False, "schema": None,
        "policy_version": "unknown", "policy_current": False,
        "ddragon_version": "unknown", "source_status": "unknown",
        "total_items": 0, "classes": {key: 0 for key in sorted(ITEM_CLASSES)},
        "recommendable_count": 0, "warnings": [],
    }
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("not an object")
        meta = raw.get("meta")
        classes = raw.get("classes")
        items = raw.get("items")
        if (not isinstance(meta, dict) or not isinstance(classes, dict)
                or not isinstance(items, dict) or not items
                or set(classes) != set(items)
                or any(c not in ITEM_CLASSES for c in classes.values())):
            raise ValueError("incomplete classification or item records")
        result["schema"] = raw.get("schema")
        result["policy_version"] = str(meta.get("policy_version", "unknown"))
        result["policy_current"] = result["policy_version"] == ITEM_POLICY_VERSION
        result["ddragon_version"] = str(meta.get("ddragon_version", "unknown"))
        result["source_status"] = str(meta.get("availability", "unknown"))
        counts = Counter(classes.values())
        result["classes"] = {key: counts[key] for key in sorted(ITEM_CLASSES)}
        result["total_items"] = len(items)
        result["recommendable_count"] = sum(counts[key] for key in RECOMMENDABLE_CLASSES)
        result["valid"] = True
        if not result["policy_current"]:
            result["warnings"].append("cache uses an older or unknown policy")
        if result["source_status"] != "verified_two_source":
            result["warnings"].append("cache lacks two-source verified status")
        if not counts["final"]:
            result["warnings"].append("ZERO classified final items; Next: unavailable is plausible")
    except (OSError, ValueError, TypeError, UnicodeError):
        result["warnings"].append("cache missing, corrupt or structurally incomplete")
    return result


def format_report(reports: list[dict]) -> str:
    lines = [
        "ARAM Oracle item eligibility: offline read-only report",
        "A classified item does not prove live Mayhem shop availability.",
        "Cache alone cannot recover source-conflict details (DD into vs CD to, prices).",
    ]
    if not reports:
        return "\n".join(lines + [
            "NO CACHE FOUND: run the app's existing catalog load separately; "
            "this report never downloads or changes data.",
        ])
    for report in reports:
        lines.append("")
        lines.append(f"Cache: {report['file']}")
        lines.append(
            f"valid={report['valid']} schema={report['schema']} "
            f"policy={report['policy_version']} current={report['policy_current']} "
            f"patch={report['ddragon_version']} status={report['source_status']}"
        )
        lines.append(
            f"total={report['total_items']} final={report['classes']['final']} "
            f"boots_tier2={report['classes']['boots_tier2']} "
            f"recommendable={report['recommendable_count']}"
        )
        for category, count in report["classes"].items():
            if count:
                lines.append(f"  {category}: {count}")
        for warning in report["warnings"]:
            lines.append(f"WARNING: {warning}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=_CACHE_DIR,
                        help="Existing local cache folder (read-only).")
    parser.add_argument("--json", action="store_true",
                        help="Machine-readable aggregate classification counts.")
    args = parser.parse_args(argv)
    reports = [
        inspect_cache(path) for path in
        sorted(args.cache_dir.glob("items_v5_*.json"))
        if path.is_file()
    ]
    if args.json:
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
    else:
        print(format_report(reports))
    return 0 if reports and all(r["valid"] for r in reports) else 2


if __name__ == "__main__":
    raise SystemExit(main())
