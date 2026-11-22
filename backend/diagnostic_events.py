"""Privacy-minimal, non-blocking structured diagnostic event journal.

Only predeclared event types and enumerated/numeric fields can be persisted.
No champion/player names, account IDs, raw LCDA payloads, OCR text or images.
The polling thread only enqueues; a daemon writer owns all filesystem I/O.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Values are strict enums or bounded numeric types. Never log arbitrary strings.
SCHEMA: dict[str, dict[str, object]] = {
    "lcda": {
        "status": frozenset(("available", "unavailable", "error")),
        "error_class": frozenset(("none", "http", "connection", "timeout", "request", "parse", "http_404", "refused", "bad_json")),
    },
    "game_status": {
        "state": frozenset((
            "client_idle", "champ_select", "loading", "live_data_unavailable",
            "in_game", "champion_unresolved", "post_game",
        )),
    },
    "ocr_window": {
        "state": frozenset(("opened", "closed")),
        "reason": frozenset(("level_due", "damage", "manual_choice", "confirmed", "offer_disappeared", "reset", "unknown")),
        "level": "int",
    },
    "ocr_scan_stage": {
        "stage": frozenset((
            "not_scanned", "ocr_unavailable", "game_window_unavailable",
            "game_not_focused", "game_occluded", "capture_invalid",
            "capture_unavailable", "geometry_unsupported",
            "titles_verifying", "titles_unidentified",
            "titles_detected", "titles_unchanged", "titles_transition",
            "verified_absence",
        )),
    },
    "ocr_recognition": {
        "outcome": frozenset((
            "detected", "unchanged", "disappeared", "no_augments", "unavailable",
            "error", "manual_detected", "manual_empty", "not_focused",
            "occluded", "capture_unavailable",
        )),
        "count": "int",
        "confidence": "confidence100",
    },
    "capture_backend": {"backend": frozenset(("wgc", "mss_zorder", "none"))},
    "ocr_occlusion": {"owner": frozenset(("self", "other"))},
    "ocr_foreground": {"owner": frozenset(("league", "self", "other"))},
    "wgc_degraded": {"streak": "int"},
    "overlay_capture_exclusion": {"status": frozenset(("unsupported",))},
    "offer_cue": {
        "cue": frozenset(("present", "absent", "mixed")),
        "ocr": frozenset(("titles", "none")),
    },
    "identity_overridden": {
        "slot": frozenset(("left", "centre", "right")),
        "verified_by": frozenset(("ocr",)),
    },
    "augment_inference": {
        "result": frozenset(("pending", "auto", "ambiguous", "none")),
        "confidence": "confidence1",
    },
    "augment_confirmation": {
        "method": frozenset(("manual", "automatic")),
        "kind": frozenset(("augment", "anvil", "unknown")),
    },
    "item_data_source": {
        "source": frozenset(("network", "cache", "ddragon_unverified")),
    },
    "item_source_conflict": {"item_id": "item_id"},
    "item_outside_pool": {
        "item_id": "item_id",
        "class": frozenset((
            "final", "component", "boots_tier1", "boots_tier2",
            "augment_reward", "conditional", "mode_variant",
            "not_on_aram_map", "not_purchasable", "consumable_trinket",
            "unknown",
        )),
    },
    "f0_trace": {
        # F0 is opt-in at its caller; this schema excludes all free-form text.
        "feature": frozenset(("champion", "augment", "build")),
        "stage": frozenset(("local_cell", "alias", "capture", "matching",
                            "offer", "epoch", "build_inputs", "eligibility",
                            "next_item", "ui")),
        "status": frozenset(("accepted", "rejected", "unknown", "stale")),
        "reason": frozenset((
            "lcu_unavailable", "local_cell_missing", "local_cell_not_found",
            "local_cell_ambiguous", "local_champion_unselected",
            "champion_unmapped", "local_champion_mapped",
            "titles_detected", "titles_unidentified", "titles_transition",
            "titles_verifying", "geometry_unsupported", "game_not_focused",
            "game_occluded", "capture_unavailable", "ocr_unavailable",
            "verified_absence", "capture_unverified",
            "slots_verified_partial", "slots_verified_complete",
            "slot_order_invalid", "slot_identity_invalid",
            "slot_identity_duplicate", "title_input_invalid", "title_short",
            "catalog_empty", "below_threshold", "insufficient_margin",
            "title_matched", "slot_identity_changed",
            "already_in_build", "slot_candidate_selected",
            "item_name_duplicate", "boots_conflict",
            "exclusive_group_conflict", "candidate_excluded",
            "stale_epoch", "stale_offer",
            "new_offer_due", "scan_level_due", "epoch_superseded",
            "offer_disappeared", "ledger_unverified",
            "champion_unknown", "item_pool_unverified", "inventory_unknown",
            "augments_unconfirmed", "inputs_present", "verified_candidate",
            "item_class_excluded", "item_not_in_verified_pool",
            "already_owned", "no_candidate", "ranked_next_item",
            "item_recipe_unknown", "slot_blocked",
            "score_breakdown_unavailable",
        )),
        "source": frozenset((
            "none", "lcu", "lcda", "ocr", "ledger", "catalog", "pipeline",
        )),
        "slot": frozenset(("left", "centre", "right")),
        "epoch": "int",
        "count": "int",
        "item_id": "item_id",
        "similarity": "confidence100",  # fuzzy title ratio, NOT OCR probability
    },
    "match_transition": {
        "from_state": frozenset(("no_game", "champ_select", "in_game", "post_game")),
        "to_state": frozenset(("no_game", "champ_select", "in_game", "post_game")),
    },
}


def default_log_dir() -> Path:
    """User-local data, never the git checkout, bundle or working directory."""
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        if root:
            return Path(root) / "ARAMOracle" / "logs"
        return Path.home() / "AppData" / "Local" / "ARAMOracle" / "logs"
    root = os.environ.get("XDG_STATE_HOME")
    return (Path(root) if root else Path.home() / ".local" / "state") / "aram-oracle" / "logs"


def _clean(event: str, fields: dict) -> dict | None:
    specification = SCHEMA.get(event)
    if specification is None:
        return None
    safe = {}
    for key, constraint in specification.items():
        if key not in fields:
            continue
        value = fields[key]
        if isinstance(constraint, frozenset):
            if isinstance(value, str) and value in constraint:
                safe[key] = value
        elif constraint == "item_id":
            if isinstance(value, str) and value.isascii() and value.isdecimal() and 4 <= len(value) <= 6:
                safe[key] = value
        elif constraint == "int":
            if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 1000:
                safe[key] = value
        elif constraint in ("confidence1", "confidence100"):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                maximum = 1 if constraint == "confidence1" else 100
                if 0 <= value <= maximum:
                    safe[key] = round(float(value), 3)
    return safe


class StructuredEventLogger:
    """Bounded, loss-tolerant JSONL journal; emit() never waits for disk."""

    def __init__(
        self, directory: Path | None = None, *, max_bytes: int = 256 * 1024,
        backups: int = 3, queue_size: int = 256,
    ) -> None:
        if max_bytes < 128 or not (0 <= backups <= 10) or queue_size < 1:
            raise ValueError("invalid event log limits")
        self.directory = Path(directory) if directory is not None else default_log_dir()
        self.max_bytes = max_bytes
        self.backups = backups
        self._queue: queue.Queue[str | None] = queue.Queue(maxsize=queue_size)
        self._worker: threading.Thread | None = None
        self._running = False
        self._last: dict[str, str] = {}
        self._transition_lock = threading.Lock()
        self.dropped = 0

    def start(self) -> bool:
        if self._running:
            return True
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._running = True
            self._worker = threading.Thread(
                target=self._write_loop, name="aram-diagnostic-writer", daemon=True,
            )
            self._worker.start()
            return True
        except (OSError, RuntimeError):
            self._running = False
            self._worker = None
            return False

    def emit(self, event: str, **fields: object) -> bool:
        """Enqueue a whitelisted event without I/O, waits or exception leakage."""
        if not self._running:
            return False
        safe = _clean(event, fields)
        if safe is None:
            return False
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **safe,
        }
        try:
            self._queue.put_nowait(json.dumps(record, separators=(",", ":")))
            return True
        except queue.Full:
            self.dropped += 1
            return False

    def transition(self, event: str, **fields: object) -> bool:
        """Suppress identical consecutive statuses without blocking the poller."""
        safe = _clean(event, fields)
        if safe is None or not self._running:
            return False
        key = json.dumps(safe, sort_keys=True)
        if not self._transition_lock.acquire(blocking=False):
            self.dropped += 1
            return False
        try:
            if self._last.get(event) == key:
                return False
            queued = self.emit(event, **safe)
            if queued:
                self._last[event] = key
            return queued
        finally:
            self._transition_lock.release()

    def _write_loop(self) -> None:
        handler: RotatingFileHandler | None = None
        try:
            handler = RotatingFileHandler(
                self.directory / "events.jsonl", maxBytes=self.max_bytes,
                backupCount=self.backups, encoding="utf-8", delay=True,
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
        except OSError:
            pass
        while True:
            message = self._queue.get()
            try:
                if message is None:
                    break
                if handler is not None:
                    try:
                        record = logging.LogRecord(
                            "aram-oracle.structured", logging.INFO, "", 0, message, (), None,
                        )
                        handler.emit(record)
                    except (OSError, ValueError):
                        # Diagnostics must never interrupt game polling.
                        pass
            finally:
                self._queue.task_done()
        if handler is not None:
            try:
                handler.close()
            except OSError:
                pass

    def stop(self) -> None:
        """Drain the bounded queue on service shutdown (never from poll_tick)."""
        worker = self._worker
        if worker is None:
            return
        self._running = False
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                self.dropped += 1
                self._queue.put_nowait(None)
            except queue.Empty:
                pass
        worker.join(timeout=2.0)
        self._worker = None
        self._last.clear()


events = StructuredEventLogger()
