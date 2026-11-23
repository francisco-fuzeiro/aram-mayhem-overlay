"""Pure C2 offer ledger. Recognition and hints cannot confirm gameplay picks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
import math
import re

from backend.workflow.picked_augment import (
    PickedAugmentEvidence, MAX_PICK_EVENT_AGE_S,
)


OfferState = Literal["due", "visible", "awaiting_confirm", "confirmed", "reconciled"]
IdentitySource = Literal["ocr", "user_identify"]
PickSource = Literal["user_confirm", "postgame", "verified_external", "cursor_inferred"]
SLOTS = ("left", "centre", "right")
CANDIDATE_QUIET_S = 6.0


class LedgerError(Exception):
    """A bounded, API-safe error code; never includes OCR or user data."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass
class SlotIdentity:
    augment_id: str | None = None
    source: IdentitySource | None = None
    verified_at_epoch: int | None = None


@dataclass
class Offer:
    offer_id: int
    level: int
    epoch: int
    slots: dict[str, SlotIdentity] = field(
        default_factory=lambda: {slot: SlotIdentity() for slot in SLOTS}
    )
    state: OfferState = "due"
    candidate_id: str | None = None
    candidate_source: Literal["click_hint"] | None = None
    picked_id: str | None = None
    pick_source: PickSource | None = None


