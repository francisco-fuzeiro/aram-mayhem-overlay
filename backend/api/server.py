import asyncio
import json
import os
from itertools import count
import sys
import time
from types import SimpleNamespace
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from contextlib import asynccontextmanager, nullcontext
import logging

logger = logging.getLogger("aram-oracle")

from backend.static_data.loader import StaticData
from backend.storage.db import init_db, get_champion_record, get_all_personal_winrates
from backend.static_data.updater import force_refresh
from backend.workflow.pipeline import Pipeline
from backend.collectors.lcda import LCDAResult, get_raw_game_data, parse_game_snapshot
from backend.collectors.anvil_voucher import AnvilVoucherPurchaseObserver
from backend.collectors import anvil_popup
from backend.collectors import card_presence
from backend.engine.stat_anvil_offer import resolve_offer as resolve_anvil_offer, title_catalog as anvil_title_catalog
from backend.collectors.lcu import read_champ_select, read_gameflow
from backend.engine.champion_select import summarize_champion_select
from backend.tierdb.service import TierListService
from backend.collectors import screen_ocr as ocr_capture
from backend.collectors.screen_ocr import (
    detect_augments, is_available as ocr_available, watcher as screen_watcher,
)
from backend.collectors.offer_lifecycle import OfferLifecycle
from backend.workflow.offer_ledger import LedgerError, OfferLedger, SLOTS
from backend.workflow.picked_augment import PickedAugmentEvidence
from backend.models import GamePhase, GameSnapshot, PipelineResult
from backend.engine.build_suggester import BUILD_STYLES
from backend import preferences
from backend.config import config  # explicit opt-in for diagnostic screenshot policy
from backend.engine.augment_detector import match_augment
from backend.diagnostics import collector as diagnostics
from backend.diagnostic_events import events as event_log
from backend import feature_diagnostics
from backend.feature_registry import UI_FEATURES
from backend.workflow.f0_trace import (
    classify_champion_identity, classify_offer_slots, emit_f0_trace,
)

static_data = StaticData()

# Allocated before each LCU request, not after network return. A delayed old
# response therefore cannot appear fresher than a newer request.
_champ_select_revisions = count(1)


# -- Thread-safe game state --

OCR_PHASES = frozenset({
    "disabled", "ocr_missing", "no_game", "capture_unavailable",
    "occluded", "no_offer", "verifying", "detected", "unreadable",
})
_CAPTURE_LOSS_PHASES = frozenset({"occluded", "capture_unavailable", "no_game"})
_ACTIVE_OCR_PHASES = frozenset({"detected", "verifying", "unreadable"})


class _OcrWatcherObservation(tuple):
    """Keep A4's three-value result contract with atomic A5 evidence metadata."""

    def __new__(cls, action, ids, detected, *, reverified=False,
                stage="not_scanned", foreground="other", has_partial=False,
                has_current=False):
        obj = super().__new__(cls, (action, ids, detected))
        obj.reverified = bool(reverified)
        obj.stage = stage
        obj.foreground = foreground if foreground in ("league", "self", "other") else "other"
        obj.has_partial = bool(has_partial)
        obj.has_current = bool(has_current)
        return obj


class _ManualScanEvidence(tuple):
    """Positional legacy (ids, detected), with proven capture facts attached."""

    def __new__(cls, ids, detected, *, proven, reverified, foreground, stage):
        obj = super().__new__(cls, (ids, detected))
        obj.proven = bool(proven)
        obj.reverified = bool(reverified)
        obj.foreground = foreground
        obj.stage = stage
        return obj


def _ledger_verified_titles(ledger: OfferLedger, slots: dict[str, str | None],
                            epoch: int) -> None:
    """Apply OCR identity atomically, logging only approved override metadata."""
    if not ledger.offers:
        raise LedgerError("unknown_offer")
    offer = ledger.offers[-1]
    previous = {
        slot: identity.augment_id
        for slot, identity in offer.slots.items()
        if identity.source == "user_identify"
    }
    ledger.on_verified_titles(slots, epoch)
    for slot, former in previous.items():
        if slots.get(slot) is not None and slots[slot] != former:
            event_log.emit("identity_overridden", slot=slot, verified_by="ocr")


def _manual_scan_parts(value):
    """A legacy untyped result is NEVER capture evidence."""
    ids, detected = value[:2]
    proven = getattr(value, "proven", len(value) == 3 and value[2] is True)
    reverified = getattr(value, "reverified", len(value) == 3 and value[2] is True)
    foreground = getattr(value, "foreground", "other")
    stage = getattr(value, "stage", "not_scanned")
    return ids, detected, proven, reverified, foreground, stage





