"""A3 offline regression: only verified League-window pixels may reach OCR."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from PIL import Image

from backend.collectors.league_window import LeagueWindow
from backend.collectors import window_capture as wc


GAME = LeagueWindow(hwnd=17, left=-1920, top=100, right=-960, bottom=640, focused=False)


class FakeFrame:
    def __init__(self, frame=None, ts=10.0):
        self.frame = valid_bgra() if frame is None else frame
        self.ts = ts
        self.closed = 0
        self.calls = 0

    def latest(self):
        self.calls += 1
        return self.frame.copy(), self.ts

    def close(self):
        self.closed += 1


class FakeWin32:
    def __init__(self):
        self.minimized = False
        self.foreground = 99
        self.pids = {17: 1017, 99: 1999}
        self.above = []
        self.rects = {}
        self.hidden = set()
        self.cloaked = set()
        self.offset = (0, 0)

    def is_minimized(self, hwnd):
        return self.minimized

    def foreground_window(self):
        return self.foreground

    def process_id(self, hwnd):
        return self.pids.get(hwnd, 1999)

    def frame_bounds(self, hwnd):
        return GAME.rect

    def client_to_screen(self, hwnd, point):
        return GAME.left + point[0] + self.offset[0], GAME.top + point[1] + self.offset[1]

    def windows_above(self, hwnd):
        return self.above

    def is_window_visible(self, hwnd):
        return hwnd not in self.hidden

    def is_cloaked(self, hwnd):
        return hwnd in self.cloaked

    def window_rect(self, hwnd):
        return self.rects.get(hwnd)


def valid_bgra():
    arr = np.zeros((540, 960, 4), dtype=np.uint8)
    arr[:, :, 3] = 255
    arr[:, :, 0] = np.arange(960, dtype=np.uint8)[None, :]
    arr[:, :, 1] = np.arange(540, dtype=np.uint8)[:, None]
    return arr


@pytest.fixture(autouse=True)
def isolated_session(monkeypatch):
    wc.reset_capture_state()
    monkeypatch.setattr(wc, "find_league_window", lambda **kwargs: GAME)
    yield
    wc.reset_capture_state()


def capture(api=None, factory=None, **kwargs):
    return wc.capture_league_client(
        GAME, win32=api or FakeWin32(),
        frame_source_factory=factory or (lambda hwnd: FakeFrame()),
        clock=lambda: 10.0, platform_name="win32", **kwargs,
    )


def test_wgc_valid_without_focus_and_window_only_source():
    result = capture()
    assert result.reason == "ok" and result.image.size == (960, 540)
    assert result.proof.backend == "wgc"
    assert result.proof.hwnd == 17
    assert result.proof.client_rect == GAME.rect
    assert result.proof.foreground == "other"


@pytest.mark.parametrize("frame,ts", [
    (np.zeros((540, 960, 4), dtype=np.uint8), 10.0),
    (valid_bgra(), 9.69),
    (np.zeros((545, 960, 4), dtype=np.uint8), 10.0),
])
def test_invalid_frame_never_exposes_pixels_or_tries_mss(monkeypatch, frame, ts):
    monkeypatch.setattr(wc, "_mss_grab", lambda rect: pytest.fail("unsafe fallback"))
    result = capture(factory=lambda hwnd: FakeFrame(frame, ts))
    assert result.reason == "invalid_frame" and result.image is None and result.proof is None


def test_window_change_disposes_unverified_frame(monkeypatch):
    calls = iter((GAME, replace(GAME, left=GAME.left + 1)))
    monkeypatch.setattr(wc, "find_league_window", lambda **kwargs: next(calls))
    result = capture()
    assert result.reason == "window_changed" and result.image is None


def test_missing_window_and_unsupported_platform(monkeypatch):
    monkeypatch.setattr(wc, "find_league_window", lambda **kwargs: None)
    assert capture().reason == "no_window"
    assert wc.capture_league_client(GAME, platform_name="linux").reason == "unsupported_platform"


def test_minimized_refuses_any_capture():
    api = FakeWin32()
    api.minimized = True
    assert capture(api=api).reason == "minimized"


def test_wgc_unavailable_and_transparent_layered_foreign_overlay_blocks(monkeypatch):
    api = FakeWin32()
    api.above = [99]  # Transparent and layered windows must not be ignored.
    api.rects[99] = (-1600, 300, -1200, 500)
    monkeypatch.setattr(wc, "_mss_grab", lambda rect: pytest.fail("covered"))
    result = capture(api=api, factory=lambda hwnd: (_ for _ in ()).throw(ImportError()))
    assert result.reason == "occluded" and result.occluder == "other"
    assert result.image is None


def test_unavailable_backend_allows_zorder_proven_client_only_crop(monkeypatch):
    api = FakeWin32()
    api.above = [99]
    api.rects[99] = (-1900, 110, -1800, 180)  # Outside title bands.
    grabbed = []
    def grab(rect):
        grabbed.append(rect)
        return Image.fromarray(valid_bgra()[:, :, :3], "RGB")
    monkeypatch.setattr(wc, "_mss_grab", grab)
    result = capture(api=api, factory=lambda hwnd: (_ for _ in ()).throw(ImportError()))
    assert result.reason == "ok" and result.proof.backend == "mss_zorder"
    assert grabbed == [GAME.rect]


def test_our_overlay_over_titles_blocks_even_with_capture_exclusion(monkeypatch):
    api = FakeWin32()
    api.above = [88]
    api.pids[88] = wc.os.getpid()
    api.rects[88] = (-1600, 300, -1200, 500)
    monkeypatch.setattr(wc, "_mss_grab", lambda rect: pytest.fail("covered"))
    result = capture(api=api, factory=lambda hwnd: (_ for _ in ()).throw(ImportError()))
    assert result.reason == "occluded" and result.occluder == "self"


def test_cloaked_window_does_not_block_safe_fallback(monkeypatch):
    api = FakeWin32()
    api.above = [99]
    api.cloaked.add(99)
    api.rects[99] = (-1600, 300, -1200, 500)
    monkeypatch.setattr(wc, "_mss_grab", lambda rect: Image.fromarray(valid_bgra()[:, :, :3], "RGB"))
    assert capture(api=api, factory=lambda hwnd: (_ for _ in ()).throw(ImportError())).reason == "ok"


def test_second_zorder_check_discards_fallback_image(monkeypatch):
    api = FakeWin32()
    grabs = []
    def grab(rect):
        grabs.append(rect)
        api.above = [99]
        api.rects[99] = (-1600, 300, -1200, 500)
        return Image.fromarray(valid_bgra()[:, :, :3], "RGB")
    monkeypatch.setattr(wc, "_mss_grab", grab)
    result = capture(api=api, factory=lambda hwnd: (_ for _ in ()).throw(ImportError()))
    assert len(grabs) == 1 and result.reason == "occluded" and result.image is None


def test_degraded_wgc_never_automatically_falls_back(monkeypatch):
    monkeypatch.setattr(wc, "_mss_grab", lambda rect: pytest.fail("no auto downgrade"))
    sources = []
    def factory(hwnd):
        source = FakeFrame(np.zeros((540, 960, 4), dtype=np.uint8))
        sources.append(source)
        return source
    for _ in range(25):
        result = capture(factory=factory)
        assert result.image is None
    assert result.reason == "backend_unavailable"
    assert len(sources) == 2 and sources[0].closed >= 1


def test_explicit_degraded_fallback_still_checks_occlusion(monkeypatch):
    source = FakeFrame(np.zeros((540, 960, 4), dtype=np.uint8))
    for _ in range(20):
        capture(factory=lambda hwnd: source)
    monkeypatch.setattr(wc, "_mss_grab", lambda rect: Image.fromarray(valid_bgra()[:, :, :3], "RGB"))
    assert capture(allow_screen_copy_fallback=True).proof.backend == "mss_zorder"

def test_wgc_adapter_copies_transient_frame_and_closes_once(monkeypatch):
    import sys
    from types import SimpleNamespace

    callbacks = {}
    controls = []
    constructor_args = []
    class FakeControl:
        def __init__(self):
            self.calls = 0
        def stop(self):
            self.calls += 1
    class FakeWindowsCapture:
        def __init__(self, **kwargs):
            constructor_args.append(kwargs)
        def event(self, fn):
            callbacks[fn.__name__] = fn
            return fn
        def start_free_threaded(self):
            control = FakeControl()
            controls.append(control)
            return control

    monkeypatch.setitem(sys.modules, "windows_capture",
                        SimpleNamespace(WindowsCapture=FakeWindowsCapture))
    source = wc.WgcFrameSource(17)
    frame = valid_bgra()
    original = frame[20, 30, 0]
    callbacks["on_frame_arrived"](SimpleNamespace(frame_buffer=frame), controls[0])
    frame[20, 30, 0] = original ^ 255
    captured, arrival = source.latest()
    assert captured[20, 30, 0] == original
    assert isinstance(arrival, float) and arrival > 0
    assert constructor_args[0]["window_hwnd"] == 17
    assert constructor_args[0]["minimum_update_interval"] == 100
    assert constructor_args[0]["cursor_capture"] is False
    source.close()
    source.close()
    assert controls[0].calls == 1
    assert source.latest() is None


def test_wgc_window_frame_offset_is_cropped_to_client(monkeypatch):
    api = FakeWin32()
    class BorderWin32(FakeWin32):
        def frame_bounds(self, hwnd):
            return (GAME.left - 8, GAME.top - 8, GAME.right + 8, GAME.bottom + 8)
    api = BorderWin32()
    frame = np.zeros((556, 976, 4), dtype=np.uint8)
    frame[8:548, 8:968] = valid_bgra()
    result = capture(api=api, factory=lambda hwnd: FakeFrame(frame))
    assert result.reason == "ok" and result.image.size == (960, 540)
    assert result.image.getpixel((30, 20)) == (0, 20, 30)


def test_untrusted_proofless_roi_never_reaches_watcher(monkeypatch):
    from backend.collectors import screen_ocr, slot_title_ocr
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: GAME)
    monkeypatch.setattr(screen_ocr, "capture_augment_region", lambda *a, **k:
                        Image.new("RGB", (672, 151)))
    monkeypatch.setattr(slot_title_ocr, "recognize_title_slot",
                        lambda *a: pytest.fail("no OCR for proofless frame"))
    watcher = screen_ocr.ScreenWatcher()
    assert watcher.check({}) == ("capture_unavailable", None)
    assert watcher.last_scan_stage == "capture_invalid"


def test_verified_recovery_resets_wgc_invalid_streak_budget():
    sources = []
    def factory(hwnd):
        source = FakeFrame(np.zeros((540, 960, 4), dtype=np.uint8))
        sources.append(source)
        return source

    for _ in range(10):
        assert capture(factory=factory).reason == "invalid_frame"
    # The first new session recovers once. A later unrelated failure streak
    # must get one fresh restart rather than being called permanently degraded.
    sources[1].frame = valid_bgra()
    assert capture(factory=factory).reason == "ok"
    sources[1].frame = np.zeros((540, 960, 4), dtype=np.uint8)
    for _ in range(10):
        assert capture(factory=factory).reason == "invalid_frame"
    assert len(sources) == 2
    assert capture(factory=factory).reason == "invalid_frame"
    assert len(sources) == 3
