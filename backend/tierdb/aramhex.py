"""Importer for AramHex ARAM: Mayhem statistics (czgreat/aramhex-data).

Data licence: CC BY-NC 4.0. Usable only while ARAM Oracle is non-commercial
(owner decision 2026-11-23), always with attribution. In commercial mode the
source is refused before anything is stored.

Layout (verified 2026-11-23 on 16.23/normal): ``meta.json`` maps every file
name to its SHA-256; ``heroes.json`` is ``{riot_champion_key: {games, wins, ...}}``;
``hero_augments.json`` is ``{riot_champion_key: {augment_id: {games, wins,
low_sample}}}``; ``augments.json`` is ``{augment_id: {name, rarity}}``.
Augment exposure is "held at game end, any of the six slots, deduplicated".
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from backend.tierdb.store import Observation, SnapshotMeta, SourceMeta, TierStore

SOURCE_NAME = "aramhex"
REPO_URL = "https://github.com/czgreat/aramhex-data"
RAW_URL = "https://raw.githubusercontent.com/czgreat/aramhex-data/{ref}/{path}"
ATTRIBUTION = (
    "ARAM: Mayhem statistics from AramHex (github.com/czgreat/aramhex-data), "
    "CC BY-NC 4.0. Not affiliated with Riot Games or Tencent."
)
EXPECTED_LICENSE = "CC BY-NC 4.0"
REQUIRED_FILES = ("heroes.json", "hero_augments.json", "augments.json")
RARITIES = {"silver", "gold", "prismatic"}


class AramhexFormatError(ValueError):
    """The dataset does not match the verified AramHex layout or checksums."""


class LicenseError(PermissionError):
    """The dataset's licence does not allow use in the current app mode."""


@dataclass(frozen=True)
class AramhexDataset:
    source: SourceMeta
    snapshot: SnapshotMeta
    observations: list[Observation]
    quarantine: list[tuple[str, str]]
    augments: dict[str, tuple[str, str]]


def _source() -> SourceMeta:
    return SourceMeta(
        name=SOURCE_NAME, url=REPO_URL, license="CC-BY-NC-4.0",
        attribution=ATTRIBUTION, commercial_ok=False,
    )


