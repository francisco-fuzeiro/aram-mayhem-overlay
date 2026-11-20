"""Pure C2 offer ledger. Recognition and hints cannot confirm gameplay picks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


OfferState = Literal["due", "visible", "awaiting_confirm", "confirmed", "reconciled"]
IdentitySource = Literal["ocr", "user_identify"]
PickSource = Literal["user_confirm", "postgame"]
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
        if offer.state not in ("visible", "awaiting_confirm", "confirmed"):
            raise LedgerError("offer_closed")
        if augment_id not in (item.augment_id for item in offer.slots.values()):
            raise LedgerError("not_in_offer")
        offer.picked_id = augment_id
        offer.pick_source = "user_confirm"
        offer.candidate_id = None
        offer.candidate_source = None
        offer.state = "confirmed"
        return offer

    def confirm_slot(self, slot: str) -> Offer:
        self._slot(slot)
        target = next(
            (offer for offer in self.offers if offer.state == "awaiting_confirm"),
            None,
        )
        if target is None:
            target = next(
                (offer for offer in reversed(self.offers) if offer.state == "visible"),
                None,
            )
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
