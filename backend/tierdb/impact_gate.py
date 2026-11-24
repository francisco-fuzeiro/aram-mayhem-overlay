"""Impact metric in the live overlay, gated by the local holdout.

Owner decision 23/11: impact (damage + heal/shield per minute against the
champion's own baseline) feeds the in-match ±1 tier adjustment only once the
temporal holdout on the player's own imported games says ``enable``. Until
then ``lookup`` returns None and nothing changes. The import of local LCU
history is opt-in (Settings switch), stored outside the repo.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

HISTORY_PREFERENCES_FILE = Path.home() / ".aram-oracle" / "history_preferences.json"
IMPACT_WEIGHT = 0.20     # vote weight once enabled (build 0.40, synergy 0.25)


def load_history_enabled(path: Path | None = None) -> bool:
    source = path if path is not None else HISTORY_PREFERENCES_FILE
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False
    except (OSError, ValueError) as exc:
        logger.warning("Unreadable history preference %s: %s", source, exc)
        return False
    value = payload.get("history_import_enabled") if isinstance(payload, dict) else None
    return value is True


def save_history_enabled(enabled: bool, path: Path | None = None) -> None:
    if not isinstance(enabled, bool):
        raise ValueError("history_import_enabled must be a boolean")
    target = path if path is not None else HISTORY_PREFERENCES_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps({"history_import_enabled": enabled}) + "\n", encoding="utf-8")
    os.replace(tmp, target)


class ImpactGate:
    """Holds the holdout verdict and, when it is ``enable``, the impact map."""

    def __init__(self, rows_source=None, prior_source=None):
        self._rows_source = rows_source
        self._prior_source = prior_source
        self._lock = threading.Lock()
        self.verdict: str = "not_evaluated"
        self.counts: dict = {}
        self._impact: dict = {}

    def _rows(self) -> list[dict]:
        if self._rows_source is not None:
            return list(self._rows_source())
        from backend.storage.db import get_participants
        return get_participants()

    def _prior(self) -> dict | None:
        if self._prior_source is not None:
            return self._prior_source()
        from backend.tierdb.riot_prior import load_prior
        return load_prior() or None

    def refresh(self) -> str:
        """Re-run the holdout on the stored history (call off the event loop)."""
        from backend.tierdb.impact import augment_impact
        from backend.tierdb.impact_holdout import evaluate
        try:
            rows = self._rows()
            prior = self._prior()
            if not rows:
                result = {"verdict": "insufficient_data", "games": 0, "test_rows": 0}
            else:
                result = evaluate(rows, prior=prior)
            impact = ({k: v["impact"] for k, v in augment_impact(rows, prior=prior).items()}
                      if result.get("verdict") == "enable" else {})
        except Exception:  # history is optional; never break the overlay
            logger.exception("Impact holdout failed")
            result, impact = {"verdict": "failed"}, {}
        with self._lock:
            self.verdict = str(result.get("verdict"))
            self.counts = {k: result.get(k) for k in ("games", "test_rows")}
            self._impact = impact
        return self.verdict

    @property
    def enabled(self) -> bool:
        return self.verdict == "enable" and bool(self._impact)

    def lookup(self, champion_id, augment_id) -> float | None:
        if not self.enabled:
            return None
        return self._impact.get((str(champion_id), str(augment_id)))

    def status(self) -> dict:
        """Counts and verdict only: no champions, games or players."""
        return {"impact_verdict": self.verdict, "impact_active": self.enabled,
                "games": self.counts.get("games"), "test_rows": self.counts.get("test_rows")}
