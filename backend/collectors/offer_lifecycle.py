"""M5/C4: conservative, evidence-gated augment offer lifecycle.

C2/C3 title OCR can positively verify an offer, but unreadable cards alone
cannot prove absence or distinguish a dialogue from an animation. Do not guess
from level, focus loss, empty text, HP changes or stat deltas. A "gone" state
requires an independently verified absence signal; the current watcher emits
no such signal until native negative/occlusion fixtures are calibrated.
"""
from __future__ import annotations


class OfferLifecycle:
    """Pure UI-observation state; never mutates the player's chosen augments."""

    _VALID_ACTIONS = frozenset({
        "detected", "no_augments", "unchanged", "not_focused",
        "unavailable", "disappeared",
    })

    def __init__(self) -> None:
        self.state = "inactive"

    def open(self) -> None:
        """A new pick is due, but an actual on-screen offer is not verified."""
        self.state = "pending"

    def close(self) -> None:
        """Player confirmation, match end or reset closes the observation."""
        self.state = "inactive"

    def observe(
        self, action: str, *, identified: int = 0, verified_absence: bool = False,
    ) -> str:
        """Update only from grounded evidence, never from a missing OCR title.

        'detected' must come from the C3 two-read temporal gate; identified
        is the count of strict C2 matched physical cards (0..3).
        'disappeared' is not valid negative evidence on its own.
        """
        if action not in self._VALID_ACTIONS:
            raise ValueError("invalid offer observation")
        if self.state in ("inactive", "gone"):
            return self.state

        if action == "detected":
            self.state = "present" if 1 <= identified <= 3 else "uncertain"
        elif action in ("not_focused", "unavailable"):
            self.state = "suspended"
        elif action == "disappeared":
            self.state = "gone" if verified_absence else "uncertain"
        elif action == "no_augments" and self.state == "present":
            self.state = "uncertain"
        # A static frame is not positive or negative evidence.
        return self.state
