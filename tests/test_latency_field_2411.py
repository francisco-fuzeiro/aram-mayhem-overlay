"""Field 24/11 (latency): augment reads took 13-17 s after the cards showed.

Synthetic pixels, titles and clocks only; nothing opens League.
"""
from __future__ import annotations

from collections import Counter
from types import SimpleNamespace

import numpy as np
from PIL import Image

from backend.collectors import screen_ocr, slot_title_ocr
from backend.collectors import window_capture as wc
from backend.collectors.league_window import LeagueWindow
from backend.collectors.slot_temporal import SlotTemporalTracker
from backend.collectors.slot_title_ocr import SLOTS
from backend.collectors.window_capture import CaptureProof

TITLES = {10: ("a", "Synthetic A", 98), 20: ("c", "Synthetic C", 97)}


def crops(left, centre, right):
    return {slot: Image.new("RGB", (8, 8), (v, v, v))
            for slot, v in zip(SLOTS, (left, centre, right))}


def observe(tracker, left, centre, right):
    return tracker.observe(
        crops(left, centre, right), {},
        lambda _slot, crop, _n: TITLES.get(crop.getpixel((0, 0))[0]),
        lambda crop: str(crop.getpixel((0, 0))[0]),
        lambda a, b: 0 if a == b else 256,
    )


def test_animated_unknown_card_no_longer_blocks_the_readable_cards():
    # Right card: unreadable title whose crop changes every frame (animation).
    tracker = SlotTemporalTracker()
    assert observe(tracker, 10, 20, 31) is None
    result = observe(tracker, 10, 20, 32)
    assert result is not None
    assert [result.slots[s][0] if result.slots[s] else None for s in SLOTS] == ["a", "c", None]
    assert not tracker.has_pending


def test_animation_still_cannot_erase_an_accepted_title():
    tracker = SlotTemporalTracker()
    observe(tracker, 10, 20, 31)
    observe(tracker, 10, 20, 32)
    # Left card animates into unreadable frames with moving hashes.
    assert observe(tracker, 41, 20, 32) is None
    assert observe(tracker, 42, 20, 32) is None
    assert tracker.snapshot().slots["left"][0] == "a"


GAME = LeagueWindow(77, -1200, 40, -240, 580, False)


def verified(codes=(10, 20, 30), timestamp=10.0, reason="ok"):
    if reason != "ok":
        return screen_ocr.RegionCapture(None, None, reason)
    proof = CaptureProof("wgc", GAME.hwnd, GAME.rect, timestamp, "other")
    return screen_ocr.RegionCapture(Image.new("RGB", (4, 4), codes), proof, "ok")


def watcher_with(monkeypatch, frames, **kwargs):
    queue = list(frames)
    reads = Counter()
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: GAME)
    monkeypatch.setattr(screen_ocr, "capture_augment_region",
                        lambda *_a, **_k: queue.pop(0))
    monkeypatch.setattr(screen_ocr, "crop_title_slots", lambda image, *_: {
        slot: Image.new("RGB", (8, 8), (v, v, v))
        for slot, v in zip(SLOTS, image.getpixel((0, 0)))})
    monkeypatch.setattr(screen_ocr, "_perceptual_hash",
                        lambda image: str(image.getpixel((0, 0))[0]))
    monkeypatch.setattr(screen_ocr, "_hamming_distance", lambda a, b: abs(int(a) - int(b)))
    titles = {10: ("a", "A", 98), 20: ("c", "C", 97), 30: ("d", "D", 96)}

    def read(slot, image, _names):
        reads[slot] += 1
        return titles.get(image.getpixel((0, 0))[0])

    monkeypatch.setattr(slot_title_ocr, "recognize_title_slot", read)
    return screen_ocr.ScreenWatcher(sleep_fn=lambda _s: None, **kwargs), queue, reads