class GameState:
    """Encapsulates all mutable augment/OCR state with an asyncio.Lock.

    Replaces the former module-level globals. All mutations go through
    methods that acquire ``self._lock`` so the poll loop and WS handlers
    never see partial updates.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # Poll ticks serialize LCDA/OCR and preserve message ordering without
        # holding the game-state mutation lock across network I/O.
        self.poll_lock = asyncio.Lock()
        self.pipeline: Pipeline | None = None
        self.ws_clients: set[WebSocket] = set()
        self.ws_send_queues: dict[WebSocket, asyncio.Queue[tuple[str, asyncio.Future[None] | None]]] = {}
        self.ws_send_tasks: dict[WebSocket, asyncio.Task[None]] = {}
        # Augment choices injected by overlay / OCR
        self.augment_choices: list[str] = []
        self.chosen_augments: list[str] = []  # real augments only (max 4)
        self.chosen_stat_anvils: list[str] = []  # stat anvil / voucher picks
        # Voucher purchase is an LCDA signal only: never verified popup/OCR.
        self.anvil_voucher_observer = AnvilVoucherPurchaseObserver()
        self.anvil_voucher_purchase_events: int = 0
        self.anvil_voucher_trigger_pending: bool = False
        self.anvil_voucher_last_purchase: tuple[str, ...] = ()
        # P0-C: dedicated Stat Anvil popup watch. The voucher edge only opens
        # an attention window; the offer exists only after title OCR.
        self.anvil_window_until: float | None = None
        self.anvil_voucher_tier: str | None = None
        self.anvil_epoch: int = 0
        self.anvil_offer = None  # AnvilOfferResolution with status "ok"
        self.anvil_absent_ticks: int = 0
        self.anvil_prev_counts: dict | None = None
        self.anvil_picked_ids: list[str] = []  # shards picked (cursor-inferred)
        # Field fix: OCR-free card presence trail (cue + card under cursor).
        # Positions are reduced to a slot name and never leave memory.
        self.presence_trail: list = []
        self.build_style: str = "Balanced"  # player preference, survives match resets
        self.overlay_preferences: dict = dict(preferences.DEFAULT_OVERLAY)  # D4a: stored only
        # OCR state
        self.ocr_enabled: bool = True
        self.ocr_last_detected: list[str] = []
        self.ocr_slot_choices: dict[str, str | None] | None = None
        # Complete prior offer identity, never proof that a NEW offer is visible.
        self._prior_due_triple: tuple[str, str, str] | None = None
        self.ocr_stale: bool = False
        self.ocr_stale_since_epoch: int | None = None
        self.ocr_phase: str = "no_offer"
        self.ocr_foreground: str = "other"
        self.ocr_unreadable_ticks: int = 0
        self.offer_lifecycle = OfferLifecycle()
        self.offer_ledger = OfferLedger(AUGMENT_PICK_LEVELS_SORTED)
        # Monotonic offer generation fences OCR results from old windows and
        # manual scans that finish after a match transition or player action.
        self.offer_epoch: int = 0
        # Augment pick window
        self.last_known_level: int = 0
        self.scan_window_open: bool = False
        self.scan_window_level: int = 0
        self.was_dead: bool = False  # track death transitions
        # Stat deltas may at most suggest a likely card after OCR disappearance.
        self.stat_snapshot_before: dict[str, float] = {}
        self.stat_snapshot_level_before: int | None = None
        self.stat_snapshot_items_before: tuple[str, ...] | None = None
        self.awaiting_stat_delta: bool = False
        self.delta_wait_ticks: int = 0
        self.confirmation_pending: bool = False
        # Post-game detection
        self.had_game_last_tick: bool = False
        self.post_game: bool = False
        self.post_game_time: float = 0.0
        self.lifecycle_status: str | None = None
        # Session identity and temporary LCDA loss are game-specific, not
        # stored on disk or included in diagnostic events.
        self.match_id: str | None = None
        self._match_sequence: int = 0
        self._last_game_time: float | None = None
        self._last_champion_id: str | None = None
        self._last_player_key: str | None = None
        self.lcda_misses: int = 0
        self.first_lcda_miss_at: float | None = None
        self._item_outside_pool_seen: set[str] = set()

    @property
    def offer_state(self) -> str:
        return self.offer_lifecycle.state

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    def set_ocr_phase(
        self, phase: str, *, reverified: bool = False, offer_closed: bool = False,
    ) -> None:
        """Latch a stale offer until fresh A3/A4 proof or verified closure.

        Focusing League, blank OCR, a single changed slot, and an unchanged
        screenshot are never sufficient evidence to clear stale.
        """
        if phase not in OCR_PHASES:
            raise ValueError("unknown OCR phase")
        if (
            self.scan_window_open
            and self.ocr_phase in _ACTIVE_OCR_PHASES
            and phase in _CAPTURE_LOSS_PHASES
        ):
            if not self.ocr_stale:
                self.ocr_stale_since_epoch = self.offer_epoch
            self.ocr_stale = True
        if offer_closed or (phase == "detected" and reverified):
            self.ocr_stale = False
            self.ocr_stale_since_epoch = None
        self.ocr_phase = phase

    def reset(self) -> None:
        """Reset all game-specific state (called when no game is detected)."""
        # Clear manually entered picks too. An OCR-less match must not
        # leak augment choices into the next match.
        if self.scan_window_open:
            event_log.emit("ocr_window", state="closed", reason="reset", level=self.scan_window_level)
        self.ocr_last_detected.clear()
        self.ocr_slot_choices = None
        self._prior_due_triple = None
        self.ocr_stale = False
        self.ocr_stale_since_epoch = None
        self.ocr_phase = "disabled" if not self.ocr_enabled else "no_offer"
        self.ocr_foreground = "other"
        self.ocr_unreadable_ticks = 0
        self.offer_lifecycle.close()
        self.offer_epoch += 1
        self.augment_choices.clear()
        self.chosen_augments.clear()
        self.chosen_stat_anvils.clear()
        self.anvil_voucher_observer.reset()
        self.anvil_voucher_purchase_events = 0
        self.anvil_voucher_trigger_pending = False
        self.anvil_voucher_last_purchase = ()
        self.anvil_window_until = None
        self.anvil_voucher_tier = None
        self.anvil_offer = None
        self.anvil_absent_ticks = 0
        self.anvil_prev_counts = None
        self.anvil_picked_ids = []
        self.presence_trail = []
        self.offer_ledger = OfferLedger(AUGMENT_PICK_LEVELS_SORTED)
        screen_watcher.reset()
        self.last_known_level = 0
        self.scan_window_open = False
        self.scan_window_level = 0
        self.was_dead = False
        self.stat_snapshot_before.clear()
        self.stat_snapshot_level_before = None
        self.stat_snapshot_items_before = None
        self.awaiting_stat_delta = False
        self.delta_wait_ticks = 0
        self.confirmation_pending = False
        self._item_outside_pool_seen.clear()

    def set_ocr_enabled(self, enabled: bool, *, watcher=None) -> None:
        """Require fresh C3 reads whenever OCR is toggled during an offer.

        Called while holding GameState.lock by the WS handler. Historical
        choices remain diagnostics-only; disabling never confirms a pick.
        """
        enabled = bool(enabled)
        if enabled == self.ocr_enabled:
            return
        self.ocr_enabled = enabled
        self.offer_epoch += 1
        if self.offer_ledger.offers:
            try:
                self.offer_ledger.set_current_epoch(self.offer_epoch)
            except LedgerError:
                pass  # Closed offers cannot be reopened by Settings.
        if watcher is not None:
            watcher.reset()
        # The disabled badge must remain accurate even between offers.
        self.set_ocr_phase(
            "disabled" if not enabled else
            "no_game" if self.scan_window_open else "no_offer"
        )
        if self.scan_window_open:
            self.offer_ledger.on_titles_unverified()
            self.offer_lifecycle.observe("unavailable")
            # An OCR toggle invalidates previous advice, not offer identity.
            if not self.ocr_stale:
                self.ocr_stale_since_epoch = self.offer_epoch
            self.ocr_stale = True

    def accept_new_due_slot_identity(self, slots: dict[str, str | None]) -> bool:
        """Abstain if a new level re-reads the preceding physical cards.

        A level threshold and a fresh C3 reading do not prove the previous
        offer has visually ended. This bounded fence rejects replays of its
        three identities (including permutations) and incomplete transitions.
        Distinct titles still need native offer-boundary validation.
        """
        # A level threshold is eligibility, never proof that an earlier
        # augment selection ended. A late reroll may change *all* three
        # visible titles, so an identity difference alone cannot open the
        # next offer. Until an approved boundary/auto-pick provider exists,
        # only resolved earlier offers authorize this later generation.
        if len(self.offer_ledger.offers) > 1 and any(
            offer.state not in ("confirmed", "reconciled")
            for offer in self.offer_ledger.offers[:-1]
        ):
            return False
        previous = self._prior_due_triple
        if previous is None:
            return True
        current = tuple(slots.get(slot) for slot in SLOTS)
        if any(not isinstance(item, str) or not item for item in current):
            return False
        if set(current) == set(previous):
            return False
        self._prior_due_triple = None
        return True

    def accept_manual_ocr(
        self, ids: list[str], detected: list[dict], *,
        match_id: str | None, offer_epoch: int,
        capture_proven: bool = False, reverified: bool = False,
    ) -> bool:
        """Apply only an in-window, current-generation C3-verified scan.

        The caller holds GameState.lock. A stale async scan cannot recreate
        a closed or already confirmed offer or cross into a new match.
        """
        if (not self.scan_window_open or not self.ocr_enabled
                or not capture_proven or (self.ocr_stale and not reverified)
                or self.match_id != match_id or self.offer_epoch != offer_epoch):
            return False
        slots = _slots_from_detected(detected)
        if slots is None:
            return False
        current_ids = [value for value in slots.values() if value is not None]
        if ids != current_ids or not self.accept_new_due_slot_identity(slots):
            return False
        if self.offer_ledger.offers and current_ids and (not self.ocr_stale or reverified):
            try:
                _ledger_verified_titles(
                    self.offer_ledger, slots, self.offer_ledger.offers[-1].epoch,
                )
            except LedgerError:
                return False
        self.offer_lifecycle.observe("detected", identified=len(current_ids))
        self.augment_choices[:] = current_ids
        self.ocr_last_detected[:] = current_ids
        self.ocr_slot_choices = slots
        self.set_ocr_phase("detected", reverified=reverified)
        return True

    def get_augment_state(self) -> dict:
        """Current augment tracking state for the frontend."""
        expected = expected_augments_for_level(self.last_known_level)
        return {
            "max": len(AUGMENT_PICK_LEVELS),  # always 4
            "eligible": expected,
            "chosen": len(_confirmed_augment_ids(self)),
            "chosen_augments": _confirmed_augment_ids(self),
            "stat_anvils": len(self.chosen_stat_anvils),
        }


AUGMENT_PICK_LEVELS = {3, 7, 11, 15}
AUGMENT_PICK_LEVELS_SORTED = sorted(AUGMENT_PICK_LEVELS)  # [3, 7, 11, 15]

game_state = GameState()


def expected_augments_for_level(level: int) -> int:
    """How many augments a player should have picked by this level."""
    return sum(1 for lvl in AUGMENT_PICK_LEVELS_SORTED if level >= lvl)



def should_open_augment_scan(
    level: int, previous_level: int, chosen_count: int, just_respawned: bool,
) -> bool:
    """Trigger when picks become due, including the initial in-game snapshot.

    Some Mayhem selections appear immediately at an eligible level, before a
    death/respawn transition. A fresh observed threshold is sufficient to scan.
    Repeated polls at that level do not reopen a closed scan indefinitely.
    """
    due = expected_augments_for_level(level) > chosen_count
    new_threshold = (
        expected_augments_for_level(level)
        > expected_augments_for_level(previous_level)
    )
    return due and (new_threshold or just_respawned)


@asynccontextmanager
async def lifespan(app: FastAPI):
    diagnostics.install_log_handler()
    event_log.start()  # nonblocking event queue; writer owns all disk I/O
    feature_diagnostics.session_start()
    # Every entrypoint (CLI, desktop overlay, and direct ASGI) needs a DB.
    init_db()
    saved_preferences = preferences.load_preferences()
    game_state.build_style = saved_preferences["build_style"]
    game_state.overlay_preferences = saved_preferences["overlay"]
    static_data.load()
    game_state.pipeline = Pipeline(static_data)
    feature_diagnostics.record("tierdb.switch", "ok",
                               "enabled" if tier_service.enabled() else "disabled")
    # Tier lists: refresh in the background when missing or older than 3 days.
    if os.environ.get("ARAM_ORACLE_TIERLIST_AUTO_UPDATE", "1") != "1":
        feature_diagnostics.record("tierdb.update", "skipped", "auto_update_off")
    elif tier_service.needs_update(max_age_hours=72):
        tier_service.start_update(static_data)
    else:
        feature_diagnostics.record("tierdb.update", "skipped", "fresh")

    poll_task = asyncio.create_task(_poll_game_loop())
    presence_task = asyncio.create_task(_presence_loop())
    yield
    for task in (poll_task, presence_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    event_log.stop()


app = FastAPI(lifespan=lifespan)

# Empirical Mayhem tier lists (backend/tierdb). Shown now by owner decision
# 2026-11-23, behind a live switch; never exposes win rates or sample sizes.
tier_service = TierListService()


def _visible_augment_ids(recommendations, offers) -> list[str]:
    """Augment ids the overlay may show: recommendations, then offer slots."""
    ids: list[str] = []

    def add(value):
        if isinstance(value, str) and value and value not in ids:
            ids.append(value)

    for rec in recommendations or []:
        if isinstance(rec, dict):
            add(rec.get("augment_id"))
    if isinstance(offers, dict):
        offers = offers.get("offers")
    for offer in offers or []:
        slots = offer.get("slots") if isinstance(offer, dict) else None
        if isinstance(slots, dict):
            for slot in ("left", "centre", "right"):
                identity = slots.get(slot)
                if isinstance(identity, dict):
                    add(identity.get("augment_id"))
    return ids


def _offer_context_adjuster(champion_id, chosen_augments, mayhem, enemy, sd):
    """adjust(aid) -> (step, reason) for the in-match context adjustment.

    Demand = champion stats + the adapted build's item stats; synergy with the
    augments already chosen; enemy comp; the player's own synced games.
    """
    from backend.models import StatVector
    from backend.tierdb.context_adjust import context_adjust

    def vec(obj):
        stats = getattr(obj, "stats", None)
        return {f: float(getattr(stats, f, 0.0) or 0.0) for f in StatVector.fields()} \
            if stats is not None else None

    demand: dict = {}
    champion = sd.get_champion(champion_id) if hasattr(sd, "get_champion") else None
    items = [e.get("id") for e in ((mayhem or {}).get("adapted") or [])]
    for source in [champion] + [sd.get_item(i) for i in items if i]:
        for k, v in (vec(source) or {}).items():
            demand[k] = demand.get(k, 0.0) + v
    get_aug = getattr(sd, "get_augment", lambda _a: None)
    chosen = [v for v in (vec(get_aug(str(a))) for a in (chosen_augments or [])) if v]
    try:
        personal = get_all_personal_winrates(str(champion_id)) or {}
        record_ = get_champion_record(str(champion_id))
    except Exception:  # personal history is optional
        personal, record_ = {}, None
    base = (record_[0] / record_[1]) if record_ and record_[1] >= 10 else 0.5

    def adjust(aid):
        return context_adjust(vec(get_aug(str(aid))), demand=demand, chosen=chosen,
                              enemy=enemy or {}, personal=personal.get(str(aid)),
                              personal_base=base)
    return adjust


def _augment_tier_payload(champion_id, augment_ids, adjust=None) -> dict:
    """Tiers of the visible augments. ``adjust(aid) -> (step, reason)`` adds the
    in-match context adjustment (±1 tier, owner decision 23/11); ranks stay."""
    from backend.tierdb.context_adjust import shift_tier

    record = feature_diagnostics.record
    if not tier_service.enabled():
        record("tierdb.offer_tiers", "skipped", "tiers_off")
        return {"tiers_enabled": False, "augment_tiers": {}}
    if not champion_id:
        record("tierdb.offer_tiers", "skipped", "no_champion")
        return {"tiers_enabled": False, "augment_tiers": {}}
    if not augment_ids:
        record("tierdb.offer_tiers", "skipped", "no_visible_augments")
        return {"tiers_enabled": True, "augment_tiers": {}}
    tiers = {}
    for aid in augment_ids:
        entry = tier_service.provider.augment_tier(champion_id, aid)
        if entry is not None:
            tiers[aid] = {k: entry.get(k) for k in (
                "tier", "rank", "rank_total", "tie_group", "tie_end",
                "level", "confidence", "rarity")}
            step, reason = (0, None)
            if adjust is not None and entry.get("tier"):
                step, reason = adjust(aid)
            adjusted = shift_tier(entry.get("tier"), step, entry.get("level")) \
                if entry.get("tier") else None
            tiers[aid]["adjusted_tier"] = adjusted
            tiers[aid]["adjust"] = 0 if adjusted == entry.get("tier") else step
            tiers[aid]["adjust_reason"] = reason if tiers[aid]["adjust"] else None
    if tiers:
        if adjust is None:
            record("tierdb.context_adjust", "skipped", "no_context")
        else:
            moved = sum(1 for t in tiers.values() if t["adjust"])
            record("tierdb.context_adjust", "ok", "adjusted" if moved else "unchanged",
                   moved or None)
        record("tierdb.offer_tiers", "ok", "tiers_attached", min(len(tiers), 1000))
    elif not tier_service.provider.loaded:
        record("tierdb.offer_tiers", "failed", "export_missing")
    else:
        record("tierdb.offer_tiers", "failed", "champion_not_in_tierlist")
    return {"tiers_enabled": True, "augment_tiers": tiers}


def _annotate_champion_candidates(result: dict) -> dict:
    """Add Mayhem strength (tier) and potential to champion-select candidates."""
    candidates = [c for c in result.get("candidates") or [] if isinstance(c, dict)]
    record = feature_diagnostics.record
    if not tier_service.enabled():
        for candidate in candidates:
            candidate["mayhem"] = None
        record("tierdb.champselect_tiers", "skipped", "tiers_off")
        return result
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        entry = tier_service.provider.champion_tier(str(candidate.get("id", "")))
        candidate["mayhem"] = None if entry is None else {
            "strength": entry.get("tier"), "potential": entry.get("potential"),
            "rank": entry.get("rank"), "rank_total": entry.get("rank_total"),
            "tie_group": entry.get("tie_group"), "tie_end": entry.get("tie_end"),
            "confidence": entry.get("confidence"),
        }
    annotated = sum(1 for c in candidates if c.get("mayhem"))
    if not candidates:
        record("tierdb.champselect_tiers", "skipped", "no_candidates")
    elif annotated:
        record("tierdb.champselect_tiers", "ok", "annotated", min(annotated, 1000))
    elif not tier_service.provider.loaded:
        record("tierdb.champselect_tiers", "failed", "export_missing")
    else:
        record("tierdb.champselect_tiers", "failed", "no_candidate_in_tierlist")
    return result


_AUGMENT_TO_ANVIL = {"ap": "ap", "ad": "ad", "attack_speed": "as", "hp": "hp",
                     "lethality": "lethality", "pen": "mpen", "crit": "crit", "cdr": "ah"}


def _item_context(item, champion, enemy: dict, allies: dict, fate: set):
    """Bounded 0-3 match bonus for an item and the first reason (heuristic,
    except Weapon of Fate picks which AramHex measures)."""
    props = getattr(item, "properties", frozenset()) or frozenset()
    reasons: list[tuple[float, str]] = []
    if item is not None and item.id in fate:
        reasons.append((1.5, "Weapon of Fate pick (measured)"))
    e = enemy or {}
    if e.get("enemies_analyzed", 0) > 0 and props:
        ap = champion is not None and (champion.role.lower() == "mage"
                                       or champion.stats.ap > champion.stats.ad)
        if "anti_heal" in props and (e.get("sustain_pressure", 0) >= 0.35
                                     or e.get("healing_items", 0) >= 3):
            reasons.append((1.5, "enemies heal a lot"))
        if ("magic_pen" if ap else "armor_pen") in props and (
                e.get("tanks", 0) >= 2 or e.get("armor_items", 0) >= 3
                or (ap and e.get("magic_resist_items", 0) >= 3)):
            reasons.append((1.5, "enemies stack resistances"))
        if "armor" in props and e.get("physical_pressure", 0) >= 0.6:
            reasons.append((1.5, "enemies deal mostly physical damage"))
        if "magic_resist" in props and e.get("magic_pressure", 0) >= 0.6:
            reasons.append((1.5, "enemies deal mostly magic damage"))
        if props & {"shield", "health"} and e.get("burst_pressure", 0) >= 0.5:
            reasons.append((1.0, "high enemy burst"))
        if props & {"tenacity", "cleanse"} and e.get("cc_pressure", 0) >= 0.5:
            reasons.append((1.0, "heavy enemy crowd control"))
    a = allies or {}
    if (a.get("known") and a.get("frontline", 1) == 0 and "health" in props
            and props & {"armor", "magic_resist"}):
        reasons.append((1.0, "allies lack frontline"))
    if not reasons:
        return 0.0, None
    return min(3.0, sum(v for v, _ in reasons)), reasons[0][1]


def _mayhem_build_payload(champion_id, chosen_augments, owned_ids, enemy, allies, sd):
    """Reference build (measured), adapted build (max 3 swaps, >= 0.5) and
    heuristic Stat Anvil priorities for the overlay. No win rates."""
    from backend.tierdb.anvil_stats import ANVIL_STATS, rank_anvil_options
    from backend.tierdb.build_adapt import adapt_build, strength_from_rank

    record = feature_diagnostics.record
    if not tier_service.enabled():
        record("items.reference_build", "skipped", "tiers_off")
        record("anvil.stat_estimate", "skipped", "tiers_off")
        return None
    if not champion_id:
        record("items.reference_build", "skipped", "no_champion")
        return None
    data = tier_service.provider.items(str(champion_id))
    if not data or not data.get("reference"):
        record("items.reference_build", "failed",
               "champion_not_in_tierlist" if tier_service.provider.loaded else "export_missing")
        record("anvil.stat_estimate", "skipped", "no_demand")
        return None
    champion = sd.get_champion(champion_id) if hasattr(sd, "get_champion") else None
    finals = data.get("final") or {}
    strength = {iid: strength_from_rank(e.get("rank"), e.get("rank_total"))
                for iid, e in finals.items()}
    groups = getattr(sd, "exclusive_item_groups", {}) or {}

    def conflicts(a, b):
        return any(a in ids and b in ids for ids in groups.values())

    fate = set()
    chosen = [str(a) for a in (chosen_augments or [])]
    for aug in chosen:
        fate |= set((data.get("fate") or {}).get(aug, []))

    def context(iid):
        return _item_context(sd.get_item(iid), champion, enemy, allies, fate)

    canonical = getattr(sd, "canonical_item_id", lambda x: str(x))
    owned = {canonical(i) for i in (owned_ids or [])}
    reference = list(data["reference"])
    adapted = adapt_build(reference, strength, context=context, owned=owned,
                          conflicts=conflicts)

    def name(iid):
        item = sd.get_item(iid)
        return item.name if item is not None and item.name else iid

    payload = {
        "reference": [{"id": i, "name": name(i)} for i in reference],
        "adapted": [{"id": i, "name": name(i)} for i in adapted.items],
        "boots": ({"id": data["boots_reference"], "name": name(data["boots_reference"])}
                  if data.get("boots_reference") else None),
        "swaps": [{"slot": s["slot"], "out": s["out"], "in": s["in"],
                   "out_name": name(s["out"]), "in_name": name(s["in"]),
                   "reason": s["reason"]} for s in adapted.swaps],
        "anvil_stats": [],
    }
    record("items.reference_build", "ok", "attached")
    demand = data.get("stat_demand") or {}
    if not demand:
        record("anvil.stat_estimate", "skipped", "no_demand")
        return payload
    boost: dict[str, float] = {}
    for aug in chosen:
        augment = sd.get_augment(aug) if hasattr(sd, "get_augment") else None
        stats = getattr(augment, "stats", None)
        for field_name, stat in _AUGMENT_TO_ANVIL.items():
            value = float(getattr(stats, field_name, 0.0) or 0.0) if stats else 0.0
            if value > 0:
                boost[stat] = max(boost.get(stat, 0.0), min(value, 1.0))
    ranked = rank_anvil_options([{"id": s, "stat": s} for s in ANVIL_STATS], demand,
                                enemy=enemy, allies=allies, augment_stats=boost)
    payload["anvil_stats"] = [{"stat": r["stat"], "tier": r["tier"], "level": r["level"],
                               "reason": r["reason"]} for r in ranked[:3]]
    record("anvil.stat_estimate", "ok", "estimated", len(payload["anvil_stats"]))
    return payload


def _align_next_with_mayhem_build(build_state: dict, mayhem: dict | None,
                                  current_gold, sd) -> dict:
    """Make Next follow the tier list build shown beside it.

    Fiora match test 23/11: the legacy engine suggested Bloodthirster while the
    measured reference started with Ravenous Hydra. With a tier list build, Next
    is the first adapted item not owned yet. Boots timing, a full inventory and
    a completed adapted build keep the engine's choice.
    """
    if not mayhem or not mayhem.get("adapted") or build_state.get("slot_blocked"):
        return build_state
    canonical = getattr(sd, "canonical_item_id", lambda x: str(x))
    engine_next = build_state.get("next_item_id")
    boots = (mayhem.get("boots") or {}).get("id")
    if engine_next and boots and canonical(engine_next) == boots:
        return build_state
    owned = {canonical(i) for i in (build_state.get("purchased_items") or [])}
    owned |= {canonical(i) for i in (build_state.get("owned_build_ids") or [])}
    candidate = next((e["id"] for e in mayhem["adapted"] if e.get("id") not in owned), None)
    if candidate is None:
        return build_state
    out = dict(build_state)
    out["next_source"] = "tierlist"
    if engine_next and canonical(engine_next) == candidate:
        return out
    item = sd.get_item(candidate)
    cost = int(getattr(item, "cost", 0) or 0) if item is not None else 0
    out["engine_next_item_id"] = engine_next
    out["next_item_id"] = candidate
    out["next_item_name"] = item.name if item is not None and item.name else candidate
    out["next_item_gold_needed"] = cost
    out["gold_to_next"] = (max(0, cost - int(current_gold))
                           if isinstance(current_gold, (int, float)) and cost else None)
    return out


def _handle_feature_ack(msg: dict) -> bool:
    """Accept a DOM-render report from the overlay for UI features only."""
    if (not isinstance(msg, dict) or msg.get("feature") not in UI_FEATURES
            or not str(msg.get("feature")).startswith(("tierdb.", "items."))):
        return False
    count = msg.get("count")
    return feature_diagnostics.record(msg.get("feature"), msg.get("status"),
                                      msg.get("reason"), count if count is not None else None)


def _accept_feature_ack(state: GameState, msg: dict) -> bool:
    """DOM-only ACK, fenced to the current match and verified Anvil offer.

    Never trust an acknowledgment as proof of League shop stock or a newly
    presented popup. Never persist match IDs, item identities or OCR text.
    """
    if not isinstance(msg, dict):
        return False
    if set(msg) - {"type", "feature", "status", "reason", "count",
                    "match_id", "offer_epoch"}:
        return False
    feature = msg.get("feature")
    count = msg.get("count")
    if (feature not in UI_FEATURES or msg.get("type") != "feature_ack"
            or msg.get("status") != "ok" or msg.get("reason") != "rendered"
            or not state.had_game_last_tick or not state.match_id
            or msg.get("match_id") != state.match_id
            or type(count) is not int or count <= 0):
        return False
    if feature == "build.next_item_render":
        if count != 1:
            return False
    elif feature == "anvil.offer_render":
        # P0-C: only the dedicated, visually verified popup of THIS epoch,
        # with as many cards as were read. A voucher edge never qualifies.
        offer = state.anvil_offer
        if (offer is None or getattr(offer, "status", None) != "ok"
                or type(msg.get("offer_epoch")) is not int
                or msg["offer_epoch"] != state.anvil_epoch
                or count != len(offer.shards)
                or any(static_data.get_stat_anvil(s.id) is None for s in offer.shards)):
            return False
    else:
        return False
    return feature_diagnostics.record(feature, "ok", "rendered", count)


@app.get("/api/diagnostics/features")
def get_feature_report():
    """Sanitized last-session IDs, statuses and aggregate counts only."""
    return feature_diagnostics.build_report()


# In PyInstaller bundles, sys._MEIPASS points to the extraction dir.
_APP_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent))
FRONTEND_DIR = _APP_ROOT / "frontend"


# -- Static file serving for overlay --


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/overlay")


@app.get("/overlay")
def serve_overlay():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"error": "frontend/index.html not found"}


@app.get("/settings")
def serve_settings():
    """Full interactive pre-game settings page, outside the click-through UI."""
    page = FRONTEND_DIR / "settings.html"
    if page.exists():
        return FileResponse(page)
    return {"error": "frontend/settings.html not found"}


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


# -- REST --


from pydantic import BaseModel, Field, StrictBool


class BuildPreferenceRequest(BaseModel):
    build_style: str


@app.get("/api/preferences")
async def get_preferences():
    async with game_state.lock:
        return {
            "schema_version": preferences.PREFERENCES_SCHEMA_VERSION,
            "build_style": game_state.build_style,
            "available_styles": list(BUILD_STYLES),
            "overlay": dict(game_state.overlay_preferences),
        }


@app.put("/api/preferences")
async def update_preferences(req: BuildPreferenceRequest):
    """Save a user's default build direction for all future and live updates."""
    if req.build_style not in BUILD_STYLES:
        raise HTTPException(status_code=422, detail="invalid build style")
    async with game_state.lock:
        try:
            preferences.save_build_style(req.build_style)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        except OSError:
            logger.exception("Could not persist build-style preference")
            raise HTTPException(
                status_code=500, detail="Could not save preferences"
            ) from None
        game_state.build_style = req.build_style
    await _broadcast(json.dumps({
        "type": "preferences_updated",
        "build_style": req.build_style,
    }))
    return {"build_style": req.build_style, "saved": True}



