"""M5/C3: independent, temporal, fail-closed Mayhem title-slot observations.

Consumes already bounded title crops, not game/desktop capture. Each slot must
produce two consecutive visually stable and identically matched OCR readings
before its accepted identity changes. Transient animation frames are ignored.
Offer presence/disappearance and obstructing dialogues remain M5/C4.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PIL import Image

from backend.collectors.slot_title_ocr import SLOTS, SlotMatches

Match = tuple[str, str, int] | None

# 32x32 average hashes: keep jitter tolerance below visibly changed glyph strokes.
# Separate much stricter threshold confirms that two pending frames are stable.
CHANGE_THRESHOLD = 6
STABLE_THRESHOLD = 5
REQUIRED_CONSECUTIVE_READS = 2
UNKNOWN_RETRY_INTERVAL_TICKS = 4  # bounded polling, not a busy OCR loop


@dataclass
class _Pending:
    hash_value: str
    match: Match
    count: int


class SlotTemporalTracker:
    """Record a validated title/hash independently for each physical card."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._accepted: dict[str, Match] = dict.fromkeys(SLOTS)
        self._baselines: dict[str, str] = {}
        self._pending: dict[str, _Pending] = {}
        self._has_identified_card = False
        self._refresh_required = False
        self._unknown_retry_ticks: dict[str, int] = {}

    def suspend(self) -> None:
        """On focus/capture loss preserve old identities, but distrust old hashes.

        Refocus requires two fresh readings of all slots; the server must
        separately mark its last display snapshot stale until this succeeds.
        """
        self._baselines.clear()
        self._pending.clear()
        self._refresh_required = True

    @property
    def has_pending(self) -> bool:
        """True while any physical title slot awaits a confirming OCR read."""
        return bool(self._pending)

    @property
    def has_unverified_changes(self) -> bool:
        """Some title slot is still awaiting a second C3 verification read.

        This is NOT offer disappearance evidence; C4 uses it only to withhold
        old recommendations during animation, reroll or occlusion.
        """
        return bool(self._pending)

    def snapshot(self) -> SlotMatches | None:
        """Last confirmed physical slots; not proof the window is still focused."""
        if not self._has_identified_card:
            return None
        return SlotMatches(self._accepted)

    def observe(
        self,
        crops: dict[str, Image.Image],
        augment_names: dict[str, str],
        read_slot: Callable[[str, Image.Image, dict[str, str]], Match],
        hash_image: Callable[[Image.Image], str],
        hash_distance: Callable[[str, str], int],
    ) -> SlotMatches | None:
        """Read only changed slots, publishing only fully verified differences.

        None means no publishable change (not an offer disappearance). A
        SlotMatches result includes explicit unknowns and unchanged positions.
        """
        if list(crops) != list(SLOTS):
            raise ValueError("exactly three ordered, client-bounded crops required")

        verified: dict[str, tuple[Match, str]] = {}
        for slot in SLOTS:
            crop = crops[slot]
            image_hash = hash_image(crop)
            baseline = self._baselines.get(slot)
            if baseline is not None and hash_distance(image_hash, baseline) <= CHANGE_THRESHOLD:
                if self._accepted[slot] is not None:
                    self._pending.pop(slot, None)
                    continue
                # OCR can fail temporarily on an unchanged image. Retry the
                # unknown slot at a bounded rate, never the valid neighbours.
                remaining = self._unknown_retry_ticks.get(
                    slot, UNKNOWN_RETRY_INTERVAL_TICKS,
                )
                if remaining > 0:
                    self._unknown_retry_ticks[slot] = remaining - 1
                    self._pending.pop(slot, None)
                    continue
                self._unknown_retry_ticks[slot] = UNKNOWN_RETRY_INTERVAL_TICKS
                self._baselines.pop(slot, None)

            # No old baseline (new offer/refocus) or a changed card: sample OCR.
            # This uses the same strict C2 matcher irrespective of the trigger.
            match = read_slot(slot, crop, augment_names)
            previous = self._pending.get(slot)
            signature = match[0] if match is not None else None
            previous_signature = (
                previous.match[0] if previous is not None and previous.match is not None
                else None
            )
            if (
                previous is not None
                and hash_distance(image_hash, previous.hash_value) <= STABLE_THRESHOLD
                and signature == previous_signature
            ):
                count = previous.count + 1
            else:
                count = 1
            self._pending[slot] = _Pending(image_hash, match, count)
            if count >= REQUIRED_CONSECUTIVE_READS:
                verified[slot] = match, image_hash
                self._pending.pop(slot, None)

        if not verified:
            return None

        # Updating the hashes even for a revalidated identical title prevents
        # OCR spam when only its visual appearance changed.
        proposed = dict(self._accepted)
        for slot, (match, _hash) in verified.items():
            proposed[slot] = match

        # A newly scanned duplicate cannot steal the identity of an untouched
        # slot. If both duplicates were newly scanned, both fail closed.
        locations: dict[str, list[str]] = {}
        for slot, match in proposed.items():
            if match is not None:
                locations.setdefault(match[0], []).append(slot)
        for competing in locations.values():
            if len(competing) > 1:
                for slot in competing:
                    if slot in verified:
                        proposed[slot] = None

        changed = any(
            (self._accepted[slot][0] if self._accepted[slot] else None)
            != (proposed[slot][0] if proposed[slot] else None)
            for slot in verified
        )
        self._accepted = proposed
        for slot, (_match, image_hash) in verified.items():
            self._baselines[slot] = image_hash
            if proposed[slot] is None:
                self._unknown_retry_ticks[slot] = UNKNOWN_RETRY_INTERVAL_TICKS
            else:
                self._unknown_retry_ticks.pop(slot, None)

        if any(value is not None for value in proposed.values()):
            self._has_identified_card = True

        # A focus return must reverify *all* slots before clearing the stale
        # display flag, even if they remain equal to the old confirmed offer.
        if self._refresh_required:
            if len(self._baselines) != len(SLOTS):
                return None
            self._refresh_required = False
            return self.snapshot()

        return self.snapshot() if changed else None
