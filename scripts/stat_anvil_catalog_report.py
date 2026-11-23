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


_PUBLIC_HASH = "507cdd64276919f5.bin.json"
_SAFE_BIN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}" + re.escape(".bin.json") + "$")
_MAX_LISTED_BIN_BYTES = 32 * 1024 * 1024


def _public_index_rows(patch: str, directory: str) -> tuple[str, list[dict]]:
    """Read the official CDragon JSON directory index, without HTML scraping."""
    import requests
    if not _PATCH.fullmatch(patch):
        raise AnvilCatalogError("invalid patch identifier")
    if not directory.startswith("game/") or not directory.endswith("/"):
        raise AnvilCatalogError("unexpected public index directory")
    if any(part in ("", ".", "..") for part in directory.strip("/").split("/")):
        raise AnvilCatalogError("unsafe public index directory")
    url = f"https://raw.communitydragon.org/json/{patch}/{directory}"
    try:
        response = requests.get(url, timeout=20)
        if response.status_code == 404:
            return "index_unavailable", []
        response.raise_for_status()
        rows = response.json()
    except (requests.RequestException, ValueError):
        return "index_unavailable", []
    if not isinstance(rows, list) or len(rows) > 30000:
        return "index_invalid", []
    return "indexed", [row for row in rows if isinstance(row, dict)]


def inspect_public_bin_index(patch: str) -> dict:
    """List only filename candidates, NEVER certify real shard/popup content."""
    status, rows = _public_index_rows(patch, "game/unknown/")
    result = {
        "patch": patch, "directory": "game/unknown/", "status": status,
        "bin_json_count": 0, "known_hashed_bin_present": False,
        "possible_public_filenames": [], "catalogue_verified": False,
        "live_popup_verified": False,
    }
    if status != "indexed":
        return result
    candidates = []
    for row in rows:
        name = row.get("name")
        if (row.get("type") != "file" or not isinstance(name, str)
                or not _SAFE_BIN.fullmatch(name)):
            continue
        result["bin_json_count"] += 1
        if name == _PUBLIC_HASH:
            result["known_hashed_bin_present"] = True
        size = row.get("size")
        if (name != _PUBLIC_HASH and type(size) is int
                and 1024 <= size <= _MAX_LISTED_BIN_BYTES):
            candidates.append(name)
    result["possible_public_filenames"] = sorted(candidates)
    return result


def _follow_patch_directory(path: str) -> bool:
    """Only public game-content trees likely to contain map/Anvil bin files."""
    parts = path.strip("/").split("/")
    if not parts or parts[0] != "game" or len(parts) > 9:
        return False
    if len(parts) == 2:
        return parts[1] in {"data", "maps", "unknown", "levels"}
    if len(parts) == 3 and parts[:2] == ["game", "data"]:
        return parts[2] in {"maps", "modes", "gamemodes", "cherry"}
    if len(parts) == 3 and parts[:2] == ["game", "maps"]:
        return any(word in parts[2].lower() for word in
                   ("map", "mode", "cherry", "aram", "mayhem", "arena", "shipping"))
    return any(word in parts[-1].lower() for word in
               ("map", "mode", "cherry", "aram", "mayhem", "arena", "shipping", "unknown"))


def _bin_priority(path: str) -> int:
    lower = path.lower()
    if "anvil" in lower:
        return 100
    if any(word in lower for word in ("mayhem", "cherry", "aram")):
        return 90
    if "507cdd64276919f5" in lower:
        return 80
    if "/unknown/" in lower:
        return 70
    if "gameplay" in lower:
        return 60
    if any(word in lower for word in ("map", "mode", "arena")):
        return 50
    return 0


