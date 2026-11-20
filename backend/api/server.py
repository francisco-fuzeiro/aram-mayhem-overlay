import asyncio
import json
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
from backend.storage.db import init_db, get_champion_record
from backend.static_data.updater import force_refresh
from backend.workflow.pipeline import Pipeline
from backend.collectors.lcda import LCDAResult, get_raw_game_data, parse_game_snapshot
from backend.collectors.lcu import read_champ_select, read_gameflow
from backend.engine.champion_select import summarize_champion_select
from backend.collectors import screen_ocr as ocr_capture
from backend.collectors.screen_ocr import (
    detect_augments, is_available as ocr_available, watcher as screen_watcher,
)
from backend.collectors.offer_lifecycle import OfferLifecycle
from backend.models import GamePhase, GameSnapshot, PipelineResult
from backend.engine.build_suggester import BUILD_STYLES
from backend import preferences
from backend.config import config  # explicit opt-in for diagnostic screenshot policy
from backend.engine.augment_detector import match_augment
from backend.diagnostics import collector as diagnostics
from backend.diagnostic_events import events as event_log

static_data = StaticData()


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

    def __new__(cls, ids, detected, *, proven, reverified, foreground):
        obj = super().__new__(cls, (ids, detected))
        obj.proven = bool(proven)
        obj.reverified = bool(reverified)
        obj.foreground = foreground
        return obj


def _manual_scan_parts(value):
    """A legacy untyped result is NEVER capture evidence."""
    ids, detected = value[:2]
    proven = getattr(value, "proven", len(value) == 3 and value[2] is True)
    reverified = getattr(value, "reverified", len(value) == 3 and value[2] is True)
    foreground = getattr(value, "foreground", "other")
    return ids, detected, proven, reverified, foreground





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
        self.build_style: str = "Balanced"  # player preference, survives match resets
        self.overlay_preferences: dict = dict(preferences.DEFAULT_OVERLAY)  # D4a: stored only
        # OCR state
        self.ocr_enabled: bool = True
        self.ocr_last_detected: list[str] = []
        self.ocr_slot_choices: dict[str, str | None] | None = None
        self.ocr_stale: bool = False
        self.ocr_stale_since_epoch: int | None = None
        self.ocr_phase: str = "no_offer"
        self.ocr_foreground: str = "other"
        self.ocr_unreadable_ticks: int = 0
        self.offer_lifecycle = OfferLifecycle()
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
        self.ocr_stale = False
        self.ocr_stale_since_epoch = None
        self.ocr_phase = "no_offer"
        self.ocr_foreground = "other"
        self.ocr_unreadable_ticks = 0
        self.offer_lifecycle.close()
        self.offer_epoch += 1
        self.augment_choices.clear()
        self.chosen_augments.clear()
        self.chosen_stat_anvils.clear()
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
        if watcher is not None:
            watcher.reset()
        if self.scan_window_open:
            self.offer_lifecycle.observe("unavailable")
            self.set_ocr_phase("disabled" if not enabled else "no_game")
            # An OCR toggle invalidates previous advice, not offer identity.
            if not self.ocr_stale:
                self.ocr_stale_since_epoch = self.offer_epoch
            self.ocr_stale = True

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
        if ids != current_ids:
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
            "chosen": len(self.chosen_augments),
            "chosen_augments": list(self.chosen_augments),
            "stat_anvils": len(self.chosen_stat_anvils),
        }


game_state = GameState()

AUGMENT_PICK_LEVELS = {3, 7, 11, 15}
AUGMENT_PICK_LEVELS_SORTED = sorted(AUGMENT_PICK_LEVELS)  # [3, 7, 11, 15]


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
    # Every entrypoint (CLI, desktop overlay, and direct ASGI) needs a DB.
    init_db()
    saved_preferences = preferences.load_preferences()
    game_state.build_style = saved_preferences["build_style"]
    game_state.overlay_preferences = saved_preferences["overlay"]
    static_data.load()
    game_state.pipeline = Pipeline(static_data)

    poll_task = asyncio.create_task(_poll_game_loop())
    yield
    poll_task.cancel()
    try:
        await poll_task
    except asyncio.CancelledError:
        pass
    event_log.stop()


app = FastAPI(lifespan=lifespan)

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


