"""Temporal holdout for the impact metric on the local 10-player history.

Train on the oldest games, test on the newest. For each test player we predict
the result from their augments with (a) local shrunk ΔWR only, (b) impact only,
(c) ΔWR + w·impact, and report the AUC of each. Impact may be switched on in
context_adjust only if (c) beats (a) by >= MIN_GAIN on >= MIN_TEST_ROWS rows.
Prints counts and scores only: no champion names, games or players.

    py -3.11 -m scripts.validate_impact_holdout [--db PATH] [--train 0.7] [--no-prior]

Uses the local normal-ARAM prior (scripts/collect_aram_damage_prior.py) if present;
run with and without it to see whether the prior helps.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.storage.db import DB_PATH, get_participants
from backend.tierdb.impact_holdout import (  # noqa: F401  (re-exported for tests)
    MIN_GAIN, MIN_TEST_ROWS, WEIGHTS, evaluate,
)
from backend.tierdb.riot_prior import load_prior


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--train", type=float, default=0.7)
    parser.add_argument("--no-prior", action="store_true",
                        help="ignore the local normal-ARAM damage prior")
    args = parser.parse_args()
    prior = None if args.no_prior else load_prior()
    print(json.dumps(evaluate(get_participants(db_path=args.db), args.train, prior=prior),
                     indent=2))


if __name__ == "__main__":
    main()
