"""F2/4C-01: fail-closed contract for independent Mayhem card-count evidence.

This module does not detect card shapes, read OCR titles, capture the screen,
or attest to a source's legitimacy. Only a separately reviewed, client-visible
visual counter with an approved calibration may construct trusted evidence.
Until native calibration exists there is no approved production producer.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

from backend.collectors.card_title_geometry import title_bands_from_client_rect
from backend.collectors.window_capture import CaptureProof


CardCountVerdict = Literal["unknown", "three_verified", "four_unsupported"]
_SOURCE = "calibrated_client_visual"
_FRAME_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_MIN_THREE_READS = 2
_MAX_SEEN_FRAMES = 128


@dataclass(frozen=True)
class CardCountEvidence:
    """One frame's independent visual layout report, never a proof by itself."""

    match_id: str
    offer_epoch: int
    window_key: tuple[int, tuple[int, int, int, int]]
    captured_at: float
    frame_id: str
    card_count: int | None
    source: str
    calibration_id: str
    verified: bool


class OfferCardCountGate:
    """Hold three-slot OCR until two distinct approved three-card observations.

    A credible four-card frame immediately forbids three-slot mapping. Any
    ambiguous, stale, unapproved or mismatched frame returns unknown and
    invalidates the preceding three-card streak. Nothing here ever confirms
    that a player selected or acquired an augment.
    """

    def __init__(self, approved_calibration: str | None = None) -> None:
        self._approved = (
            approved_calibration
            if isinstance(approved_calibration, str) and approved_calibration
            else None
        )
        self.reset()

    def reset(self) -> None:
        self._scope: tuple[object, ...] | None = None
        self._last_at: float | None = None
        self._seen_frames: set[str] = set()
        self._three_streak = 0

    def _valid(
        self, report: object, proof: object, *,
        match_id: str, offer_epoch: int,
    ) -> bool:
        if (self._approved is None or not isinstance(report, CardCountEvidence)
                or not isinstance(proof, CaptureProof)):
            return False
        if (report.verified is not True or report.source != _SOURCE
                or report.calibration_id != self._approved):
            return False
        if (not isinstance(match_id, str) or not match_id.strip()
                or report.match_id != match_id):
            return False
        if (type(offer_epoch) is not int or offer_epoch < 0
                or type(report.offer_epoch) is not int
                or report.offer_epoch != offer_epoch):
            return False
        if (proof.backend not in ("wgc", "mss_zorder")
                or proof.foreground != "league"
                or type(proof.hwnd) is not int or proof.hwnd <= 0
                or report.window_key != (proof.hwnd, proof.client_rect)
                or title_bands_from_client_rect(proof.client_rect) is None):
            return False
        if (not isinstance(report.frame_id, str)
                or not _FRAME_ID.fullmatch(report.frame_id)):
            return False
        if (type(report.card_count) is not int
                or report.card_count not in (3, 4)):
            return False
        for timestamp in (report.captured_at, proof.captured_at):
            if (not isinstance(timestamp, (int, float))
                    or isinstance(timestamp, bool)
                    or not math.isfinite(timestamp) or timestamp <= 0):
                return False
        return report.captured_at == proof.captured_at

    def observe(
        self, report: object, proof: CaptureProof, *,
        match_id: str, offer_epoch: int,
    ) -> CardCountVerdict:
        if not self._valid(report, proof, match_id=match_id,
                           offer_epoch=offer_epoch):
            self.reset()
            return "unknown"

        # _valid checked type and exact membership; the report is known.
        assert isinstance(report, CardCountEvidence)
        scope = (
            match_id, offer_epoch, report.window_key, report.calibration_id,
        )
        if self._scope != scope:
            self.reset()
            self._scope = scope
        if (report.frame_id in self._seen_frames
                or (self._last_at is not None
                    and report.captured_at <= self._last_at)
                or len(self._seen_frames) >= _MAX_SEEN_FRAMES):
            self.reset()
            return "unknown"

        self._seen_frames.add(report.frame_id)
        self._last_at = report.captured_at
        if report.card_count == 4:
            self._three_streak = 0
            return "four_unsupported"
        self._three_streak += 1
        if self._three_streak >= _MIN_THREE_READS:
            return "three_verified"
        return "unknown"
