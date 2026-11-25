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


from backend.tierdb.service import latest_dataset as _latest_dataset  # noqa: E402
from backend.tierdb.service import riot_champion_aliases  # noqa: E402


def _static_inputs(with_heuristic: bool):
    from backend.static_data.loader import StaticData
    from backend.tierdb.service import static_inputs

    sd = StaticData()
    sd.load()
    return static_inputs(sd, with_heuristic)


def _say(message: str) -> None:
    """Progress on the console: the update downloads ~25 MB and builds for minutes."""
    import time
    print(f"{time.strftime('%H:%M:%S')} {message}", flush=True)


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
            _say("fetching champion names (Data Dragon)")
            aliases = (json.loads(alias_file.read_text(encoding="utf-8"))
                       if alias_file else riot_champion_aliases())
            if getattr(args, "dir", None):
                directory = args.dir
            else:
                ref, dataset = _latest_dataset(getattr(args, "ref", "main"))
                dataset = getattr(args, "dataset", None) or dataset
                _say(f"downloading AramHex {dataset} ({ref})")
                directory = aramhex.download_dataset(
                    ref, dataset, Path(tempfile.mkdtemp(prefix="aramhex-")), progress=_say)
            _say("storing the dataset")
            snap_id = aramhex.ingest_aramhex(store, directory, aliases)
            patch = store.snapshot(snap_id).patch
            print(f"ingested snapshot {snap_id} (patch {patch})")
            if not getattr(args, "dir", None):
                from backend.tierdb.service import ingest_previous_patch
                prev = ingest_previous_patch(store, ref, patch, aliases, progress=_say)
                if prev:
                    print(f"ingested previous patch snapshot {prev} (champion pool)")
            if args.cmd == "update":
                _say("loading champion/item data")
                roles, heuristic = _static_inputs(not args.no_heuristic)
                _say("building the tier lists (about 1 minute)")
                run_id = run_build(store, patch, roles, heuristic)
                _say("exporting")
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