@app.put("/api/preferences/overlay")
async def update_overlay_preferences(payload: dict):
    """D4a: validate and store full overlay layout; never apply to Qt here."""
    try:
        overlay = preferences.validate_overlay(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    async with game_state.lock:
        try:
            preferences.save_overlay_preferences(overlay)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        except OSError:
            logger.exception("Could not persist overlay preferences")
            raise HTTPException(
                status_code=500, detail="Could not save preferences"
            ) from None
        game_state.overlay_preferences = overlay
        style = game_state.build_style
    await _broadcast(json.dumps({
        "type": "preferences_updated",
        "build_style": style,
        "overlay": overlay,
        "schema_version": preferences.PREFERENCES_SCHEMA_VERSION,
    }))
    return {
        "schema_version": preferences.PREFERENCES_SCHEMA_VERSION,
        "overlay": overlay,
        "saved": True,
    }


class TierListSwitchRequest(BaseModel):
    enabled: StrictBool


@app.get("/api/tierlist")
def tierlist_status():
    """Tier list status for Settings: never includes win rates or samples."""
    return tier_service.status()


@app.put("/api/tierlist")
def update_tierlist_switch(req: TierListSwitchRequest):
    try:
        tier_service.set_enabled(req.enabled)
    except OSError:
        logger.exception("Could not persist tier list switch")
        feature_diagnostics.record("tierdb.switch", "failed", "save_error")
        raise HTTPException(status_code=500, detail="Could not save preference") from None
    enabled = tier_service.enabled()
    feature_diagnostics.record("tierdb.switch", "ok", "enabled" if enabled else "disabled")
    return {"enabled": enabled}


@app.post("/api/tierlist/update")
def start_tierlist_update():
    return {"started": tier_service.start_update(static_data)}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "data_loaded": static_data.loaded_ok,
        "champions_loaded": len(static_data._champions),
        "augments_loaded": len(static_data._augments),
        "items_loaded": len(static_data._items),
    }


@app.get("/champion/{champion_id}")
def get_champion(champion_id: str):
    champ = static_data.get_champion(champion_id)
    if champ is None:
        return {"error": "not found"}
    return {"id": champ.id, "name": champ.name, "stats": vars(champ.stats)}


@app.get("/api/static-names")
def get_static_names():
    items = {**static_data._all_item_names,
             **{iid: item.name for iid, item in static_data._items.items()}}
    augments = {
        aid: {"name": aug.name, "tier": aug.tier.value}
        for aid, aug in static_data._augments.items()
    }
    stat_anvils = {
        aid: {"name": aug.name, "tier": aug.tier.value}
        for aid, aug in static_data._stat_anvils.items()
    }
    champions = {cid: champ.name for cid, champ in static_data._champions.items()}
    return {"items": items, "augments": augments, "stat_anvils": stat_anvils, "champions": champions}


def _read_champ_select_payload() -> dict | None:
    """Synchronous, read-only LCU access; poller runs this in a worker thread."""
    revision = next(_champ_select_revisions)
    snapshot = read_champ_select()
    if snapshot is None:
        emit_f0_trace("champion", "local_cell", "unknown",
                      "lcu_unavailable", source="lcu")
        return None
    draft, id_map = snapshot
    identity_status, identity_reason = classify_champion_identity(draft, id_map)
    # Only the public LCU champion catalog number may enter diagnostics.
    # Never store local cell ID, summonerId, Riot ID, player name or lockfile.
    public_champion_id = None
    if identity_status == "accepted" and isinstance(draft, dict):
        team = draft.get("myTeam")
        if isinstance(team, list):
            local_cell = draft.get("localPlayerCellId")
            matched = [
                row for row in team
                if isinstance(row, dict) and row.get("cellId") == local_cell
            ]
            if len(matched) == 1:
                numeric = matched[0].get("championId")
                if (type(numeric) is int and 1 <= numeric <= 4096
                        and isinstance(id_map, dict)
                        and str(numeric) in id_map):
                    public_champion_id = numeric
    emit_f0_trace("champion", "local_cell", identity_status,
                  identity_reason, source="lcu",
                  champion_id=public_champion_id)
    result = summarize_champion_select(
        draft, id_map, static_data.get_champion,
        record_lookup=get_champion_record,
    )
    if (identity_status == "accepted"
            and not any(row.get("current") for row in result.get("candidates", []))):
        emit_f0_trace("champion", "alias", "rejected",
                      "champion_unmapped", source="lcu")
    result["revision"] = revision
    return _annotate_champion_candidates(result)


@app.post("/api/history/import")
async def import_personal_history():
    """Explicit, local-only sync of own ARAM Mayhem matches.

    Called on user action only. Never returns raw match or player data.
    """
    if config.get("lcu_history_enabled", False) is not True:
        raise HTTPException(
            status_code=403,
            detail="LCU history import disabled pending policy review and explicit opt-in",
        )
    from backend.storage.history_import import sync_recent_mayhem_games
    return await asyncio.to_thread(sync_recent_mayhem_games)


@app.get("/api/champ-select/status")
def champ_select_status():
    """Local debug endpoint; no account IDs or client secrets are exposed."""
    payload = _read_champ_select_payload()
    return payload if payload else {"type": "champ_select_unavailable",
                                    "revision": next(_champ_select_revisions)}


@app.get("/api/ocr/status")
def ocr_status():
    readiness = ocr_capture.readiness_status()
    observed_stage = getattr(screen_watcher, "last_scan_stage", "not_scanned")
    # A mocked or outdated watcher must not inject free-form diagnostics.
    if observed_stage not in ocr_capture.SCAN_STAGES:
        observed_stage = "not_scanned"
    return {
        "scan_window_open": bool(game_state.scan_window_open),
        "scan_stage": observed_stage,
        "catalog_available": bool(static_data._augments),
        "available": readiness["available"],
        "reason": readiness["reason"],
        "next_step": readiness["next_step"],
        "enabled": game_state.ocr_enabled,
        "last_detected": game_state.ocr_last_detected,
        "offer_state": game_state.offer_state,
        "phase": game_state.ocr_phase,
        "stale": game_state.ocr_stale,
        "stale_since_epoch": game_state.ocr_stale_since_epoch,
        "foreground": game_state.ocr_foreground,
        "capture_backend": getattr(screen_watcher, "last_capture_backend", None),
        "offers": game_state.offer_ledger.payload(),
    }


@app.post("/api/ocr/scan")
async def ocr_scan():
    """Manual diagnostic OCR; never capture/inject outside a current offer.

    Uses the exact C3 temporal watcher shared with WS/automatic scans.
    The active match and offer epoch are captured under the state lock,
    and checked again after blocking OCR completes in a worker thread.
    """
    async with game_state.lock:
        request_match = game_state.match_id
        request_epoch = game_state.offer_epoch
        allowed = game_state.scan_window_open and game_state.ocr_enabled
        if not allowed:
            return {
                "status": "unavailable",
                "phase": game_state.ocr_phase,
                "error": "No active augment offer scan",
                "detected": [],
                "augment_choices_set": list(game_state.augment_choices),
                "ocr_slots": game_state.ocr_slot_choices,
            }
    if not ocr_available():
        return {
            "status": "unavailable", "phase": "ocr_missing",
            "error": "OCR not available — is Tesseract installed?",
            "detected": [],
        }

    result = await asyncio.to_thread(_run_ocr_scan_manual)
    ids, detected, proven, reverified, foreground, stage = _manual_scan_parts(result)
    async with game_state.lock:
        applied = game_state.accept_manual_ocr(
            ids, detected, match_id=request_match, offer_epoch=request_epoch,
            capture_proven=proven, reverified=reverified,
        )
        if applied:
            status = "detected"
            game_state.ocr_foreground = foreground
        elif (
            game_state.scan_window_open and game_state.ocr_enabled
            and game_state.offer_epoch == request_epoch
            and game_state.match_id == request_match
        ):
            failed_phase = _manual_scan_failure_phase(stage)
            game_state.offer_lifecycle.observe(
                "unavailable" if failed_phase in _CAPTURE_LOSS_PHASES
                else "transition"
            )
            game_state.set_ocr_phase(failed_phase)
            game_state.offer_ledger.on_titles_unverified()
            status = "transition"
        else:
            status = "superseded"
        response = {
            "status": status,
            "phase": game_state.ocr_phase,
            "stale": game_state.ocr_stale,
            "reverified": bool(applied and reverified),
            "foreground": game_state.ocr_foreground,
            "detected": detected if applied else [],
            "augment_choices_set": list(game_state.augment_choices),
            "ocr_slots": game_state.ocr_slot_choices,
            "offer_state": game_state.offer_state,
            "offer_epoch": game_state.offer_epoch,
            "match_id": game_state.match_id,
            "offers": game_state.offer_ledger.payload(),
        }
    # Publication uses the same offer epoch and never sends an unproven card.
    await _broadcast(json.dumps({
        **response, "type": "ocr_result",
        "augment_choices": list(response["augment_choices_set"]),
    }))
    return response


@app.get("/api/ocr/screenshots")
def list_screenshots():
    """List saved screenshots for debugging OCR region calibration."""
    if config.get("ocr_debug_screenshots", False) is not True:
        return []
    ss_dir = ocr_capture.SCREENSHOT_DIR
    if not ss_dir.exists():
        return []
    files = sorted(ss_dir.glob("card_*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": f.name, "url": f"/api/ocr/screenshots/{f.name}"} for f in files[:20]]


@app.get("/api/ocr/screenshots/{filename}")
def get_screenshot(filename: str):
    """Serve a saved screenshot."""
    if config.get("ocr_debug_screenshots", False) is not True or not filename.startswith("card_"):
        return {"error": "not found"}
    ss_dir = ocr_capture.SCREENSHOT_DIR
    path = (ss_dir / filename).resolve()
    if not path.is_relative_to(ss_dir.resolve()):
        return {"error": "not found"}
    if not path.exists() or not path.suffix == ".png":
        return {"error": "not found"}
    return FileResponse(path, media_type="image/png")


