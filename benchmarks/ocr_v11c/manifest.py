"""Local-only human labels -> independent development / sealed holdout manifests.

This module never captures screenshots, starts League, performs OCR, uploads
data, or writes into the repository. Human labels precede model predictions.
Exact duplicate pixels and bytes are rejected; visually modified derivatives
still require honest source-frame provenance and manual exclusion.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

from PIL import Image

from benchmarks.ocr_v11b.validation import validate_manifest

REQUIRED = (
    "file", "source_session", "source_frame", "offer_id", "slot", "category",
    "expected", "rarity", "two_line", "split", "privacy_approved",
)
SPLITS = ("development", "holdout")
SLOTS = ("left", "centre", "right")
CATEGORIES = ("title", "dialog", "no_offer")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{3,48}$")
_ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}


def _safe_token(value: str, field: str, *, optional: bool = False) -> str:
    value = (value or "").strip()
    if optional and not value:
        return ""
    if not _SAFE_ID.fullmatch(value):
        raise ValueError(f"{field} must be a pseudonymous 3-48 character ID")
    return value


def _label_boolean(value: str, field: str) -> bool:
    value = (value or "").strip().lower()
    if value not in ("true", "false"):
        raise ValueError(f"{field} must be true or false")
    return value == "true"


def prepare_manifests(labels: Path, root: Path, frozen_hashes: set[str]) -> dict:
    """Fail closed on provenance, consent, duplicates and split leakage.

    The holdout is assigned explicitly by the human *before* OCR evaluation.
    A session is never allowed to occur in both development and holdout.
    """
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("private crop directory does not exist")
    with labels.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or any(k not in reader.fieldnames for k in REQUIRED):
            raise ValueError("label CSV is missing required columns")
        lines = list(reader)
    if not lines:
        raise ValueError("no human-labeled crops (independent holdout BLOCKED)")

    manifests = {key: {"samples": []} for key in SPLITS}
    original_hashes = set(frozen_hashes)
    seen_bytes = set()
    seen_pixels = set()
    seen_frame_slot = set()
    session_splits = {}
    for index, row in enumerate(lines, 1):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"invalid CSV row {index}")
        if (row["privacy_approved"] or "").strip().lower() != "yes":
            raise ValueError(f"privacy approval required for CSV row {index}")
        split = (row["split"] or "").strip().lower()
        if split not in SPLITS:
            raise ValueError("split must be explicitly development or holdout")
        session = _safe_token(row["source_session"], "source_session")
        frame = _safe_token(row["source_frame"], "source_frame")
        offer = _safe_token(row["offer_id"], "offer_id", optional=True)
        if session in session_splits and session_splits[session] != split:
            raise ValueError("session leakage across development and holdout")
        session_splits[session] = split
        slot = (row["slot"] or "").strip().lower()
        category = (row["category"] or "").strip().lower()
        if slot not in SLOTS or category not in CATEGORIES:
            raise ValueError("invalid physical slot or category")
        key = (session, frame, slot)
        if key in seen_frame_slot:
            raise ValueError("duplicate source frame and physical slot")
        seen_frame_slot.add(key)
        expected = (row["expected"] or "").strip()
        if (category == "title") != bool(expected):
            raise ValueError("human title required only for title category")
        two_line = _label_boolean(row["two_line"], "two_line")
        rarity = (row["rarity"] or "").strip()
        if rarity not in ("", "Silver", "Gold", "Prismatic", "Other", "Unknown"):
            raise ValueError("unknown rarity (use Unknown if uncertain)")

        filename = (row["file"] or "").strip()
        if not filename or "\\" in filename or filename.startswith("/") or (
            any(part in ("", ".", "..") for part in filename.split("/"))
        ):
            raise ValueError("unsafe crop path")
        path = (root / filename).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("crop must exist inside private root")
        if path.suffix.lower() not in _ALLOWED_SUFFIXES:
            raise ValueError("only still-image crops are supported")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in original_hashes:
            raise ValueError("frozen original reuse is not independent")
        if digest in seen_bytes:
            raise ValueError("duplicate crop bytes across samples")
        seen_bytes.add(digest)
        try:
            with Image.open(path) as img:
                rgb = img.convert("RGB")
                pixel_key = hashlib.sha256(
                    str(rgb.size).encode("ascii") + rgb.tobytes()
                ).hexdigest()
        except (OSError, ValueError) as exc:
            raise ValueError("invalid or unreadable crop image") from exc
        if pixel_key in seen_pixels:
            raise ValueError("duplicate decoded pixels despite different encoding")
        seen_pixels.add(pixel_key)

        sample = {
            "id": f"sample-{index:05d}",
            "kind": "independent",
            "sha256": digest,
            "source_session": session,
            "source_frame": frame,
            "offer_id": offer,
            "expected": expected if category == "title" else None,
            "category": category,
            "slot": slot,
            "privacy_approved": True,
            "file": filename,
            "two_line": two_line,
            "rarity": rarity or "Unknown",
        }
        manifests[split]["samples"].append(sample)

    for payload in manifests.values():
        validate_manifest(payload, original_hashes, require_independent=True)
    seal = hashlib.sha256(
        json.dumps(manifests["holdout"], sort_keys=True,
                   separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {**manifests, "holdout_seal": seal}


def main():
    parser = argparse.ArgumentParser(
        description="PRIVATE manual CSV labels -> session-separated holdout; no OCR")
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    from benchmarks.ocr_v11c.evaluate_local import assert_private_paths
    assert_private_paths(Path(__file__).resolve().parents[2],
                         [args.labels, args.root, args.out])
    from benchmarks.ocr_v11.runner import REFERENCE_SHA, read_cases
    reference = args.reference.resolve()
    actual_sha = subprocess.check_output(
        ["git", "-C", str(reference), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual_sha != REFERENCE_SHA:
        raise ValueError("reference is not the fixed audited SHA")
    cases, _ = read_cases(reference)
    original_hashes = {case["sha256"] for case in cases}
    result = prepare_manifests(args.labels, args.root, original_hashes)
    args.out.mkdir(parents=True, exist_ok=True)
    for split in SPLITS:
        file = args.out / f"{split}.manifest.json"
        file.write_text(json.dumps(result[split], indent=2), encoding="utf-8")
    (args.out / "holdout.sha256").write_text(
        result["holdout_seal"] + "\n", encoding="ascii"
    )
    # Never print paths, titles, sessions, image hashes, or local OCR results.
    print("PRIVATE_LABELS_PREPARED " + json.dumps({
        "development": len(result["development"]["samples"]),
        "holdout": len(result["holdout"]["samples"]),
        "holdout_status": "SEALED_NOT_EVALUATED"
        if result["holdout"]["samples"] else "BLOCKED",
        "upload": "NEVER_AUTOMATIC",
    }), flush=True)


if __name__ == "__main__":
    main()
