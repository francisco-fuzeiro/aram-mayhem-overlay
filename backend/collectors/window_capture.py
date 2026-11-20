"""A3: verified, window-only League client capture.

WGC is the preferred source. Screen-copy fallback is allowed only after a
backend startup failure or explicit degraded-backend preference, and only when
both z-order checks prove the card titles unobstructed. Never capture a monitor.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np
from PIL import Image

from backend.collectors.card_title_geometry import title_bands_from_client_rect
from backend.collectors.league_window import LeagueWindow, _NativeWin32, find_league_window

MIN_FRAME_STDDEV = 3.0
FRAME_MAX_AGE_S = 0.25
FRAME_SIZE_TOLERANCE_PX = 2
WGC_MIN_UPDATE_INTERVAL_MS = 100
WGC_INVALID_STREAK_LIMIT = 10

Reason = Literal[
    "ok", "no_window", "minimized", "occluded", "backend_unavailable",
    "invalid_frame", "window_changed", "unsupported_platform",
]
Backend = Literal["wgc", "mss_zorder"]
Foreground = Literal["league", "self", "other"]


@dataclass(frozen=True)
class CaptureProof:
    backend: Backend
    hwnd: int
    client_rect: tuple[int, int, int, int]
    captured_at: float
    foreground: Foreground


@dataclass(frozen=True)
class CaptureResult:
    image: Image.Image | None
    proof: CaptureProof | None
    reason: Reason
    occluder: Literal["self", "other"] | None = None


class FrameSource(Protocol):
    def latest(self) -> tuple[np.ndarray, float] | None: ...
    def close(self) -> None: ...


class WgcFrameSource:
    """Own lazy 2.0.1 WindowsCapture events and copy transient frame buffers."""

    def __init__(self, hwnd: int) -> None:
        from windows_capture import WindowsCapture

        self._lock = threading.Lock()
        self._latest: tuple[np.ndarray, float] | None = None
        self._closed = False
        self._control = None
        capture = WindowsCapture(
            cursor_capture=False, draw_border=False, secondary_window=False,
            minimum_update_interval=WGC_MIN_UPDATE_INTERVAL_MS,
            dirty_region=False, window_hwnd=hwnd,
        )

        @capture.event
        def on_frame_arrived(frame, capture_control):
            with self._lock:
                if not self._closed:
                    # 2.0.1 frame_buffer is a zero-copy view, valid only here.
                    self._latest = (frame.frame_buffer.copy(), time.monotonic())

        @capture.event
        def on_closed():
            with self._lock:
                self._closed = True
                self._latest = None

        self._control = capture.start_free_threaded()

    def latest(self) -> tuple[np.ndarray, float] | None:
        with self._lock:
            if self._closed or self._latest is None:
                return None
            # The stored array is already a callback-owned copy. Readers must
            # not mutate it, so return another copy to isolate concurrent calls.
            return self._latest[0].copy(), self._latest[1]

    def close(self) -> None:
        with self._lock:
            if self._closed and self._control is None:
                return
            self._closed = True
            self._latest = None
            control, self._control = self._control, None
        if control is not None:
            try:
                control.stop()
            except Exception:
                # External capture-control shutdown must never reach the poller.
                pass


_lock = threading.RLock()
_hwnd: int | None = None
_source: FrameSource | None = None
_invalid_streak = 0
_restarted = False
_degraded = False


def reset_capture_state() -> None:
    """Release the persistent per-HWND WGC session (also on match reset)."""
    global _hwnd, _source, _invalid_streak, _restarted, _degraded
    with _lock:
        if _source is not None:
            try:
                _source.close()
            except (OSError, RuntimeError):
                pass
        _hwnd = None
        _source = None
        _invalid_streak = 0
        _restarted = False
        _degraded = False


def _notify(result: CaptureResult) -> CaptureResult:
    from backend.diagnostic_events import events

    events.transition(
        "capture_backend",
        backend=result.proof.backend if result.proof is not None else "none",
    )
    if result.proof is not None:
        events.transition("ocr_foreground", owner=result.proof.foreground)
    if result.occluder:
        events.transition("ocr_occlusion", owner=result.occluder)
    return result


def _failure(reason: Reason, *, occluder=None) -> CaptureResult:
    return _notify(CaptureResult(None, None, reason, occluder))


def _foreground(api, hwnd: int) -> Foreground:
    try:
        active = api.foreground_window()
        if active == hwnd:
            return "league"
        if active and api.process_id(active) == os.getpid():
            return "self"
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return "other"


def _intersects(a: tuple[int, int, int, int],
                b: tuple[int, int, int, int]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def zorder_clear(
    game: LeagueWindow, *, win32,
) -> tuple[bool, Literal["self", "other"] | None]:
    """Include transparent, layered and our own overlay windows; fail closed."""
    bands = title_bands_from_client_rect(game.rect)
    if bands is None:
        return False, "other"
    title_rects = [
        (game.left + x, game.top + y, game.left + x + w, game.top + y + h)
        for (x, y, w, h) in bands.values()
    ]
    try:
        for hwnd in win32.windows_above(game.hwnd):
            if not win32.is_window_visible(hwnd) or win32.is_cloaked(hwnd):
                continue
            rect = win32.window_rect(hwnd)
            if rect is None or len(rect) != 4:
                return False, "other"
            if rect[2] <= rect[0] or rect[3] <= rect[1]:
                continue
            if any(_intersects(rect, band) for band in title_rects):
                owner = "self" if win32.process_id(hwnd) == os.getpid() else "other"
                return False, owner
        return True, None
    except (OSError, ValueError, TypeError, AttributeError):
        return False, "other"


def _mss_grab(rect: tuple[int, int, int, int]) -> Image.Image:
    """Copy exactly the validated League client rectangle, never a display."""
    import mss

    left, top, right, bottom = rect
    with mss.mss() as screen:
        shot = screen.grab({
            "left": left, "top": top,
            "width": right - left, "height": bottom - top,
        })
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def _valid_image(image: Image.Image, game: LeagueWindow) -> bool:
    width, height = game.right - game.left, game.bottom - game.top
    if image.mode != "RGB" or image.size != (width, height):
        return False
    # Only the augment region's variation is relevant, not unrelated HUD.
    from backend.collectors.screen_ocr import get_augment_region

    a, b, c, d = get_augment_region(width, height)
    roi = np.asarray(image)[int(height * b):int(height * d),
                            int(width * a):int(width * c), :]
    if roi.size == 0:
        return False
    return float(max(np.std(roi[:, :, channel]) for channel in range(3))) >= MIN_FRAME_STDDEV


def _frame_client(
    frame: np.ndarray, game: LeagueWindow, api,
) -> Image.Image | None:
    if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8
            or frame.ndim != 3 or frame.shape[2] != 4):
        return None
    try:
        bounds = api.frame_bounds(game.hwnd)
        client_origin = api.client_to_screen(game.hwnd, (0, 0))
        if bounds is None or client_origin is None:
            return None
        fleft, ftop, fright, fbottom = bounds
        if not all(isinstance(value, int) for value in bounds):
            return None
        fw, fh = fright - fleft, fbottom - ftop
        if (abs(frame.shape[1] - fw) > FRAME_SIZE_TOLERANCE_PX
                or abs(frame.shape[0] - fh) > FRAME_SIZE_TOLERANCE_PX):
            return None
        if client_origin != (game.left, game.top):
            return None
        x, y = client_origin[0] - fleft, client_origin[1] - ftop
        w, h = game.right - game.left, game.bottom - game.top
        if x < 0 or y < 0 or x + w > frame.shape[1] or y + h > frame.shape[0]:
            return None
        client = frame[y:y+h, x:x+w]
        if abs(client.shape[1] - w) > FRAME_SIZE_TOLERANCE_PX or abs(client.shape[0] - h) > FRAME_SIZE_TOLERANCE_PX:
            return None
        # WGC provides BGRA. Keep only the verified League client, no alpha.
        return Image.fromarray(client[:, :, [2, 1, 0]].copy(), "RGB")
    except (OSError, ValueError, TypeError, AttributeError, IndexError):
        return None


def _safe_mss(game: LeagueWindow, api, clock) -> CaptureResult:
    clear, owner = zorder_clear(game, win32=api)
    if not clear:
        return _failure("occluded", occluder=owner)
    try:
        img = _mss_grab(game.rect)
    except (OSError, ValueError, RuntimeError, ImportError):
        return _failure("backend_unavailable")
    clear, owner = zorder_clear(game, win32=api)
    if not clear:
        return _failure("occluded", occluder=owner)
    if not _valid_image(img, game):
        return _failure("invalid_frame")
    return CaptureResult(img, CaptureProof(
        "mss_zorder", game.hwnd, game.rect, clock(),
        _foreground(api, game.hwnd),
    ), "ok")


def _wgc(game: LeagueWindow, api, clock, factory) -> CaptureResult:
    global _hwnd, _source, _invalid_streak, _restarted, _degraded
    if _hwnd != game.hwnd:
        reset_capture_state()
        _hwnd = game.hwnd
    if _degraded:
        return CaptureResult(None, None, "backend_unavailable")
    if _source is None:
        try:
            _source = factory(game.hwnd)
        except Exception:
            # Dependency startup errors are the only automatic MSS fallback.
            return CaptureResult(None, None, "backend_unavailable")
    try:
        sample = _source.latest()
    except Exception:
        sample = None
    request_time = clock()
    img = None
    ts = None
    if sample is not None:
        try:
            frame, ts = sample
            if isinstance(ts, (int, float)) and request_time - FRAME_MAX_AGE_S <= ts <= request_time + FRAME_MAX_AGE_S:
                img = _frame_client(frame, game, api)
        except (TypeError, ValueError):
            img = None
    if img is not None and _valid_image(img, game):
        _invalid_streak = 0
        _restarted = False  # A recovered frame ends the degraded-streak episode.
        return CaptureResult(img, CaptureProof(
            "wgc", game.hwnd, game.rect, float(ts),
            _foreground(api, game.hwnd),
        ), "ok")

    _invalid_streak += 1
    if _invalid_streak >= WGC_INVALID_STREAK_LIMIT:
        _invalid_streak = 0
        if _source is not None:
            try:
                _source.close()
            except (OSError, RuntimeError):
                pass
        _source = None
        if _restarted:
            _degraded = True
            from backend.diagnostic_events import events
            events.transition("wgc_degraded", streak=WGC_INVALID_STREAK_LIMIT)
        else:
            _restarted = True
    return CaptureResult(None, None, "invalid_frame")


def capture_league_client(
    game: LeagueWindow, *, win32=None, frame_source_factory=None,
    clock=time.monotonic, platform_name=None,
    allow_screen_copy_fallback: bool = False,
) -> CaptureResult:
    """Return RGB pixels only if the exact source/window/time are proven.

    All public paths use the fresh real executable locator; focus is diagnostic.
    Explicit fallback is honored only for unavailable or degraded WGC sessions.
    """
    if (platform_name or sys.platform) != "win32":
        return _failure("unsupported_platform")
    try:
        api = win32 if win32 is not None else _NativeWin32()
        pre = find_league_window(win32=api, platform_name="win32")
        if pre is None:
            reset_capture_state()
            return _failure("no_window")
        if api.is_minimized(game.hwnd):
            reset_capture_state()
            return _failure("minimized")
        if pre.hwnd != game.hwnd or pre.rect != game.rect:
            reset_capture_state()
            return _failure("window_changed")
        if title_bands_from_client_rect(game.rect) is None:
            return _failure("invalid_frame")
        with _lock:
            result = _wgc(game, api, clock, frame_source_factory or WgcFrameSource)
            # Fail-closed on invalid frames; explicit opt-in only unlocks MSS
            # after the WGC session has become unusable/degraded.
            if result.reason == "backend_unavailable" and (
                not _degraded or allow_screen_copy_fallback
            ):
                result = _safe_mss(game, api, clock)
            post = find_league_window(win32=api, platform_name="win32")
            if (post is None or post.hwnd != game.hwnd or post.rect != game.rect
                    or api.is_minimized(game.hwnd)):
                return _failure("window_changed")
            return _notify(result)
    except (OSError, ValueError, TypeError, AttributeError):
        return _failure("backend_unavailable")
