"""Private local V1.1c holdout evaluator with explicit seal/unlock gate.

No automatic uploads or game interaction. Holdout is never run implicitly,
and all private labels / crops / output must be outside the Git checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def assert_private_paths(repository: Path, paths: list[Path]) -> None:
    root = repository.resolve()
    for path in paths:
        if path.resolve().is_relative_to(root):
            raise ValueError("private inputs and outputs must be outside the Git checkout")


def validate_sealed_holdout(manifest: Path, seal: Path, *, unlock: bool) -> int:
    if not unlock:
        raise ValueError("explicit --unlock-holdout is required after freezing candidate")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    samples = payload.get("samples", [])
    if not isinstance(samples, list) or not samples:
        raise ValueError("no independent holdout samples approved; BLOCKED")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected = hashlib.sha256(canonical).hexdigest()
    stored = seal.read_text(encoding="ascii").strip().lower()
    if stored != expected:
        raise ValueError("holdout manifest seal mismatch; do not evaluate modified labels")
    return len(samples)


def main():
    p = argparse.ArgumentParser(description="PRIVATE offline holdout, no uploads")
    p.add_argument("--labels-dir", required=True, type=Path)
    p.add_argument("--reference", required=True, type=Path)
    p.add_argument("--models", required=True, type=Path)
    p.add_argument("--holdout-root", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--split", choices=("development", "holdout"),
                   default="development")
    p.add_argument("--unlock-holdout", action="store_true")
    a = p.parse_args()
    repository = Path(__file__).resolve().parents[2]
    manifest = a.labels_dir / (a.split + ".manifest.json")
    assert_private_paths(repository, [a.labels_dir, a.holdout_root, a.out, manifest])
    if not manifest.is_file():
        raise ValueError("human-labelled manifest is missing; BLOCKED")
    if a.split == "holdout":
        count = validate_sealed_holdout(
            manifest, a.labels_dir / "holdout.sha256", unlock=a.unlock_holdout
        )
    else:
        rows = json.loads(manifest.read_text(encoding="utf-8")).get("samples", [])
        count = len(rows)
        if not count:
            raise ValueError("no approved development rows; BLOCKED")
    print(f"PRIVATE_{a.split.upper()}_READY count={count} (local only)", flush=True)
    command = [
        sys.executable, "-m", "benchmarks.ocr_v11b.run_holdout",
        "--reference", str(a.reference), "--models", str(a.models),
        "--manifest", str(manifest), "--holdout-root", str(a.holdout_root),
        "--out", str(a.out),
    ]
    subprocess.run(command, check=True)
    print("PRIVATE_OCR_EVALUATION_COMPLETED; review only on this device", flush=True)


if __name__ == "__main__":
    main()
