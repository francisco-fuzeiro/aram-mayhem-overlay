"""Tier DB command line (runs on the user's machine; data stays local).

    python -m backend.tierdb ingest-aramhex [--ref main] [--dataset patches/16.23/normal]
    python -m backend.tierdb ingest-aramhex --dir path/to/patches/16.23/normal
    python -m backend.tierdb build --patch 16.23 [--no-heuristic]
    python -m backend.tierdb export [--run RUN_ID]
    python -m backend.tierdb update            # ingest latest + build + export
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from backend.tierdb import aramhex
from backend.tierdb.export import export_run
from backend.tierdb.pipeline import run_build
from backend.tierdb.runtime import DEFAULT_EXPORT_FILE
from backend.tierdb.store import TierStore

DEFAULT_DB = Path.home() / ".aram-oracle" / "tierdb.sqlite"


def riot_champion_aliases() -> dict[str, str]:
    """Riot numeric champion key -> lowercase Data Dragon id (public data)."""
    import requests

    base = "https://ddragon.leagueoflegends.com"
    versions = requests.get(f"{base}/api/versions.json", timeout=10)
    versions.raise_for_status()
    version = versions.json()[0]
    r = requests.get(f"{base}/cdn/{version}/data/en_US/champion.json", timeout=15)
    r.raise_for_status()
    return {str(c["key"]): c["id"].lower() for c in r.json()["data"].values()}


def _static_inputs(with_heuristic: bool):
    from backend.engine.augment_rating import rate_augment
    from backend.static_data.loader import StaticData

    sd = StaticData()
    sd.load()
    champions = list(sd._champions.values())
    roles = {c.id: c.role for c in champions}
    heuristic = {}
    if with_heuristic:
        for champ in champions:
            for aug in sd.all_augments():
                rating = rate_augment(champ, aug, [])
                heuristic[(champ.id, aug.id)] = rating.score
    return roles, heuristic


def _latest_dataset(ref: str) -> tuple[str, str]:
    import requests

    r = requests.get(aramhex.RAW_URL.format(ref=ref, path="latest.json"), timeout=15)
    r.raise_for_status()
    latest = r.json()
    seq = latest.get("seq")
    return (f"data-v{seq}" if seq else ref), latest["path"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.tierdb")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest-aramhex")
    ing.add_argument("--dir", type=Path)
    ing.add_argument("--ref", default="main")
    ing.add_argument("--dataset")
    ing.add_argument("--aliases", type=Path,
                     help="JSON {riot_key: champion_id} instead of fetching Data Dragon")
    bld = sub.add_parser("build")
    bld.add_argument("--patch", required=True)
    bld.add_argument("--no-heuristic", action="store_true")
    exp = sub.add_parser("export")
    exp.add_argument("--run", type=int)
    exp.add_argument("--out", type=Path, default=DEFAULT_EXPORT_FILE)
    upd = sub.add_parser("update")
    upd.add_argument("--no-heuristic", action="store_true")
    upd.add_argument("--out", type=Path, default=DEFAULT_EXPORT_FILE)
    args = parser.parse_args(argv)

    store = TierStore(args.db)
    try:
        if args.cmd in ("ingest-aramhex", "update"):
            alias_file = getattr(args, "aliases", None)
            aliases = (json.loads(alias_file.read_text(encoding="utf-8"))
                       if alias_file else riot_champion_aliases())
            if getattr(args, "dir", None):
                directory = args.dir
            else:
                ref, dataset = _latest_dataset(getattr(args, "ref", "main"))
                dataset = getattr(args, "dataset", None) or dataset
                directory = aramhex.download_dataset(
                    ref, dataset, Path(tempfile.mkdtemp(prefix="aramhex-")))
            snap_id = aramhex.ingest_aramhex(store, directory, aliases)
            patch = store.snapshot(snap_id).patch
            print(f"ingested snapshot {snap_id} (patch {patch})")
            if args.cmd == "update":
                roles, heuristic = _static_inputs(not args.no_heuristic)
                run_id = run_build(store, patch, roles, heuristic)
                export_run(store, run_id, args.out)
                print(f"built run {run_id}; exported to {args.out}")
        elif args.cmd == "build":
            roles, heuristic = _static_inputs(not args.no_heuristic)
            print(f"built run {run_build(store, args.patch, roles, heuristic)}")
        elif args.cmd == "export":
            run_id = args.run or store.connection.execute(
                "SELECT MAX(id) FROM tier_run").fetchone()[0]
            if run_id is None:
                print("no tier run to export", file=sys.stderr)
                return 1
            doc = export_run(store, run_id, args.out)
            print(json.dumps({"run_id": run_id, "patch": doc["patch"], "out": str(args.out)}))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
