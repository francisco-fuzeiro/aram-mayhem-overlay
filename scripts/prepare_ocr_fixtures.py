"""Prepare offline, title-band-only OCR fixtures from opt-in League card crops.

This utility NEVER captures a screen, runs OCR or reads the League process.
The source PNGs must already be card-only crops (M4/B3). It re-encodes
pixel data to strip metadata, then writes exactly three PNG bands and a
{left, centre, right} ground-truth JSON file. Real gameplay validation
and positional calibration remain separate Windows/League gates.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Mapping

from PIL import Image, UnidentifiedImageError


SLOTS = ("left", "centre", "right")
_CASE_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_:-]*\Z")
_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "ocr"


def _validate_truth(truth: Mapping[str, str | None]) -> None:
    if set(truth) != set(SLOTS):
        raise ValueError("Truth must contain left, centre and right exactly")
    for value in truth.values():
        if value is not None and (
            not isinstance(value, str)
            or not 1 <= len(value) <= 80
            or _ID_RE.fullmatch(value) is None
        ):
            raise ValueError("Truth IDs must be a bounded catalog ID or null")


def _read_redacted_band(path: Path) -> Image.Image:
    """Load a small title-band PNG and discard all image metadata."""
    try:
        if path.stat().st_size > 3_000_000:
            raise ValueError("Card-title input exceeds 3 MB")
        with Image.open(path) as source:
            if source.format != "PNG":
                raise ValueError("Card-title input must be a PNG")
            width, height = source.size
            # Reject desktop, full augment strip, cards with description,
            # tiny/unusable crops and inconsistent aspect ratios.
            if not (80 <= width <= 960 and 20 <= height <= 200
                    and width >= height * 1.5):
                raise ValueError("Source is not a bounded card-title band")
            source.load()
            pixels = source.convert("RGB")
            sanitized = Image.new("RGB", source.size)
            sanitized.paste(pixels)
            return sanitized
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError("Invalid, missing or unreadable card PNG") from exc


def prepare_fixture_case(
    *,
    sources: Mapping[str, Path],
    truth: Mapping[str, str | None],
    case_id: str,
    output_dir: Path,
) -> dict[str, Path]:
    """Save three privacy-redacted title bands plus one exact truth JSON.

    Validate *all* inputs and check output collisions before writing anything.
    Existing fixtures are never silently overwritten. No input PNG is copied
    verbatim, and arbitrary tags/EXIF/OCR text are discarded on re-encode.
    """
    if not isinstance(case_id, str) or len(case_id) > 80 or _CASE_RE.fullmatch(case_id) is None:
        raise ValueError("Case ID must be a neutral lowercase hyphen-separated slug")
    if set(sources) != set(SLOTS):
        raise ValueError("Exactly three input card title bands are required")
    _validate_truth(truth)

    input_paths = {slot: Path(sources[slot]) for slot in SLOTS}
    if len({path.resolve() for path in input_paths.values()}) != 3:
        raise ValueError("Each slot must reference a different source PNG")

    # Reading and validating before creating any destination avoids partially
    # committed fixtures for invalid input images or mismatched dimensions.
    cards = {slot: _read_redacted_band(input_paths[slot]) for slot in SLOTS}
    widths = [cards[s].width for s in SLOTS]
    heights = [cards[s].height for s in SLOTS]
    if max(widths) - min(widths) > 4 or max(heights) - min(heights) > 4:
        raise ValueError("Three card title bands must have similar dimensions")

    output_dir = Path(output_dir)
    result = {slot: output_dir / f"{case_id}.{slot}.png" for slot in SLOTS}
    result["truth"] = output_dir / f"{case_id}.truth.json"
    if any(path.exists() for path in result.values()):
        raise FileExistsError("Fixture already exists; select a new case ID")

    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        for slot in SLOTS:
            path = result[slot]
            with path.open("xb") as handle:
                created.append(path)
                cards[slot].save(handle, format="PNG")
        with result["truth"].open("x", encoding="utf-8", newline="\n") as handle:
            created.append(result["truth"])
            json.dump({slot: truth[slot] for slot in SLOTS}, handle, indent=2)
            handle.write("\n")
    except (OSError, ValueError):
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare three metadata-stripped League card-title PNGs "
                    "and explicit ground-truth augment IDs; no screen capture.",
    )
    for slot in SLOTS:
        parser.add_argument(f"--{slot}", type=Path, required=True,
                            help=f"Existing M4/B3 {slot} card-title PNG")
        parser.add_argument(f"--{slot}-id", required=True,
                            help="Actual catalog augment ID, or 'unknown' for null")
    parser.add_argument("--case-id", required=True,
                        help="Neutral slug, e.g. offer-1440p-01")
    parser.add_argument("--output-dir", type=Path, default=_DEFAULT_DIR)
    args = parser.parse_args(argv)
    sources = {slot: getattr(args, slot) for slot in SLOTS}
    truth = {
        slot: None if getattr(args, f"{slot}_id").casefold() in ("null", "unknown")
        else getattr(args, f"{slot}_id")
        for slot in SLOTS
    }
    result = prepare_fixture_case(
        sources=sources, truth=truth, case_id=args.case_id,
        output_dir=args.output_dir,
    )
    print(f"Created 3 redacted title PNGs and {result['truth']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