def discover_patch_anvil_bins(
    patch: str, *, max_bins: int = 80,
    max_index_directories: int = 48,
    max_bytes: int = 128 * 1024 * 1024,
) -> dict:
    """Explicit bounded network discovery of REAL public AnvilData.

    Fetch CDragon's official JSON directory index for the versioned game
    subtree, inspect plausible .bin.json contents and parse the actual
    AnvilData+RootSpell structures. No guessing, no disk writes, no game
    API/screen/player data. A capped or unavailable scan is NOT negative proof.
    """
    import requests
    from backend.static_data.anvil_public_catalog import parse_public_bins

    if not isinstance(patch, str) or not _PATCH.fullmatch(patch):
        raise AnvilCatalogError("patch must be major.minor")
    if (type(max_bins) is not int or not (0 <= max_bins <= 200)
            or type(max_index_directories) is not int
            or not (1 <= max_index_directories <= 100)
            or type(max_bytes) is not int or not (1 <= max_bytes <= 256 * 1024 * 1024)):
        raise AnvilCatalogError("invalid public discovery budget")

    queue = ["game/"]
    visited: set[str] = set()
    candidates: dict[str, tuple[int, int]] = {}
    index_errors: list[str] = []
    while queue and len(visited) < max_index_directories:
        directory = queue.pop(0)
        if directory in visited:
            continue
        visited.add(directory)
        status, rows = _public_index_rows(patch, directory)
        if status != "indexed":
            index_errors.append(directory)
            continue
        for row in rows:
            name = row.get("name")
            typ = row.get("type")
            if not isinstance(name, str):
                continue
            if typ == "directory":
                if (re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,80}", name)
                        and name not in (".", "..")):
                    child = directory + name + "/"
                    if (_follow_patch_directory(child) and child not in visited
                            and child not in queue):
                        queue.append(child)
                continue
            if typ != "file" or not _SAFE_BIN.fullmatch(name):
                continue
            size = row.get("size")
            full_path = directory + name
            priority = _bin_priority(full_path)
            if (type(size) is int and 1024 <= size <= _MAX_LISTED_BIN_BYTES
                    and priority > 0):
                candidates[full_path] = (priority, size)

    pending_directories = bool(queue)
    ordered = sorted(candidates, key=lambda path: (
        -candidates[path][0], -candidates[path][1], path,
    ))
    selected = ordered[:max_bins]
    incomplete = pending_directories or len(ordered) > max_bins or bool(index_errors)
    inspected = 0
    total_bytes = 0
    matched_docs = []
    matched_paths = []
    keyword_paths: list[str] = []
    source_errors = []
    for path in selected:
        estimated = candidates[path][1]
        if total_bytes + estimated > max_bytes:
            incomplete = True
            break
        url = f"https://raw.communitydragon.org/{patch}/{path}"
        try:
            response = requests.get(url, timeout=25)
            if response.status_code == 404:
                source_errors.append(path)
                incomplete = True
                continue
            response.raise_for_status()
            data = response.content
            if len(data) > _MAX_LISTED_BIN_BYTES or total_bytes + len(data) > max_bytes:
                incomplete = True
                break
            total_bytes += len(data)
            inspected += 1
            # Record public keyword hits separately; they do not validate
            # AnvilData and can be unrelated to current Mayhem shards.
            if b"StatAnvil" in data or b"Anvil" in data:
                keyword_paths.append(path)
            if b"AnvilData" not in data:
                continue
            document = response.json()
            if not isinstance(document, dict):
                source_errors.append(path)
                incomplete = True
                continue
            if not any(
                isinstance(row, dict) and row.get("__type") == "AnvilData"
                for row in document.values()
            ):
                continue
            # Require full, authoritative shard/spell shape; a keyword hit
            # alone is not a public catalogue or a live card.
            try:
                candidates_found = parse_public_bins([document])
            except (AnvilCatalogError, ValueError):
                source_errors.append(path)
                incomplete = True
                continue
            if candidates_found:
                matched_docs.append(document)
                matched_paths.append(path)
        except (requests.RequestException, ValueError):
            source_errors.append(path)
            incomplete = True

    shards = parse_public_bins(matched_docs) if matched_docs else []
    report = summarize_anvil_source(shards, patch)
    have_all_tiers = all(report["tiers"].values())
    verified = report["total"] > 0 and have_all_tiers
    report.update({
        "status": ("found" if verified else
                   "scan_incomplete" if incomplete else
                   "partial_tiers" if report["total"] else "no_source"),
        "source_verified": verified,
        "source_paths": sorted(matched_paths),
        "keyword_paths": sorted(keyword_paths)[:25],
        "index_directories_scanned": len(visited),
        "index_failures": len(index_errors),
        "candidate_bin_files": len(ordered),
        "bin_files_inspected": inspected,
        "source_files_unavailable_or_invalid": len(source_errors),
        "downloaded_bytes": total_bytes,
        "scan_complete": not incomplete,
        "live_popup_verified": False,
    })
    if not verified:
        report["warnings"].append(
            "No full three-tier real AnvilData source verified; keep recommendations disabled"
        )
        report["warnings"].append(
            "Only selected patch-index directories and plausible bin names were searched; "
            "zero is not proof all game bins lack Stat Anvils"
        )
    if incomplete:
        report["warnings"].append(
            "Discovery bounded/incomplete or public index unavailable; zero is not proof of absence"
        )
    return report


