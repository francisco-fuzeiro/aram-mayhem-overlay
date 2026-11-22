"""Safety accounting: one three-card offer must be one simultaneous frame.

Rerolls and partial follow-up frames must never be silently combined with
earlier frames into a fictitious successful three-card recognition.
"""
from __future__ import annotations

from collections import defaultdict

SLOTS = frozenset(("left", "centre", "right"))


def group_offers(rows: list[dict]) -> dict:
    grouped = defaultdict(dict)
    for row in rows:
        session = row.get("source_session")
        frame = row.get("source_frame")
        offer = row.get("offer_id")
        if not (session and frame and offer):
            # Older metadata cannot prove simultaneous card visibility.
            continue
        slot = row.get("slot")
        if slot not in SLOTS:
            raise ValueError("invalid physical slot for three-card offer")
        key = (session, frame, offer)
        if slot in grouped[key]:
            raise ValueError("duplicate physical slot in the same source frame")
        grouped[key][slot] = row["status"]
    complete = [states for states in grouped.values() if set(states) == SLOTS]
    return {
        "complete": len(complete),
        "all_correct": sum(all(x == "correct" for x in s.values()) for s in complete),
        "incomplete": len(grouped) - len(complete),
    }
