"""Tier list service used by the local API: status, live switch, updates.

Updates download the latest AramHex dataset, rebuild both tier lists and
export them, in a background thread so the overlay never blocks. Failures are
reported in ``status()``; the previous export stays in use.
"""
from __future__ import annotations

import logging
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from backend import feature_diagnostics as diag
from backend.tierdb import aramhex
from backend.tierdb.export import export_run
from backend.tierdb.pipeline import run_build
from backend.tierdb.runtime import (
    DEFAULT_EXPORT_FILE,
    TIER_PREFERENCES_FILE,
    TierListProvider,
    load_empirical_tiers_enabled,
    save_empirical_tiers_enabled,
)
from backend.tierdb.store import TierStore

logger = logging.getLogger("aram-oracle.tierdb")

DEFAULT_DB = Path.home() / ".aram-oracle" / "tierdb.sqlite"
DD_BASE = "https://ddragon.leagueoflegends.com"


def riot_champion_aliases() -> dict[str, str]:
    """Riot numeric champion key -> lowercase Data Dragon id (public data)."""
    import requests

    versions = requests.get(f"{DD_BASE}/api/versions.json", timeout=10)
    versions.raise_for_status()
    version = versions.json()[0]
    r = requests.get(f"{DD_BASE}/cdn/{version}/data/en_US/champion.json", timeout=15)
    r.raise_for_status()
    return {str(c["key"]): c["id"].lower() for c in r.json()["data"].values()}


def latest_dataset(ref: str = "main") -> tuple[str, str]:
    """(pinned git ref, dataset path) of the newest normal-rules AramHex data."""
    import requests

    r = requests.get(aramhex.RAW_URL.format(ref=ref, path="latest.json"), timeout=15)
    r.raise_for_status()
    latest = r.json()
    seq = latest.get("seq")
    return (f"data-v{seq}" if seq else ref), latest["path"]


def static_inputs(static_data, with_heuristic: bool = True):
    """Roles and curated 0-10 fit scores from the app's loaded static data."""
    champions = list(getattr(static_data, "_champions", {}).values()) if static_data else []
    roles = {c.id: c.role for c in champions}
    heuristic: dict = {}
    if with_heuristic and champions:
        from backend.engine.augment_rating import rate_augment

        for champ in champions:
            for aug in static_data.all_augments():
                heuristic[(champ.id, aug.id)] = rate_augment(champ, aug, []).score
    return roles, heuristic


def item_inputs(static_data):
    """Verified item pool (item eligibility, #107) as tier-list inputs, or None.

    Without a verified two-source catalog no item tiers are built: AramHex
    holdings alone do not prove an item is purchasable in this Mayhem patch.
    """
    import numpy as np

    from backend.tierdb.pipeline import ItemInputs

    getter = getattr(static_data, "recommendable_items", None)
    items = list(getter()) if callable(getter) else []
    eligible = {i.id for i in items if i.item_class == "final"}
    if not eligible:
        return None
    boots = {i.id for i in items if i.item_class == "boots_tier2"}
    groups = dict(getattr(static_data, "exclusive_item_groups", {}) or {})

    def conflicts(a, b):
        return a != b and any(a in ids and b in ids for ids in groups.values())

    fit = {}
    champions = list(getattr(static_data, "_champions", {}).values())
    vectors = {i.id: np.array(i.stats.to_array(), dtype=float) for i in items}
    for champ in champions:
        cv = np.array(champ.stats.to_array(), dtype=float)
        cn = float(np.linalg.norm(cv))
        for iid, iv in vectors.items():
            n = cn * float(np.linalg.norm(iv))
            fit[(champ.id, iid)] = max(0.0, float(cv @ iv) / n) if n else 0.0
    return ItemInputs(eligible=eligible, boots_eligible=boots,
                      canonical=getattr(static_data, "canonical_item_id", lambda x: x),
                      fit=fit, conflicts=conflicts)


