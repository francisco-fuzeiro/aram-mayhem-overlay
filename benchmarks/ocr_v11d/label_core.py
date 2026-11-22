"""Local-only, explicitly confirmed screenshot-crop labels for OCR V1.1d.

No imports of game APIs, capture, network, OCR runtime or model inference.
Every crop is manually selected from an existing file by the human operator.
The V1.1c manifest and evaluation gates remain authoritative.
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
from pathlib import Path
import re
from uuid import uuid4

from PIL import Image

from benchmarks.ocr_v11c.manifest import REQUIRED

EXTRA = ("scene", "reroll", "focus", "opgg", "resolution", "dpi")
FIELDNAMES = tuple(REQUIRED) + EXTRA
SLOTS = frozenset(("left", "centre", "right"))
CATEGORIES = frozenset(("title", "dialog", "no_offer"))
RARITIES = frozenset(("Silver", "Gold", "Prismatic", "Other", "Unknown"))
SCENES = frozenset(("offer", "reroll", "animation", "transition", "dialog", "no_offer"))
FOCUS = frozenset(("game", "alt_tab", "unknown"))
OPGG = frozenset(("yes", "no", "unknown"))
DPI = frozenset(("unknown", "100", "125", "150", "175", "200", "250", "300"))
TOKEN = re.compile(r"^[A-Za-z0-9_-]{3,48}$")


def title_suggestions(query: str, titles, *, limit: int = 20) -> list[str]:
    """Suggest catalog spelling without auto-accepting approximate titles."""
    if limit < 1:
        return []
    return [title for title in sorted(set(titles), key=str.casefold)
            if query.strip().casefold() in title.casefold()][:limit]


def _id(value: str, field: str, *, optional: bool = False) -> str:
    value = (value or "").strip()
    if optional and not value:
        return ""
    if not TOKEN.fullmatch(value):
        raise ValueError(f"{field} must be a pseudonymous 3-48 character identifier")
    return value


def _pixel_digest(image: Image.Image) -> str:
    rgb = image.convert("RGB")
    return hashlib.sha256(str(rgb.size).encode("ascii") + rgb.tobytes()).hexdigest()


def _existing_rows(root: Path) -> list[dict]:
    labels = root / "human_labels.csv"
    if not labels.exists():
        return []
    with labels.open("r", encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)
        if not reader.fieldnames or not set(REQUIRED).issubset(reader.fieldnames):
            raise ValueError("existing labels schema mismatch; do not overwrite")
        return list(reader)


def save_confirmed_frame(
    image: Image.Image, selections: list[dict], private_root: Path, *,
    repository: Path, catalog: set[str], frozen_hashes: set[str],
    session: str, frame: str, offer: str, split: str,
    confirmed: bool, context: dict | None = None,
) -> int:
    """Atomically append only human-approved crop labels and private PNGs.

    No inference is invoked here. A single screenshot supplies every physical
    slot in this call; new screenshot => new frame ID, including rerolls.
    """
    if not confirmed:
        raise ValueError("explicit human confirmation is required before saving")
    root = Path(private_root).resolve()
    repo = Path(repository).resolve()
    if root == repo or root.is_relative_to(repo):
        raise ValueError("private data must remain outside the repository")
    if not isinstance(image, Image.Image) or not selections or len(selections) > 3:
        raise ValueError("one screenshot needs one to three manually selected crops")
    session = _id(session, "session")
    frame = _id(frame, "frame")
    offer = _id(offer, "offer", optional=True)
    if split not in ("development", "holdout"):
        raise ValueError("explicit development/holdout split required")
    context = context or {}
    scene = context.get("scene", "offer")
    focus = context.get("focus", "unknown")
    opgg = context.get("opgg", "unknown")
    dpi = str(context.get("dpi", "unknown"))
    reroll = context.get("reroll", "none")
    if scene not in SCENES or focus not in FOCUS or opgg not in OPGG or dpi not in DPI:
        raise ValueError("unknown observation context")
    if reroll not in ("none", "left", "centre", "right", "unknown"):
        raise ValueError("unknown reroll position")

    old = _existing_rows(root)
    for row in old:
        if row["source_session"] == session and row["split"] != split:
            raise ValueError("session leakage across development and holdout")
    occupied = {(r["source_session"], r["source_frame"], r["slot"]) for r in old}
    seen_sha, seen_pixels = set(frozen_hashes), set()
    private_crops = root / "crops"
    for row in old:
        relative = Path(row["file"])
        path = (root / relative).resolve()
        if path == root or not path.is_relative_to(root) or not path.is_file():
            raise ValueError("missing or unsafe existing private image")
        seen_sha.add(hashlib.sha256(path.read_bytes()).hexdigest())
        with Image.open(path) as previous:
            seen_pixels.add(_pixel_digest(previous))

    new_rows, new_images = [], []
    slots = set()
    for selection in selections:
        slot = selection.get("slot")
        category = selection.get("category")
        expected = (selection.get("expected") or "").strip()
        rarity = selection.get("rarity", "Unknown")
        two_line = selection.get("two_line", False)
        if slot not in SLOTS or slot in slots:
            raise ValueError("invalid or duplicate physical slot")
        slots.add(slot)
        if (session, frame, slot) in occupied:
            raise ValueError("duplicate source frame and physical slot")
        if category not in CATEGORIES or rarity not in RARITIES or type(two_line) is not bool:
            raise ValueError("invalid category, rarity or two-line flag")
        if category == "title":
            if not expected or expected not in catalog:
                raise ValueError("title must exactly match the verified canonical catalog")
        elif expected or two_line:
            raise ValueError("negative/dialog image cannot contain a human title label")
        rect = selection.get("rect")
        if not isinstance(rect, (tuple, list)) or len(rect) != 4 or not all(
            type(n) is int for n in rect
        ):
            raise ValueError("invalid rectangle")
        left, top, right, bottom = rect
        if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
            raise ValueError("crop rectangle must stay strictly inside the screenshot")
        crop = image.crop((left, top, right, bottom)).convert("RGB")
        encoded = io.BytesIO()
        crop.save(encoded, format="PNG")
        payload = encoded.getvalue()
        sha = hashlib.sha256(payload).hexdigest()
        pixels = _pixel_digest(crop)
        if sha in seen_sha:
            if sha in frozen_hashes:
                raise ValueError("frozen original reuse is not independent")
            raise ValueError("duplicate encoded crop")
        if pixels in seen_pixels:
            raise ValueError("duplicate decoded crop pixels")
        seen_sha.add(sha)
        seen_pixels.add(pixels)
        filename = "crops/" + uuid4().hex + ".png"
        new_images.append((filename, payload))
        row = dict(
            file=filename, source_session=session, source_frame=frame,
            offer_id=offer, slot=slot, category=category, expected=expected,
            rarity=rarity, two_line=str(two_line).lower(), split=split,
            privacy_approved="yes", scene=scene, reroll=reroll,
            focus=focus, opgg=opgg, resolution=f"{image.width}x{image.height}",
            dpi=dpi,
        )
        new_rows.append(row)

    # Validate all inputs before any private files are created.
    private_crops.mkdir(parents=True, exist_ok=True)
    written = []
    temp = root / ("labels-" + uuid4().hex + ".tmp")
    try:
        for name, payload in new_images:
            destination = root / name
            with destination.open("xb") as handle:
                handle.write(payload)
            written.append(destination)
        with temp.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDNAMES,
                                    extrasaction="ignore")
            writer.writeheader()
            writer.writerows(old)
            writer.writerows(new_rows)
        os.replace(temp, root / "human_labels.csv")
    except Exception:
        temp.unlink(missing_ok=True)
        for file in written:
            file.unlink(missing_ok=True)
        raise
    return len(new_rows)