from pydantic import BaseModel, Field


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
    snapshot = read_champ_select()
    if snapshot is None:
        return None
    draft, id_map = snapshot
    return summarize_champion_select(
        draft, id_map, static_data.get_champion,
        record_lookup=get_champion_record,
    )


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
    return payload if payload else {"type": "champ_select_unavailable"}


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
    ids, detected, proven, reverified, foreground = _manual_scan_parts(result)
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
            game_state.offer_lifecycle.observe("transition")
            game_state.set_ocr_phase("verifying")
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
                result = game_state.pipeline.run(snapshot) if game_state.pipeline else None
                if result:
                    await _send_ws_message(websocket, json.dumps(
                        _serialize_result(result, static_data)
                    ))

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
                aug_id = msg.get("augment_id", "")
                async with game_state.lock:
                    # Classify by data: stat anvil IDs go to stat_anvils list
                    is_stat_anvil = static_data.get_stat_anvil(aug_id) is not None
                    if aug_id:
                        if is_stat_anvil and aug_id not in game_state.chosen_stat_anvils:
                            game_state.chosen_stat_anvils.append(aug_id)
                        elif not is_stat_anvil and aug_id not in game_state.chosen_augments:
                            game_state.chosen_augments.append(aug_id)
                    game_state.augment_choices.clear()
                    game_state.ocr_last_detected.clear()
                    game_state.ocr_slot_choices = None
                    if game_state.scan_window_open:
                        event_log.emit("ocr_window", state="closed", reason="manual_choice",
                                       level=game_state.scan_window_level)
                    game_state.scan_window_open = False
                    game_state.offer_lifecycle.close()
                    game_state.offer_epoch += 1
                    game_state.confirmation_pending = False
                    game_state.awaiting_stat_delta = False
                    game_state.delta_wait_ticks = 0
                    game_state.stat_snapshot_before.clear()
                    game_state.stat_snapshot_level_before = None
                    game_state.stat_snapshot_items_before = None
                    screen_watcher.reset()
                    if aug_id:
                        event_log.emit(
                            "augment_confirmation", method="manual",
                            kind="anvil" if is_stat_anvil else "augment",
                        )
                await _send_ws_message(websocket, json.dumps({
                    "type": "ack",
                    "action": "choose_augment",
                    "chosen_augments": list(game_state.chosen_augments),
                }))

            elif msg_type == "clear_augments":
                async with game_state.lock:
                    game_state.augment_choices.clear()
                    game_state.ocr_slot_choices = None
                    game_state.chosen_augments.clear()
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
                # Manual OCR cannot run or publish outside a current pick
                # window. The generation is captured BEFORE async OCR so
                # a completed/changed offer cannot receive late results.
                async with game_state.lock:
                    request_match = game_state.match_id
                    request_epoch = game_state.offer_epoch
                    allowed = (
                        game_state.scan_window_open and game_state.ocr_enabled
                        and not game_state.confirmation_pending
                        and not game_state.awaiting_stat_delta
                    )
                ids, detected = ([], [])
                if allowed:
                    ids, detected = await asyncio.to_thread(_run_ocr_scan_manual)
                async with game_state.lock:
                    applied = allowed and game_state.accept_manual_ocr(
                        ids, detected, match_id=request_match,
                        offer_epoch=request_epoch,
                    )
                    if applied:
                        status = "detected"
                    elif (allowed and game_state.match_id == request_match
                          and game_state.offer_epoch == request_epoch
                          and game_state.scan_window_open
                          and game_state.ocr_enabled):
                        # The watcher may be verifying a changed title.
                        # Never republish historical card identities.
                        game_state.offer_lifecycle.observe("transition")
                        status = "transition"
                    else:
                        status = "superseded"
                    message = {
                        "type": "ocr_result", "status": status,
                        "detected": detected if applied else [],
                        "augment_choices": list(game_state.augment_choices),
                        "offer_state": game_state.offer_state,
                        "offer_epoch": game_state.offer_epoch,
                        "match_id": game_state.match_id,
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
    names = {aid: aug.name for aid, aug in static_data._stat_anvils.items()}
    names.update({aid: aug.name for aid, aug in static_data._augments.items()})
    return names


def _run_ocr_scan_manual() -> _ManualScanEvidence:
    """Use the shared A3/A4 proven watcher; never accept cached unchanged slots.

    Protect the watcher scan and its proof flags under the same RLock: a
    concurrent automatic read cannot change the evidence before it is copied.
    """
    augment_names = _ocr_title_catalog()
    with screen_watcher._lock:
        matches = detect_augments(
            augment_names, save=config.get("ocr_debug_screenshots", False) is True,
        )
        proven = bool(matches) and screen_watcher.last_scan_stage == "titles_detected"
        reverified = bool(proven and screen_watcher._temporal.last_emit_reverified)
        foreground = screen_watcher._last_foreground
    event_log.emit(
        "ocr_recognition", outcome="manual_detected" if proven else "manual_empty",
        count=len(matches or []),
        confidence=float(max((m[2] for m in matches or []), default=0)),
    )
    ids = [m[0] for m in matches] if proven else []
    detected = _slot_detection_payload(matches) if proven else []
    return _ManualScanEvidence(
        ids, detected, proven=proven, reverified=reverified,
        foreground=foreground,
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
    if action == "detected" and (matches or hasattr(matches, "slots")):
        ids = [m[0] for m in matches]
        detected = _slot_detection_payload(matches)
        return _OcrWatcherObservation(action, ids, detected, **metadata)
    return _OcrWatcherObservation(action, [], None, **metadata)


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
        screen_watcher=screen_watcher,
        to_thread=asyncio.to_thread,
        broadcast=_broadcast,
        try_stat_delta_match=_try_stat_delta_match,
        send_augment_confirm=_send_augment_confirm,
        serialize_result=_serialize_result,
        static_data=static_data,
    )


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

                # Open when a new pick level is reached OR on respawn.
                expected = expected_augments_for_level(current_level)
                have = len(state.chosen_augments)

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
                    state.offer_epoch += 1
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
                        state.ocr_stale = True
                        missing_message = json.dumps({
                            "type": "ocr_result", "status": "unavailable",
                            "stale": True, "offer_state": state.offer_state,
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
                    action, ids, detected = await deps.to_thread(
                        deps.run_watcher_check
                    )
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
                        if action == "detected" and detected:
                            state.offer_lifecycle.observe(
                                "detected", identified=sum(
                                    isinstance(row.get("id"), str) for row in detected
                                ),
                            )
                            state.ocr_stale = False
                            state.augment_choices.clear()
                            state.augment_choices.extend(ids)
                            state.ocr_last_detected.clear()
                            state.ocr_last_detected.extend(ids)
                            state.ocr_slot_choices = _slots_from_detected(detected)
                            logger.info("OCR detected augments: %s", detected)
                            ocr_msg = json.dumps({
                                "type": "ocr_result",
                                "status": "detected", "stale": False,
                                "offer_state": state.offer_state,
                                "detected": detected,
                                "augment_choices": list(state.augment_choices),
                                "offer_epoch": state.offer_epoch,
                                "match_id": state.match_id,
                            })
                            ocr_message = ocr_msg

                        elif action in ("not_focused", "occluded", "capture_unavailable", "unavailable"):
                            state.offer_lifecycle.observe(action)
                            state.ocr_stale = True
                            ocr_message = json.dumps({
                                "type": "ocr_result", "status": action,
                                "offer_state": state.offer_state,
                                "stale": True,
                                "augment_choices": list(state.augment_choices),
                                "offer_epoch": state.offer_epoch,
                                "match_id": state.match_id,
                            })
                        elif action == "transition":
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
                            state.offer_lifecycle.observe(
                                "disappeared", verified_absence=True,
                            )
                            logger.info("Verified offer gone — confirmation pending")
                            state.scan_window_open = False
                            state.offer_epoch += 1
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
                            state.offer_lifecycle.observe(action)
                    if ocr_message is not None:
                        await deps.broadcast(ocr_message)

                except Exception as e:
                    logger.warning("OCR watcher error: %s", e, exc_info=True)

            # Inject overlay augment state
            snapshot.augment_choices = list(state.augment_choices)
            snapshot.chosen_augments = list(state.chosen_augments)
            snapshot.build_style = state.build_style

            result = state.pipeline.run(snapshot) if state.pipeline else None
            if result:
                update = deps.serialize_result(result, deps.static_data, snapshot)
                if isinstance(update, dict):
                    update = {**update, "ocr_stale": state.ocr_stale,
                              "ocr_slots": state.ocr_slot_choices,
                              "offer_state": state.offer_state,
                              "offer_epoch": state.offer_epoch}
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
    """Serialize the current offer; caller protects state with its lock."""
    candidates = []
    for aid in game_state.augment_choices:
        aug = static_data.get_augment(aid)
        if aug:
            candidates.append({
                "id": aug.id,
                "name": aug.name,
                "tier": aug.tier.value,
            })
    return json.dumps({
        "type": "augment_confirm",
        "candidates": candidates,
        "best_guess_id": best_guess_id,
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
        out["game_time"] = snapshot.game_time
        out["current_gold"] = snapshot.current_gold
        out["level"] = snapshot.level
        out["scan_window_open"] = game_state.scan_window_open
        out["augment_state"] = game_state.get_augment_state()
        out["enemies"] = [
            {
                "id": eid,
                "name": _resolve_champion_name(eid, sd),
                "cc_sec": _get_enemy_cc(eid, sd),
            }
            for eid in snapshot.enemy_champion_ids
        ]

    return _strip_augment_win_stats(out)


def _get_enemy_cc(champ_id: str, sd: StaticData) -> float:
    champ = sd.get_champion(champ_id)
    if champ and champ.cc_profile:
        return champ.cc_profile.total_hard_cc_sec
    return 0.0
