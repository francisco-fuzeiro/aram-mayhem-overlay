"""Verified picked-augment evidence contract, not a live data provider.

The standalone Oracle currently has NO approved provider of automatic Mayhem
pick events. In particular, Riot's LCDA is not the Overwolf GEP API.
Only an explicitly trusted in-process adapter may supply proof to the ledger;
the dataclass's verified flag alone must never authorize an event.

No network listener, bridge, process inspection or game input is implemented.
"""

from __future__ import annotations

from dataclasses import dataclass


# Conservative receipt-age bound for a future authenticated adapter; this
# is NOT a measured latency SLA or proof that a replay was not received.
MAX_PICK_EVENT_AGE_S = 10.0


@dataclass(frozen=True, slots=True)
class PickedAugmentEvidence:
    """One source-verified, canonical pick with match/offer/epoch provenance.

    The future provider must prove match and offer association, map an
    unambiguous public catalog ID, assign a bounded opaque event ID, and
    attach an actual non-replayed source timestamp. A raw OCR observation,
    click location, level threshold, empty card crop or guessed stat delta
    cannot construct authoritative evidence.
    """

    match_id: str
    offer_id: int
    epoch: int
    catalog_id: str
    source: str
    source_event_id: str
    observed_at: float
    verified: bool
