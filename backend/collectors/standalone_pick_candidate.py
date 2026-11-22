"""F5.2 passive, fail-closed Mayhem pick *candidate* from visible evidence.

This module does NOT capture cursor/clicks, take screenshots, identify the
actual selected augment, or confirm gameplay picks. It is deliberately
UNWIRED in production until independent native calibration and policy review.

The known open-source hover + missing-OCR heuristic is not adequate proof.
An independently calibrated clickable card region and actual button-down
edge may identify intent; three independently calibrated visual absences
only establish that the previous offer is no longer visible. Neither is a
positive assertion that the intended augment was acquired. The output
cannot be passed as PickedAugmentEvidence to the verified-pick ledger.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re

from backend.collectors.offer_visibility import (
    IndependentCue, VerifiedAbsenceGate, WindowKey,
)
from backend.workflow.offer_ledger import SLOTS


# Conservative synthetic proof budget, not a measured League animation SLA.
MAX_CLICK_TO_DISAPPEAR_S = 8.0
MAX_OPEN_TO_CLICK_S = 30.0
_CLICK_ID_RE = re.compile(r"[A-Za-z0-9_.:-]{1,96}")


@dataclass(frozen=True)
class CalibratedCardLayout:
    """Full clickable bounds, *not* the already validated OCR title bands."""

    key: WindowKey
    calibration_id: str
    rects: dict[str, tuple[int, int, int, int]]  # client x, y, w, h


@dataclass(frozen=True)
class ClickObservation:
    """An in-game left-button down edge from a future approved local reader."""

    key: WindowKey
    client_point: tuple[int, int]
    at: float
    source: str
    event_id: str
    left_button_down_edge: bool
    league_foreground: bool


@dataclass(frozen=True)
class StandalonePickCandidate:
    """Unverified intent + independently verified disappearance.

    This is NOT the domain's PickedAugmentEvidence. In particular, it must
    never enter OfferLedger.confirm_verified_external or the build inputs.
    """

    match_id: str
    offer_id: int
    epoch: int
    catalog_id: str
    slot: str
    source: str = "standalone_visual_candidate"
    verified: bool = False


def _finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _valid_key(key: object) -> bool:
    if not isinstance(key, tuple) or len(key) != 2:
        return False
    hwnd, rect = key
    return (
        type(hwnd) is int and hwnd > 0
        and isinstance(rect, tuple) and len(rect) == 4
        and all(type(x) is int for x in rect)
        and rect[2] > rect[0] and rect[3] > rect[1]
    )


def _approved_rects(
    layout: CalibratedCardLayout, key: WindowKey,
) -> dict[str, tuple[int, int, int, int]] | None:
    if not isinstance(layout.rects, dict) or set(layout.rects) != set(SLOTS):
        return None
    width = key[1][2] - key[1][0]
    height = key[1][3] - key[1][1]
    chosen = {}
    for slot in SLOTS:
        rect = layout.rects[slot]
        if (not isinstance(rect, tuple) or len(rect) != 4
                or any(type(v) is not int for v in rect)):
            return None
        x, y, w, h = rect
        if x < 0 or y < 0 or w < 1 or h < 1 or x + w > width or y + h > height:
            return None
        chosen[slot] = (x, y, w, h)
    # Overlapping clickable zones make provenance of a single click ambiguous.
    for i, a in enumerate(SLOTS):
        for b in SLOTS[i + 1:]:
            x, y, w, h = chosen[a]
            u, v, sw, sh = chosen[b]
            if max(x, u) < min(x + w, u + sw) and max(y, v) < min(y + h, v + sh):
                return None
    return chosen


class StandalonePickCandidateGate:
    """Shadow-only: one click edge + three independently verified absences.

    Disabled by default. The future native reader must separately prove League
    foreground, the focused captured League window, a genuine input edge,
    independent clickable-card geometry, and an independent visual marker.
    No invocation from production is present in this phase.
    """

    def __init__(
        self, *, approved_calibration: str | None = None,
        approved_click_source: str | None = None,
    ) -> None:
        self._approved_calibration = (
            approved_calibration if isinstance(approved_calibration, str)
            and approved_calibration.strip() else None
        )
        self._approved_click_source = (
            approved_click_source if isinstance(approved_click_source, str)
            and approved_click_source.strip() else None
        )
        self._absence = VerifiedAbsenceGate(self._approved_calibration)
        self._issued_generations: set[tuple[str, int, int]] = set()
        self.reset()

    def reset(self) -> None:
        self._absence.suspend()
        self._context: tuple[str, int, int] | None = None
        self._key: WindowKey | None = None
        self._rects: dict[str, tuple[int, int, int, int]] = {}
        self._ids: dict[str, str] = {}
        self._opened_at = 0.0
        self._click: tuple[str, float] | None = None
        self._seen_click_ids: set[str] = set()
        self._last_visual_at: float | None = None
        self._invalid = False
        self._issued_generations.clear()

    def _disarm(self) -> None:
        self._absence.suspend()
        self._click = None
        self._invalid = True

    def begin(
        self, *, match_id: str, offer_id: int, epoch: int, key: WindowKey,
        layout: CalibratedCardLayout, verified_slots: dict[str, str],
        capture_proven: bool, at: float,
    ) -> bool:
        """Arm only a trusted three-card offer, with real card-area geometry."""
        context = (match_id, offer_id, epoch)
        if self._context == context:
            return False  # No rearm or duplicate candidate in the same offer.
        self._absence.suspend()
        self._context = None
        self._key = None
        self._click = None
        self._invalid = False
        self._seen_click_ids.clear()
        self._last_visual_at = None
        if (
            not self._approved_calibration
            or capture_proven is not True or not _valid_key(key)
            or not isinstance(layout, CalibratedCardLayout)
            or layout.key != key
            or layout.calibration_id != self._approved_calibration
            or not isinstance(match_id, str) or not 0 < len(match_id) <= 128
            or type(offer_id) is not int or offer_id < 1
            or type(epoch) is not int or epoch < 1
            or context in self._issued_generations
            or not _finite(at)
            or not isinstance(verified_slots, dict)
            or set(verified_slots) != set(SLOTS)
            or any(not isinstance(v, str) or not v for v in verified_slots.values())
            or len(set(verified_slots.values())) != len(SLOTS)
        ):
            return False
        rects = _approved_rects(layout, key)
        if rects is None:
            return False
        self._context = context
        self._key = key
        self._rects = rects
        self._ids = {slot: verified_slots[slot] for slot in SLOTS}
        self._opened_at = float(at)
        self._absence.confirm_present(key)
        return True

    def observe_click(self, obs: ClickObservation) -> bool:
        """Record one real focused left-button down edge in one exact card."""
        if self._context is None or self._key is None or self._invalid:
            return False
        if not isinstance(obs, ClickObservation):
            return False
        if obs.key != self._key or obs.league_foreground is not True:
            self._disarm()
            return False
        if (
            self._approved_click_source is None
            or obs.source != self._approved_click_source
            or obs.left_button_down_edge is not True
            or not isinstance(obs.event_id, str)
            or _CLICK_ID_RE.fullmatch(obs.event_id) is None
            or obs.event_id in self._seen_click_ids
            or not _finite(obs.at)
            or not self._opened_at <= obs.at <= self._opened_at + MAX_OPEN_TO_CLICK_S
            or not isinstance(obs.client_point, tuple)
            or len(obs.client_point) != 2
            or any(type(i) is not int for i in obs.client_point)
        ):
            return False
        px, py = obs.client_point
        hit = [
            slot for slot, (x, y, w, h) in self._rects.items()
            if x <= px < x + w and y <= py < y + h
        ]
        if len(hit) != 1:
            return False
        self._seen_click_ids.add(obs.event_id)
        if len(self._seen_click_ids) > 10:
            self._disarm()
            return False
        if self._click is not None and self._click[0] != hit[0]:
            self._disarm()  # Multiple candidate cards, cannot infer a pick.
            return False
        self._click = (hit[0], float(obs.at))
        self._absence.confirm_present(self._key)
        self._last_visual_at = None
        return True

    def observe_visual(
        self, cue: IndependentCue | None, *, at: float,
    ) -> StandalonePickCandidate | None:
        """Emit an UNVERIFIED candidate only after three safe absent reads."""
        if self._context is None or self._key is None or self._invalid:
            return None
        if not _finite(at) or (
            self._last_visual_at is not None and at <= self._last_visual_at
        ):
            self._absence.observe(None, self._key)
            return None
        self._last_visual_at = float(at)
        if not isinstance(cue, IndependentCue) or cue.key != self._key:
            self._disarm()
            return None
        if not self._absence.is_approved(cue, self._key):
            self._disarm()
            return None
        if cue.verdict in ("occluded", "unknown"):
            self._disarm()
            return None
        if self._click is None:
            self._absence.observe(cue, self._key)
            return None
        slot, click_at = self._click
        if at < click_at or at - click_at > MAX_CLICK_TO_DISAPPEAR_S:
            self._disarm()
            return None
        if not self._absence.observe(cue, self._key):
            return None
        match_id, offer_id, epoch = self._context
        result = StandalonePickCandidate(
            match_id=match_id, offer_id=offer_id, epoch=epoch,
            catalog_id=self._ids[slot], slot=slot,
        )
        self._issued_generations.add(self._context)
        self._disarm()
        return result
