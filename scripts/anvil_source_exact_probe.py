"""Evidence-only direct audit of public patch-pinned Stat Anvil BIN.

Do not read local files, League APIs or player data. Returns ONLY public
structure and aggregate counts, never raw JSON, item IDs or gameplay scores.
The official 16.23 source must be confirmed by live HTTP, not fixtures.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter

import requests

from backend.static_data.anvil_public_catalog import AnvilCatalogError, parse_public_bins

EXACT_PATH = "game/unknown/507cdd64276919f5.bin.json"
_PATCH = re.compile(r"^\d{2}\.\d{1,2}$")
_RARITIES = {0: "silver", 8: "gold", 9: "prismatic"}


def inspect_direct_public_source(patch: str) -> dict:
    if not isinstance(patch, str) or not _PATCH.fullmatch(patch):
        raise AnvilCatalogError("invalid public patch")
    result = {
        "patch": patch, "source_path": EXACT_PATH, "http_status": None,
        "raw_anvil_data": 0,
        "raw_rarity_singletons": {v: 0 for v in _RARITIES.values()},
        "raw_mixed": 0, "raw_unclassified": 0,
        "parser_total": 0, "parser_tiers": {v: 0 for v in _RARITIES.values()},
        "parser_error": None,
        "source_verified": False,
        "live_popup_verified": False,
        "index_status": "not_checked", "exact_filename_in_index": None,
        "index_named_candidates": [],
    }
    url = f"https://raw.communitydragon.org/{patch}/{EXACT_PATH}"
    try:
        response = requests.get(url, timeout=30)
        result["http_status"] = response.status_code
        if response.status_code == 404:
            _inspect_index(patch, result)
            return result
        response.raise_for_status()
        if len(response.content) > 8 * 1024 * 1024:
            result["parser_error"] = "public_bin_exceeds_limit"
            return result
        data = response.json()
        if not isinstance(data, dict):
            result["parser_error"] = "invalid_public_json_root"
            return result
        for item in data.values():
            if not isinstance(item, dict) or item.get("__type") != "AnvilData":
                continue
            result["raw_anvil_data"] += 1
            codes = item.get("AnvilTypes")
            if not isinstance(codes, list) or not codes:
                result["raw_unclassified"] += 1
            elif len(codes) == 1 and type(codes[0]) is int and codes[0] in _RARITIES:
                result["raw_rarity_singletons"][_RARITIES[codes[0]]] += 1
            elif len(codes) > 1 and all(type(c) is int and c in _RARITIES for c in codes):
                result["raw_mixed"] += 1
            else:
                result["raw_unclassified"] += 1
        try:
            parsed = parse_public_bins([data])
            result["parser_total"] = len(parsed)
            tiers = Counter(row.tier for row in parsed)
            result["parser_tiers"] = {tier: tiers[tier] for tier in _RARITIES.values()}
        except (AnvilCatalogError, ValueError, TypeError):
            result["parser_error"] = "source_parser_rejected_structure"
        result["source_verified"] = (
            result["raw_anvil_data"] > 0
            and result["parser_error"] is None
            and result["parser_total"] > 0
            and all(result["parser_tiers"].values())
        )
    except (requests.RequestException, ValueError, UnicodeError):
        result["parser_error"] = "public_source_unavailable"
    return result


def _inspect_index(patch: str, report: dict) -> None:
    """On 404, inspect the exact patch's public index by filename only."""
    url = f"https://raw.communitydragon.org/json/{patch}/game/unknown/"
    try:
        response = requests.get(url, timeout=25)
        if response.status_code == 404:
            report["index_status"] = "missing"
            return
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            report["index_status"] = "invalid"
            return
        names = [
            row["name"] for row in data
            if isinstance(row, dict) and row.get("type") == "file"
            and isinstance(row.get("name"), str)
        ]
        report["index_status"] = "checked"
        report["exact_filename_in_index"] = EXACT_PATH.rsplit("/", 1)[-1] in names
        # Report known-hash related candidate names, not arbitrary guessing.
        report["index_named_candidates"] = sorted(
            x for x in names if x.startswith("507cdd64276919f5")
        )[:10]
    except (requests.RequestException, ValueError, UnicodeError):
        report["index_status"] = "unavailable"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch", default="16.23")
    args = parser.parse_args(argv)
    try:
        result = inspect_direct_public_source(args.patch)
    except AnvilCatalogError as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["source_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
