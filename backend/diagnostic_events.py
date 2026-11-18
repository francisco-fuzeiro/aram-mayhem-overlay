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
    "ocr_recognition": {
        "outcome": frozenset((
            "detected", "unchanged", "disappeared", "no_augments", "unavailable",
            "error", "manual_detected", "manual_empty",
        )),
        "count": "int",
        "confidence": "confidence100",
    },
    "augment_inference": {
        "result": frozenset(("pending", "auto", "ambiguous", "none")),
        "confidence": "confidence1",
    },
    "augment_confirmation": {
        "method": frozenset(("manual", "automatic")),
        "kind": frozenset(("augment", "anvil", "unknown")),
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