_KEYWORD_BIN_PATHS = (
    "game/gameplay.bin.json",
    "game/maps/modespecificdata/cherry.bin.json",
)
_PUBLIC_RELATIVE_BIN = re.compile(
    r"^game/(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_.-]+\\.bin\\.json$"
)
_MAX_PROBE_BYTES = 16 * 1024 * 1024
_MAX_PROBE_NODES = 100000
_MAX_PROBE_EXAMPLES = 40


def _validate_public_bin_path(path: object) -> str:
    if (not isinstance(path, str) or len(path) > 200
            or not _PUBLIC_RELATIVE_BIN.fullmatch(path)
            or any(segment in (".", "..") for segment in path.split("/"))):
        raise AnvilCatalogError("only safe game/*.bin.json paths are allowed")
    return path


def summarize_public_anvil_references(path: str, data: object) -> dict:
    """Bounded, public-only structural inspection: NEVER validates offers.

    Show the precise key/value JSON locations that mention Anvil, plus
    top-level versus nested __type=AnvilData. A keyword is a lead only.
    """
    _validate_public_bin_path(path)
    report = {
        "path": path,
        "valid_json": isinstance(data, dict),
        "top_level_anvil_data": 0,
        "nested_anvil_data": 0,
        "keyword_hit_count": 0,
        "keyword_examples": [],
        "nodes_inspected": 0,
        "truncated": False,
        "catalogue_verified": False,
    }
    if not isinstance(data, dict):
        return report
    stack: list[tuple[str, object, int]] = [("$", data, 0)]
    while stack and report["nodes_inspected"] < _MAX_PROBE_NODES:
        parent_path, node, depth = stack.pop()
        report["nodes_inspected"] += 1
        if isinstance(node, dict):
            if node.get("__type") == "AnvilData":
                key = ("top_level_anvil_data" if depth == 1
                       else "nested_anvil_data")
                report[key] += 1
            for name, value in node.items():
                if not isinstance(name, str):
                    continue
                child_path = f"{parent_path}.{name[:70]}"
                key_hit = "anvil" in name.lower()
                value_hit = isinstance(value, str) and "anvil" in value.lower()
                if key_hit or value_hit:
                    report["keyword_hit_count"] += 1
                    if len(report["keyword_examples"]) < _MAX_PROBE_EXAMPLES:
                        public_value = (value[:160] if isinstance(value, str)
                                        else "<object>" if isinstance(value, dict)
                                        else "<array>" if isinstance(value, list)
                                        else "<scalar>")
                        report["keyword_examples"].append({
                            "json_path": child_path[:250],
                            "public_value": public_value,
                        })
                if isinstance(value, (dict, list)) and depth < 16:
                    stack.append((child_path, value, depth + 1))
        elif isinstance(node, list):
            for i, value in enumerate(node[:10000]):
                if isinstance(value, (dict, list)):
                    stack.append((f"{parent_path}[{i}]", value, depth + 1))
                elif isinstance(value, str) and "anvil" in value.lower():
                    report["keyword_hit_count"] += 1
                    if len(report["keyword_examples"]) < _MAX_PROBE_EXAMPLES:
                        report["keyword_examples"].append({
                            "json_path": f"{parent_path}[{i}]"[:250],
                            "public_value": value[:160],
                        })
    report["truncated"] = bool(stack)
    return report


