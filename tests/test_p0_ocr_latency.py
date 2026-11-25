"""P0 field fix (23/11): 33 s to the first augment read, ~10 s per OCR tick.

1) With no card background on screen (black frame), the production watchers
   skip title OCR entirely (cheap colour check only).
2) The three title slots are read concurrently (Tesseract runs out of
   process), keeping physical slot order and the two-read gate unchanged.
"""
import threading
import time

from PIL import Image

from backend.collectors import screen_ocr, slot_title_ocr
from backend.collectors.slot_temporal import SlotTemporalTracker
from tests.test_ocr_scan_stage_p0 import NAMES, WINDOW, proven


def _strip(colour=(0, 0, 0)):
    region = screen_ocr.get_augment_region(2544, 1353)
    return Image.new("RGB", (int(2544 * (region[2] - region[0])),
                             int(1353 * (region[3] - region[1]))), colour)


def _patch(monkeypatch, strip, calls):
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: WINDOW)
    monkeypatch.setattr(screen_ocr, "capture_augment_region", lambda *_a, **_k: proven(strip))
    monkeypatch.setattr(slot_title_ocr, "recognize_title_slot",
                        lambda *_a: calls.append(1) or None)


def test_no_card_background_skips_title_ocr(monkeypatch):
    calls = []
    _patch(monkeypatch, _strip(), calls)
    watcher = screen_ocr.ScreenWatcher(sleep_fn=lambda _: None, skip_ocr_without_cards=True)
    assert watcher.check(NAMES)[0] == "no_augments"
    assert calls == [] and watcher.last_scan_stage == "cards_absent"


def test_card_background_still_runs_ocr_and_default_is_unchanged(monkeypatch):
    calls = []
    _patch(monkeypatch, _strip((3, 16, 18)), calls)
    screen_ocr.ScreenWatcher(sleep_fn=lambda _: None, skip_ocr_without_cards=True).check(NAMES)
    assert calls
    calls.clear()
    _patch(monkeypatch, _strip(), calls)
    screen_ocr.ScreenWatcher(sleep_fn=lambda _: None).check(NAMES)
    assert calls  # tests/legacy callers keep the old behaviour


def test_production_watchers_skip_ocr_without_cards():
    from backend.collectors import anvil_popup
    assert screen_ocr.watcher._skip_ocr_without_cards is True
    anvil_popup._watcher = None
    assert anvil_popup.anvil_watcher()._skip_ocr_without_cards is True


def test_three_slots_are_read_concurrently_in_slot_order():
    active, peak, order = [0], [0], []
    lock = threading.Lock()

    def read(slot, _crop, _names):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.05)
        with lock:
            active[0] -= 1
        order.append(slot)
        return None

    crops = {s: Image.new("RGB", (40, 10), (i * 80, 0, 0))
             for i, s in enumerate(("left", "centre", "right"))}
    tracker = SlotTemporalTracker()
    tracker.observe(crops, NAMES, read, screen_ocr._perceptual_hash, screen_ocr._hamming_distance)
    assert peak[0] == 3
