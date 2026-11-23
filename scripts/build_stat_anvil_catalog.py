"""Regenerate ``data/anvils/stat_anvils_<patch>.json`` from public game files.

Offline by default: pass the downloaded public bin and an allowlisted string
extract (``tests/fixtures/anvils/`` holds the 16.23 pair). With ``--fetch`` it
downloads both from CommunityDragon for the given patch (network required).

    py -3.11 -m scripts.build_stat_anvil_catalog --patch 16.23 \
        --bin tests/fixtures/anvils/statanvils.16.23.bin.json \
        --strings tests/fixtures/anvils/stringtable.anvils.16.23.en_us.json

Never commit a catalogue whose patch differs from its source files.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.static_data.anvil_public_catalog import AnvilCatalogError
from backend.static_data.stat_anvil_catalog import (
    SOURCE_PATH, STRINGTABLE_PATH, build_catalog, catalog_path, sha256_text,
    validate_catalog,
)

ROOT = Path(__file__).resolve().parent.parent
CDRAGON = "https://raw.communitydragon.org/{patch}/{path}"


def _fetch(patch: str, locale: str) -> tuple[str, dict, str | None]:
    import requests

    response = requests.get(CDRAGON.format(patch=patch, path=SOURCE_PATH), timeout=60)
    response.raise_for_status()
    table = requests.get(CDRAGON.format(
        patch=patch, path=STRINGTABLE_PATH.format(locale=locale)), timeout=120)
    table.raise_for_status()
    return response.text, table.json()["entries"], response.headers.get("last-modified")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch", required=True)
    parser.add_argument("--bin", type=Path)
    parser.add_argument("--strings", type=Path)
    parser.add_argument("--last-modified")
    parser.add_argument("--locale", default="en_us")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="fail if the committed catalogue differs")
    args = parser.parse_args(argv)
    if args.fetch:
        text, strings, last_modified = _fetch(args.patch, args.locale)
    else:
        if not args.bin or not args.strings:
            parser.error("--bin and --strings are required without --fetch")
        text = args.bin.read_text(encoding="utf-8")
        raw = json.loads(args.strings.read_text(encoding="utf-8"))
        strings = raw.get("entries", raw)
        last_modified = args.last_modified
    source = {
        "url": CDRAGON.format(patch=args.patch, path=SOURCE_PATH),
        "path": SOURCE_PATH, "sha256": sha256_text(text),
        "last_modified": last_modified,
        "strings": STRINGTABLE_PATH.format(locale=args.locale),
    }
    try:
        catalog = build_catalog(json.loads(text), strings, patch=args.patch, source=source)
        validate_catalog(catalog, expected_patch=args.patch)
    except AnvilCatalogError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    out = catalog_path(ROOT, args.patch)
    body = json.dumps(catalog, indent=1, ensure_ascii=False) + "\n"
    if args.check:
        return 0 if out.exists() and json.loads(out.read_text("utf-8")) == catalog else 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    print(json.dumps({k: catalog[k] for k in ("patch", "total", "tiers", "raw_tiers")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