def probe_public_anvil_keyword_paths(
    patch: str, paths: list[str] | tuple[str, ...] = _KEYWORD_BIN_PATHS,
) -> dict:
    """Opt-in HTTP GET for exact, allowlisted-origin public bin path(s).

    No disk writes, Riot endpoints, match records, OCR or player information.
    Missing/invalid sources keep catalogue_verified false unconditionally.
    """
    import requests

    if not isinstance(patch, str) or not _PATCH.fullmatch(patch):
        raise AnvilCatalogError("invalid public patch")
    if not isinstance(paths, (list, tuple)) or not (1 <= len(paths) <= 8):
        raise AnvilCatalogError("expected one to eight public bin paths")
    validated = [_validate_public_bin_path(path) for path in paths]
    if len(set(validated)) != len(validated):
        raise AnvilCatalogError("duplicate public bin paths")
    result = {
        "patch": patch, "paths": [], "catalogue_verified": False,
        "live_popup_verified": False,
        "warnings": [
            "Keyword matches or nested AnvilData are not a verified Stat Anvil catalog.",
            "Only exact top-level AnvilData plus valid spell/tier parsing can verify identities.",
        ],
    }
    for path in validated:
        try:
            response = requests.get(
                f"https://raw.communitydragon.org/{patch}/{path}",
                timeout=25,
            )
            if response.status_code == 404:
                result["paths"].append({"path": path, "status": "missing"})
                continue
            response.raise_for_status()
            if len(response.content) > _MAX_PROBE_BYTES:
                result["paths"].append({"path": path, "status": "oversize"})
                continue
            report = summarize_public_anvil_references(path, response.json())
            report["status"] = ("inspected" if report["valid_json"]
                                else "invalid_json_root")
            result["paths"].append(report)
        except (requests.RequestException, UnicodeError, ValueError):
            result["paths"].append({"path": path, "status": "unavailable"})
    return result


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
    parser.add_argument("--discover", action="store_true",
                        help="With --public-patch, inspect indexed .bin.json candidates in bounded public game directories")
    parser.add_argument("--probe-keyword-paths", action="store_true",
                        help="Opt-in inspect direct public Anvil keyword hits without assuming these are catalogues")
    parser.add_argument("--probe-path", action="append",
                        help="Additional safe public game/*.bin.json path (requires --probe-keyword-paths)")
    parser.add_argument("--discovery-bins", type=int, default=80,
                        help="Bounded search limit, default 80 public bins, maximum 200")
    parser.add_argument("--discovery-dirs", type=int, default=48,
                        help="Bounded public index directory limit, default 48, maximum 100")
    parser.add_argument("--locale", type=str,
                        help="Opt-in public game string table (~31 MB), e.g. en_us")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.locale and not args.public_patch:
        parser.error("--locale requires --public-patch")
    if args.discover and not args.public_patch:
        parser.error("--discover requires --public-patch")
    if args.discover and args.locale:
        parser.error("--discover does not yet resolve titles; run a pinned source lookup separately")
    if args.probe_keyword_paths and not args.public_patch:
        parser.error("--probe-keyword-paths requires --public-patch")
    if args.probe_keyword_paths and (args.discover or args.locale):
        parser.error("--probe-keyword-paths is separate from discovery and title lookup")
    if args.probe_path and not args.probe_keyword_paths:
        parser.error("--probe-path requires --probe-keyword-paths")
    if args.probe_keyword_paths:
        try:
            report = probe_public_anvil_keyword_paths(
                args.public_patch, args.probe_path or _KEYWORD_BIN_PATHS,
            )
        except AnvilCatalogError as exc:
            print(f"PUBLIC ANVIL PROBE INVALID: {exc}")
            return 2
        print(json.dumps(report, indent=2, sort_keys=True))
        # This probe can never return a verified catalogue; exit 2 is intentional.
        return 2
    if args.public_patch:
        try:
            result = (discover_patch_anvil_bins(
                          args.public_patch, max_bins=args.discovery_bins,
                          max_index_directories=args.discovery_dirs,
                      ) if args.discover else
                      public_patch_report(args.public_patch, locale=args.locale))
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
                  + (
                      f"patch={result['patch']} status={result['status']} "
                      f"bins_scanned={result['bin_files_inspected']}/"
                      f"{result['candidate_bin_files']} "
                      f"dirs={result['index_directories_scanned']} "
                      f"source_paths={result['source_paths']} "
                      f"keyword_paths={result['keyword_paths']} "
                      f"total={result['total']} tiers={result['tiers']}\n"
                      if args.discover else
                      f"patch={result['patch']} bins={result['public_bins']} "
                      f"total={result['total']} tiers={result['tiers']}\n"
                  )
                  + f"live_popup_verified={result['live_popup_verified']} "
                  + f"rankings_verified={result['rankings_verified']}\n"
                  + "\n".join(
                      f"{row['tier']} | {row['id']} | {row['name']} | "
                      f"{row['kind']} | {row['values']}"
                      for row in result["titles"]
                  ) + "\n"
                  + "\n".join("WARNING: " + w for w in result["warnings"])
              ))
        return 0 if (result["source_verified"] if args.discover
                     else result["total"] > 0) else 2
    reports = [
        inspect_cache(path) for path in
        sorted(args.cache_dir.glob("augments_v5_*.json")) if path.is_file()
    ]
    print(json.dumps({"reports": reports}, indent=2, sort_keys=True)
          if args.json else format_report(reports))
    return 0 if reports and all(r["valid"] for r in reports) else 2


if __name__ == "__main__":
    raise SystemExit(main())