def _read_verified(directory: Path, name: str, listed: dict) -> object:
    # meta.json lists ``name: sha256``; latest.json/index.json use
    # ``name: {sha256, size}``. Accept both, require one.
    entry = listed.get(name)
    expected = entry.get("sha256") if isinstance(entry, dict) else entry
    if not isinstance(expected, str) or len(expected) != 64:
        raise AramhexFormatError(f"{name} is not listed with a SHA-256 in meta.json files")
    data = (directory / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected.lower():
        raise AramhexFormatError(f"SHA-256 mismatch for {name}")
    try:
        return json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AramhexFormatError(f"{name} is not valid JSON") from exc


def _count(entry: dict, key: str) -> int:
    value = entry.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise AramhexFormatError(f"invalid {key!r}: {value!r}")
    return value


def load_aramhex_dataset(
    directory: Path | str,
    champion_alias: dict[str, str],
    *,
    allow_event_mode: bool = False,
) -> AramhexDataset:
    """Parse and verify one ``patches/<patch>/<mode>`` directory.

    ``champion_alias`` maps Riot numeric champion keys to the app's lowercase
    Data Dragon ids. Unmapped champions, excluded augments and augments
    without a known rarity are quarantined with a reason, never dropped
    silently and never guessed.
    """
    directory = Path(directory)
    meta_bytes = (directory / "meta.json").read_bytes()
    try:
        meta = json.loads(meta_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AramhexFormatError("meta.json is not valid JSON") from exc

    if meta.get("license") != EXPECTED_LICENSE:
        raise LicenseError(f"unexpected AramHex licence {meta.get('license')!r}")
    if meta.get("mode") != "normal" and not allow_event_mode:
        raise AramhexFormatError(
            f"mode {meta.get('mode')!r} is an event rule set; only 'normal' is comparable"
        )
    patch = meta.get("patch")
    if not isinstance(patch, str) or not patch:
        raise AramhexFormatError("meta.json has no patch")
    listed = meta.get("files") or {}

    heroes, hero_augments, augments_raw = (
        _read_verified(directory, name, listed) for name in REQUIRED_FILES
    )
    if not all(isinstance(x, dict) for x in (heroes, hero_augments, augments_raw)):
        raise AramhexFormatError("top-level JSON objects expected")

    excluded = {str(k): str(v) for k, v in (meta.get("excluded_augments") or {}).items()}
    quarantine: list[tuple[str, str]] = []
    augments: dict[str, tuple[str, str]] = {}
    for aid, info in sorted(augments_raw.items()):
        rarity = (info or {}).get("rarity")
        if aid in excluded:
            continue
        if rarity not in RARITIES:
            quarantine.append((f"augment {aid}", f"unknown rarity {rarity!r}"))
            continue
        augments[aid] = (str(info.get("name", "")), rarity)
    for aid, reason in sorted(excluded.items()):
        quarantine.append((f"augment {aid}", f"excluded by source: {reason}"))

    threshold = meta.get("low_sample_threshold")
    observations: list[Observation] = []
    for key, entry in sorted(heroes.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
        alias = champion_alias.get(str(key))
        if alias is None:
            quarantine.append((f"champion {key}", "unmapped Riot champion key"))
            continue
        games, wins = _count(entry, "games"), _count(entry, "wins")
        if games == 0:
            continue
        observations.append(Observation(
            scope="champion", metric="win", champion_id=alias, wins=wins, n=games,
            low_sample=bool(entry.get("low_sample", False)),
        ))
        unknown_here: set[str] = set()
        for aid, pair in sorted((hero_augments.get(key) or {}).items()):
            if aid in excluded:
                continue
            if aid not in augments:
                unknown_here.add(aid)
                continue
            g, w = _count(pair, "games"), _count(pair, "wins")
            if g == 0:
                continue
            low = bool(pair.get("low_sample", isinstance(threshold, int) and g < threshold))
            observations.append(Observation(
                scope="champ_aug", metric="win", champion_id=alias, augment_id=aid,
                wins=w, n=g, low_sample=low,
            ))
        for aid in sorted(unknown_here):
            quarantine.append((f"augment {aid} on champion {key}", "no rarity in augments.json"))

    window = meta.get("window") or {}
    snapshot = SnapshotMeta(
        patch=patch,
        region=f"CN ({len(meta.get('regions') or [])} regions combined)",
        sha256=hashlib.sha256(meta_bytes).hexdigest(),
        queue=None,
        window_start=window.get("start"),
        window_end=window.get("end_exclusive"),
        metric_definitions={
            "win": "wins/games of players holding the augment at game end "
                   "(any slot, deduplicated per player); champion baseline from heroes.json",
            "augment_exposure": meta.get("augment_exposure"),
            "mode": meta.get("mode"),
            "matches": meta.get("matches"),
            "low_sample_threshold": threshold,
        },
    )
    return AramhexDataset(_source(), snapshot, observations, quarantine, augments)


def ingest_aramhex(
    store: TierStore,
    directory: Path | str,
    champion_alias: dict[str, str],
    *,
    app_mode: str = "noncommercial",
    allow_event_mode: bool = False,
) -> int:
    """Verify and store one AramHex dataset; return the snapshot id."""
    if app_mode != "noncommercial":
        raise LicenseError("AramHex data is CC BY-NC 4.0: not usable in commercial mode")
    ds = load_aramhex_dataset(directory, champion_alias, allow_event_mode=allow_event_mode)
    return store.ingest(ds.source, ds.snapshot, ds.observations,
                        quarantine=ds.quarantine, augments=ds.augments)


def download_dataset(ref: str, dataset_path: str, target: Path, fetch=None) -> Path:
    """Download one dataset directory pinned to a git ref (e.g. ``data-v20``).

    ``fetch(url) -> bytes`` is injectable for tests; checksums are verified by
    :func:`load_aramhex_dataset` afterwards, not trusted from the transport.
    """
    if fetch is None:
        import requests

        def fetch(url: str) -> bytes:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content

    target.mkdir(parents=True, exist_ok=True)
    meta_bytes = fetch(RAW_URL.format(ref=ref, path=f"{dataset_path}/meta.json"))
    (target / "meta.json").write_bytes(meta_bytes)
    for name in REQUIRED_FILES:
        data = fetch(RAW_URL.format(ref=ref, path=f"{dataset_path}/{name}"))
        (target / name).write_bytes(data)
    return target
