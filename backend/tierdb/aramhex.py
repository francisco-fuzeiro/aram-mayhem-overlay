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

from backend.tierdb.store import (
    ItemObservation,
    Observation,
    SnapshotMeta,
    SourceMeta,
    TierStore,
)

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
# Optional equipment tables (16.22+), imported when meta.json lists them.
ITEM_FILES = (
    "item_metadata.json", "hero_items.json", "equipment_recommendation_heroes.json",
    "hero_item_holdings.json", "equipment_heroes.json", "core_builds.json",
    "hero_augment_items.json",
)


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
    item_observations: tuple[ItemObservation, ...] = ()
    item_info: dict | None = None


def _load_items(directory: Path, listed: dict, champion_alias: dict[str, str],
                quarantine: list[tuple[str, str]]):
    """Parse the optional equipment tables; empty when the dataset has none."""
    present = [name for name in ITEM_FILES if name in listed]
    if not present:
        return [], {}
    missing = sorted(set(ITEM_FILES) - set(present))
    if missing:
        raise AramhexFormatError(f"incomplete equipment tables: {', '.join(missing)} not listed")
    t = {name: _read_verified(directory, name, listed) for name in ITEM_FILES}
    if not all(isinstance(v, dict) for v in t.values()):
        raise AramhexFormatError("equipment tables must be JSON objects")
    info = {}
    for iid, meta in t["item_metadata.json"].items():
        if not isinstance(meta, dict) or not isinstance(meta.get("category"), str):
            raise AramhexFormatError(f"item_metadata.json entry {iid} has no category")
        info[str(iid)] = (meta["category"], tuple(str(x) for x in meta.get("types") or ()))
    boots = {iid for iid, (_, types) in info.items() if "Boots" in types}
    obs: list[ItemObservation] = []
    unmapped: set[tuple[str, str]] = set()

    def champ(key, table):
        alias = champion_alias.get(str(key))
        if alias is None:
            unmapped.add((str(key), table))
        return alias

    def counts(entry):
        if not isinstance(entry, dict):
            raise AramhexFormatError(f"invalid equipment entry {entry!r}")
        return _count(entry, "games"), _count(entry, "wins")

    for table, scope, base_table, base_scope, keep in (
        ("hero_items.json", "champ_item", "equipment_recommendation_heroes.json",
         "champ_item_base", lambda iid: True),
        ("hero_item_holdings.json", "champ_boots", "equipment_heroes.json",
         "champ_boots_base", lambda iid: iid in boots),
    ):
        for key, entry in sorted(t[base_table].items()):
            alias = champ(key, base_table)
            g, w = counts(entry)
            if alias and g:
                obs.append(ItemObservation(scope=base_scope, champion_id=alias, wins=w, n=g))
        for key, items in sorted(t[table].items()):
            alias = champ(key, table)
            if alias is None:
                continue
            for iid, entry in sorted((items or {}).items()):
                if not keep(str(iid)):
                    continue
                g, w = counts(entry)
                if g:
                    obs.append(ItemObservation(scope=scope, champion_id=alias, item_id=str(iid),
                                               wins=w, n=g,
                                               low_sample=bool(entry.get("low_sample", False))))
    for key, cores in sorted(t["core_builds.json"].items()):
        alias = champ(key, "core_builds.json")
        if alias is None:
            continue
        if not isinstance(cores, list):
            raise AramhexFormatError(f"core_builds.json entry {key} is not a list")
        for core in cores:
            g, w = counts(core)
            items = core.get("items")
            if (not isinstance(items, list) or not items or
                    not all(isinstance(i, str) for i in items)):
                raise AramhexFormatError(f"core_builds.json entry {key} has invalid items")
            pick = core.get("pick")
            if g:
                obs.append(ItemObservation(
                    scope="champ_core", champion_id=alias, items=tuple(items),
                    ordered=bool(core.get("ordered", False)), wins=w, n=g,
                    value=float(pick) if isinstance(pick, (int, float)) else None))
    for key, by_aug in sorted(t["hero_augment_items.json"].items()):
        alias = champ(key, "hero_augment_items.json")
        if alias is None:
            continue
        for aid, ref in sorted((by_aug or {}).items()):
            g = _count(ref, "eligible_total")
            w = _count(ref, "eligible_wins")
            if g:
                obs.append(ItemObservation(scope="champ_aug_item_base", champion_id=alias,
                                           augment_id=str(aid), wins=w, n=g))
            for entry in ref.get("items") or []:
                gi, wi = counts(entry)
                if gi:
                    obs.append(ItemObservation(scope="champ_aug_item", champion_id=alias,
                                               augment_id=str(aid), item_id=str(entry["item"]),
                                               wins=wi, n=gi))
    for key, table in sorted(unmapped):
        quarantine.append((f"champion {key} in item table {table}", "unmapped Riot champion key"))
    return obs, info


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

    item_observations, item_info = _load_items(directory, listed, champion_alias, quarantine)
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
    return AramhexDataset(_source(), snapshot, observations, quarantine, augments,
                          tuple(item_observations), item_info)


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
    snapshot_id = store.ingest(ds.source, ds.snapshot, ds.observations,
                               quarantine=ds.quarantine, augments=ds.augments)
    if ds.item_observations:
        store.ingest_items(snapshot_id, list(ds.item_observations), ds.item_info)
    return snapshot_id


def download_dataset(ref: str, dataset_path: str, target: Path, fetch=None,
                     progress=None) -> Path:
    """Download one dataset directory pinned to a git ref (e.g. ``data-v20``).

    ``fetch(url) -> bytes`` is injectable for tests; checksums are verified by
    :func:`load_aramhex_dataset` afterwards, not trusted from the transport.
    """
    if fetch is None:
        import requests

        def fetch(url: str) -> bytes:
            response = requests.get(url, timeout=(10, 60))
            response.raise_for_status()
            return response.content

    target.mkdir(parents=True, exist_ok=True)
    meta_bytes = fetch(RAW_URL.format(ref=ref, path=f"{dataset_path}/meta.json"))
    (target / "meta.json").write_bytes(meta_bytes)
    try:
        listed = json.loads(meta_bytes.decode("utf-8-sig")).get("files") or {}
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        listed = {}
    names = list(REQUIRED_FILES) + [n for n in ITEM_FILES if n in listed]
    for i, name in enumerate(names, start=1):
        data = fetch(RAW_URL.format(ref=ref, path=f"{dataset_path}/{name}"))
        (target / name).write_bytes(data)
        if progress:
            progress(f"  {dataset_path}: {i}/{len(names)} {name} ({len(data) // 1024} KB)")
    return target
