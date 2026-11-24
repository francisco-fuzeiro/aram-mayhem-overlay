"""
ARAM Oracle — Screen OCR Augment Detection

Captures a screenshot of the augment selection area, runs OCR,
and fuzzy-matches detected text against known augment names.

Uses per-title-slot perceptual hashing and two consecutive consistent OCR
readings. Unchanged physical slots retain their verified names across rerolls.

Screenshots are never stored by default; explicitly opted-in debugging can save images.

Requires Tesseract OCR installed:
  Windows: winget install UB-Mannheim.TesseractOCR
  Or download from: https://github.com/UB-Mannheim/tesseract/wiki
"""
import hashlib
import math
import re
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from backend.collectors.league_window import find_league_window, LeagueWindow
from backend.collectors.window_capture import capture_league_client, reset_capture_state, CaptureProof
from backend.collectors.card_title_geometry import title_bands_from_client_rect
from backend.collectors.offer_card_count import OfferCardCountGate
from backend.collectors.slot_title_ocr import SlotMatches, crop_title_slots, recognize_title_slots
from backend.collectors.offer_visibility import (
    VerifiedAbsenceGate, IndependentCue, card_background_cue, CARD_BG_SHADOW_MODE,
)

logger = logging.getLogger("aram-oracle.ocr")

try:
    import mss
    import pytesseract
    from PIL import Image, ImageFilter, ImageEnhance, ImageOps
    from rapidfuzz import fuzz, process

    OCR_AVAILABLE = True
except ImportError as e:
    OCR_AVAILABLE = False
    logger.warning("OCR dependencies not installed: %s", e)

# Default Tesseract path on Windows (UB-Mannheim installer)
# Override with TESSERACT_PATH env var if Tesseract is installed elsewhere.
import os as _os

_DEFAULT_TESS_WIN = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_tess_path = _os.environ.get("TESSERACT_PATH", _DEFAULT_TESS_WIN)
if OCR_AVAILABLE and Path(_tess_path).exists():
    pytesseract.pytesseract.tesseract_cmd = _tess_path


# -- Paths: screenshots are never stored in the installed bundle or git checkout --
def default_screenshot_dir() -> Path:
    from backend.diagnostic_events import default_log_dir
    return default_log_dir().parent / "screenshots"


SCREENSHOT_DIR = default_screenshot_dir()

# -- Screen regions --
# Region as fractions of screen: (left%, top%, right%, bottom%)
AUGMENT_REGION_16_9 = (0.15, 0.22, 0.85, 0.50)
AUGMENT_REGION_21_9 = (0.24, 0.22, 0.76, 0.50)  # Ultrawide letterboxed
AUGMENT_REGION_16_10 = (0.15, 0.20, 0.85, 0.48)

# Legacy alias for backwards compatibility
AUGMENT_REGION = AUGMENT_REGION_16_9

# Minimum fuzzy match score to accept (0-100)
MATCH_THRESHOLD = 65

# Minimum text length to even attempt matching
MIN_TEXT_LEN = 3

# Max screenshots to keep (oldest get cleaned up)
MAX_SCREENSHOTS = 15
MAX_SCREENSHOT_AGE_SECONDS = 3 * 24 * 3600

# Perceptual hash size (NxN grid). Higher = more sensitive to small changes.
HASH_SIZE = 32
BURST_SECOND_READ_DELAY_S = 0.5  # A4: one fresh, proven second capture in the same tick
# Field 24/11 (latency): capture_invalid cost 6-8 s in every augment window.
# A transient WGC miss (no fresh frame yet, a repeated callback) is retried a
# few times inside the same tick instead of costing a whole poll cycle and a
# full three-slot re-verification.
CAPTURE_RETRY_ATTEMPTS = 4
CAPTURE_RETRY_DELAY_S = 0.08
TRANSIENT_CAPTURE_REASONS = frozenset(("invalid_frame", "backend_unavailable"))



_logged_resolution = False


def get_augment_region(screen_width: int, screen_height: int) -> tuple[float, float, float, float]:
    """Return the augment screen region adjusted for aspect ratio."""
    # Check config override first
    try:
        from backend.config import config
        override = config.get("ocr_region")
        if isinstance(override, (list, tuple)) and len(override) == 4:
            try:
                fracs = tuple(float(x) for x in override)
            except (TypeError, ValueError):
                fracs = ()
            if len(fracs) == 4 and all(math.isfinite(v) for v in fracs):
                left, top, right, bottom = fracs
                area = (right - left) * (bottom - top)
                if (0 <= left < right <= 1 and 0 <= top < bottom <= 1
                        and area <= 0.5):
                    return fracs
            logger.warning("OCR region override rejected: must remain inside League client")
    except Exception:
        pass

    ratio = screen_width / screen_height if screen_height > 0 else 1.78

    if ratio >= 2.2:       # 21:9 ultrawide (2.33)
        return AUGMENT_REGION_21_9
    elif ratio >= 1.55:    # 16:9 (1.78) and 16:10 (1.6)
        return AUGMENT_REGION_16_9
    else:                  # 4:3 or other
        return AUGMENT_REGION_16_9


