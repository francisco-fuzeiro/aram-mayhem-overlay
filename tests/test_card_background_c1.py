"""C1 v3 RED: card-background evidence is diagnostic-only and capture-proven.

Real images remain in the reviewed v3 source archive (SHA-pinned by the repo),
never replaced with invented negative League screenshots. No game is launched.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from PIL import Image

from backend.collectors import offer_visibility as visibility
from backend.collectors import screen_ocr
from backend.collectors.league_window import LeagueWindow
from backend.collectors.slot_title_ocr import SlotMatches
from backend.collectors.window_capture import CaptureProof
from backend.diagnostic_events import SCHEMA, _clean, events


ROOT = Path(__file__).resolve().parents[1]
TITLES = ROOT / "tests" / "fixtures" / "ocr_titles"
NO_OFFER_SHA16 = {
    "card_centre_1795134399156658000_1.png": "5ff58b0e19c6cb7d",
    "card_left_1795134399156658000_0.png": "3ce0daf3992ffd7a",
    "card_left_1795134416913524800_0.png": "ed9d083d1fd753ab",
    "card_right_1795134399156658000_2.png": "9dec9e402dce42a3",
    "card_right_1795134416913524800_2.png": "3ffc4b3921976267",
}


def title_images():
    """The 13 reviewed title bands (including two dialogue covers) and 8 snips."""
    paths = sorted((TITLES / "1440p").glob("*.png")) + sorted((TITLES / "snips").glob("*.png"))
    assert len(paths) == 21
    return {path.name: Image.open(path).convert("RGB") for path in paths}


def no_offer_images():
    """Load all five reviewed negatives; verify bytes against the v3 manifest."""
    directory = TITLES / "no_offer"
    paths = sorted(directory.glob("*.png"))
    assert {path.name for path in paths} == set(NO_OFFER_SHA16)
    images = {}
    for path in paths:
        assert sha256(path.read_bytes()).hexdigest()[:16] == NO_OFFER_SHA16[path.name]
        images[path.name] = Image.open(path).convert("RGB")
    return images


def test_c1_calibration_constants_and_shadow_default():
    assert visibility.CARD_BG_CALIBRATION_ID == "card_bg_v2"
    assert visibility.CARD_BG_RGB == (3, 16, 18)
    assert visibility.CARD_BG_CHANNEL_TOLERANCE == 12
    assert visibility.CARD_BG_PRESENT_MIN == 0.50
    assert visibility.CARD_BG_ABSENT_MAX == 0.05
    assert visibility.CARD_BG_SHADOW_MODE is True


def test_c1_all_21_reviewed_card_images_including_two_dialogues_are_present():
    fractions = [visibility.card_teal_fraction(image) for image in title_images().values()]
    assert len(fractions) == 21
    assert all(fraction >= 0.50 for fraction in fractions)


def test_c1_five_reviewed_negative_images_have_no_card_background():
    fractions = [visibility.card_teal_fraction(image) for image in no_offer_images().values()]
    assert len(fractions) == 5
    assert all(fraction <= 0.05 for fraction in fractions)


def test_c1_pure_fraction_matches_exact_per_channel_tolerance():
    image = Image.new("RGB", (4, 1))
    image.putdata([(3, 16, 18), (15, 28, 30), (16, 28, 30), (3, 16, 31)])
    assert visibility.card_teal_fraction(image) == 0.5
    assert visibility.card_teal_fraction(image.convert("RGBA")) == 0.5


def test_c1_three_slot_present_absent_mixed_classification_with_real_images():
    real = title_images()
    negative = no_offer_images()
    positives = [real[name] for name in (
        "region_1795025142_left.png",
        "region_1795025142_centre.png",
        "region_1795025142_right.png",
    )]
    negatives = [negative[name].resize((342, 96)) for name in (
        "card_left_1795134399156658000_0.png",
        "card_centre_1795134399156658000_1.png",
        "card_right_1795134399156658000_2.png",
    )]
    def slots(images):
        return dict(zip(("left", "centre", "right"), images))
    assert visibility.card_background_cue(slots(positives)) == "present"
    assert visibility.card_background_cue(slots(negatives)) == "absent"
    assert visibility.card_background_cue(slots(positives[:2] + negatives[2:])) == "mixed"
    assert visibility.card_background_cue({"left": positives[0]}) == "mixed"


def test_c1_diagnostic_schema_whitelists_only_the_two_enum_fields():
    assert SCHEMA["offer_cue"]["cue"] == frozenset(("present", "absent", "mixed"))
    assert SCHEMA["offer_cue"]["ocr"] == frozenset(("titles", "none"))
    assert _clean("offer_cue", {"cue": "absent", "ocr": "none",
                                "player_name": "SENSITIVE", "path": "private"}) == {
        "cue": "absent", "ocr": "none",
    }


def test_c1_five_absent_ticks_cannot_close_offer_or_change_actions(monkeypatch):
    game = LeagueWindow(hwnd=17, left=8, top=31, right=2552, bottom=1384, focused=False)
    recognised = SlotMatches({
        slot: (str(i), f"Synthetic {slot}", 98)
        for i, slot in enumerate(("left", "centre", "right"), 1)
    })
    class StableTracker:
        has_pending = False
        has_unverified_changes = False
        def observe(self, *args):
            return None
        def snapshot(self):
            return recognised
        def suspend(self):
            pass
    watcher = screen_ocr.ScreenWatcher(sleep_fn=lambda _: None)
    watcher._temporal = StableTracker()
    watcher._absence_gate.confirm_present((game.hwnd, game.rect))
    monkeypatch.setattr(screen_ocr, "is_available", lambda: True)
    monkeypatch.setattr(screen_ocr, "find_league_window", lambda: game)
    seq = iter(range(1, 8))
    def capture(*args, **kwargs):
        return screen_ocr.RegionCapture(
            Image.new("RGB", (30, 30)),
            CaptureProof("wgc", game.hwnd, game.rect, float(next(seq)), "other"),
            "ok",
        )
    monkeypatch.setattr(screen_ocr, "capture_augment_region", capture)
    negatives = no_offer_images()
    crops = {slot: image for slot, image in zip(("left", "centre", "right"), list(negatives.values())[:3])}
    monkeypatch.setattr(screen_ocr, "crop_title_slots", lambda *args: crops)
    observed = []
    monkeypatch.setattr(events, "transition", lambda event, **fields: observed.append((event, fields)) or True)
    for _ in range(5):
        action, slots = watcher.check({})
        assert action == "unchanged"
        assert slots is None
        assert watcher.current_slots is recognised
        assert watcher._absence_gate._approved is None
    cues = [fields for event, fields in observed if event == "offer_cue"]
    assert cues == [{"cue": "absent", "ocr": "titles"}]
    # A3: without source proof, neither image classification nor a new cue is authorized.
    monkeypatch.setattr(screen_ocr, "capture_augment_region",
                        lambda *args, **kwargs: screen_ocr.RegionCapture(Image.new("RGB", (30, 30)), None, "ok"))
    assert watcher.check({})[0] == "capture_unavailable"
    assert len([event for event, _ in observed if event == "offer_cue"]) == 1
