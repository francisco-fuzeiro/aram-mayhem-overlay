"""Offline, read-only candidate coverage for Stat Anvil source investigation.

Run from the checkout with League and Oracle closed:
    py -3.11 -m scripts.stat_anvil_catalog_report
    py -3.11 -m scripts.stat_anvil_catalog_report --json

Existing CommunityDragon-derived augment caches are *not* authoritative
Stat Anvil choice catalogs. Tier-zero entries, if any, are only leads.
This script never opens the game, accesses local player info, makes HTTP calls
or writes files. No title is promoted to a selectable Anvil option.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

_DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cache"


def inspect_cache(path: Path) -> dict:
    result = {
        "file": path.name, "valid": False, "total_rows": 0,
        "tier_zero_rows": 0, "candidate_titles": [],
        "verified_stat_options": False, "warnings": [],
    }
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(raw, dict) or not raw or
                any(not isinstance(item_id, str) or not item_id.isascii()
                    or not item_id.isdecimal() or not isinstance(row, dict)
                    or type(row.get("tier")) is not int
                    or row["tier"] not in (0, 1, 2, 3)
                    or not isinstance(row.get("name"), str)
                    or not row["name"].strip()
                    for item_id, row in raw.items())):
            raise ValueError("invalid or incomplete public augment cache")
        tier_zero = sorted(
            ((item_id, row["name"]) for item_id, row in raw.items()
             if row["tier"] == 0),
            key=lambda pair: (int(pair[0]), pair[1]),
        )
        result["valid"] = True
        result["total_rows"] = len(raw)
        result["tier_zero_rows"] = len(tier_zero)
        result["candidate_titles"] = [
            {"id": item_id, "name": name} for item_id, name in tier_zero
        ]
        if not tier_zero:
            result["warnings"].append(
                "NO TIER-ZERO rows in this cache: no Anvil choice names from this source"
            )
        else:
            result["warnings"].append(
                "Tier-zero entries are NOT verified Stat Anvil options or visible cards"
            )
    except (OSError, ValueError, TypeError, UnicodeError):
        result["warnings"].append(
            "Cache missing, corrupt or structurally incomplete"
        )
    return result


def format_report(reports: list[dict]) -> str:
    lines = [
        "ARAM Oracle Stat Anvil candidate-source report (read-only)",
        "Tier-zero public augment rows are NOT verified Stat Anvil options.",
        "Neither catalog presence nor a voucher proves a visible popup.",
    ]
    if not reports:
        return "\n".join(lines + ["NO CACHE FOUND: no conclusion about in-game options."])
    for report in reports:
        lines += [
            "",
            f"Cache: {report['file']}",
            f"valid={report['valid']} total={report['total_rows']} "
            f"tier_zero={report['tier_zero_rows']} "
            f"verified_options={report['verified_stat_options']}",
        ]
        for item in report["candidate_titles"]:
            lines.append(f"  possible source row: {item['id']} | {item['name']}")
        for warning in report["warnings"]:
            lines.append(f"WARNING: {warning}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=_DEFAULT_CACHE_DIR,
                        help="Existing local augment cache folder, read-only")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    reports = [
        inspect_cache(path) for path in
        sorted(args.cache_dir.glob("augments_v5_*.json")) if path.is_file()
    ]
    print(json.dumps({"reports": reports}, indent=2, sort_keys=True)
          if args.json else format_report(reports))
    return 0 if reports and all(r["valid"] for r in reports) else 2


if __name__ == "__main__":
    raise SystemExit(main())