@app.post("/api/refresh")
async def refresh_data():
    """Force-refresh all cached augment and item data from APIs."""
    counts = force_refresh(static_data)
    async with game_state.lock:
        game_state.pipeline = Pipeline(static_data)
    return {"status": "refreshed", "loaded": counts}


@app.get("/api/augments/search")
def search_augments(
    q: str = Query(default="", min_length=0),
    tier: int | None = Query(default=None, ge=0, le=3),
):
    results = []
    query = q.lower()
    # Search augments and stat anvils based on tier filter
    pool = static_data.all_stat_anvils() if tier == 0 else static_data.all_augments()
    if tier is None:
        pool = static_data.all_augments() + static_data.all_stat_anvils()
    for aug in pool:
        if tier is not None and aug.tier.value != tier:
            continue
        if query and query not in aug.name.lower():
            continue
        results.append({
            "id": aug.id,
            "name": aug.name,
            "tier": aug.tier.value,
            "tier_name": aug.tier.name.replace("_", " ").title(),
            "description": aug.description,
        })
    results.sort(key=lambda a: a["name"])
    return results[:50]


# -- Explicit C2 offer identity and confirmation (local API only) --


class OfferIdentifyRequest(BaseModel):
    offer_id: int
    epoch: int
    slot: str
    augment_id: str


class OfferConfirmRequest(BaseModel):
    offer_id: int
    epoch: int
    augment_id: str


class OfferSlotRequest(BaseModel):
    slot: str


class OfferRecoverRequest(BaseModel):
    offer_id: int


def _offer_http_error(exc: LedgerError) -> HTTPException:
    code = exc.code
    status = (404 if code == "unknown_offer"
              else 422 if code in ("bad_slot", "not_in_catalog")
              else 409)
    return HTTPException(status_code=status, detail=code)


def _confirmed_augment_ids(state: GameState) -> list[str]:
    """Only explicit confirmed real augments may enter B4 build inputs."""
    is_anvil = getattr(static_data, "get_stat_anvil", None)
    return [
        aid for aid in state.offer_ledger.active_augment_ids()
        if not callable(is_anvil) or is_anvil(aid) is None
    ]


def _confirmed_anvil_ids(state: GameState) -> list[str]:
    """Keep stat anvils separate from the build's augment synergy input."""
    is_anvil = getattr(static_data, "get_stat_anvil", None)
    return [
        aid for aid in state.offer_ledger.active_augment_ids()
        if callable(is_anvil) and is_anvil(aid) is not None
    ]


def _sync_confirmed_augments(
    state: GameState, confirmed_offer, *, method: str = "manual",
) -> None:
    """Update build inputs only after a separately verified confirmation.

    Confirmation of a pending old offer must never close, clear, advance
    or otherwise modify the latest offer. State lock is held by caller.
    """
    state.chosen_augments[:] = _confirmed_augment_ids(state)
    state.chosen_stat_anvils[:] = _confirmed_anvil_ids(state)
    if not state.offer_ledger.offers or confirmed_offer is not state.offer_ledger.offers[-1]:
        return
    if not (state.scan_window_open or state.confirmation_pending
            or state.awaiting_stat_delta):
        return  # repeated identical confirmation has no lifecycle side effects
    state.augment_choices.clear()
    state.ocr_last_detected.clear()
    state.ocr_slot_choices = None
    if state.scan_window_open:
        event_log.emit(
            "ocr_window", state="closed",
            reason=("confirmed" if method == "automatic" else
                    "cursor_pick" if method == "cursor" else "manual_choice"),
            level=state.scan_window_level,
        )
    state.scan_window_open = False
    state.offer_lifecycle.close()
    state.offer_epoch += 1
    state.confirmation_pending = False
    state.awaiting_stat_delta = False
    state.delta_wait_ticks = 0
    state.stat_snapshot_before.clear()
    state.stat_snapshot_level_before = None
    state.stat_snapshot_items_before = None
    screen_watcher.reset()
    kind = ("anvil" if confirmed_offer.picked_id in state.chosen_stat_anvils
            else "augment")
    event_log.emit("augment_confirmation", method=method, kind=kind)


def _apply_approved_pick_evidence(
    state: GameState, evidence: PickedAugmentEvidence, *,
    catalog: set[str], approved_sources: frozenset[str] = frozenset(),
    now: float,
) -> bool:
    """Apply a separately authenticated pick under the existing state lock.

    No production event adapter calls this yet. An app-approved in-process
    provider must prove the actual source/match/offer before invoking it;
    there is deliberately NO HTTP/WS endpoint accepting this event.
    Existing poll ticks read confirmed IDs for dynamic build/synergy inputs.
    """
    confirmed, applied = state.offer_ledger.confirm_verified_external(
        evidence, current_match_id=state.match_id,
        catalog=catalog, approved_sources=approved_sources, now=now,
    )
    if applied:
        _sync_confirmed_augments(state, confirmed, method="automatic")
    return applied


@app.post("/api/offers/identify")
async def identify_offer(req: OfferIdentifyRequest):
    async with game_state.lock:
        try:
            offer = game_state.offer_ledger.identify(
                req.offer_id, req.epoch, req.slot, req.augment_id,
                set(static_data._augments),
            )
        except LedgerError as exc:
            raise _offer_http_error(exc) from None
        return {"offer_id": offer.offer_id, "epoch": offer.epoch,
                "offers": game_state.offer_ledger.payload()}


@app.post("/api/offers/confirm")
async def confirm_offer(req: OfferConfirmRequest):
    async with game_state.lock:
        try:
            offer = game_state.offer_ledger.confirm(
                req.offer_id, req.epoch, req.augment_id,
            )
        except LedgerError as exc:
            raise _offer_http_error(exc) from None
        _sync_confirmed_augments(game_state, offer)
        return {"offer_id": offer.offer_id, "epoch": offer.epoch,
                "chosen_augments": _confirmed_augment_ids(game_state),
                "offers": game_state.offer_ledger.payload()}


@app.post("/api/offers/confirm-slot")
async def confirm_offer_slot(req: OfferSlotRequest):
    async with game_state.lock:
        try:
            offer = game_state.offer_ledger.confirm_slot(req.slot)
        except LedgerError as exc:
            raise _offer_http_error(exc) from None
        _sync_confirmed_augments(game_state, offer)
        return {"offer_id": offer.offer_id, "epoch": offer.epoch,
                "chosen_augments": _confirmed_augment_ids(game_state),
                "offers": game_state.offer_ledger.payload()}


@app.post("/api/offers/recover")
async def recover_offer(req: OfferRecoverRequest):
    async with game_state.lock:
        try:
            offer = game_state.offer_ledger.open_for_recovery(req.offer_id)
        except LedgerError as exc:
            raise _offer_http_error(exc) from None
        game_state.offer_epoch += 1  # invalidate in-flight OCR operations
        if offer.epoch != game_state.offer_epoch:
            game_state.offer_ledger.set_current_epoch(
                max(game_state.offer_epoch, offer.epoch + 1),
            )
            game_state.offer_epoch = offer.epoch
        game_state.scan_window_open = True
        game_state.offer_lifecycle.open()
        screen_watcher.reset()
        recovery = {
            "offer_id": offer.offer_id, "epoch": offer.epoch,
            "offers": game_state.offer_ledger.payload(),
            "match_id": game_state.match_id,
        }
    # A manual Alt+S recovery runs outside WebView. Publish its identity
    # only after the ledger lock is released so inline identification can open
    # even when OCR is unavailable. This never confirms a pick.
    await _broadcast(json.dumps({
        "type": "offer_recovered", **recovery,
    }))
    return recovery


class BugReportRequest(BaseModel):
    description: str = Field(default="", max_length=2000)


_last_bug_report_time: float = 0.0
_BUG_REPORT_COOLDOWN = 30.0  # seconds between reports


@app.post("/api/bug-report")
async def create_bug_report(req: BugReportRequest | None = None):
    """Generate a bug report with recent errors, logs, WS messages, and game state.

    Saves locally as JSON backup and optionally posts as a GitHub issue
    (if github_token and github_repo are configured in config.toml).
    Rate-limited to one report per 30 seconds.
    """
    global _last_bug_report_time
    user_description = req.description if req else ""

    # Serialize the cooldown check and local write so concurrent submissions
    # cannot both be accepted. A failed disk write must not consume cooldown.
    async with game_state.lock:
        now = time.monotonic()
        if now - _last_bug_report_time < _BUG_REPORT_COOLDOWN:
            remaining = max(1, int(_BUG_REPORT_COOLDOWN - (now - _last_bug_report_time)))
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {remaining}s before submitting another report",
            )

        state_dict = {
            "augment_choices": list(game_state.augment_choices),
            "chosen_augments": list(game_state.chosen_augments),
            "chosen_stat_anvils": list(game_state.chosen_stat_anvils),
            "last_known_level": game_state.last_known_level,
            "scan_window_open": game_state.scan_window_open,
            "awaiting_stat_delta": game_state.awaiting_stat_delta,
            "ocr_enabled": game_state.ocr_enabled,
        }
        try:
            report_path = diagnostics.generate_report(
                game_state_dict=state_dict, user_description=user_description,
            )
        except OSError:
            logger.exception("Unable to save the local diagnostic report")
            raise HTTPException(
                status_code=500, detail="Could not save local diagnostic report",
            ) from None
        _last_bug_report_time = now

    # Attempt GitHub issue creation
    github_url = None
    title, body = diagnostics.format_github_issue(
        game_state_dict=state_dict,
        user_description=user_description,
    )
    from backend.github_reporter import post_issue
    gh_result = post_issue(title, body)
    if gh_result:
        github_url = gh_result.get("html_url")

    return {
        "status": "created",
        "path": str(report_path),
        "filename": report_path.name,
        "github_url": github_url,
    }


# -- WebSocket --