def update_tierlist(*, db_path: Path, export_path: Path, roles: dict, heuristic: dict,
                    aliases: dict | None = None, dataset_dir: Path | None = None,
                    items=None) -> dict:
    aliases = aliases if aliases is not None else riot_champion_aliases()
    if dataset_dir is None:
        ref, dataset = latest_dataset()
        dataset_dir = aramhex.download_dataset(
            ref, dataset, Path(tempfile.mkdtemp(prefix="aramhex-")))
    store = TierStore(db_path)
    try:
        snap_id = aramhex.ingest_aramhex(store, dataset_dir, aliases)
        patch = store.snapshot(snap_id).patch
        run_id = run_build(store, patch, roles, heuristic, items=items)
        export_run(store, run_id, export_path)
    finally:
        store.close()
    return {"patch": patch, "run_id": run_id, "snapshot_id": snap_id,
            "finished_at": datetime.now(timezone.utc).isoformat()}


def classify_update_error(exc: BaseException) -> str:
    """Map an update failure to a diagnostics reason (no free text)."""
    import urllib.error
    try:
        import requests
        network = (requests.RequestException,)
    except ImportError:  # pragma: no cover
        network = ()
    if isinstance(exc, aramhex.LicenseError):
        return "license"
    if isinstance(exc, aramhex.AramhexFormatError):
        return "bad_dataset"
    if isinstance(exc, (ConnectionError, TimeoutError, urllib.error.URLError) + network):
        return "network"
    if isinstance(exc, ValueError):
        return "build_failed"
    return "unexpected"


class TierListService:
    def __init__(self, export_path: Path | None = None, preferences_path: Path | None = None,
                 db_path: Path | None = None):
        self.export_path = Path(export_path or DEFAULT_EXPORT_FILE)
        self.preferences_path = Path(preferences_path or TIER_PREFERENCES_FILE)
        self.db_path = Path(db_path or DEFAULT_DB)
        self.provider = TierListProvider(self.export_path, enabled=self.enabled)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None
        self.last_update: dict | None = None

    def enabled(self) -> bool:
        return load_empirical_tiers_enabled(self.preferences_path)

    def set_enabled(self, value: bool) -> None:
        save_empirical_tiers_enabled(value, self.preferences_path)

    @property
    def updating(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def status(self) -> dict:
        self.provider._load()
        available = self.provider._mtime is not None
        generated = None
        if available:
            generated = datetime.fromtimestamp(
                self.export_path.stat().st_mtime, timezone.utc).isoformat()
        return {
            "enabled": self.enabled(),
            "available": available,
            "patch": self.provider.patch if available else None,
            "generated_at": generated,
            "sources": [{"name": s.get("name"), "attribution": s.get("attribution")}
                        for s in (self.provider.sources if available else [])],
            "updating": self.updating,
            "last_error": self.last_error,
            "last_update": self.last_update,
        }

    def needs_update(self, max_age_hours: float = 72.0) -> bool:
        try:
            age = time.time() - self.export_path.stat().st_mtime
        except OSError:
            return True
        return age > max_age_hours * 3600

    def start_update(self, static_data) -> bool:
        """Start one background update; False if one is already running."""
        with self._lock:
            if self.updating:
                diag.record("tierdb.update", "skipped", "already_running")
                return False

            def work():
                try:
                    roles, heuristic = static_inputs(static_data)
                    self.last_update = update_tierlist(
                        db_path=self.db_path, export_path=self.export_path,
                        roles=roles, heuristic=heuristic, items=item_inputs(static_data))
                    self.last_error = None
                    diag.record("tierdb.update", "ok", "updated")
                except Exception as exc:  # reported, never raised into the API
                    logger.warning("Tier list update failed: %s", exc)
                    self.last_error = f"{type(exc).__name__}: {exc}"
                    diag.record("tierdb.update", "failed", classify_update_error(exc))

            self._thread = threading.Thread(target=work, name="tierlist-update", daemon=True)
            self._thread.start()
            return True

    def wait(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