class OfferLedger:
    """An in-memory, match-local ledger with independently fenced offers.

    The caller passes server.AUGMENT_PICK_LEVELS_SORTED; levels are deliberately
    not duplicated here. Every mutation of a named offer validates its epoch.
    """

    def __init__(self, pick_levels):
        self._levels = tuple(pick_levels)
        self._epoch = 0
        self.offers: list[Offer] = []
        # Match-local, bounded by the number of actual confirmed offers.
        # Never serialize opaque provider event IDs into overlay/diagnostics.
        self._verified_external_events: dict[tuple[str, str], tuple[int, int, str]] = {}

    def _next_epoch(self) -> int:
        self._epoch += 1
        return self._epoch

    def _get(self, offer_id: int) -> Offer:
        if type(offer_id) is not int or not 1 <= offer_id <= len(self.offers):
            raise LedgerError("unknown_offer")
        return self.offers[offer_id - 1]

    def _checked(self, offer_id: int, epoch: int) -> Offer:
        offer = self._get(offer_id)
        if type(epoch) is not int or epoch != offer.epoch:
            raise LedgerError("stale_epoch")
        return offer

    @staticmethod
    def _slot(slot: str) -> None:
        if slot not in SLOTS:
            raise LedgerError("bad_slot")

    def set_current_epoch(self, epoch: int) -> None:
        """Fence only the newest open offer to a new server capture generation."""
        if not self.offers:
            return
        if type(epoch) is not int or epoch <= self._epoch:
            raise LedgerError("stale_epoch")
        latest = self.offers[-1]
        if latest.state not in ("due", "visible", "awaiting_confirm"):
            return
        latest.epoch = epoch
        self._epoch = epoch

    def on_level(self, level: int) -> Offer | None:
        if type(level) is not int or level < 0:
            return None
        while len(self.offers) < len(self._levels):
            next_level = self._levels[len(self.offers)]
            if level < next_level:
                break
            self.offers.append(Offer(
                offer_id=len(self.offers) + 1,
                level=next_level,
                epoch=self._next_epoch(),
            ))
        return self.offers[-1] if self.offers else None

    def on_verified_titles(self, slots: dict[str, str | None], epoch: int) -> None:
        if not self.offers:
            raise LedgerError("unknown_offer")
        offer = self._checked(self.offers[-1].offer_id, epoch)
        if offer.state in ("confirmed", "reconciled"):
            raise LedgerError("offer_closed")
        if not isinstance(slots, dict) or set(slots) != set(SLOTS):
            raise LedgerError("bad_slot")
        nonnull = [value for value in slots.values() if value is not None]
        if not nonnull:
            self.on_titles_unverified()
            return
        if any(not isinstance(value, str) or not value for value in nonnull):
            raise LedgerError("not_in_offer")
        if len(nonnull) != len(set(nonnull)):
            raise LedgerError("identity_conflict")
        # A complete fresh OCR observation may move an identity to a new
        # position while removing it from the old one. Only the post-update
        # identities may be required unique; never mutate on conflict.
        final = {slot: slots[slot] for slot in SLOTS}
        final_ids = [value for value in final.values() if value is not None]
        if len(set(final_ids)) != len(final_ids):
            raise LedgerError("identity_conflict")
        for slot, augment_id in slots.items():
            if augment_id is None:
                # Verified unknown is not evidence for keeping a previous
                # rerolled slot identity; never allow a stale pick.
                offer.slots[slot] = SlotIdentity(None, None, epoch)
                continue
            identity = offer.slots[slot]
            if identity.augment_id == augment_id and identity.source == "user_identify":
                continue
            offer.slots[slot] = SlotIdentity(augment_id, "ocr", epoch)
        offer.state = "visible"

    def on_titles_unverified(self) -> None:
        if self.offers and self.offers[-1].state == "visible":
            self.offers[-1].state = "awaiting_confirm"

    def open_for_recovery(self, offer_id: int) -> Offer:
        offer = self._get(offer_id)
        if offer is not self.offers[-1] or offer.state != "due":
            raise LedgerError("offer_closed")
        offer.epoch = self._next_epoch()
        offer.state = "visible"
        return offer

    def identify(self, offer_id: int, epoch: int, slot: str,
                 augment_id: str, catalog: set[str]) -> Offer:
        offer = self._checked(offer_id, epoch)
        self._slot(slot)
        if offer.state not in ("visible", "awaiting_confirm"):
            raise LedgerError("offer_closed")
        if not isinstance(augment_id, str) or augment_id not in catalog:
            raise LedgerError("not_in_catalog")
        if any(other != slot and item.augment_id == augment_id
               for other, item in offer.slots.items()):
            raise LedgerError("identity_conflict")
        offer.slots[slot] = SlotIdentity(augment_id, "user_identify", epoch)
        return offer

    def set_candidate(self, offer_id: int, epoch: int, slot: str) -> None:
        offer = self._checked(offer_id, epoch)
        self._slot(slot)
        if offer.state not in ("visible", "awaiting_confirm"):
            raise LedgerError("offer_closed")
        identity = offer.slots[slot]
        if identity.augment_id is None:
            raise LedgerError("bad_slot")
        offer.candidate_id = identity.augment_id
        offer.candidate_source = "click_hint"

    def confirm(self, offer_id: int, epoch: int, augment_id: str) -> Offer:
        offer = self._checked(offer_id, epoch)
        if offer.state == "confirmed":
            if offer.picked_id == augment_id:
                if offer.pick_source == "cursor_inferred":
                    offer.pick_source = "user_confirm"  # user agrees
                return offer  # idempotent; never close the newest offer again
            if offer.pick_source != "cursor_inferred":
                raise LedgerError("offer_closed")
            # The user corrects an inferred pick (Alt+N): their word wins.
        elif offer.state not in ("visible", "awaiting_confirm"):
            raise LedgerError("offer_closed")
        if augment_id not in (item.augment_id for item in offer.slots.values()):
            raise LedgerError("not_in_offer")
        offer.picked_id = augment_id
        offer.pick_source = "user_confirm"
        offer.candidate_id = None
        offer.candidate_source = None
        offer.state = "confirmed"
        return offer

    def confirm_verified_external(
        self, evidence: PickedAugmentEvidence, *,
        current_match_id: str | None,
        catalog: set[str],
        approved_sources: frozenset[str] = frozenset(),
        now: float,
    ) -> tuple[Offer, bool]:
        """Confirm exactly once from a *separately authenticated* event.

        An approved in-process adapter must validate the underlying provider
        before calling this method. The caller passes explicit source approval,
        normally EMPTY: there is no live pick provider in the standalone app.

        The event may identify a picked augment without OCR titles, but it
        cannot attach to another match or offer, resurrect an old generation,
        or override manual/postgame confirmation. The caller owns the state
        lock and performs downstream build refresh ONLY on a new acceptance.
        """
        if not isinstance(evidence, PickedAugmentEvidence):
            raise LedgerError("bad_evidence")
        if evidence.verified is not True:
            raise LedgerError("unverified_source")
        if not isinstance(evidence.source, str) or (
            evidence.source not in approved_sources
        ):
            raise LedgerError("unapproved_source")
        if (not isinstance(current_match_id, str) or not current_match_id
                or not isinstance(evidence.match_id, str)
                or not evidence.match_id
                or evidence.match_id != current_match_id):
            raise LedgerError("match_mismatch")
        if type(evidence.offer_id) is not int or type(evidence.epoch) is not int:
            raise LedgerError("bad_evidence")
        offer = self._checked(evidence.offer_id, evidence.epoch)
        if (not isinstance(evidence.catalog_id, str)
                or evidence.catalog_id not in catalog):
            raise LedgerError("not_in_catalog")
        if (not isinstance(evidence.source_event_id, str)
                or re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}",
                                evidence.source_event_id) is None):
            raise LedgerError("bad_evidence")
        if (type(evidence.observed_at) not in (int, float)
                or type(now) not in (int, float)
                or not math.isfinite(evidence.observed_at)
                or not math.isfinite(now)
                or not 0 <= now - evidence.observed_at <= MAX_PICK_EVENT_AGE_S):
            raise LedgerError("stale_evidence")

        key = (evidence.source, evidence.source_event_id)
        known = self._verified_external_events.get(key)
        if known is not None:
            if (known == (offer.offer_id, offer.epoch, evidence.catalog_id)
                    and offer.state == "confirmed"
                    and offer.pick_source == "verified_external"
                    and offer.picked_id == evidence.catalog_id):
                return offer, False
            raise LedgerError("duplicate_event")
        if offer.state not in ("due", "visible", "awaiting_confirm"):
            raise LedgerError("offer_closed")

        # The provider, not guessed OCR slots, proves the chosen identity.
        offer.picked_id = evidence.catalog_id
        offer.pick_source = "verified_external"
        offer.candidate_id = None
        offer.candidate_source = None
        offer.state = "confirmed"
        self._verified_external_events[key] = (
            offer.offer_id, offer.epoch, evidence.catalog_id,
        )
        return offer, True

    def _slot_target(self) -> Offer | None:
        target = next(
            (offer for offer in self.offers if offer.state == "awaiting_confirm"),
            None,
        )
        if target is None:
            target = next(
                (offer for offer in reversed(self.offers) if offer.state == "visible"),
                None,
            )
        return target

    def confirm_inferred(self, slot: str) -> Offer:
        """Cards vanished with the cursor over one card: a correctable pick.

        Never overrides a user/postgame/provider pick; Alt+N replaces it.
        """
        self._slot(slot)
        target = self._slot_target()
        if target is None or target.slots[slot].augment_id is None:
            raise LedgerError("bad_slot")
        offer = self.confirm(target.offer_id, target.epoch, target.slots[slot].augment_id)
        offer.pick_source = "cursor_inferred"
        return offer

    def confirm_slot(self, slot: str) -> Offer:
        self._slot(slot)
        target = self._slot_target()
        if target is None and self.offers and (
                self.offers[-1].pick_source == "cursor_inferred"):
            target = self.offers[-1]  # correcting the inferred pick
        if target is None or target.slots[slot].augment_id is None:
            raise LedgerError("bad_slot")
        return self.confirm(target.offer_id, target.epoch,
                            target.slots[slot].augment_id)

    def active_augment_ids(self) -> list[str]:
        return [
            offer.picked_id
            for offer in self.offers
            if offer.state in ("confirmed", "reconciled") and offer.picked_id is not None
        ]

    def scanning_needed(self) -> bool:
        return any(
            offer.state in ("due", "visible", "awaiting_confirm")
            for offer in self.offers
        )

    def payload(self) -> list[dict]:
        """Only public identity, candidate and pick values; no telemetry."""
        return [
            {
                "offer_id": offer.offer_id,
                "level": offer.level,
                "epoch": offer.epoch,
                "state": offer.state,
                "slots": {
                    slot: {"augment_id": identity.augment_id, "source": identity.source}
                    for slot, identity in offer.slots.items()
                },
                "candidate_id": offer.candidate_id,
                "picked_id": offer.picked_id,
                "pick_source": offer.pick_source,
            }
            for offer in self.offers
        ]
