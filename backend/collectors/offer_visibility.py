"""M5/C4b: independent, fail-closed visual absence evidence gate.

THIS IS NOT A LEAGUE UI CLASSIFIER. Runtime has no calibrated negative marker
and deliberately leaves the gate disabled. A future independent, privacy-
reviewed visual marker must be calibrated with actual absent/dialogue/animation
frames and explicitly enabled in code before it can supply evidence.
Title OCR failure, blank crop hashes and elapsed time are NOT negative proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Policy debounce, not a measured classifier accuracy or a League-specific
# animation duration. Every observation must come from a separate focused scan.
REQUIRED_ABSENCE_READS = 3

WindowKey = tuple[int, tuple[int, int, int, int]]


@dataclass(frozen=True)
class IndependentCue:
    """Independent client-visual marker, never OCR-derived card-name absence.

    calibration_id is a code-reviewed, fixture-backed detector revision. A
    cue without an exact approved calibration/window match is not authoritative.
    """

    verdict: str  # absent | occluded | visible | unknown
    calibration_id: str
    key: WindowKey


class VerifiedAbsenceGate:
    """Count independently verified negative frames only after a known offer.

    The constructor defaults to disabled, and the current production watcher
    supplies neither an observer nor an approved calibration. No raw desktop
    pixels, hidden game state or automatic game action are involved.
    """

    def __init__(self, approved_calibration: str | None = None) -> None:
        self._approved = (
            approved_calibration if isinstance(approved_calibration, str)
            and approved_calibration.strip() else None
        )
        self.suspend()

    def suspend(self) -> None:
        """Revoke prior presence on reset, focus loss or window identity change."""
        self._present_key: WindowKey | None = None
        self._absence_count = 0

    def confirm_present(self, key: WindowKey) -> None:
        """Only C3-confirmed physical titles can establish prior presence."""
        self._present_key = key
        self._absence_count = 0

    def is_approved(self, cue: object, key: WindowKey) -> bool:
        return (
            self._approved is not None
            and isinstance(cue, IndependentCue)
            and cue.calibration_id == self._approved
            and cue.key == key
        )

    def observe(self, cue: object, key: WindowKey) -> bool:
        """True only after three uninterrupted, independently sourced absences.

        Any unverified, conflicting, occluded or uncertain cue breaks the streak.
        Changed window identity revokes the previous presence proof entirely.
        """
        if self._present_key is None:
            return False
        if key != self._present_key:
            self.suspend()
            return False
        if isinstance(cue, IndependentCue) and cue.key != key:
            self.suspend()
            return False
        if not self.is_approved(cue, key) or cue.verdict != "absent":
            self._absence_count = 0
            return False
        self._absence_count += 1
        return self._absence_count >= REQUIRED_ABSENCE_READS


# C1 v3: an independent *shadow-only* description of the existing three
# title-band images. This is intentionally NOT an IndependentCue and has no
# approved calibration for the VerifiedAbsenceGate.
CARD_BG_CALIBRATION_ID = "card_bg_v2"
CARD_BG_RGB = (3, 16, 18)
CARD_BG_CHANNEL_TOLERANCE = 12
CARD_BG_PRESENT_MIN = 0.50
CARD_BG_ABSENT_MAX = 0.05
CARD_BG_SHADOW_MODE = True
_CARD_SLOTS = ("left", "centre", "right")


def card_teal_fraction(title_crop: "Image.Image") -> float:
    """Return the RGB fraction within ±12 of all three reference channels."""
    rgb = title_crop.convert("RGB")
    pixels = rgb.tobytes()
    total = rgb.width * rgb.height
    if total <= 0:
        return 0.0
    red, green, blue = CARD_BG_RGB
    tol = CARD_BG_CHANNEL_TOLERANCE
    matched = sum(
        1 for i in range(0, len(pixels), 3)
        if abs(pixels[i] - red) <= tol
        and abs(pixels[i + 1] - green) <= tol
        and abs(pixels[i + 2] - blue) <= tol
    )
    return matched / total


def card_background_cue(
    crops: dict[str, "Image.Image"],
) -> Literal["present", "absent", "mixed"]:
    """Pure three-slot cue: present, absent or mixed; never an offer decision."""
    if not isinstance(crops, dict) or set(crops) != set(_CARD_SLOTS):
        return "mixed"
    try:
        fractions = tuple(card_teal_fraction(crops[slot]) for slot in _CARD_SLOTS)
    except (AttributeError, TypeError, ValueError):
        return "mixed"
    if all(fraction >= CARD_BG_PRESENT_MIN for fraction in fractions):
        return "present"
    if all(fraction <= CARD_BG_ABSENT_MAX for fraction in fractions):
        return "absent"
    return "mixed"