@app.websocket("/ws/game")
async def game_ws(websocket: WebSocket):
    """
    Bidirectional WebSocket for game state.
    Client can send:
      - {"type": "snapshot", "data": {...}} — manual snapshot
      - {"type": "set_augment_choices", "augment_ids": [...]} — set offered augments
      - {"type": "choose_augment", "augment_id": "..."} — mark augment as chosen
      - {"type": "clear_augments"} — reset augment tracking
    Server pushes PipelineResult on every poll cycle.
    """
    await websocket.accept()
    async with game_state.lock:
        game_state.ws_clients.add(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            diagnostics.record_ws_message("inbound", raw)

            try:
                msg = json.loads(raw)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Invalid JSON from WS client: %s", e)
                await _send_ws_message(websocket, json.dumps({"error": "invalid json"}))
                continue

            if not isinstance(msg, dict):
                await _send_ws_message(websocket, json.dumps({"error": "expected JSON object"}))
                continue

            msg_type = msg.get("type", "")

            if msg_type == "snapshot":
                data = msg.get("data")
                if not isinstance(data, dict):
                    await _send_ws_message(websocket, json.dumps({"error": "snapshot requires 'data' object"}))
                    continue
                snapshot = _parse_snapshot(data)
                snapshot.chosen_augments = _confirmed_augment_ids(game_state)
                result = game_state.pipeline.run(snapshot) if game_state.pipeline else None
                if result:
                    await _send_ws_message(websocket, json.dumps(
                        _serialize_result(result, static_data)
                    ))

            elif msg_type == "feature_ack":
                # Tier list renders (incl. champ select) ack without a match;
                # every other UI feature stays match/offer fenced.
                if str(msg.get("feature", "")).startswith(("tierdb.", "items.")):
                    _handle_feature_ack(msg)
                else:
                    async with game_state.lock:
                        _accept_feature_ack(game_state, msg)

            elif msg_type == "set_augment_choices":
                augment_ids = msg.get("augment_ids", [])
                if not isinstance(augment_ids, list):
                    await _send_ws_message(websocket, json.dumps({"error": "'augment_ids' must be a list"}))
                    continue
                async with game_state.lock:
                    game_state.augment_choices.clear()
                    game_state.augment_choices.extend(augment_ids)
                    game_state.ocr_slot_choices = None
                await _send_ws_message(websocket, json.dumps({
                    "type": "ack",
                    "action": "set_augment_choices",
                    "augment_ids": list(game_state.augment_choices),
                }))

            elif msg_type == "choose_augment":
                # Legacy local action delegates to explicit confirmation; a
                # guessed/unknown ID can never be appended to build inputs.
                aug_id = msg.get("augment_id")
                async with game_state.lock:
                    try:
                        offer_id = msg.get("offer_id")
                        epoch = msg.get("epoch")
                        if offer_id is None or epoch is None:
                            # Historical client compatibility: newest offer
                            # only, still requires an identified offered ID.
                            if not game_state.offer_ledger.offers:
                                raise LedgerError("unknown_offer")
                            latest = game_state.offer_ledger.offers[-1]
                            offer_id, epoch = latest.offer_id, latest.epoch
                        offer = game_state.offer_ledger.confirm(offer_id, epoch, aug_id)
                    except LedgerError as exc:
                        response = {"type": "error", "action": "choose_augment",
                                    "error": exc.code}
                    else:
                        _sync_confirmed_augments(game_state, offer)
                        response = {
                            "type": "ack", "action": "choose_augment",
                            "offer_id": offer.offer_id, "epoch": offer.epoch,
                            "chosen_augments": _confirmed_augment_ids(game_state),
                            "offers": game_state.offer_ledger.payload(),
                        }
                await _send_ws_message(websocket, json.dumps(response))

            elif msg_type == "clear_augments":
                async with game_state.lock:
                    game_state.augment_choices.clear()
                    game_state.ocr_slot_choices = None
                    # Clearing manual search never erases ledger-confirmed picks.
                    game_state.chosen_augments[:] = _confirmed_augment_ids(game_state)
                    game_state.chosen_stat_anvils.clear()
                    game_state.confirmation_pending = False
                    game_state.awaiting_stat_delta = False
                    game_state.delta_wait_ticks = 0
                    game_state.stat_snapshot_before.clear()
                    game_state.stat_snapshot_level_before = None
                    game_state.stat_snapshot_items_before = None
                await _send_ws_message(websocket, json.dumps({
                    "type": "ack",
                    "action": "clear_augments",
                }))

            elif msg_type == "scan_augments":
                # Same A3/A4-proven gate as REST and Alt+S. Pending stat/choice
                # confirmation is not a veto to reading cards, but an unverified
                # scan can never add an augment or resurrect a closed offer.
                async with game_state.lock:
                    request_match = game_state.match_id
                    request_epoch = game_state.offer_epoch
                    allowed = game_state.scan_window_open and game_state.ocr_enabled
                result = ([], [])
                if allowed and ocr_available():
                    result = await asyncio.to_thread(_run_ocr_scan_manual)
                ids, detected, proven, reverified, foreground, stage = _manual_scan_parts(result)
                async with game_state.lock:
                    applied = allowed and game_state.accept_manual_ocr(
                        ids, detected, match_id=request_match,
                        offer_epoch=request_epoch, capture_proven=proven,
                        reverified=reverified,
                    )
                    if applied:
                        game_state.ocr_foreground = foreground
                        status = "detected"
                    elif (allowed and game_state.match_id == request_match
                          and game_state.offer_epoch == request_epoch
                          and game_state.scan_window_open
                          and game_state.ocr_enabled):
                        failed_phase = _manual_scan_failure_phase(stage)
                        game_state.offer_lifecycle.observe(
                            "unavailable" if failed_phase in _CAPTURE_LOSS_PHASES
                            else "transition"
                        )
                        game_state.set_ocr_phase(failed_phase)
                        game_state.offer_ledger.on_titles_unverified()
                        status = "transition"
                    else:
                        status = "superseded"
                    message = {
                        "type": "ocr_result", "status": status,
                        "phase": game_state.ocr_phase,
                        "stale": game_state.ocr_stale,
                        "reverified": bool(applied and reverified),
                        "foreground": game_state.ocr_foreground,
                        "detected": detected if applied else [],
                        "augment_choices": list(game_state.augment_choices),
                        "offer_state": game_state.offer_state,
                        "offer_epoch": game_state.offer_epoch,
                        "match_id": game_state.match_id,
                        "offers": game_state.offer_ledger.payload(),
                    }
                await _send_ws_message(websocket, json.dumps(message))

            elif msg_type == "set_build_style":
                # Backward-compatible preference action for older overlay clients.
                style = msg.get("style")
                if not isinstance(style, str) or style not in BUILD_STYLES:
                    await _send_ws_message(websocket, json.dumps({"error": "invalid build style"}))
                    continue
                save_failed = False
                async with game_state.lock:
                    try:
                        preferences.save_build_style(style)
                    except OSError:
                        logger.exception("Could not persist WS build style")
                        save_failed = True
                    else:
                        game_state.build_style = style
                if save_failed:
                    await _send_ws_message(websocket, json.dumps({"error": "could not save build style"}))
                    continue
                await _send_ws_message(websocket, json.dumps({
                    "type": "ack", "action": "set_build_style", "style": style,
                }))

            elif msg_type == "toggle_ocr":
                async with game_state.lock:
                    requested = msg.get("enabled", not game_state.ocr_enabled)
                    if not isinstance(requested, bool):
                        await _send_ws_message(websocket, json.dumps({
                            "error": "OCR enabled must be boolean",
                        }))
                        continue
                    game_state.set_ocr_enabled(requested, watcher=screen_watcher)
                    response = {
                        "type": "ack", "action": "toggle_ocr",
                        "enabled": game_state.ocr_enabled,
                        "offer_state": game_state.offer_state,
                        "offer_epoch": game_state.offer_epoch,
                        "match_id": game_state.match_id,
                    }
                    stale_message = {
                        "type": "ocr_result",
                        "status": "disabled" if not requested else "unavailable",
                        "phase": game_state.ocr_phase,
                        "foreground": game_state.ocr_foreground,
                        "stale": game_state.ocr_stale,
                        "offer_state": game_state.offer_state,
                        "offer_epoch": game_state.offer_epoch,
                        "match_id": game_state.match_id,
                    }
                await _send_ws_message(websocket, json.dumps(response))
                # Every connected overlay needs this invalidation, not just
                # the Settings client which initiated the toggle.
                await _broadcast(json.dumps(stale_message))

            else:
                await _send_ws_message(websocket, json.dumps({"error": "unknown message type"}))

    except WebSocketDisconnect:
        pass
    finally:
        async with game_state.lock:
            game_state.ws_clients.discard(websocket)
        sender = game_state.ws_send_tasks.pop(websocket, None)
        game_state.ws_send_queues.pop(websocket, None)
        if sender is not None:
            sender.cancel()


# -- Polling loop --


def _slot_detection_payload(matches) -> list[dict]:
    """Serialize three observed positions, including explicit unknown slots."""
    from backend.collectors.slot_title_ocr import SlotMatches
    if isinstance(matches, SlotMatches):
        return [
            {
                "slot": slot,
                "id": value[0] if value else None,
                "name": value[1] if value else None,
                "confidence": value[2] if value else 0,
            }
            for slot, value in matches.slots.items()
        ]
    # Legacy mocked/manual test inputs never authorise slot mapping.
    return [
        {"id": aid, "name": name, "confidence": score}
        for aid, name, score in matches or []
    ]


def _slots_from_detected(detected: list[dict] | None) -> dict[str, str | None] | None:
    from backend.collectors.slot_title_ocr import SLOTS
    if not isinstance(detected, list) or len(detected) != len(SLOTS):
        return None
    if [row.get("slot") for row in detected] != list(SLOTS):
        return None
    values = [row.get("id") for row in detected]
    if any(value is not None and not isinstance(value, str) for value in values):
        return None
    if len([value for value in values if value is not None]) != len(set(
        value for value in values if value is not None
    )):
        return None
    return dict(zip(SLOTS, values))


def _ocr_title_catalog() -> dict[str, str]:
    """Share one deterministic title catalog for manual and watcher scans."""
    # Stat Anvil titles have a dedicated watcher (P0-C); shared Silver/Gold
    # titles must never be read into an augment offer.
    return {aid: aug.name for aid, aug in static_data._augments.items()}


def _run_ocr_scan_manual() -> _ManualScanEvidence:
    """Use the shared A3/A4 proven watcher; never accept cached unchanged slots.

    Protect the watcher scan and its proof flags under the same RLock: a
    concurrent automatic read cannot change the evidence before it is copied.
    """
    augment_names = _ocr_title_catalog()
    with getattr(screen_watcher, "_lock", nullcontext()):
        matches = detect_augments(
            augment_names, save=config.get("ocr_debug_screenshots", False) is True,
        )
        proven = bool(matches) and getattr(
            screen_watcher, "last_scan_stage", "not_scanned",
        ) == "titles_detected"
        temporal = getattr(screen_watcher, "_temporal", None)
        reverified = bool(proven and getattr(temporal, "last_emit_reverified", False))
        foreground = getattr(screen_watcher, "_last_foreground", "other")
        stage = getattr(screen_watcher, "last_scan_stage", "not_scanned")
    event_log.emit(
        "ocr_recognition", outcome="manual_detected" if proven else "manual_empty",
        count=len(matches or []),
        confidence=float(max((m[2] for m in matches or []), default=0)),
    )
    ids = [m[0] for m in matches] if proven else []
    detected = _slot_detection_payload(matches) if proven else []
    return _ManualScanEvidence(
        ids, detected, proven=proven, reverified=reverified,
        foreground=foreground, stage=stage,
    )


def _run_watcher_check() -> tuple[str, list[str], list[dict] | None]:
    """Capture an atomic A3/A4 observation with separate A5 evidence."""
    augment_names = _ocr_title_catalog()
    # Fake watchers used in older offline tests lack a lock or metadata.
    with getattr(screen_watcher, "_lock", nullcontext()):
        action, matches = screen_watcher.check(
            augment_names, save=config.get("ocr_debug_screenshots", False) is True,
        )
        temporal = getattr(screen_watcher, "_temporal", None)
        current = temporal.snapshot() if temporal is not None else None
        has_current = bool(current is not None and any(
            value is not None for value in current.slots.values()
        ))
        has_partial = bool(has_current and any(
            value is None for value in current.slots.values()
        ))
        metadata = {
            "stage": getattr(screen_watcher, "last_scan_stage", "not_scanned"),
            "foreground": getattr(screen_watcher, "_last_foreground", "other"),
            "reverified": bool(
                getattr(temporal, "last_emit_reverified", False)
                and action == "detected"
            ),
            "has_partial": has_partial,
            "has_current": has_current,
        }
    if action != "unchanged":
        event_log.emit(
            "ocr_recognition", outcome=action, count=len(matches or []),
            confidence=float(max((m[2] for m in matches or []), default=0)),
        )
    # F0: classify evidence only, never alter the strict OCR decision.
    if action == "detected" and hasattr(matches, "slots"):
        slot_ids = {slot: value[0] if value else None
                    for slot, value in matches.slots.items()}
        status, reason = classify_offer_slots(
            slot_ids, stage=metadata["stage"], stale=False, epoch_valid=True,
        )
        emit_f0_trace("augment", "matching", status, reason,
                      source="ocr", count=len(matches))
        for slot, value in matches.slots.items():
            emit_f0_trace(
                "augment", "matching", "accepted" if value else "unknown",
                "slots_verified_complete" if value else "titles_unidentified",
                source="ocr", slot=slot,
            )
    elif action not in ("unchanged",):
        stage = metadata["stage"]
        safe_reason = stage if stage in (
            "titles_verifying", "titles_transition", "titles_unidentified",
            "geometry_unsupported", "game_not_focused", "game_occluded",
            "capture_unavailable", "ocr_unavailable", "verified_absence",
        ) else "capture_unverified"
        emit_f0_trace("augment", "capture", "unknown",
                      safe_reason, source="ocr")
    if action == "detected" and (matches or hasattr(matches, "slots")):
        ids = [m[0] for m in matches]
        detected = _slot_detection_payload(matches)
        return _OcrWatcherObservation(action, ids, detected, **metadata)
    return _OcrWatcherObservation(action, [], None, **metadata)


def _manual_scan_failure_phase(stage: str) -> str:
    """Classify manual capture failure from the verified watcher scan stage."""
    if stage == "ocr_unavailable":
        return "ocr_missing"
    if stage == "game_window_unavailable":
        return "no_game"
    if stage == "game_occluded":
        return "occluded"
    if stage in ("capture_invalid", "geometry_unsupported"):
        return "capture_unavailable"
    if stage in ("titles_unidentified", "titles_unchanged", "verified_absence"):
        return "no_offer"
    return "verifying"


def _phase_for_observation(state: GameState, observation: tuple) -> str:
    """Map capture outcomes to exactly nine honest phases; no focus gating."""
    action = observation[0]
    stage = getattr(observation, "stage", "not_scanned")
    if action == "occluded":
        state.ocr_unreadable_ticks = 0
        return "occluded"
    if action == "capture_unavailable":
        state.ocr_unreadable_ticks = 0
        return "capture_unavailable"
    if action == "unavailable":
        state.ocr_unreadable_ticks = 0
        return "no_game" if stage == "game_window_unavailable" else "capture_unavailable"
    if stage == "titles_verifying" or action == "transition":
        state.ocr_unreadable_ticks = 0
        return "verifying"
    if action in ("detected", "unchanged", "no_augments"):
        if getattr(observation, "has_partial", False):
            state.ocr_unreadable_ticks += 1
            return "unreadable" if state.ocr_unreadable_ticks >= 3 else "verifying"
        state.ocr_unreadable_ticks = 0
        if action == "detected" or getattr(observation, "has_current", False):
            return "detected"
        return "no_offer"
    state.ocr_unreadable_ticks = 0
    return "no_offer"


def _record_match_phase(state: GameState, phase: str) -> None:
    """Diagnostic-only phase tracker: no effect on gameplay decisions."""
    previous = getattr(state, "_diagnostic_phase", "no_game")
    if previous != phase:
        event_log.emit("match_transition", from_state=previous, to_state=phase)
        state._diagnostic_phase = phase


def _status_message(state: GameState, status: str) -> str:
    """Bounded state transition diagnostics, with opaque match ID only in WS."""
    if state.lifecycle_status != status:
        state.lifecycle_status = status
        event_log.emit("game_status", state=status)
    message = {"type": "status", "state": status}
    if state.match_id and status in (
        "in_game", "champion_unresolved", "live_data_unavailable",
    ):
        message["match_id"] = state.match_id
    return json.dumps(message)


def _finish_match(state: GameState, now: float) -> None:
    """Called under the state lock; one end transition, no 300s timeout."""
    state.reset()
    state.match_id = None
    state._last_game_time = None
    state._last_champion_id = None
    state._last_player_key = None
    state.lcda_misses = 0
    state.first_lcda_miss_at = None
    state.had_game_last_tick = False
    state.post_game = True
    state.post_game_time = now
    _record_match_phase(state, "post_game")


def _begin_or_continue_match(
    state: GameState, snapshot: GameSnapshot, raw: dict, flow: object | None,
) -> None:
    """Resolve LCU match ID, else guarded champion/player + game-time fallback.

    The opaque sequence distinguishes consecutive sessions without inventing
    an authoritative League game ID. Never log the player's local identity.
    """
    import math

    flow_id = getattr(flow, "game_id", None)
    authoritative = (
        f"lcu:{flow_id}"
        if isinstance(flow_id, (str, int))
        and str(flow_id).strip() not in ("", "0", "unknown")
        else None
    )
    champion = str(getattr(snapshot, "champion_id", "") or "")
    active = raw.get("activePlayer", {}) if isinstance(raw, dict) else {}
    if not isinstance(active, dict):
        active = {}
    from backend.collectors.lcda import _riot_identity
    player_key = _riot_identity(active) or (
        str(active.get("summonerName")) if active.get("summonerName") else None
    )
    candidate_time = getattr(snapshot, "game_time", None)
    try:
        game_time = float(candidate_time) if candidate_time is not None else None
        if game_time is not None and not math.isfinite(game_time):
            game_time = None
    except (ValueError, TypeError):
        game_time = None

    different_lcu_id = bool(
        state.match_id and authoritative
        and state.match_id.startswith("lcu:") and state.match_id != authoritative
    )
    # Minor clock jitter is not enough evidence of a new match.
    regressed = bool(
        game_time is not None and state._last_game_time is not None
        and game_time < state._last_game_time - 10.0
    )
    different_champion = bool(
        champion and state._last_champion_id and champion != state._last_champion_id
    )
    different_player = bool(
        player_key and state._last_player_key and player_key != state._last_player_key
    )
    new_session = different_lcu_id or regressed or different_champion or different_player

    if state.match_id is None or new_session:
        if state.match_id is not None or state.post_game:
            state.reset()
        state._match_sequence += 1
        state.match_id = (
            authoritative if authoritative and not (
                new_session and not different_lcu_id
                and state.match_id == authoritative
            ) else f"fallback:{state._match_sequence}"
        )
    elif authoritative and state.match_id.startswith("fallback:"):
        # A late read-only LCU game ID resolves the same observed session.
        state.match_id = authoritative

    state._last_game_time = game_time if game_time is not None else state._last_game_time
    state._last_champion_id = champion or state._last_champion_id
    state._last_player_key = player_key or state._last_player_key
    state.lcda_misses = 0
    state.first_lcda_miss_at = None
    state.had_game_last_tick = True
    state.post_game = False


def _record_items_outside_pool(state: GameState, raw: dict, data: StaticData) -> None:
    """Record observed non-pool IDs once per match; never log player details.

    This is evidence for later N1 reconciliation, not permission to buy an
    item. B2 will supply exact canonical variants; no name guessing here.
    """
    meta = getattr(data, "item_pool_meta", None)
    if meta is None or meta.availability != "verified_two_source":
        return
    catalog = getattr(data, "_items", {})
    pool = getattr(catalog, "pool_ids", frozenset())
    if not isinstance(raw, dict):
        return
    players = raw.get("allPlayers")
    if not isinstance(players, list):
        return
    for player in players:
        if not isinstance(player, dict):
            continue
        items = player.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or item.get("slot") == 6:
                continue
            identifier = item.get("itemID")
            if not isinstance(identifier, (str, int)):
                continue
            item_id = str(identifier)
            if (not item_id.isascii() or not item_id.isdecimal()
                    or not 4 <= len(item_id) <= 6
                    or item_id in pool or item_id in state._item_outside_pool_seen):
                continue
            state._item_outside_pool_seen.add(item_id)
            event_log.emit(
                "item_outside_pool", item_id=item_id, **{"class": data.item_class(item_id)},
            )


def _register_lcda_miss(state: GameState, now: float) -> bool:
    """True after three consecutive misses spanning at least six seconds."""
    if not state.had_game_last_tick:
        return False
    if state.lcda_misses == 0:
        state.first_lcda_miss_at = now
    state.lcda_misses += 1
    return (
        state.lcda_misses >= 3
        and state.first_lcda_miss_at is not None
        and now - state.first_lcda_miss_at >= 6.0
    )


def _poll_dependencies() -> SimpleNamespace:
    """Capture the live integrations for one polling task.

    Tests inject their own LCDA, LCU, OCR, clock and transport dependencies
    into poll_tick instead of touching the local League client or desktop.
    """
    return SimpleNamespace(
        get_raw_game_data=get_raw_game_data,
        parse_game_snapshot=parse_game_snapshot,
        read_champ_select_payload=_read_champ_select_payload,
        read_gameflow=read_gameflow,
        ocr_available=ocr_available,
        run_watcher_check=_run_watcher_check,
        run_anvil_check=anvil_popup.run_anvil_check,
        screen_watcher=screen_watcher,
        to_thread=asyncio.to_thread,
        broadcast=_broadcast,
        try_stat_delta_match=_try_stat_delta_match,
        send_augment_confirm=_send_augment_confirm,
        serialize_result=_serialize_result,
        static_data=static_data,
    )


def _anvil_offer_payload(state: GameState, result) -> dict | None:
    """Only a verified popup with ratings is sent; the UI shows the top pick."""
    offer = state.anvil_offer
    ratings = list(getattr(result, "anvil_offer_ratings", None) or [])
    if offer is None:
        return None
    return {"epoch": state.anvil_epoch, "tier": offer.tier,
            "tier_source": offer.tier_source, "count": len(offer.shards),
            "cards": ratings if ratings else [
                {"anvil_id": s.id, "anvil_name": s.title, "tier": s.tier,
                 "stats": dict(s.stats), "score": None, "modelled": False}
                for s in offer.shards]}


def _augment_cards_verified(state: GameState) -> bool:
    slots = state.ocr_slot_choices
    return bool(state.scan_window_open and isinstance(slots, dict)
                and all(isinstance(slots.get(s), str) and slots[s]
                        for s in ("left", "centre", "right")))


def _augment_titles_blank(state: GameState) -> bool:
    slots = state.ocr_slot_choices
    return isinstance(slots, dict) and bool(slots) and all(v is None for v in slots.values())


async def _anvil_popup_tick(state: GameState, deps: SimpleNamespace, now: float) -> None:
    """P0-C: watch the screen for the Stat Anvil popup during the match.

    Field fix 23/11: neither a voucher edge nor the augment scan window may
    gate this (the popup came with no voucher while the augment window was
    still open). It uses its own watcher, which skips OCR when no card
    background is on screen, and skips while verified AUGMENT cards show.
    Diagnostics carry IDs/reasons only, never OCR text or pixels.
    """
    run = getattr(deps, "run_anvil_check", None)
    sd = getattr(deps, "static_data", None)
    catalog_fn = getattr(sd, "stat_anvil_catalog", None)
    if run is None or not callable(catalog_fn) or not state.match_id:
        return
    if (state.anvil_window_until is not None and now > state.anvil_window_until
            and state.anvil_offer is None):
        # The voucher hint expired unseen. Diagnostic only: the popup is
        # still watched below (field 23/11: it came with no voucher edge).
        state.anvil_window_until = None
        state.anvil_voucher_tier = None
        feature_diagnostics.record("anvil.offer_detected", "skipped", "popup_unverified")
    if not state.ocr_enabled or not deps.ocr_available():
        return
    if state.scan_window_open and not _augment_titles_blank(state):
        # The augment watcher is reading (or has read) augment titles: never
        # OCR the same cards twice. Field 23/11: during the Anvil popup it
        # read three BLANK titles, which is when this watcher must look.
        return
    catalog = catalog_fn()
    if not catalog:
        return
    action, ids = await deps.to_thread(run, anvil_title_catalog(catalog.values()))
    async with state.lock:
        if action in ("detected", "unchanged") and ids and all(ids):
            state.anvil_absent_ticks = 0
            res = resolve_anvil_offer(ids, catalog, voucher_tier=state.anvil_voucher_tier)
            if res.status == "ok":
                changed = (state.anvil_offer is None
                           or [s.id for s in state.anvil_offer.shards]
                           != [s.id for s in res.shards])
                if changed:
                    state.anvil_epoch += 1
                    feature_diagnostics.record(
                        "anvil.offer_detected", "ok", "verified_offer", len(res.shards))
                state.anvil_offer = res
            else:
                state.anvil_offer = None
                feature_diagnostics.record("anvil.offer_detected", res.status, res.reason)
        elif action in ("no_augments", "disappeared", "unavailable"):
            if state.anvil_offer is not None:
                state.anvil_absent_ticks += 1
                if state.anvil_absent_ticks >= anvil_popup.ABSENT_TICKS_TO_CLOSE:
                    # Popup gone (choice made or closed): end this window.
                    state.anvil_offer = None
                    state.anvil_window_until = None
                    state.anvil_voucher_tier = None
                    state.anvil_absent_ticks = 0


def _presence_armed(state: GameState) -> str | None:
    """Which verified offer the OCR-free presence probe is guarding, if any."""
    if not state.match_id:
        return None
    if state.anvil_offer is not None:
        return "anvil"
    if _augment_cards_verified(state):
        return "augment"
    return None


async def _presence_step(state: GameState, probe, now: float) -> str | None:
    """Apply one probe; on confirmed disappearance close and infer the pick.

    Returns the closed target ("augment"/"anvil") or None. Inference is a
    correctable pick (Alt+N wins); without one clear card it abstains.
    """
    message = None
    closed = None
    async with state.lock:
        target = _presence_armed(state)
        if target is None:
            state.presence_trail.clear()
            return None
        trail = state.presence_trail
        trail.append(probe)
        del trail[:-card_presence.TRAIL_LEN]
        if not card_presence.cards_gone(trail):
            return None
        slot = card_presence.infer_pick(trail)
        trail.clear()
        closed = target
        if target == "anvil":
            offer = state.anvil_offer
            index = ("left", "centre", "right", "fourth").index(slot) if slot else None
            if offer is not None and index is not None and index < len(offer.shards):
                state.anvil_picked_ids.append(offer.shards[index].id)
                feature_diagnostics.record("anvil.pick_inferred", "ok", "cursor_slot")
            else:
                feature_diagnostics.record("anvil.pick_inferred", "skipped", "cursor_ambiguous")
            state.anvil_offer = None
            state.anvil_window_until = None
            state.anvil_voucher_tier = None
            state.anvil_absent_ticks = 0
            event_log.emit("ocr_window", state="closed", reason="anvil_cards_gone",
                           level=state.scan_window_level)
        else:
            message = _augment_cards_gone(state, slot)
    if message is not None:
        await _broadcast(message)
    return closed


def _augment_cards_gone(state: GameState, slot: str | None) -> str:
    """Cards vanished (two OCR-free probes). State lock held by the caller."""
    state.offer_ledger.on_titles_unverified()
    state.offer_lifecycle.observe("disappeared", verified_absence=True)
    state.set_ocr_phase("no_offer", offer_closed=True)
    event_log.emit("ocr_window", state="closed", reason="offer_disappeared",
                   level=state.scan_window_level)
    state.confirmation_pending = True
    state.awaiting_stat_delta = True
    state.delta_wait_ticks = 0
    inferred = None
    if slot is not None:
        try:
            inferred = state.offer_ledger.confirm_inferred(slot)
        except LedgerError:
            inferred = None
    if inferred is not None:
        feature_diagnostics.record("augment.pick_inferred", "ok", "cursor_slot")
        _sync_confirmed_augments(state, inferred, method="cursor")
    else:
        feature_diagnostics.record("augment.pick_inferred", "skipped", "cursor_ambiguous")
        state.scan_window_open = False
        state.offer_epoch += 1
    return json.dumps({
        "type": "ocr_result", "status": "disappeared",
        "offer_state": state.offer_state, "stale": False,
        "phase": state.ocr_phase,
        "picked_id": inferred.picked_id if inferred is not None else None,
        "pick_source": "cursor_inferred" if inferred is not None else None,
        "augment_choices": list(state.augment_choices),
        "offer_epoch": state.offer_epoch, "match_id": state.match_id,
        "offers": state.offer_ledger.payload(),
    })


async def _presence_loop() -> None:
    """Fast OCR-free probe, active only while a verified offer is shown."""
    loop = asyncio.get_running_loop()
    while True:
        try:
            if _presence_armed(game_state) is not None:
                now = loop.time()
                probe = await asyncio.to_thread(card_presence.probe_cards, now)
                await _presence_step(game_state, probe, now)
            elif game_state.presence_trail:
                game_state.presence_trail.clear()
        except Exception as exc:  # never kill the loop; IDs only in logs
            logger.warning("Card presence probe failed: %s", type(exc).__name__)
        await asyncio.sleep(card_presence.PROBE_INTERVAL_S)


async def poll_tick(state: GameState, deps: SimpleNamespace, now: float) -> None:
    """Serialize individual polling transactions without locking out sockets."""
    async with state.poll_lock:
        await _poll_tick_once(state, deps, now)


async def _poll_tick_once(state: GameState, deps: SimpleNamespace, now: float) -> None:
    """Perform one poll, staging messages without sending under state.lock."""
    clients_count = len(state.ws_clients)
    if clients_count > 0:
        # requests.Session.get is synchronous: never call it on the ASGI event loop.
        # Legacy injected test dependencies may still supply a dict/None.
        lcda_result = await deps.to_thread(deps.get_raw_game_data)
        raw = lcda_result.payload if isinstance(lcda_result, LCDAResult) else lcda_result
        # Keep existing deterministic M1 mocks intact; production injects the
        # read-only Gameflow collector and receives explicit statuses.
        has_gameflow = hasattr(deps, "read_gameflow")
        flow = await deps.to_thread(deps.read_gameflow) if has_gameflow else None
        phase = getattr(flow, "phase", None)
        # A confirmed Gameflow post-game phase takes precedence over stale LCDA.
        end_phases = ("WaitingForStats", "PreEndOfGame", "EndOfGame")
        if phase in end_phases and state.had_game_last_tick:
            async with state.lock:
                _finish_match(state, now)
            await deps.broadcast(json.dumps({"type": "game_ended"}))
            if has_gameflow:
                await deps.broadcast(_status_message(state, "post_game"))
            return

        if raw is not None:
            _record_match_phase(state, "in_game")
            snapshot = deps.parse_game_snapshot(raw, GamePhase.IN_GAME)
            current_level = snapshot.level

            match_confirmation_due = False
            async with state.lock:
                _begin_or_continue_match(state, snapshot, raw, flow)
                # Two observed inventories, same game: detect actual voucher
                # increments. Do not open a generic 3-slot augment scan:
                # live Stat Anvil option catalogue/layout is still unknown.
                voucher_counts = getattr(snapshot, "anvil_vouchers", None)
                bought = state.anvil_voucher_observer.observe(voucher_counts)
                if bought:
                    feature_diagnostics.record(
                        "anvil.voucher_purchase", "ok", "positive_edge", len(bought),
                    )
                    # Voucher inventory alone cannot establish a visible
                    # popup; no OCR, card identity or scoring is inferred.
                    feature_diagnostics.record(
                        "anvil.offer_detected", "skipped", "popup_unverified",
                    )
                elif voucher_counts is None:
                    feature_diagnostics.record(
                        "anvil.voucher_purchase", "skipped", "source_unavailable",
                    )
                else:
                    feature_diagnostics.record(
                        "anvil.voucher_purchase", "skipped", "no_edge",
                    )
                state.anvil_voucher_last_purchase = bought
                if bought:
                    state.anvil_voucher_purchase_events += len(bought)
                    state.anvil_voucher_trigger_pending = True
                # Attention window + tier hint only; never an offer.
                watch, hint = anvil_popup.attention(state.anvil_prev_counts, voucher_counts)
                if watch:
                    state.anvil_window_until = now + anvil_popup.ANVIL_WINDOW_S
                    if hint is not None:
                        state.anvil_voucher_tier = hint
                state.anvil_prev_counts = (
                    dict(voucher_counts) if isinstance(voucher_counts, dict) else None)
                _record_items_outside_pool(state, raw, deps.static_data)
                # -- Scan window management --
                #
                # Augment offers may appear when the first eligible
                # level is reached or after a respawn. Use only the
                # observed local level/death state; no hidden data.
                #
                # Track death transitions
                previous_level = state.last_known_level
                just_respawned = (
                    state.was_dead and not snapshot.is_dead
                )
                state.was_dead = snapshot.is_dead
                state.last_known_level = current_level

                # Every threshold creates one due offer, even without OCR.
                prior_count = len(state.offer_ledger.offers)
                if prior_count and current_level >= 0:
                    previous_due = state.offer_ledger.offers[-1]
                    if (prior_count < len(AUGMENT_PICK_LEVELS_SORTED)
                            and current_level >= AUGMENT_PICK_LEVELS_SORTED[prior_count]):
                        state.offer_ledger.on_titles_unverified()
                state.offer_ledger.on_level(current_level)
                if len(state.offer_ledger.offers) != prior_count:
                    state.offer_epoch = max(
                        state.offer_epoch + 1,
                        state.offer_ledger.offers[-1].epoch + 1,
                    )
                    state.offer_ledger.set_current_epoch(state.offer_epoch)
                    emit_f0_trace("augment", "offer", "unknown",
                                  "new_offer_due", source="lcda",
                                  epoch=state.offer_epoch)
                    # A later offer must not inherit OCR candidates from its
                    # predecessor. Do not change first-offer recovery semantics.
                    if prior_count:
                        # Retain only the previous *complete* identity. It
                        # can be re-read after a temporal reset while the old
                        # offer is still physically visible.
                        previous = state.ocr_slot_choices
                        if not previous or not all(isinstance(previous.get(slot), str)
                                                   and previous[slot] for slot in SLOTS):
                            old_offer = state.offer_ledger.offers[prior_count - 1]
                            previous = {slot: old_offer.slots[slot].augment_id
                                        for slot in SLOTS}
                        state._prior_due_triple = (
                            tuple(previous[slot] for slot in SLOTS)
                            if previous and all(isinstance(previous.get(slot), str)
                                                and previous[slot] for slot in SLOTS)
                            else None
                        )
                        # A newly due offer must never inherit title identities
                        # or scoring candidates from the preceding offer, even if
                        # its scan window is still open awaiting manual confirmation.
                        # Keep the old unconfirmed OfferLedger entry intact.
                        state.augment_choices.clear()
                        state.ocr_last_detected.clear()
                        state.ocr_slot_choices = None
                        state.ocr_unreadable_ticks = 0
                        state.ocr_stale = False
                        state.ocr_stale_since_epoch = None
                        state.set_ocr_phase(
                            "verifying" if state.ocr_enabled else "disabled",
                        )
                        state.offer_lifecycle.open()
                        if state.scan_window_open:
                            # No new scan-open edge below: reset the old C3 hashes
                            # now so the new epoch must gather fresh physical reads.
                            state.scan_window_level = current_level
                            deps.screen_watcher.reset()
                        # When the scan was closed, the normal open edge below
                        # performs the same reset exactly once.
                # Open when a new pick level is reached OR on respawn.
                expected = expected_augments_for_level(current_level)
                have = len(_confirmed_augment_ids(state))

                if (
                    should_open_augment_scan(
                        current_level, previous_level, have, just_respawned
                    )
                    and not state.scan_window_open
                    and not state.awaiting_stat_delta
                    and not state.confirmation_pending
                ):
                    state.scan_window_open = True
                    state.scan_window_level = current_level
                    if len(state.offer_ledger.offers) == prior_count:
                        state.offer_epoch += 1
                        if state.offer_ledger.offers:
                            state.offer_ledger.set_current_epoch(state.offer_epoch)
                    # Log the *final* epoch after any respawn-generation bump.
                    emit_f0_trace("augment", "offer", "unknown",
                                  "scan_level_due", source="lcda",
                                  epoch=state.offer_epoch)
                    state.offer_lifecycle.open()
                    event_log.emit(
                        "ocr_window", state="opened", reason="level_due",
                        level=current_level,
                    )
                    state.awaiting_stat_delta = False
                    state.delta_wait_ticks = 0
                    state.stat_snapshot_before = dict(
                        snapshot.champion_stats
                    )
                    state.stat_snapshot_level_before = current_level
                    observed_items = getattr(snapshot, "purchased_items", None)
                    state.stat_snapshot_items_before = (
                        tuple(str(item) for item in observed_items)
                        if isinstance(observed_items, (list, tuple))
                        else None
                    )
                    deps.screen_watcher.reset()
                    logger.info(
                        "Augment pick window OPENED at eligible level "
                        "(level %d, have %d/%d augments)",
                        current_level, have, expected,
                    )

                # -- Stat delta detection --
                # Stat matching only follows an OCR disappearance signal.
                # Passive level-ups, purchases and death/respawn stat changes
                # are not evidence that the player chose an augment.
                if state.awaiting_stat_delta:
                    state.delta_wait_ticks += 1
                    if state.delta_wait_ticks >= 2:
                        match_confirmation_due = True
                        state.awaiting_stat_delta = False
                        state.delta_wait_ticks = 0

            # Confirmation acquires its own short lock for a consistent offer
            # snapshot. The injected matcher and its transport run unlocked.
            if match_confirmation_due:
                await deps.try_stat_delta_match(snapshot)

            # -- Auto OCR (only while scan window is open) --
            # A missing/disabled OCR dependency must invalidate current
            # presence instead of freezing the previous confirmed cards.
            # Only watcher.check() performs blocking screen capture.
            scan_due = state.scan_window_open and not state.awaiting_stat_delta
            ready = state.ocr_enabled and deps.ocr_available() if scan_due else False
            if scan_due and not ready:
                missing_message = None
                async with state.lock:
                    if state.offer_state != "suspended" or not state.ocr_stale:
                        state.offer_lifecycle.observe("unavailable")
                        state.set_ocr_phase(
                            "disabled" if not state.ocr_enabled else "ocr_missing"
                        )
                        # Disabling OCR with an open offer invalidates previous
                        # advice, but cannot constitute positive recovery.
                        if not state.ocr_stale:
                            state.ocr_stale_since_epoch = state.offer_epoch
                        state.ocr_stale = True
                        missing_message = json.dumps({
                            "type": "ocr_result", "status": "unavailable",
                            "phase": state.ocr_phase,
                            "foreground": state.ocr_foreground,
                            "stale": state.ocr_stale, "offer_state": state.offer_state,
                            "offer_epoch": state.offer_epoch,
                            "match_id": state.match_id,
                        })
                if missing_message is not None:
                    deps.screen_watcher.reset()
                    await deps.broadcast(missing_message)
            if scan_due and ready:
                try:
                    # A user decision or a settings toggle may happen while
                    # the blocking OCR worker is still reading this frame.
                    # Never apply a result to a different offer generation.
                    observed_epoch = state.offer_epoch
                    observed_match = state.match_id
                    observation = await deps.to_thread(deps.run_watcher_check)
                    action, ids, detected = observation
                    reverified = bool(getattr(observation, "reverified", False))
                    foreground = getattr(observation, "foreground", "other")
                    ocr_message = None
                    async with state.lock:
                        if (
                            state.offer_epoch != observed_epoch
                            or state.match_id != observed_match
                            or not state.scan_window_open
                            or not state.ocr_enabled
                            or state.awaiting_stat_delta
                        ):
                            action = "superseded"
                            emit_f0_trace("augment", "epoch", "stale",
                                          "epoch_superseded", source="ledger",
                                          epoch=state.offer_epoch)
                        if (action == "detected" and detected
                                and state._prior_due_triple is not None):
                            candidate_slots = _slots_from_detected(detected)
                            if (candidate_slots is None or
                                    not state.accept_new_due_slot_identity(candidate_slots)):
                                # An old C3-verified triple can be seen again
                                # after reset. Suppress its entire publication.
                                action, ids, detected = "transition", [], None
                        previous_phase = state.ocr_phase
                        previous_stale = state.ocr_stale
                        if action != "superseded":
                            # A verified old triple was downgraded to a
                            # transition. The original watcher observation
                            # still says detected and must not reopen UI.
                            new_phase = (
                                "verifying" if action == "transition"
                                and observation[0] == "detected"
                                else _phase_for_observation(state, observation)
                            )
                            state.set_ocr_phase(
                                new_phase, reverified=bool(
                                    action == "detected" and detected and reverified
                                ),
                            )
                            state.ocr_foreground = (
                                foreground if foreground in ("league", "self", "other")
                                else "other"
                            )
                        if action == "detected" and detected:
                            verified_slots = _slots_from_detected(detected)
                            # Physical identity changes can be rerolls, but
                            # F0 never asserts the user's actual reroll action.
                            # Previous IDs are not persisted in diagnostics.
                            previous_slots = state.ocr_slot_choices
                            if previous_slots is not None and verified_slots is not None:
                                for slot in ("left", "centre", "right"):
                                    if previous_slots.get(slot) != verified_slots.get(slot):
                                        emit_f0_trace(
                                            "augment", "matching", "unknown",
                                            "slot_identity_changed", source="ocr",
                                            slot=slot, epoch=state.offer_epoch,
                                        )
                            if ((not state.ocr_stale or reverified)
                                    and verified_slots is not None
                                    and state.offer_ledger.offers
                                    and any(verified_slots.values())):
                                try:
                                    newest = state.offer_ledger.offers[-1]
                                    _ledger_verified_titles(
                                        state.offer_ledger, verified_slots, newest.epoch,
                                    )
                                except LedgerError:
                                    pass  # no inferred/unsafe confirmation
                            state.offer_lifecycle.observe(
                                "detected", identified=sum(
                                    isinstance(row.get("id"), str) for row in detected
                                ),
                            )
                            state.augment_choices.clear()
                            state.augment_choices.extend(ids)
                            state.ocr_last_detected.clear()
                            state.ocr_last_detected.extend(ids)
                            state.ocr_slot_choices = _slots_from_detected(detected)
                            logger.info("OCR detected augments: %s", detected)
                            ocr_msg = json.dumps({
                                "type": "ocr_result",
                                "status": "detected", "stale": state.ocr_stale,
                                "offer_state": state.offer_state,
                                "detected": detected,
                                "augment_choices": list(state.augment_choices),
                                "offer_epoch": state.offer_epoch,
                                "match_id": state.match_id,
                            })
                            ocr_message = ocr_msg

                        elif action in ("not_focused", "occluded", "capture_unavailable", "unavailable"):
                            state.offer_ledger.on_titles_unverified()
                            # C4 lifecycle accepts unavailable, not A3 capture reasons.
                            state.offer_lifecycle.observe(
                                "unavailable" if action in ("occluded", "capture_unavailable")
                                else action
                            )
                            ocr_message = json.dumps({
                                "type": "ocr_result", "status": action,
                                "offer_state": state.offer_state,
                                "stale": state.ocr_stale,
                                "augment_choices": list(state.augment_choices),
                                "offer_epoch": state.offer_epoch,
                                "match_id": state.match_id,
                            })
                        elif action == "transition":
                            state.offer_ledger.on_titles_unverified()
                            # The current focused frame changed, but C3 has not
                            # verified all physical slots yet. Keep historical
                            # names for diagnostics only, never current advice.
                            state.offer_lifecycle.observe("transition")
                            ocr_message = json.dumps({
                                "type": "ocr_result", "status": "transition",
                                "offer_state": state.offer_state,
                                "stale": state.ocr_stale,
                                "augment_choices": list(state.augment_choices),
                                "offer_epoch": state.offer_epoch,
                                "match_id": state.match_id,
                            })
                        elif action == "disappeared":
                            # Compatibility with a separately VERIFIED negative
                            # signal. The C3 watcher never emits this from blank
                            # titles or dialogue/animation/focus changes.
                            # Never infer a chosen card from this action.
                            state.offer_ledger.on_titles_unverified()
                            state.offer_lifecycle.observe(
                                "disappeared", verified_absence=True,
                            )
                            state.set_ocr_phase("no_offer", offer_closed=True)
                            logger.info("Verified offer gone — confirmation pending")
                            state.scan_window_open = False
                            state.offer_epoch += 1
                            emit_f0_trace("augment", "epoch", "unknown",
                                          "offer_disappeared", source="ledger",
                                          epoch=state.offer_epoch)
                            state.confirmation_pending = True
                            state.awaiting_stat_delta = True
                            state.delta_wait_ticks = 0
                            event_log.emit(
                                "ocr_window", state="closed",
                                reason="offer_disappeared",
                                level=state.scan_window_level,
                            )
                            ocr_message = json.dumps({
                                "type": "ocr_result", "status": "disappeared",
                                "offer_state": state.offer_state,
                                "stale": False,
                                "augment_choices": list(state.augment_choices),
                                "offer_epoch": state.offer_epoch,
                                "match_id": state.match_id,
                            })
                        elif action in ("no_augments", "unchanged"):
                            if not getattr(observation, "has_current", False):
                                state.offer_ledger.on_titles_unverified()
                            state.offer_lifecycle.observe(action)
                        if (ocr_message is None and action != "superseded"
                                and (state.ocr_phase != previous_phase
                                     or state.ocr_stale != previous_stale)):
                            ocr_message = json.dumps({
                                "type": "ocr_result", "status": action,
                                "offer_state": state.offer_state,
                                "offer_epoch": state.offer_epoch,
                                "match_id": state.match_id,
                            })
                        if ocr_message is not None:
                            payload = json.loads(ocr_message)
                            payload["phase"] = state.ocr_phase
                            payload["foreground"] = state.ocr_foreground
                            payload["reverified"] = bool(
                                action == "detected" and detected and reverified
                            )
                            payload["stale"] = state.ocr_stale
                            payload["stale_since_epoch"] = state.ocr_stale_since_epoch
                            ocr_message = json.dumps(payload)
                    if ocr_message is not None:
                        await deps.broadcast(ocr_message)

                except Exception as e:
                    logger.warning("OCR watcher error: %s", e, exc_info=True)

            await _anvil_popup_tick(state, deps, now)

            # Inject overlay augment state
            snapshot.anvil_offer_ids = (
                [s.id for s in state.anvil_offer.shards] if state.anvil_offer else []
            )
            snapshot.augment_choices = list(state.augment_choices)
            snapshot.chosen_augments = _confirmed_augment_ids(state)
            snapshot.build_style = state.build_style

            result = state.pipeline.run(snapshot) if state.pipeline else None
            if result:
                update = deps.serialize_result(result, deps.static_data, snapshot)
                if isinstance(update, dict):
                    update = {**update, "ocr_stale": state.ocr_stale,
                              "ocr_phase": state.ocr_phase,
                              "ocr_foreground": state.ocr_foreground,
                              "ocr_stale_since_epoch": state.ocr_stale_since_epoch,
                              "ocr_slots": state.ocr_slot_choices,
                              "offer_state": state.offer_state,
                              "offer_epoch": state.offer_epoch,
                              "offers": state.offer_ledger.payload(),
                              "anvil_offer": _anvil_offer_payload(state, result)}
                    if state.match_id:
                        update["match_id"] = state.match_id
                await deps.broadcast(json.dumps(update))
            if has_gameflow:
                status = (
                    "champion_unresolved"
                    if state.pipeline is not None and result is None
                    else "in_game"
                )
                await deps.broadcast(_status_message(state, status))
        else:
            # LCDA interruption cannot masquerade as zero voucher stacks.
            # Reconnect requires a fresh two-read baseline before an edge.
            async with state.lock:
                state.anvil_voucher_observer.reset()
                state.anvil_voucher_last_purchase = ()
                state.anvil_voucher_trigger_pending = False
            # A single LCDA error is never an end-of-match signal.
            active_phases = ("GameStart", "InProgress", "Reconnect")
            if state.had_game_last_tick:
                async with state.lock:
                    enough_misses = _register_lcda_miss(state, now)
                if enough_misses and phase not in active_phases:
                    async with state.lock:
                        _finish_match(state, now)
                    await deps.broadcast(json.dumps({"type": "game_ended"}))
                    if has_gameflow:
                        await deps.broadcast(_status_message(state, "post_game"))
                    return
                if phase != "ChampSelect":
                    if has_gameflow:
                        await deps.broadcast(_status_message(state, "live_data_unavailable"))
                    return

            if phase == "ChampSelect" or not has_gameflow:
                draft = await deps.to_thread(deps.read_champ_select_payload)
                if phase == "ChampSelect" or draft is not None:
                    _record_match_phase(state, "champ_select")
                    async with state.lock:
                        state.reset()
                        state.match_id = None
                        state._last_game_time = None
                        state._last_champion_id = None
                        state._last_player_key = None
                        state.lcda_misses = 0
                        state.first_lcda_miss_at = None
                        state.had_game_last_tick = False
                        state.post_game = False
                    if has_gameflow:
                        await deps.broadcast(_status_message(state, "champ_select"))
                    await deps.broadcast(json.dumps(draft or {
                        "type": "champ_select", "candidates": [],
                        "current_status": "unresolved",
                        "current_champion_id": None,
                        "revision": next(_champ_select_revisions),
                    }))
                    return

            if state.post_game:
                if phase in ("None", "Lobby", "Matchmaking", "ReadyCheck", "WaitingForGame") or not has_gameflow:
                    async with state.lock:
                        state.post_game = False
                    await deps.broadcast(json.dumps({"type": "no_game"}))
                    if has_gameflow:
                        await deps.broadcast(_status_message(state, "client_idle"))
                elif has_gameflow:
                    await deps.broadcast(_status_message(state, "post_game"))
                return

            if has_gameflow:
                if phase in active_phases:
                    await deps.broadcast(_status_message(state, "loading"))
                elif phase in end_phases:
                    await deps.broadcast(_status_message(state, "post_game"))
                elif phase in ("None", "Lobby", "Matchmaking", "ReadyCheck", "WaitingForGame"):
                    async with state.lock:
                        state.reset()
                    await deps.broadcast(json.dumps({"type": "no_game"}))
                    await deps.broadcast(_status_message(state, "client_idle"))
                else:
                    # Missing/unknown LCU phase never proves the game ended.
                    await deps.broadcast(_status_message(state, "live_data_unavailable"))
            else:
                async with state.lock:
                    state.reset()
                _record_match_phase(state, "no_game")
                await deps.broadcast(json.dumps({"type": "no_game"}))


async def _poll_game_loop(interval: float | None = None):
    """Run the existing live polling cadence, with injectable single ticks."""
    if interval is None:
        try:
            from backend.config import config
            interval = config.get("poll_interval", 2.0)
        except Exception:
            interval = 2.0
    logger.info("Poll loop started (interval=%.1fs)", interval)
    deps = _poll_dependencies()
    while True:
        try:
            await poll_tick(game_state, deps, asyncio.get_running_loop().time())
        except Exception as e:
            logger.error("Poll loop error: %s", e, exc_info=True)
        await asyncio.sleep(interval)

def _queue_ws_message(
    state: GameState,
    client: WebSocket,
    message: str,
    delivered: asyncio.Future[None] | None = None,
) -> None:
    """Enqueue a socket message without awaiting network I/O or game locks."""
    if client not in state.ws_clients:
        if delivered is not None and not delivered.done():
            delivered.set_exception(ConnectionError("WebSocket disconnected"))
        return
    queue = state.ws_send_queues.get(client)
    if queue is None:
        queue = asyncio.Queue(maxsize=32)
        state.ws_send_queues[client] = queue
    if queue.full():
        _, displaced = queue.get_nowait()
        if displaced is not None and not displaced.done():
            displaced.set_exception(ConnectionError("WebSocket send queue overflow"))
        queue.task_done()
    queue.put_nowait((message, delivered))
    task = state.ws_send_tasks.get(client)
    if task is None or task.done():
        state.ws_send_tasks[client] = asyncio.create_task(
            _drain_ws_client(state, client, queue)
        )


async def _send_ws_message(client: WebSocket, message: str) -> None:
    """Preserve ACK/error delivery semantics using the ordered sender.

    Only this requesting WebSocket handler waits for its own completion.
    Polling and broadcasts remain non-blocking and outside GameState.lock.
    """
    diagnostics.record_ws_message("outbound", message)
    delivered = asyncio.get_running_loop().create_future()
    _queue_ws_message(game_state, client, message, delivered)
    await asyncio.wait_for(delivered, timeout=4.0)


async def _broadcast(message: str) -> None:
    """Enqueue ordered messages; never await a socket or hold the state lock.

    A stalled client has an independent bounded queue. Once full, its oldest
    pending message is replaced by newer state rather than blocking polling.
    """
    diagnostics.record_ws_message("outbound", message)
    state = game_state
    for client in tuple(state.ws_clients):
        _queue_ws_message(state, client, message)


async def _drain_ws_client(
    state: GameState,
    client: WebSocket,
    queue: asyncio.Queue[tuple[str, asyncio.Future[None] | None]],
) -> None:
    """One sender per client, with optional delivery receipts for direct ACKs."""
    try:
        while client in state.ws_clients:
            # Drain the available batch then exit. An idle sender must not
            # leave a task waiting on queue.get() across ASGI shutdown/tests.
            try:
                message, delivered = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            try:
                await asyncio.wait_for(client.send_text(message), timeout=3.0)
                if delivered is not None and not delivered.done():
                    delivered.set_result(None)
            except asyncio.CancelledError:
                if delivered is not None and not delivered.done():
                    delivered.cancel()
                raise
            except Exception as exc:
                if delivered is not None and not delivered.done():
                    delivered.set_exception(exc)
                state.ws_clients.discard(client)
                break
            finally:
                queue.task_done()
    finally:
        while not queue.empty():
            _, delivered = queue.get_nowait()
            if delivered is not None and not delivered.done():
                delivered.set_exception(ConnectionError("WebSocket sender stopped"))
            queue.task_done()
        if state.ws_send_tasks.get(client) is asyncio.current_task():
            state.ws_send_tasks.pop(client, None)
            state.ws_send_queues.pop(client, None)


async def _try_stat_delta_match(snapshot: GameSnapshot) -> None:
    """Prepare a guarded manual-confirmation hint under lock; send after it."""
    async with game_state.lock:
        if not game_state.confirmation_pending:
            return

        best_guess_id: str | None = None
        confidence = 0.0
        after_items = getattr(snapshot, "purchased_items", None)
        observed_items = game_state.stat_snapshot_items_before

        baseline_is_comparable = (
            bool(game_state.stat_snapshot_before)
            and game_state.stat_snapshot_level_before is not None
            and getattr(snapshot, "level", None) == game_state.stat_snapshot_level_before
            and observed_items is not None
            and isinstance(after_items, (list, tuple))
            and tuple(str(item) for item in after_items) == observed_items
        )

        if baseline_is_comparable and game_state.augment_choices:
            # Never fabricate a candidate from the catalog.
            candidates = [
                static_data.get_augment(aid)
                for aid in game_state.augment_choices
            ]
            candidates = [aug for aug in candidates if aug is not None]
            if candidates:
                matched, confidence = match_augment(
                    game_state.stat_snapshot_before,
                    dict(snapshot.champion_stats),
                    candidates,
                )
                if (
                    matched is not None
                    and matched.id in game_state.augment_choices
                    and confidence >= 0.6
                ):
                    best_guess_id = matched.id

        event_log.emit(
            "augment_inference",
            result="ambiguous" if best_guess_id else "none",
            confidence=max(0.0, min(1.0, float(confidence))),
        )
        message = _augment_confirm_message(best_guess_id)
    await _broadcast(message)


def _augment_confirm_message(best_guess_id: str | None) -> str:
    """A hint is never a pick; include the exact offer and epoch for UI."""
    target = next(
        (offer for offer in game_state.offer_ledger.offers
         if offer.state == "awaiting_confirm"),
        None,
    )
    if target is None:
        target = next(
            (offer for offer in reversed(game_state.offer_ledger.offers)
             if offer.state == "visible"),
            None,
        )
    candidates = []
    if target is not None:
        for identity in target.slots.values():
            if identity.augment_id is None:
                continue
            aug = static_data.get_augment(identity.augment_id)
            if aug:
                candidates.append({
                    "id": aug.id, "name": aug.name, "tier": aug.tier.value,
                })
    return json.dumps({
        "type": "augment_confirm",
        "offer_id": target.offer_id if target is not None else None,
        "epoch": target.epoch if target is not None else None,
        "candidates": candidates,
        "best_guess_id": best_guess_id if any(
            entry["id"] == best_guess_id for entry in candidates
        ) else None,
    })


async def _send_augment_confirm(best_guess_id: str | None) -> None:
    """Compatibility entrypoint for manual-confirmation WS messages."""
    async with game_state.lock:
        message = _augment_confirm_message(best_guess_id)
    await _broadcast(message)


# -- Helpers --


def _parse_snapshot(data: dict) -> GameSnapshot:
    return GameSnapshot(
        game_id=data.get("game_id", ""),
        phase=GamePhase(data.get("phase", "in_game")),
        champion_id=data.get("champion_id", ""),
        augment_choices=data.get("augment_choices", []),
        chosen_augments=data.get("chosen_augments", []),
        purchased_items=data.get("purchased_items", []),
        current_gold=data.get("current_gold", 0),
        game_time=data.get("game_time", 0),
        enemy_champion_ids=data.get("enemy_champion_ids", []),
        rerolls_remaining=data.get("rerolls_remaining", 0),
        build_style=data.get("build_style", "Balanced"),
    )


def _resolve_item_name(item_id: str, sd: StaticData) -> str:
    return sd.get_item_name(item_id)


def _resolve_champion_name(champ_id: str, sd: StaticData) -> str:
    champ = sd.get_champion(champ_id)
    return champ.name if champ else champ_id


def _strip_augment_win_stats(value):
    """Remove forbidden augment win-evidence keys at the output boundary.

    Explicit serializer fields remain primary; this also guards future nested
    component/provenance data for HTTP/WS consumers. It does not authorize
    derived scores or dynamic recommendations under Riot policy.
    """
    if isinstance(value, dict):
        return {
            key: _strip_augment_win_stats(child)
            for key, child in value.items()
            if not (
                isinstance(key, str)
                and key.lower().replace("_", "").replace("-", "")
                in {"winrate", "wins", "wr"}
            )
        }
    if isinstance(value, list):
        return [_strip_augment_win_stats(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_strip_augment_win_stats(item) for item in value)
    return value


def _serialize_result(
    result: PipelineResult, sd: StaticData, snapshot: GameSnapshot | None = None,
) -> dict:
    out: dict = {
        "type": "update",
        "phase": result.phase.value,
        "suggest_reroll": result.suggest_reroll,
        "reroll_reason": result.reroll_reason,
        "enemy_analysis": result.enemy_analysis,
        "ally_analysis": result.ally_analysis,
        "anvil_recommendations": result.anvil_recommendations,
        "recommendations": [
            {
                "augment_id": r.augment_id,
                "augment_name": r.augment_name,
                "score": round(r.score, 1) if r.score is not None else None,
                "confidence": r.confidence,
                "sample_size": r.sample_size,
                "components": r.components,
                "method": "composite_v1" if r.score is not None else "not_rated",
                "modelled": r.modelled,
                "provenance": r.provenance,
                "label": list(r.label),
                "core_items": r.core_items,
                "core_items_names": [_resolve_item_name(i, sd) for i in r.core_items],
                "explanation": r.explanation,
            }
            for r in result.recommendations
        ],
        "build_state": {
            "champion_id": result.build_state.champion_id,
            "champion_name": _resolve_champion_name(result.build_state.champion_id, sd),
            "chosen_augments": result.build_state.chosen_augments,
            "purchased_items": result.build_state.purchased_items,
            "owned_build_ids": result.build_state.owned_build_ids,
            "owned_build_names": result.build_state.owned_build_names,
            "anvil_stat_priorities": result.build_state.anvil_stat_priorities,
            "purchased_items_names": [
                _resolve_item_name(i, sd) for i in result.build_state.purchased_items
            ],
            "next_item_id": result.build_state.next_item_id,
            "next_item_name": (
                _resolve_item_name(result.build_state.next_item_id, sd)
                if result.build_state.next_item_id else None
            ),
            "next_item_gold_needed": result.build_state.next_item_gold_needed,
            "gold_to_next": result.build_state.gold_to_next,
            "slot_blocked": result.build_state.slot_blocked,
            "full_build": result.build_state.full_build,
            "full_build_names": [
                _resolve_item_name(i, sd) for i in result.build_state.full_build
            ],
            "alternatives": {
                style: [
                    {"id": item_id, "name": _resolve_item_name(item_id, sd)}
                    for item_id in item_ids
                ]
                for style, item_ids in result.build_state.alternatives.items()
            },
            "reasons": result.build_state.reasons,
            "selected_style": result.build_state.selected_style,
            "data_version": result.build_state.data_version,
            "build_unavailable_reason": result.build_state.build_unavailable_reason,
            "boot_replacement": (
                {
                    "sell_item_id": result.build_state.boot_replacement.sell_item_id,
                    "sell_item_name": _resolve_item_name(
                        result.build_state.boot_replacement.sell_item_id, sd
                    ),
                    "buy_item_id": result.build_state.boot_replacement.buy_item_id,
                    "buy_item_name": _resolve_item_name(
                        result.build_state.boot_replacement.buy_item_id, sd
                    ),
                    "buy_cost": result.build_state.boot_replacement.buy_cost,
                    "listed_ms_change": result.build_state.boot_replacement.listed_ms_change,
                    "reason": result.build_state.boot_replacement.reason,
                } if result.build_state.boot_replacement else None
            ),
        },
    }

    if snapshot:
        # D2 read-only display cue; no shop-open inference or gameplay action.
        out["is_dead"] = bool(getattr(snapshot, "is_dead", False))
        out["game_time"] = snapshot.game_time
        out["current_gold"] = snapshot.current_gold
        out["level"] = snapshot.level
        out["scan_window_open"] = game_state.scan_window_open
        out["augment_state"] = game_state.get_augment_state()
        out["offers"] = game_state.offer_ledger.payload()
        out["enemies"] = [
            {
                "id": eid,
                "name": _resolve_champion_name(eid, sd),
                "cc_sec": _get_enemy_cc(eid, sd),
            }
            for eid in snapshot.enemy_champion_ids
        ]

    out["mayhem_build"] = _mayhem_build_payload(
        result.build_state.champion_id, result.build_state.chosen_augments,
        result.build_state.purchased_items, result.enemy_analysis or {},
        result.ally_analysis or {}, sd)
    out["build_state"] = _align_next_with_mayhem_build(
        out["build_state"], out["mayhem_build"], out.get("current_gold"), sd)
    out.update(_augment_tier_payload(
        result.build_state.champion_id,
        _visible_augment_ids(out["recommendations"], out.get("offers")),
        adjust=(_offer_context_adjuster(
            result.build_state.champion_id, result.build_state.chosen_augments,
            out["mayhem_build"], result.enemy_analysis or {}, sd)
            if result.build_state.champion_id else None),
    ))
    return _strip_augment_win_stats(out)


def _get_enemy_cc(champ_id: str, sd: StaticData) -> float:
    champ = sd.get_champion(champ_id)
    if champ and champ.cc_profile:
        return champ.cc_profile.total_hard_cc_sec
    return 0.0
