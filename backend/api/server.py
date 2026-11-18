import asyncio
import json
import sys
import time
from types import SimpleNamespace
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger("aram-oracle")

from backend.static_data.loader import StaticData
from backend.storage.db import init_db, get_champion_record
from backend.static_data.updater import force_refresh
from backend.workflow.pipeline import Pipeline
from backend.collectors.lcda import get_raw_game_data, parse_game_snapshot
from backend.collectors.lcu import read_champ_select
from backend.engine.champion_select import summarize_champion_select
from backend.collectors.screen_ocr import (
    detect_augments, is_available as ocr_available, watcher as screen_watcher,
)
from backend.models import GamePhase, GameSnapshot, PipelineResult
from backend.engine.build_suggester import BUILD_STYLES
from backend import preferences
from backend.engine.augment_detector import has_stats_changed, match_augment
from backend.diagnostics import collector as diagnostics

static_data = StaticData()


# -- Thread-safe game state --


class GameState:
    """Encapsulates all mutable augment/OCR state with an asyncio.Lock.

    Replaces the former module-level globals. All mutations go through
    methods that acquire ``self._lock`` so the poll loop and WS handlers
    never see partial updates.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # Pipeline and connected clients (protected by lock)
        self.pipeline: Pipeline | None = None
        self.ws_clients: set[WebSocket] = set()
        # Augment choices injected by overlay / OCR
        self.augment_choices: list[str] = []
        self.chosen_augments: list[str] = []  # real augments only (max 4)
        self.chosen_stat_anvils: list[str] = []  # stat anvil / voucher picks
        self.build_style: str = "Balanced"  # player preference, survives match resets
        self.overlay_preferences: dict = dict(preferences.DEFAULT_OVERLAY)  # D4a: stored only
        # OCR state
        self.ocr_enabled: bool = True
        self.ocr_last_detected: list[str] = []
        # Augment pick window
        self.last_known_level: int = 0
        self.scan_window_open: bool = False
        self.scan_window_level: int = 0
        self.was_dead: bool = False  # track death transitions
        # Stat delta matching
        self.stat_snapshot_before: dict[str, float] = {}
        self.awaiting_stat_delta: bool = False
        self.delta_wait_ticks: int = 0
        # Post-game detection
        self.had_game_last_tick: bool = False
        self.post_game: bool = False
        self.post_game_time: float = 0.0

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    def reset(self) -> None:
        """Reset all game-specific state (called when no game is detected)."""
        # Clear manually entered picks too. An OCR-less match must not
        # leak augment choices into the next match.
        self.ocr_last_detected.clear()
        self.augment_choices.clear()
        self.chosen_augments.clear()
        self.chosen_stat_anvils.clear()
        screen_watcher.reset()
        self.last_known_level = 0
        self.scan_window_open = False
        self.scan_window_level = 0
        self.was_dead = False
        self.stat_snapshot_before.clear()
        self.awaiting_stat_delta = False
        self.delta_wait_ticks = 0

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
    from backend.storage.history_import import sync_recent_mayhem_games
    return await asyncio.to_thread(sync_recent_mayhem_games)


@app.get("/api/champ-select/status")
def champ_select_status():
    """Local debug endpoint; no account IDs or client secrets are exposed."""
    payload = _read_champ_select_payload()
    return payload if payload else {"type": "champ_select_unavailable"}


@app.get("/api/ocr/status")
def ocr_status():
    return {
        "available": ocr_available(),
        "enabled": game_state.ocr_enabled,
        "last_detected": game_state.ocr_last_detected,
    }


@app.post("/api/ocr/scan")
def ocr_scan():
    """Manually trigger an OCR scan for augment names."""
    if not ocr_available():
        return {"error": "OCR not available — is Tesseract installed?", "detected": []}

    augment_names = {aid: aug.name for aid, aug in static_data._augments.items()}
    augment_names.update({aid: aug.name for aid, aug in static_data._stat_anvils.items()})
    matches = detect_augments(augment_names, save=True)

    if matches:
        ids = [m[0] for m in matches]
        game_state.augment_choices.clear()
        game_state.augment_choices.extend(ids)
        game_state.ocr_last_detected.clear()
        game_state.ocr_last_detected.extend(ids)

    return {
        "detected": [
            {"id": aid, "name": name, "confidence": score}
            for aid, name, score in matches
        ],
        "augment_choices_set": list(game_state.augment_choices),
    }


@app.get("/api/ocr/screenshots")
def list_screenshots():
    """List saved screenshots for debugging OCR region calibration."""
    ss_dir = _APP_ROOT / "data" / "screenshots"
    if not ss_dir.exists():
        return []
    files = sorted(ss_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": f.name, "url": f"/api/ocr/screenshots/{f.name}"} for f in files[:20]]


@app.get("/api/ocr/screenshots/{filename}")
def get_screenshot(filename: str):
    """Serve a saved screenshot."""
    ss_dir = _APP_ROOT / "data" / "screenshots"
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
                await websocket.send_text(json.dumps({"error": "invalid json"}))
                continue

            if not isinstance(msg, dict):
                await websocket.send_text(json.dumps({"error": "expected JSON object"}))
                continue

            msg_type = msg.get("type", "")

            if msg_type == "snapshot":
                data = msg.get("data")
                if not isinstance(data, dict):
                    await websocket.send_text(json.dumps({"error": "snapshot requires 'data' object"}))
                    continue
                snapshot = _parse_snapshot(data)
                result = game_state.pipeline.run(snapshot) if game_state.pipeline else None
                if result:
                    await websocket.send_text(json.dumps(
                        _serialize_result(result, static_data)
                    ))

            elif msg_type == "set_augment_choices":
                augment_ids = msg.get("augment_ids", [])
                if not isinstance(augment_ids, list):
                    await websocket.send_text(json.dumps({"error": "'augment_ids' must be a list"}))
                    continue
                async with game_state.lock:
                    game_state.augment_choices.clear()
                    game_state.augment_choices.extend(augment_ids)
                await websocket.send_text(json.dumps({
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
                    game_state.scan_window_open = False
                    screen_watcher.reset()
                await websocket.send_text(json.dumps({
                    "type": "ack",
                    "action": "choose_augment",
                    "chosen_augments": list(game_state.chosen_augments),
                }))

            elif msg_type == "clear_augments":
                async with game_state.lock:
                    game_state.augment_choices.clear()
                    game_state.chosen_augments.clear()
                    game_state.chosen_stat_anvils.clear()
                await websocket.send_text(json.dumps({
                    "type": "ack",
                    "action": "clear_augments",
                }))

            elif msg_type == "scan_augments":
                # Manual scan — full OCR, resets watcher hash
                ids, detected = await asyncio.to_thread(_run_ocr_scan_manual)
                async with game_state.lock:
                    if ids:
                        game_state.augment_choices.clear()
                        game_state.augment_choices.extend(ids)
                        game_state.ocr_last_detected.clear()
                        game_state.ocr_last_detected.extend(ids)
                        screen_watcher._frozen_hash = None
                    choices_snapshot = list(game_state.augment_choices)
                await websocket.send_text(json.dumps({
                    "type": "ocr_result",
                    "detected": detected,
                    "augment_choices": choices_snapshot,
                }))

            elif msg_type == "set_build_style":
                # Backward-compatible preference action for older overlay clients.
                style = msg.get("style")
                if not isinstance(style, str) or style not in BUILD_STYLES:
                    await websocket.send_text(json.dumps({"error": "invalid build style"}))
                    continue
                async with game_state.lock:
                    try:
                        preferences.save_build_style(style)
                    except OSError:
                        logger.exception("Could not persist WS build style")
                        await websocket.send_text(json.dumps({"error": "could not save build style"}))
                        continue
                    game_state.build_style = style
                await websocket.send_text(json.dumps({
                    "type": "ack", "action": "set_build_style", "style": style,
                }))

            elif msg_type == "toggle_ocr":
                async with game_state.lock:
                    game_state.ocr_enabled = msg.get("enabled", not game_state.ocr_enabled)
                await websocket.send_text(json.dumps({
                    "type": "ack",
                    "action": "toggle_ocr",
                    "enabled": game_state.ocr_enabled,
                }))

            else:
                await websocket.send_text(json.dumps({"error": "unknown message type"}))

    except WebSocketDisconnect:
        pass
    finally:
        async with game_state.lock:
            game_state.ws_clients.discard(websocket)


# -- Polling loop --


def _run_ocr_scan_manual() -> tuple[list[str], list[dict]]:
    """Run a full OCR scan (manual trigger, bypasses hash check).

    Pure function — returns (ids, detected_dicts) without mutating game_state.
    Caller must apply results under the lock.
    """
    augment_names = {aid: aug.name for aid, aug in static_data._augments.items()}
    augment_names.update({aid: aug.name for aid, aug in static_data._stat_anvils.items()})
    matches = detect_augments(augment_names, save=True)

    ids = [m[0] for m in matches] if matches else []
    detected = [
        {"id": aid, "name": name, "confidence": score}
        for aid, name, score in matches
    ]
    return ids, detected


def _run_watcher_check() -> tuple[str, list[str], list[dict] | None]:
    """Run the ScreenWatcher.check() — hash comparison + OCR if changed.

    Pure function — returns (action, ids, detected_dicts) without mutating
    game_state. Caller must apply results under the lock.
    """
    augment_names = {aid: aug.name for aid, aug in static_data._augments.items()}
    augment_names.update({aid: aug.name for aid, aug in static_data._stat_anvils.items()})
    action, matches = screen_watcher.check(augment_names, save=True)

    if action == "detected" and matches:
        ids = [m[0] for m in matches]
        detected = [
            {"id": aid, "name": name, "confidence": score}
            for aid, name, score in matches
        ]
        return (action, ids, detected)

    return (action, [], None)


def _poll_dependencies() -> SimpleNamespace:
    """Capture the live integrations for one polling task.

    Tests inject their own LCDA, LCU, OCR, clock and transport dependencies
    into poll_tick instead of touching the local League client or desktop.
    """
    return SimpleNamespace(
        get_raw_game_data=get_raw_game_data,
        parse_game_snapshot=parse_game_snapshot,
        read_champ_select_payload=_read_champ_select_payload,
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
    """Perform exactly one iteration of the existing game poll state machine.

    No sleep or implicit clock access. The known lifecycle/inference defects
    deliberately remain observable here until the later functional-fix phases.
    """
    clients_count = len(state.ws_clients)
    if clients_count > 0:
        raw = deps.get_raw_game_data()
        if raw:
            snapshot = deps.parse_game_snapshot(raw, GamePhase.IN_GAME)
            current_level = snapshot.level

            async with state.lock:
                state.had_game_last_tick = True
                state.post_game = False
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
                ):
                    state.scan_window_open = True
                    state.scan_window_level = current_level
                    state.awaiting_stat_delta = False
                    state.delta_wait_ticks = 0
                    state.stat_snapshot_before = dict(
                        snapshot.champion_stats
                    )
                    deps.screen_watcher.reset()
                    logger.info(
                        "Augment pick window OPENED at eligible level "
                        "(level %d, have %d/%d augments)",
                        current_level, have, expected,
                    )

                # -- Stat delta detection --
                # Two paths trigger matching:
                # 1. OCR "disappeared" signal (awaiting_stat_delta)
                # 2. Passive stat change detection (no OCR needed)
                if state.awaiting_stat_delta:
                    state.delta_wait_ticks += 1
                    if state.delta_wait_ticks >= 2:
                        await deps.try_stat_delta_match(snapshot)
                        state.awaiting_stat_delta = False
                        state.delta_wait_ticks = 0

                elif state.scan_window_open and not state.awaiting_stat_delta:
                    # Passive detection: stats changed → augment was chosen
                    if (
                        state.stat_snapshot_before
                        and has_stats_changed(
                            state.stat_snapshot_before,
                            dict(snapshot.champion_stats),
                        )
                    ):
                        logger.info(
                            "Stat change detected — augment chosen "
                            "(passive detection, no OCR needed)"
                        )
                        state.awaiting_stat_delta = True
                        state.delta_wait_ticks = 0

                # Close window when player takes damage (left base)
                if (
                    state.scan_window_open
                    and not state.awaiting_stat_delta
                ):
                    if snapshot.health_pct < 0.98:
                        logger.info(
                            "Augment pick window CLOSED (took damage, hp=%.0f%%)",
                            snapshot.health_pct * 100,
                        )
                        # Player took damage without us detecting the choice
                        if state.augment_choices:
                            await deps.send_augment_confirm(None)
                        state.scan_window_open = False

            # -- Auto OCR (only while scan window is open) --
            # Run outside the lock since OCR is blocking I/O
            if (
                state.scan_window_open
                and not state.awaiting_stat_delta
                and state.ocr_enabled
                and deps.ocr_available()
            ):
                try:
                    action, ids, detected = await deps.to_thread(
                        deps.run_watcher_check
                    )
                    async with state.lock:
                        if action == "detected" and detected:
                            state.augment_choices.clear()
                            state.augment_choices.extend(ids)
                            state.ocr_last_detected.clear()
                            state.ocr_last_detected.extend(ids)
                            logger.info("OCR detected augments: %s", detected)
                            ocr_msg = json.dumps({
                                "type": "ocr_result",
                                "detected": detected,
                                "augment_choices": list(state.augment_choices),
                            })
                            await deps.broadcast(ocr_msg)

                        elif action == "disappeared":
                            # Augment UI went away — player made a selection
                            logger.info("Augment UI disappeared — awaiting stat delta")
                            state.awaiting_stat_delta = True
                            state.delta_wait_ticks = 0


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

async def _broadcast(message: str) -> None:
    """Push to WebSocket clients without re-acquiring the game-state lock.

    This coroutine is sometimes called while game_state.lock is held
    (e.g. OCR and augment confirmation). Acquiring it here deadlocked the
    poll loop. All WebSocket registration, removal and broadcasts run on
    the same ASGI event loop; taking a snapshot before the first await
    avoids simultaneous set iteration and mutation.
    """
    diagnostics.record_ws_message("outbound", message)
    clients = tuple(game_state.ws_clients)
    dead: list[WebSocket] = []
    for client in clients:
        try:
            await client.send_text(message)
        except Exception:
            dead.append(client)
    for client in dead:
        game_state.ws_clients.discard(client)

async def _try_stat_delta_match(snapshot: GameSnapshot) -> None:
    """Compare champion stats before/after to identify chosen augment.

    Must be called while holding game_state.lock.
    """
    if not game_state.stat_snapshot_before:
        await _send_augment_confirm(None)
        game_state.scan_window_open = False
        return

    # Build candidate list: prefer OCR-detected choices, fall back to all augments
    if game_state.augment_choices:
        candidates = [
            static_data.get_augment(aid)
            for aid in game_state.augment_choices
        ]
        candidates = [c for c in candidates if c is not None]
    else:
        # No OCR data — match against all augments (wider search)
        candidates = static_data.all_augments()
        logger.info(
            "No OCR augment choices — matching against all %d augments",
            len(candidates),
        )

    if not candidates:
        await _send_augment_confirm(None)
        game_state.scan_window_open = False
        return

    after_stats = dict(snapshot.champion_stats)
    matched, confidence = match_augment(game_state.stat_snapshot_before, after_stats, candidates)

    if matched and confidence >= 0.3:
        # High confidence — auto-confirm
        # Classify by data: if matched ID is in stat_anvils dict, it's a stat pick
        is_stat_anvil = static_data.get_stat_anvil(matched.id) is not None
        if is_stat_anvil:
            logger.info(
                "Auto-detected stat anvil: %s (confidence=%.2f)", matched.name, confidence
            )
            game_state.chosen_stat_anvils.append(matched.id)
        else:
            logger.info(
                "Auto-detected augment: %s (confidence=%.2f)", matched.name, confidence
            )
            game_state.chosen_augments.append(matched.id)
        game_state.augment_choices.clear()
        game_state.ocr_last_detected.clear()
        game_state.scan_window_open = False
        screen_watcher.reset()

        await _broadcast(json.dumps({
            "type": "augment_auto_chosen",
            "augment_id": matched.id,
            "augment_name": matched.name,
            "confidence": round(confidence, 2),
            "augment_state": game_state.get_augment_state(),
        }))
    else:
        # Low confidence — ask user to confirm
        logger.info(
            "Augment match ambiguous (best=%.2f) — requesting user confirmation",
            confidence,
        )
        best_guess_id = matched.id if matched else None
        await _send_augment_confirm(best_guess_id)
        # Keep scan_window_open = True so OCR can detect new choices
        # if the user hasn't confirmed yet. The choose_augment handler
        # will close it when the user manually picks.
        game_state.awaiting_stat_delta = False


async def _send_augment_confirm(best_guess_id: str | None) -> None:
    """Send augment_confirm message to all clients for manual selection."""
    candidates = []
    for aid in game_state.augment_choices:
        aug = static_data.get_augment(aid)
        if aug:
            candidates.append({
                "id": aug.id,
                "name": aug.name,
                "tier": aug.tier.value,
            })

    await _broadcast(json.dumps({
        "type": "augment_confirm",
        "candidates": candidates,
        "best_guess_id": best_guess_id,
    }))


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
                "score": round(r.score, 1),
                "confidence": r.confidence,
                "sample_size": r.sample_size,
                "components": r.components,
                "method": "composite_v1",
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
            "gold_to_next": result.build_state.gold_to_next,
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

    return out


def _get_enemy_cc(champ_id: str, sd: StaticData) -> float:
    champ = sd.get_champion(champ_id)
    if champ and champ.cc_profile:
        return champ.cc_profile.total_hard_cc_sec
    return 0.0