# -- Perceptual hashing --


def _perceptual_hash(img: "Image.Image") -> str:
    """Compute a perceptual hash (average hash) of an image.

    Resizes to a small grid, converts to grayscale, and compares each pixel
    to the mean. Returns a hex string. Fast (~1ms).
    """
    small = img.resize((HASH_SIZE, HASH_SIZE), Image.LANCZOS).convert("L")
    pixels = list(small.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if p > avg else "0" for p in pixels)
    # Convert to hex for compact storage
    return hex(int(bits, 2))[2:].zfill(HASH_SIZE * HASH_SIZE // 4)


def _hamming_distance(hash1: str, hash2: str) -> int:
    """Count differing bits between two hex hash strings."""
    if len(hash1) != len(hash2):
        return HASH_SIZE * HASH_SIZE  # max distance if incompatible
    val1 = int(hash1, 16)
    val2 = int(hash2, 16)
    xor = val1 ^ val2
    return bin(xor).count("1")


class ScreenWatcher:
    """Verified League-window title watcher with three independent temporal slots.

    A slot's title is accepted only after two stable, matching OCR readings.
    Focus loss suspends comparisons instead of interpreting a changed desktop
    frame as a reroll. C4 will separately implement offer visibility.
    """

    def __init__(
        self, *, independent_observer=None, approved_calibration: str | None = None,
        sleep_fn=None, card_count_observer=None,
        approved_card_count_calibration: str | None = None,
        skip_ocr_without_cards: bool = False,
        emit_diagnostics: bool = True,
    ) -> None:
        import threading
        from backend.collectors.slot_temporal import SlotTemporalTracker

        self._lock = threading.RLock()
        self._sleep = sleep_fn if sleep_fn is not None else time.sleep
        self._temporal = SlotTemporalTracker()
        # Production passes neither observer nor calibration: no automatic
        # disappearance. Tests may inject only synthetic independent cues.
        self._independent_observer = independent_observer
        self._absence_gate = VerifiedAbsenceGate(approved_calibration)
        # A separate, reviewed client-visible card counter may be injected in
        # future; production supplies no source/calibration and runs unchanged.
        # Title OCR, geometry and card-background pixels cannot supply count proof.
        self._card_count_observer = card_count_observer
        self._card_count_gate = OfferCardCountGate(approved_card_count_calibration)
        self._capture_stale = False
        self._refocus_pending = False
        self._transition_open = False
        self._last_detected: list[tuple[str, str, int]] = []
        self._last_scan_stage = "not_scanned"
        self._last_foreground = "other"  # A5 diagnostic, never a capture gate.
        self._last_capture_backend: str | None = None  # Read-only D2 diagnostics.
        self._last_background_observation: tuple[str, str] | None = None
        self._f0_geometry_size: tuple[int, int] | None = None  # trace only
        # Field fix 23/11 (latency): with NO card background in any title band
        # there is nothing to read, so skip Tesseract. Never proves absence of
        # an offer to the ledger; presence/disappearance stay elsewhere.
        self._skip_ocr_without_cards = skip_ocr_without_cards
        # The Anvil popup watcher shares no state with the augment watcher; its
        # stages must not be mixed into the augment window timings either.
        self._emit_diagnostics = emit_diagnostics
        self._tick_started: float | None = None
        self._tick_capture_s = 0.0
        self._tick_attempts = 0

    @property
    def last_scan_stage(self) -> str:
        with self._lock:
            return self._last_scan_stage

    @property
    def last_capture_backend(self) -> str | None:
        with self._lock:
            return self._last_capture_backend

    def _set_scan_stage(self, stage: str) -> None:
        # Only internal bounded constants, never untrusted OCR text or paths.
        from backend.diagnostic_events import events
        if stage not in SCAN_STAGES:
            stage = "not_scanned"
        self._last_scan_stage = stage
        if self._emit_diagnostics:
            events.transition("ocr_scan_stage", stage=stage)
            self._emit_tick(stage)

    def _emit_tick(self, stage: str, reason: str | None = None) -> None:
        """Bounded per-tick timings (field 24/11: where do the seconds go?)."""
        if self._tick_started is None:
            return
        from backend.diagnostic_events import events
        from backend.collectors.window_capture import last_invalid_detail
        total = time.monotonic() - self._tick_started
        self._tick_started = None
        fields = {
            "stage": stage,
            "total_ms": int(round(total * 1000)),
            "capture_ms": int(round(self._tick_capture_s * 1000)),
            "attempts": self._tick_attempts,
        }
        if reason is not None:
            fields["reason"] = reason if reason in CAPTURE_REASONS else "other"
            fields["detail"] = last_invalid_detail()
        events.emit("ocr_tick", **fields)

    def _capture(self, monitor_index: int, game: LeagueWindow,
                 after: float | None = None) -> "RegionCapture":
        """Capture with a bounded in-tick retry of transient WGC misses.

        Every returned image still carries the full A3 proof; ``after``
        additionally requires a newer WGC callback than the first frame.
        """
        result = None
        for attempt in range(CAPTURE_RETRY_ATTEMPTS):
            if attempt:
                try:
                    self._sleep(CAPTURE_RETRY_DELAY_S)
                except (OSError, RuntimeError):
                    break
            started = time.monotonic()
            result = capture_augment_region(monitor_index, league_window=game)
            self._tick_capture_s += time.monotonic() - started
            self._tick_attempts += 1
            if self._verified_region(result, game):
                if after is None or result.proof.captured_at > after:
                    return result
                continue  # A repeated callback is not a second read.
            reason = result.reason if isinstance(result, RegionCapture) else "invalid_frame"
            if reason not in TRANSIENT_CAPTURE_REASONS:
                return result
        if (after is not None and isinstance(result, RegionCapture)
                and self._verified_region(result, game)):
            return RegionCapture(None, None, "invalid_frame")
        return result

    def _record_shadow_cue(
        self, crops: dict[str, "Image.Image"], *, ocr_titles: bool = False,
    ) -> None:
        """C1 evidence only: never touch the independent absence gate or actions."""
        if not CARD_BG_SHADOW_MODE:
            return
        observation = (
            card_background_cue(crops), "titles" if ocr_titles else "none",
        )
        if observation == self._last_background_observation:
            return
        self._last_background_observation = observation
        from backend.diagnostic_events import events
        events.transition("offer_cue", cue=observation[0], ocr=observation[1])

    def reset(self) -> None:
        """Forget the completed offer, without altering any player action."""
        with self._lock:
            self._temporal.reset()
            self._absence_gate.suspend()
            self._card_count_gate.reset()
            self._capture_stale = False
            self._refocus_pending = False
            self._transition_open = False
            self._last_detected = []
            self._set_scan_stage("not_scanned")
            self._last_foreground = "other"
            self._last_capture_backend = None
            self._last_background_observation = None
            self._f0_geometry_size = None
            reset_capture_state()  # End of offer/match closes the WGC HWND session.

    @staticmethod
    def _verified_region(capture: "RegionCapture", game: LeagueWindow) -> bool:
        """Defensively require A3 source evidence for each OCR observation."""
        if (not isinstance(capture, RegionCapture) or capture.reason != "ok"
                or capture.image is None or not isinstance(capture.proof, CaptureProof)):
            return False
        proof = capture.proof
        return (
            proof.backend in ("wgc", "mss_zorder")
            and proof.hwnd == game.hwnd
            and proof.client_rect == game.rect
            and isinstance(proof.captured_at, (int, float))
            and math.isfinite(proof.captured_at)
            and proof.captured_at > 0
        )

    def _capture_failure(self, reason: str) -> tuple[str, None]:
        """Discard pending OCR and preserve A3's conservative failure mapping.

        Field 24/11: a transient frame miss (no fresh WGC frame after the
        in-tick retries) is NOT a focus/occlusion loss. It skips this tick but
        keeps the C3 baselines and pending reads, so it no longer forces all
        three slots to be read twice again. Window loss, minimise and
        occlusion keep the full conservative suspension.
        """
        if reason in TRANSIENT_CAPTURE_REASONS:
            self._last_capture_backend = None
            self._last_background_observation = None
            self._transition_open = False
            self._set_failure_stage("capture_invalid", reason)
            if self._emit_diagnostics:
                from backend.diagnostic_events import events
                events.transition("ocr_recognition", outcome="capture_unavailable")
            return ("capture_unavailable", None)
        self._card_count_gate.reset()
        self._capture_stale = True
        self._last_foreground = "other"
        self._last_capture_backend = None
        self._last_background_observation = None
        self._temporal.suspend()
        self._absence_gate.suspend()
        self._refocus_pending = True
        self._transition_open = False
        if reason in ("no_window", "minimized", "unsupported_platform"):
            stage, action = "game_window_unavailable", "unavailable"
        elif reason == "occluded":
            stage, action = "game_occluded", "occluded"
        else:
            stage, action = "capture_invalid", "capture_unavailable"
        self._set_failure_stage(stage, reason)
        if self._emit_diagnostics:
            from backend.diagnostic_events import events
            events.transition("ocr_recognition", outcome=action)
        return (action, None)

    def _set_failure_stage(self, stage: str, reason: str) -> None:
        if self._emit_diagnostics:
            self._emit_tick(stage, reason)
        self._set_scan_stage(stage)

    def _independent_card_layout(
        self, capture: "RegionCapture", game: LeagueWindow,
        match_id: str | None, offer_epoch: int | None,
    ) -> str:
        """Opt-in layout attestation; never count using three cropped titles.

        The observed report is bound to the *same* verified capture, window,
        match and epoch. A source failure is unverified, not assumed three.
        The default installation has no producer and preserves legacy scans.
        """
        if self._card_count_observer is None:
            return "legacy_disabled"
        try:
            report = self._card_count_observer(
                capture.image, game, capture.proof, match_id, offer_epoch,
            )
        except Exception as exc:
            # No paths, OCR text, screenshots or dynamic exception messages.
            logger.warning("Independent layout source failed: %s", type(exc).__name__)
            report = None
        return self._card_count_gate.observe(
            report, capture.proof,
            match_id=match_id if isinstance(match_id, str) else "",
            offer_epoch=offer_epoch if type(offer_epoch) is int else -1,
        )

    def _layout_abstain(self, verdict: str) -> tuple[str, None]:
        """Never use previously accepted three-slot names across layout doubt."""
        self._capture_stale = True
        # A four-card or unknown panel must not leave a prior three-card
        # snapshot addressable. Suspend afterwards so new titles are marked
        # freshly reverified before the stale UI can recover.
        self._temporal.reset()
        self._temporal.suspend()
        self._absence_gate.suspend()
        self._refocus_pending = True
        self._transition_open = False
        self._last_detected = []
        self._last_background_observation = None
        self._set_scan_stage(
            "layout_four_unsupported"
            if verdict == "four_unsupported" else "layout_unverified"
        )
        return ("transition", None)

    def check(
        self,
        augment_names: dict[str, str],
        monitor_index: int = 1,
        save: bool = False,
        *,
        match_id: str | None = None,
        offer_epoch: int | None = None,
    ) -> tuple[str, SlotMatches | None]:
        """Observe each changed title crop and return only verified slot changes.

        This synchronous operation is invoked via to_thread by the poll loop;
        locking also serializes manual scans and prevents overlapping OCR
        calls from mixing their temporal order.
        """
        from backend.collectors.slot_title_ocr import recognize_title_slot

        with self._lock:
            self._tick_started = time.monotonic()
            self._tick_capture_s = 0.0
            self._tick_attempts = 0
            if not is_available():
                self._card_count_gate.reset()
                self._last_background_observation = None
                self._capture_stale = True
                self._temporal.suspend()
                self._absence_gate.suspend()
                self._refocus_pending = True
                self._transition_open = False
                self._set_scan_stage("ocr_unavailable")
                return ("unavailable", None)

            game = find_league_window()
            if game is None:
                self._card_count_gate.reset()
                self._last_background_observation = None
                self._capture_stale = True
                self._temporal.suspend()
                self._absence_gate.suspend()
                self._refocus_pending = True
                self._transition_open = False
                self._set_scan_stage("game_window_unavailable")
                return ("unavailable", None)
            result = self._capture(monitor_index, game)
            if not self._verified_region(result, game):
                reason = (
                    result.reason if isinstance(result, RegionCapture) and result.reason != "ok"
                    else "proof_invalid"  # never a transient miss: full suspension
                )
                return self._capture_failure(reason)
            capture = result
            self._last_foreground = capture.proof.foreground
            self._last_capture_backend = capture.proof.backend
            img = capture.image
            if self._capture_stale:
                self._temporal.suspend()
                self._capture_stale = False
                self._refocus_pending = True

            # F2/4C: an optional independently approved count must authorize
            # all three-slot processing before any crop/title OCR is read.
            layout = self._independent_card_layout(
                capture, game, match_id, offer_epoch,
            )
            if layout not in ("legacy_disabled", "three_verified"):
                return self._layout_abstain(layout)

            rect = game.rect
            width, height = rect[2] - rect[0], rect[3] - rect[1]
            crops = crop_title_slots(img, rect, get_augment_region(width, height))
            if crops is None:
                self._last_background_observation = None
                self._capture_stale = True
                self._temporal.suspend()
                self._absence_gate.suspend()
                self._refocus_pending = True
                self._transition_open = False
                self._set_scan_stage("geometry_unsupported")
                return ("unavailable", None)

            if self._skip_ocr_without_cards:
                from backend.collectors.card_presence import downsample
                if card_background_cue(downsample(crops)) == "absent":
                    self._transition_open = False
                    current = self._temporal.snapshot()
                    self._set_scan_stage("cards_absent")
                    return ("unchanged" if current is not None else "no_augments", None)

            # Record *relative* physical title rectangles once per client
            # dimension, and only after verified capture+valid ROI geometry.
            # Never log the HWND, desktop origin, crop pixels or OCR text.
            if (_os.environ.get("ARAM_ORACLE_F0_TRACE") == "1"
                    and self._f0_geometry_size != (width, height)):
                from backend.workflow.f0_trace import emit_f0_geometry
                if emit_f0_geometry(
                    (width, height), title_bands_from_client_rect(game.rect),
                ):
                    self._f0_geometry_size = (width, height)

            # A separate classifier may be plugged in ONLY after real native
            # absent/dialogue fixtures validate a code-reviewed calibration.
            # OCR title absence, changing hashes and time are never negative
            # evidence. In production this remains None (disabled).
            key = (game.hwnd, game.rect)
            cue = None
            if self._independent_observer is not None:
                try:
                    cue = self._independent_observer(img, game)
                except Exception:
                    logger.exception("Independent offer visual cue failed closed")
            # A4 must not discard a calibrated first-frame occlusion when
            # the next frame becomes readable: the provisional title scan
            # cannot be allowed to confirm a possibly obstructed offer.
            if self._absence_gate.is_approved(cue, key) and cue.verdict == "occluded":
                self._record_shadow_cue(crops)  # A3-proven first image; OCR withheld.
                self._temporal.suspend()
                self._transition_open = False
                self._refocus_pending = False
                self._set_scan_stage("titles_transition")
                return ("transition", None)

            result = self._temporal.observe(
                crops, augment_names, recognize_title_slot,
                _perceptual_hash, _hamming_distance,
            )
            if result is None and self._temporal.has_pending:
                # Reverting to a historical baseline within this burst must
                # not make an interrupted offer current without fresh proof.
                if self._temporal.snapshot() is not None and not self._refocus_pending:
                    self._transition_open = True
                # Do not carry one pending frame across occlusion to complete
                # temporal verification. Re-capture and independently prove
                # the second frame in this serialized, worker-thread tick.
                try:
                    self._sleep(BURST_SECOND_READ_DELAY_S)
                except (OSError, RuntimeError):
                    return self._capture_failure("invalid_frame")
                # A3 can return the latest WGC callback more than once. A
                # previously observed callback must never count as a new read;
                # field 23/11-24/11: wait briefly for a newer one in-tick.
                second = self._capture(
                    monitor_index, game, after=capture.proof.captured_at,
                )
                if not self._verified_region(second, game):
                    reason = (
                        second.reason if isinstance(second, RegionCapture) and second.reason != "ok"
                        else "proof_invalid"  # never a transient miss: full suspension
                    )
                    return self._capture_failure(reason)
                # A four-card transition during the second C3 read invalidates
                # the provisional first-frame OCR before any accepted result.
                second_layout = self._independent_card_layout(
                    second, game, match_id, offer_epoch,
                )
                if second_layout not in ("legacy_disabled", "three_verified"):
                    return self._layout_abstain(second_layout)
                second_crops = crop_title_slots(
                    second.image, rect, get_augment_region(width, height),
                )
                if second_crops is None:
                    self._last_background_observation = None
                    self._capture_stale = True
                    self._temporal.suspend()
                    self._absence_gate.suspend()
                    self._refocus_pending = True
                    self._transition_open = False
                    self._set_scan_stage("geometry_unsupported")
                    return ("unavailable", None)
                capture = second
                crops = second_crops  # C1 observes only the final independently proven frame.
                self._last_foreground = capture.proof.foreground
                img = capture.image
                if self._independent_observer is not None:
                    try:
                        cue = self._independent_observer(img, game)
                    except Exception:
                        logger.exception("Independent offer visual cue failed closed")
                        cue = None
                result = self._temporal.observe(
                    second_crops, augment_names, recognize_title_slot,
                    _perceptual_hash, _hamming_distance,
                )
            pending = self._temporal.has_unverified_changes
            current = self._temporal.snapshot()
            fresh_named = (
                result is not None and not pending and
                any(value is not None for value in result.slots.values())
            )
            # This reports colour evidence from the current A3-proven frame.
            # Historical/stale or still-verifying OCR never masquerades as titles.
            self._record_shadow_cue(
                crops,
                ocr_titles=(
                    current is not None and not pending
                    and not self._refocus_pending
                    and any(value is not None for value in current.slots.values())
                ),
            )

            if fresh_named:
                self._absence_gate.confirm_present(key)
            elif pending or (
                current is not None and
                all(value is None for value in current.slots.values())
            ):
                # Three independently approved negative scans may close an
                # already positively verified offer. No approved production
                # observer exists yet, so this cannot fire in actual games.
                if self._absence_gate.observe(cue, key):
                    self._transition_open = False
                    self._set_scan_stage("verified_absence")
                    return ("disappeared", None)
            else:
                self._absence_gate.observe(None, key)

            if self._absence_gate.is_approved(cue, key) and cue.verdict == "occluded":
                # Independent dialogue/occlusion evidence hides advice now.
                # Force two fresh C3 reads before accepting the cards again.
                self._temporal.suspend()
                self._transition_open = False
                self._refocus_pending = False
                self._set_scan_stage("titles_transition")
                return ("transition", None)

            if pending:
                # C3 may have already verified one slot while another is still
                # animating. Withhold the entire snapshot until ALL pending
                # slots have settled, retaining old IDs only for diagnostics.
                if self._refocus_pending:
                    # B2: never claim an unchanged verified offer if no
                    # historical C3 snapshot exists on this focus recovery.
                    self._set_scan_stage("titles_verifying")
                    return ("unchanged" if current is not None else "no_augments", None)
                if current is not None:
                    self._transition_open = True
                    self._set_scan_stage("titles_verifying")
                    return ("transition", None)
                self._set_scan_stage("titles_verifying")
                return ("no_augments", None)

            if result is not None:
                self._transition_open = False
                self._refocus_pending = False
                self._last_detected = list(result)
                if save:
                    save_screenshot(
                        img, label="verified_title_slots", proof=capture.proof,
                    )
                self._set_scan_stage("titles_detected")
                return ("detected", result)

            if self._transition_open:
                # A one-frame animation returned to the old visual baseline,
                # but that historical identity must not become current without
                # two fresh OCR confirmations across the three physical slots.
                self._temporal.suspend()
                self._transition_open = False
                self._set_scan_stage("titles_transition")
                return ("transition", None)

            self._set_scan_stage("titles_unchanged" if current is not None else "titles_unidentified")
            return ("unchanged" if current is not None else "no_augments", None)

    @property
    def verifying_named(self) -> bool:
        """Some slot has a pending read naming an augment (cards are augments)."""
        with self._lock:
            return self._temporal.has_named_pending

    @property
    def current_slots(self) -> SlotMatches | None:
        with self._lock:
            return self._temporal.snapshot()

    @property
    def last_detected(self) -> list[tuple[str, str, int]]:
        with self._lock:
            return list(self._last_detected)

    @property
    def has_detection(self) -> bool:
        with self._lock:
            return self._temporal.snapshot() is not None


# Fixed codes for safe, bounded OCR diagnostics. Never record captured pixels,
# raw OCR strings, player data or local filesystem paths.
CAPTURE_REASONS = frozenset((
    "no_window", "minimized", "occluded", "backend_unavailable",
    "invalid_frame", "window_changed", "unsupported_platform",
))
SCAN_STAGES = frozenset((
    "not_scanned", "ocr_unavailable", "game_window_unavailable",
    "game_not_focused", "game_occluded", "capture_invalid",
    "capture_unavailable", "geometry_unsupported",
    "titles_verifying", "titles_unidentified",
    "titles_detected", "titles_unchanged", "titles_transition",
    "layout_unverified", "layout_four_unsupported", "verified_absence",
    "cards_absent",
))


# -- Module-level singleton --
watcher = ScreenWatcher(skip_ocr_without_cards=True)


# -- Standalone functions (unchanged API for backwards compat) --


def readiness_status() -> dict[str, bool | str]:
    """Pre-game dependency preflight; never claims League OCR accuracy.

    Return only fixed, safe reason codes and setup instructions. In
    particular, do not expose installed paths, environment values or raw
    subprocess errors through the local API.
    """
    if not OCR_AVAILABLE:
        return {
            "available": False,
            "reason": "python_dependencies_missing",
            "next_step": "Install the application OCR Python dependencies and restart ARAM Oracle.",
        }
    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:
        # A malformed/broken executable should not crash Settings. Paths and
        # subprocess output can include private local data: log the type only.
        logger.debug("Tesseract preflight failed: %s", type(exc).__name__)
        if _os.environ.get("TESSERACT_PATH"):
            return {
                "available": False,
                "reason": "configured_executable_unavailable",
                "next_step": "Check TESSERACT_PATH points to a working tesseract.exe and restart ARAM Oracle.",
            }
        return {
            "available": False,
            "reason": "executable_unavailable",
            "next_step": (
                "Install Tesseract with winget install UB-Mannheim.TesseractOCR "
                "(Windows), then restart ARAM Oracle. If already installed, "
                "set TESSERACT_PATH to its executable and restart."
            ),
        }
    try:
        # The executable version alone does not prove that --lang eng can
        # decode League card titles. Keep the probe read-only and path-free.
        languages = pytesseract.get_languages(config="")
    except Exception as exc:
        logger.debug("Tesseract language probe failed: %s", type(exc).__name__)
        return {
            "available": False,
            "reason": "language_probe_unavailable",
            "next_step": "Verify the Tesseract language data installation (eng) and TESSDATA_PREFIX, then restart ARAM Oracle.",
        }
    if "eng" not in languages:
        return {
            "available": False,
            "reason": "english_language_missing",
            "next_step": "Install the English Tesseract traineddata (eng) or correct TESSDATA_PREFIX, then restart ARAM Oracle.",
        }
    return {
        "available": True,
        "reason": "ready",
        "next_step": "Tesseract and English traineddata are available. League card recognition still requires Windows validation.",
    }


def is_available() -> bool:
    """Backward-compatible boolean dependency gate, sharing Settings preflight."""
    return bool(readiness_status()["available"])


def screenshot_opted_in() -> bool:
    """Only a strict opt-in in config enables diagnostic card images."""
    from backend.config import config
    return config.get("ocr_debug_screenshots", False) is True


def _prune_screenshots(directory: Path) -> None:
    """Bound retention by both 72-hour age and maximum crop-file count."""
    now = time.time()
    paths = sorted(directory.glob("card_*.png"), key=lambda p: p.stat().st_mtime)
    for path in list(paths):
        try:
            if now - path.stat().st_mtime > MAX_SCREENSHOT_AGE_SECONDS:
                path.unlink()
                paths.remove(path)
        except OSError:
            pass
    while len(paths) > MAX_SCREENSHOTS:
        path = paths.pop(0)
        try:
            path.unlink()
        except OSError:
            pass


def _ensure_screenshot_dir() -> Path:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    _prune_screenshots(SCREENSHOT_DIR)
    return SCREENSHOT_DIR


@dataclass(frozen=True)
class RegionCapture:
    """Verified League augment ROI. A bare PIL image is never OCR evidence."""
    image: "Image.Image | None"
    proof: CaptureProof | None
    reason: str
    occluder: str | None = None


def capture_augment_region(
    monitor_index: int = 1, *, league_window: LeagueWindow | None = None,
) -> RegionCapture:
    """Crop from a validated *window* frame, never from the desktop.

    The legacy monitor_index is ignored. A typed proof is compulsory for OCR
    and for optional title-only diagnostics. Focus is diagnostic, not a gate.
    """
    if not OCR_AVAILABLE:
        return RegionCapture(None, None, "backend_unavailable")
    game = league_window if league_window is not None else find_league_window()
    if game is None:
        return RegionCapture(None, None, "no_window")
    from backend.config import config
    capture = capture_league_client(
        game, allow_screen_copy_fallback=(
            config.get("allow_screen_copy_fallback") is True
        ),
    )
    if capture.reason != "ok" or capture.image is None or capture.proof is None:
        return RegionCapture(None, None, capture.reason, capture.occluder)
    if capture.proof.hwnd != game.hwnd or capture.proof.client_rect != game.rect:
        return RegionCapture(None, None, "window_changed")
    width, height = game.right - game.left, game.bottom - game.top
    a, b, c, d = get_augment_region(width, height)
    bounds = (
        int(width * a), int(height * b),
        int(width * a) + int(width * (c - a)),
        int(height * b) + int(height * (d - b)),
    )
    if (capture.image.mode != "RGB" or capture.image.size != (width, height)
            or bounds[0] < 0 or bounds[1] < 0
            or bounds[2] > width or bounds[3] > height
            or bounds[2] <= bounds[0] or bounds[3] <= bounds[1]):
        return RegionCapture(None, None, "invalid_frame")
    return RegionCapture(capture.image.crop(bounds), capture.proof, "ok")


def save_screenshot(
    img: "Image.Image",
    label: str = "",
    ocr_texts: list[str] | None = None,
    matches: list[tuple[str, str, int]] | None = None,
    *, proof: CaptureProof | None = None,
) -> Path | None:
    """Save only bounded card-title crops from a proven League window.

    Legacy label/OCR text/matches arguments are intentionally ignored:
    they never enter filenames, images or logs. Full window/screen images
    cannot pass the client augment-region dimension and source-proof checks.
    """
    if not OCR_AVAILABLE or not screenshot_opted_in():
        return None
    game = find_league_window()
    if (game is None or not isinstance(proof, CaptureProof)
            or proof.hwnd != game.hwnd or proof.client_rect != game.rect
            or proof.backend not in ("wgc", "mss_zorder")
            or proof.captured_at <= 0):
        return None
    left, top, right, bottom = game.rect
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        return None
    a, b, c, d = get_augment_region(width, height)
    expected_size = (int(width * (c - a)), int(height * (d - b)))
    if img.size != expected_size or img.width < 150 or img.height < 50:
        logger.warning("Diagnostic image rejected: not a verified League augment region")
        return None

    # Pure, reviewed client-relative title geometry. The OCR *region* may
    # contain icons and other screen elements; persist only verified bounds.
    bands = title_bands_from_client_rect(game.rect)
    if bands is None:
        logger.debug("Diagnostic title crops unavailable for this client geometry")
        return None

    # The captured image origin is the OCR region within the focused client,
    # not the desktop or a third of the OCR strip.
    region_left = int(width * a)
    region_top = int(height * b)
    crops = []
    for slot, (x, y, band_width, band_height) in bands.items():
        lx, ly = x - region_left, y - region_top
        bounds = (lx, ly, lx + band_width, ly + band_height)
        if (lx < 0 or ly < 0 or bounds[2] > img.width
                or bounds[3] > img.height):
            # Fail closed if a custom OCR region excludes any title; never
            # silently clip or persist a non-title portion of the game.
            logger.debug("Diagnostic title band outside captured League region")
            return None
        crops.append((slot, bounds))

    try:
        directory = _ensure_screenshot_dir()
        stamp = time.time_ns()
        first: Path | None = None
        for index, (slot, bounds) in enumerate(crops):
            path = directory / f"card_{slot}_{stamp}_{index}.png"
            img.crop(bounds).save(path, "PNG")
            if first is None:
                first = path
        _prune_screenshots(directory)
        return first
    except OSError as exc:
        logger.warning("Card crop save failed: %s", type(exc).__name__)
        return None


def preprocess_for_ocr(img: "Image.Image") -> "Image.Image":
    """Enhance screenshot for better OCR accuracy on game UI."""
    w, h = img.size
    if w < 1500:
        img = img.resize((w * 2, h * 2), Image.LANCZOS)

    gray = img.convert("L")

    enhancer = ImageEnhance.Contrast(gray)
    gray = enhancer.enhance(2.5)

    gray = gray.filter(ImageFilter.SHARPEN)

    pixels = list(gray.getdata())
    avg = sum(pixels) / len(pixels) if pixels else 128
    if avg < 128:
        gray = ImageOps.invert(gray)

    return gray


def extract_text(img: "Image.Image") -> list[str]:
    """Run OCR on preprocessed image and return candidate text lines."""
    if not OCR_AVAILABLE:
        return []

    processed = preprocess_for_ocr(img)

    try:
        raw = pytesseract.image_to_string(
            processed,
            lang="eng",
            config="--psm 6 --oem 3",
        )
    except (OSError, RuntimeError) as e:
        logger.error("OCR failed: %s", e)
        return []

    lines = []
    for line in raw.split("\n"):
        cleaned = line.strip()
        if len(cleaned) >= MIN_TEXT_LEN and any(c.isalpha() for c in cleaned):
            lines.append(cleaned)

    return lines


def _normalize_augment_text(text: str) -> str:
    """Normalize OCR noise to the same alphabet as augment catalog names."""
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def match_augments(
    ocr_texts: list[str],
    augment_names: dict[str, str],
    threshold: int | None = None,
) -> list[tuple[str, str, int]]:
    """Match offered augments, including titles wrapped across OCR lines.

    Adjacent-line joining and normalization adapted from the pure matcher in
    zp96-cmd/mayhem-overlay/src/main/ocr-match.js (MIT declared in its package
    metadata; Copyright 2026 Zac Pitts; see THIRD_PARTY_NOTICES.md).
    Retains our existing rapidfuzz matcher and the 3-card maximum.
    """
    if not OCR_AVAILABLE or not ocr_texts or not augment_names:
        return []

    if threshold is None:
        try:
            from backend.config import config
            threshold = config.get("match_threshold", MATCH_THRESHOLD)
        except Exception:
            threshold = MATCH_THRESHOLD

    name_to_id: dict[str, str] = {}
    for aug_id, name in augment_names.items():
        normalized = _normalize_augment_text(name)
        if normalized:
            name_to_id[normalized] = str(aug_id)
    if not name_to_id:
        return []
    all_names = list(name_to_id)

    normalized_lines = [
        _normalize_augment_text(line) for line in ocr_texts
        if isinstance(line, str)
    ]
    normalized_lines = [line for line in normalized_lines if len(line) >= MIN_TEXT_LEN]

    # The Mayhem Overlay matcher joins neighbouring OCR lines when an augment
    # title wraps, rather than treating each line as a separate augment.
    joined_lines = [
        normalized_lines[index] + " " + normalized_lines[index + 1]
        for index in range(len(normalized_lines) - 1)
    ]
    texts = normalized_lines + joined_lines

    matches: dict[str, tuple[str, int]] = {}
    name_by_id = {str(aug_id): name for aug_id, name in augment_names.items()}

    for text in texts:
        variants = [text]
        words = text.split()
        # Existing fragment search, useful for text with borders or UI labels.
        for start in range(len(words)):
            for stop in range(start + 1, min(start + 6, len(words) + 1)):
                fragment = " ".join(words[start:stop])
                if len(fragment) >= MIN_TEXT_LEN:
                    variants.append(fragment)

        for variant in variants:
            result = process.extractOne(
                variant,
                all_names,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=threshold,
            )
            if result:
                normalized_name, score, _ = result
                aug_id = name_to_id[normalized_name]
                if aug_id not in matches or score > matches[aug_id][1]:
                    matches[aug_id] = (name_by_id[aug_id], int(score))

    sorted_matches = sorted(
        ((aid, name, score) for aid, (name, score) in matches.items()),
        key=lambda result: (-result[2], result[1]),
    )
    # An augment offer has three cards. Reject weak incidental labels when
    # three confident matches have already been found.
    strong = [item for item in sorted_matches if item[2] >= 85]
    return (strong if len(strong) >= 3 else sorted_matches)[:3]


def detect_augments(
    augment_names: dict[str, str],
    monitor_index: int = 1,
    save: bool = False,
) -> list[tuple[str, str, int]]:
    """Manual capture uses exactly the automatic two-read temporal gate.

    A single manual request may return no fresh result while the second
    observation is pending. A later automatic/manual tick finishes the gate.
    Never bypass strict OCR or publish provisional single-frame matches.
    """
    action, matches = watcher.check(
        augment_names, monitor_index=monitor_index, save=save,
    )
    if action == "detected" and matches is not None:
        return matches
    if action == "unchanged":
        return watcher.current_slots or []
    return []