def test_transient_miss_between_ticks_keeps_c3_baselines(monkeypatch):
    misses = [verified(reason="invalid_frame")] * screen_ocr.CAPTURE_RETRY_ATTEMPTS
    watcher, queue, reads = watcher_with(monkeypatch, [
        verified(timestamp=10.0), verified(timestamp=10.6),  # tick 1: detected
        *misses,                                            # tick 2: WGC miss
        verified(timestamp=12.0),                           # tick 3: unchanged
    ])
    assert watcher.check({})[0] == "detected"
    assert watcher.check({}) == ("capture_unavailable", None)
    reads.clear()
    action, _ = watcher.check({})
    # Before 24/11 every miss forced all three slots to be read twice again.
    assert action == "unchanged" and sum(reads.values()) == 0
    assert watcher.current_slots.slots["left"][0] == "a"


def test_window_loss_still_forces_full_reverification(monkeypatch):
    watcher, _queue, _reads = watcher_with(monkeypatch, [
        verified(timestamp=10.0), verified(timestamp=10.6),
        verified(reason="window_changed"),
    ])
    assert watcher.check({})[0] == "detected"
    assert watcher.check({}) == ("capture_unavailable", None)
    assert watcher._temporal._refresh_required is True


def test_tick_timing_event_is_bounded(monkeypatch):
    from backend import diagnostic_events
    emitted = []
    monkeypatch.setattr(diagnostic_events.events, "emit",
                        lambda event, **f: emitted.append((event, f)) or True)
    monkeypatch.setattr(diagnostic_events.events, "transition", lambda *a, **k: True)
    misses = [verified(reason="invalid_frame")] * screen_ocr.CAPTURE_RETRY_ATTEMPTS
    watcher, _q, _r = watcher_with(monkeypatch, misses)
    watcher.check({})
    ticks = [f for e, f in emitted if e == "ocr_tick"]
    assert len(ticks) == 1
    tick = ticks[0]
    assert tick["stage"] == "capture_invalid" and tick["reason"] == "invalid_frame"
    assert tick["attempts"] == screen_ocr.CAPTURE_RETRY_ATTEMPTS
    clean = diagnostic_events._clean("ocr_tick", tick)
    assert {"stage", "total_ms", "capture_ms", "attempts", "reason", "detail"} <= set(clean)


def test_anvil_watcher_never_writes_augment_scan_stages(monkeypatch):
    from backend import diagnostic_events
    seen = []
    monkeypatch.setattr(diagnostic_events.events, "transition",
                        lambda event, **f: seen.append(event) or True)
    monkeypatch.setattr(diagnostic_events.events, "emit",
                        lambda event, **f: seen.append(event) or True)
    watcher, _q, _r = watcher_with(
        monkeypatch, [verified(reason="window_changed")], emit_diagnostics=False)
    watcher.check({})
    assert watcher.last_scan_stage == "capture_invalid"
    assert seen == []


def test_report_shows_tick_median_and_capture_misses(tmp_path):
    from backend import feature_diagnostics as fd
    rows = [
        ('2026-11-24T21:00:00+00:00', '"event":"session_start"'),
        ('2026-11-24T21:00:10+00:00', '"event":"ocr_window","state":"opened","reason":"level_due","level":7'),
        ('2026-11-24T21:00:11+00:00', '"event":"ocr_tick","stage":"capture_invalid","total_ms":400,"capture_ms":350,"attempts":4,"reason":"invalid_frame","detail":"stale_frame"'),
        ('2026-11-24T21:00:12+00:00', '"event":"ocr_tick","stage":"titles_detected","total_ms":1200,"capture_ms":30,"attempts":2'),
        ('2026-11-24T21:00:12+00:00', '"event":"ocr_scan_stage","stage":"titles_detected"'),
        ('2026-11-24T21:00:20+00:00', '"event":"ocr_window","state":"closed","reason":"cursor_pick","level":7'),
    ]
    (tmp_path / "events.jsonl").write_text(
        "".join('{"timestamp":"%s",%s}\n' % r for r in rows), encoding="utf-8")
    w = fd.build_report(tmp_path)["ocr_windows"][0]
    assert w["ticks"] == 2 and w["tick_ms_median"] == 1200
    assert w["capture_misses"] == {"invalid_frame/stale_frame": 1}
    assert "invalid_frame/stale_frame: 1" in fd.render_markdown(fd.build_report(tmp_path))


