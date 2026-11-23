"""Offline, read-only candidate coverage for Stat Anvil source investigation.

Run from the checkout with League and Oracle closed:
    py -3.11 -m scripts.stat_anvil_catalog_report
    py -3.11 -m scripts.stat_anvil_catalog_report --json

Existing CommunityDragon-derived augment caches are *not* authoritative
Stat Anvil choice catalogs. Tier-zero entries, if any, are only leads.
By default it never makes HTTP requests; --public-patch is an explicit
network-only public CDragon read (no file writes). It never opens the game,
accesses player information or writes files. No title is promoted to a selectable Anvil option.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from backend.static_data.anvil_public_catalog import (
    AnvilCatalogError, parse_public_bins, parse_public_stringtable,
    summarize_anvil_source,
)

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


# Public, patch-pinned bin locations, documented and validated against the
# MIT ARAM Mayhem Tracker's public source study. Riot moved the entries on 16.22.
# Source reference: https://github.com/Sygnano/aram-mayhem-tracker
ANVIL_BIN_PATHS = (
    "game/data/maps/shipping/map12/map12.bin.json",
    "game/unknown/507cdd64276919f5.bin.json",
)
_PATCH = re.compile(r"^\d{2}\.\d{1,2}$")


def public_patch_report(patch: str, *, locale: str | None = None) -> dict:
    """Optional network-only discovery; public sources, no cache writes."""
    import requests

    if not _PATCH.fullmatch(patch):
        raise AnvilCatalogError("patch must be major.minor (e.g. 16.23)")
    if locale is not None and not re.fullmatch(r"[a-z]{2}_[a-z]{2}", locale):
        raise AnvilCatalogError("locale must be e.g. en_us, pt_br")
    root = f"https://raw.communitydragon.org/{patch}"
    docs, found_paths = [], []
    for path in ANVIL_BIN_PATHS:
        response = requests.get(f"{root}/{path}", timeout=35)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        docs.append(response.json())
        found_paths.append(path.rsplit("/", 1)[-1])
    shards = parse_public_bins(docs)
    summary = summarize_anvil_source(shards, patch)
    summary["public_bins"] = found_paths
    summary["titles"] = []
    if locale and shards:
        table_url = f"{root}/game/{locale}/data/menu/en_us/lol.stringtable.json"
        response = requests.get(table_url, timeout=60)
        response.raise_for_status()
        names = parse_public_stringtable(response.json(), shards)
        summary["titles"] = [
            {"id": shard.item_id, "name": names[shard.item_id],
             "tier": shard.tier, "kind": shard.kind,
             "values": list(shard.values)}
            for shard in shards if shard.item_id in names
        ]
        summary["titles_found"] = len(summary["titles"])
        summary["titles_missing"] = len(shards) - len(summary["titles"])
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=_DEFAULT_CACHE_DIR,
                        help="Existing local augment cache folder, read-only")
    parser.add_argument("--public-patch", type=str,
                        help="Opt-in public CDragon AnvilData bins, e.g. 16.23; makes network requests")
    parser.add_argument("--locale", type=str,
                        help="Opt-in public game string table (~31 MB), e.g. en_us")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.locale and not args.public_patch:
        parser.error("--locale requires --public-patch")
    if args.public_patch:
        try:
            result = public_patch_report(args.public_patch, locale=args.locale)
        except (AnvilCatalogError, ValueError) as exc:
            print(f"PUBLIC ANVIL SOURCE UNVERIFIED: {exc}")
            return 2
        except Exception as exc:
            import requests
            if not isinstance(exc, requests.RequestException):
                raise
            print("PUBLIC ANVIL SOURCE UNAVAILABLE: network request failed")
            return 2
        print(json.dumps(result, indent=2, sort_keys=True)
              if args.json else (
                  "ARAM Oracle public Stat Anvil source (NOT live-verified)\n"
                  + f"patch={result['patch']} bins={result['public_bins']} "
                  + f"total={result['total']} tiers={result['tiers']}\n"
                  + f"live_popup_verified={result['live_popup_verified']} "
                  + f"rankings_verified={result['rankings_verified']}\n"
                  + "\n".join(
                      f"{row['tier']} | {row['id']} | {row['name']} | "
                      f"{row['kind']} | {row['values']}"
                      for row in result["titles"]
                  ) + "\n"
                  + "\n".join("WARNING: " + w for w in result["warnings"])
              ))
        return 0 if result["total"] > 0 else 2
    reports = [
        inspect_cache(path) for path in
        sorted(args.cache_dir.glob("augments_v5_*.json")) if path.is_file()
    ]
    print(json.dumps({"reports": reports}, indent=2, sort_keys=True)
          if args.json else format_report(reports))
    return 0 if reports and all(r["valid"] for r in reports) else 2


if __name__ == "__main__":
    raise SystemExit(main())