class _Frame:
    def __init__(self, frame, ts):
        self.frame, self.ts, self.closed = frame, ts, 0

    def latest(self):
        return self.frame.copy(), self.ts

    def close(self):
        self.closed += 1


class _Api:
    def is_minimized(self, hwnd):
        return False

    def foreground_window(self):
        return 99

    def process_id(self, hwnd):
        return 1

    def frame_bounds(self, hwnd):
        return WGAME.rect

    def client_to_screen(self, hwnd, point):
        return WGAME.left + point[0], WGAME.top + point[1]


WGAME = LeagueWindow(hwnd=17, left=-1920, top=100, right=-960, bottom=640, focused=False)


def _bgra(valid=True):
    arr = np.zeros((540, 960, 4), dtype=np.uint8)
    arr[:, :, 3] = 255
    if valid:
        arr[:, :, 0] = np.arange(960, dtype=np.uint8)[None, :]
        arr[:, :, 1] = np.arange(540, dtype=np.uint8)[:, None]
    return arr


def test_degraded_wgc_session_is_retried_after_a_pause(monkeypatch):
    wc.reset_capture_state()
    monkeypatch.setattr(wc, "find_league_window", lambda **kwargs: WGAME)
    clock = SimpleNamespace(t=10.0)
    sources = []

    def factory(hwnd):
        source = _Frame(_bgra(valid=len(sources) >= 2), clock.t)
        sources.append(source)
        return source

    def cap():
        for s in sources:
            s.ts = clock.t
        return wc.capture_league_client(
            WGAME, win32=_Api(), frame_source_factory=factory,
            clock=lambda: clock.t, platform_name="win32")

    try:
        for _ in range(2 * wc.WGC_INVALID_STREAK_LIMIT):
            assert cap().image is None
        assert cap().reason == "backend_unavailable"
        assert wc.last_invalid_detail() == "degraded"
        clock.t += wc.WGC_DEGRADED_RETRY_S
        result = cap()
        assert result.reason == "ok" and len(sources) == 3
    finally:
        wc.reset_capture_state()


def test_stale_frame_detail_is_reported(monkeypatch):
    wc.reset_capture_state()
    monkeypatch.setattr(wc, "find_league_window", lambda **kwargs: WGAME)
    try:
        result = wc.capture_league_client(
            WGAME, win32=_Api(), frame_source_factory=lambda h: _Frame(_bgra(), 1.0),
            clock=lambda: 10.0, platform_name="win32")
        assert result.reason == "invalid_frame"
        assert wc.last_invalid_detail() == "stale_frame"
    finally:
        wc.reset_capture_state()


def test_four_card_row_is_told_apart_from_three_cards():
    from backend.collectors.card_title_geometry import (
        card_count_from_fractions, layout_probe_strips,
    )
    # Measured on the owner's 2550x1363 four-card screenshot (not stored).
    four = {-1.0: 0.10, -0.5: 0.86, 0.0: 0.08, 0.5: 0.84, 1.0: 0.0}
    three = {-1.0: 0.9, -0.5: 0.1, 0.0: 0.9, 0.5: 0.05, 1.0: 0.88}
    assert card_count_from_fractions(four) == 4
    assert card_count_from_fractions(three) == 3
    assert card_count_from_fractions({k: 0.0 for k in four}) is None
    strips = layout_probe_strips((0, 0, 2550, 1363))
    assert strips[0.0][0] < 1275 < strips[0.0][0] + strips[0.0][2]
    assert abs(strips[0.5][0] - strips[0.0][0] - 229) <= 2
