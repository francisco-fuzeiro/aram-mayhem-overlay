"""
ARAM Oracle — Screen OCR Augment Detection

Captures a screenshot of the augment selection area, runs OCR,
and fuzzy-matches detected text against known augment names.

Uses perceptual image hashing for cheap change detection:
- After a successful OCR scan, the region hash is stored.
- On subsequent ticks, only the hash is recomputed (fast).
- If the hash changes significantly, a reroll happened and OCR re-runs.

Screenshots are never stored by default; explicitly opted-in debugging can save images.

Requires Tesseract OCR installed:
  Windows: winget install UB-Mannheim.TesseractOCR
  Or download from: https://github.com/UB-Mannheim/tesseract/wiki
"""
import hashlib
import math
import re
import logging
import time
from pathlib import Path
from backend.collectors.league_window import find_league_window, LeagueWindow
from backend.collectors.card_title_geometry import title_bands_from_client_rect
from backend.collectors.slot_title_ocr import SlotMatches, crop_title_slots, recognize_title_slots

logger = logging.getLogger("aram-oracle.ocr")

try:
    import mss
    import pytesseract
    from PIL import Image, ImageFilter, ImageEnhance, ImageOps
    from rapidfuzz import fuzz, process

    OCR_AVAILABLE = True
except ImportError as e:
    OCR_AVAILABLE = False
    logger.warning("OCR dependencies not installed: %s", e)

# Default Tesseract path on Windows (UB-Mannheim installer)
# Override with TESSERACT_PATH env var if Tesseract is installed elsewhere.
import os as _os

_DEFAULT_TESS_WIN = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_tess_path = _os.environ.get("TESSERACT_PATH", _DEFAULT_TESS_WIN)
if OCR_AVAILABLE and Path(_tess_path).exists():
    pytesseract.pytesseract.tesseract_cmd = _tess_path


# -- Paths: screenshots are never stored in the installed bundle or git checkout --
def default_screenshot_dir() -> Path:
    from backend.diagnostic_events import default_log_dir
    return default_log_dir().parent / "screenshots"


SCREENSHOT_DIR = default_screenshot_dir()

# -- Screen regions --
# Region as fractions of screen: (left%, top%, right%, bottom%)
AUGMENT_REGION_16_9 = (0.15, 0.22, 0.85, 0.50)
AUGMENT_REGION_21_9 = (0.24, 0.22, 0.76, 0.50)  # Ultrawide letterboxed
AUGMENT_REGION_16_10 = (0.15, 0.20, 0.85, 0.48)

# Legacy alias for backwards compatibility
AUGMENT_REGION = AUGMENT_REGION_16_9

# Minimum fuzzy match score to accept (0-100)
MATCH_THRESHOLD = 65

# Minimum text length to even attempt matching
MIN_TEXT_LEN = 3

# Max screenshots to keep (oldest get cleaned up)
MAX_SCREENSHOTS = 15
MAX_SCREENSHOT_AGE_SECONDS = 3 * 24 * 3600

# Perceptual hash size (NxN grid). Higher = more sensitive to small changes.
HASH_SIZE = 16

# Hamming distance threshold: if distance > this, the image changed (reroll).
# With HASH_SIZE=16, total bits = 256. Threshold ~30 means ~12% difference.
HASH_CHANGE_THRESHOLD = 30


_logged_resolution = False


def get_augment_region(screen_width: int, screen_height: int) -> tuple[float, float, float, float]:
    """Return the augment screen region adjusted for aspect ratio."""
    # Check config override first
    try:
        from backend.config import config
        override = config.get("ocr_region")
        if isinstance(override, (list, tuple)) and len(override) == 4:
            try:
                fracs = tuple(float(x) for x in override)
            except (TypeError, ValueError):
                fracs = ()
            if len(fracs) == 4 and all(math.isfinite(v) for v in fracs):
                left, top, right, bottom = fracs
                area = (right - left) * (bottom - top)
                if (0 <= left < right <= 1 and 0 <= top < bottom <= 1
                        and area <= 0.5):
                    return fracs
            logger.warning("OCR region override rejected: must remain inside League client")
    except Exception:
        pass

    ratio = screen_width / screen_height if screen_height > 0 else 1.78

    if ratio >= 2.2:       # 21:9 ultrawide (2.33)
        return AUGMENT_REGION_21_9
    elif ratio >= 1.55:    # 16:9 (1.78) and 16:10 (1.6)
        return AUGMENT_REGION_16_9
    else:                  # 4:3 or other
        return AUGMENT_REGION_16_9


# -- Perceptual hashing --


def _perceptual_hash(img: "Image.Image") -> str:
    """Compute a perceptual hash (average hash) of an image.

    Resizes to a small grid, converts to grayscale, and compares each pixel
    to the mean. Returns a hex string. Fast (~1ms).
    """
    small = img.resize((HASH_SIZE, HASH_SIZE), Image.LANCZOS).convert("L")
    pixels = list(small.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if p > avg else "0" for p in pixels)
    # Convert to hex for compact storage
    return hex(int(bits, 2))[2:].zfill(HASH_SIZE * HASH_SIZE // 4)


def _hamming_distance(hash1: str, hash2: str) -> int:
    """Count differing bits between two hex hash strings."""
    if len(hash1) != len(hash2):
        return HASH_SIZE * HASH_SIZE  # max distance if incompatible
    val1 = int(hash1, 16)
    val2 = int(hash2, 16)
    xor = val1 ^ val2
    return bin(xor).count("1")


class ScreenWatcher:
    """Stateful screen watcher that uses hashing to detect augment changes.

    Usage in the poll loop:
        watcher = ScreenWatcher()

        # Each tick:
        action = watcher.check(augment_names)
        # action is one of:
        #   ("detected", matches)  — first detection or reroll detected, OCR ran
        #   ("unchanged", None)    — same augments still showing, no action needed
        #   ("no_augments", None)  — no augment UI detected on screen
        #   ("disappeared", None)  — augments were showing but are now gone (player chose)
        #   ("unavailable", None)  — OCR not ready
    """

    def __init__(self) -> None:
        self._frozen_hash: str | None = None  # hash after successful detection
        self._last_detected: list[tuple[str, str, int]] = []
        self._no_augment_hash: str | None = None  # hash of "normal gameplay" screen
        self._had_detection: bool = False  # True after augments were successfully detected
        self._disappear_confirm: int = 0   # consecutive ticks with no augments after detection
        self._capture_stale: bool = False
        self._title_client_rect: tuple[int, int, int, int] | None = None

    def reset(self) -> None:
        """Reset state (e.g., when game ends or augment confirmed)."""
        self._frozen_hash = None
        self._last_detected = []
        self._no_augment_hash = None
        self._had_detection = False
        self._disappear_confirm = 0
        self._capture_stale = False
        self._title_client_rect = None

    def check(
        self,
        augment_names: dict[str, str],
        monitor_index: int = 1,
        save: bool = False,
    ) -> tuple[str, list[tuple[str, str, int]] | None]:
        """Check the screen for augment changes.

        Returns:
            Tuple of (action, matches_or_none).
        """
        if not is_available():
            self._capture_stale = True
            return ("unavailable", None)

        game = find_league_window()
        if game is None:
            self._capture_stale = True
            return ("unavailable", None)
        if not game.focused:
            # Alt+Tab is not offer disappearance: preserve last detected cards.
            self._capture_stale = True
            return ("not_focused", None)

        # Capture only League's client area, never another monitor/desktop.
        img = capture_augment_region(monitor_index, league_window=game)
        if img is None:
            self._capture_stale = True
            return ("unavailable", None)

        if self._capture_stale:
            # After focus returns, don't trust the hash captured before Alt+Tab.
            self._frozen_hash = None
            self._capture_stale = False
        self._title_client_rect = game.rect
        current_hash = _perceptual_hash(img)

        # Case 1: No prior detection — this is the first scan
        if self._frozen_hash is None:
            # Store hash even if OCR fails, so subsequent checks can
            # detect when the screen changes (augments appearing).
            self._frozen_hash = current_hash
            return self._run_full_ocr(img, current_hash, augment_names, save)

        # Case 2: Compare hash to frozen reference
        distance = _hamming_distance(current_hash, self._frozen_hash)

        if distance <= HASH_CHANGE_THRESHOLD:
            # Screen looks the same — augments unchanged
            return ("unchanged", None)

        # Case 3: Hash changed significantly — reroll detected
        logger.info(
            "Screen changed (hamming distance=%d, threshold=%d) — reroll, rescanning",
            distance, HASH_CHANGE_THRESHOLD,
        )
        if save:
            save_screenshot(img, label="reroll_detected")

        # Reset disappear counter — this is a reroll, not a disappearance
        self._disappear_confirm = 0
        # Update frozen hash so next check compares against the new screen
        self._frozen_hash = current_hash

        return self._run_full_ocr(img, current_hash, augment_names, save)

    def _run_full_ocr(
        self,
        img: "Image.Image",
        img_hash: str,
        augment_names: dict[str, str],
        save: bool,
    ) -> tuple[str, list[tuple[str, str, int]] | None]:
        """Read individual padded title bands, retaining physical slot identity."""
        rect = self._title_client_rect
        if rect is None:
            self._capture_stale = True
            return ("unavailable", None)
        w, h = rect[2] - rect[0], rect[3] - rect[1]
        crops = crop_title_slots(img, rect, get_augment_region(w, h))
        if crops is None:
            self._capture_stale = True
            return ("unavailable", None)
        matches = recognize_title_slots(crops, augment_names)
        if save:
            save_screenshot(img, label="title_slots")
        self._frozen_hash = img_hash
        self._last_detected = list(matches)
        if matches:
            self._had_detection = True
        if matches or self._had_detection:
            # Obscuration is not an actual pick or offer disappearance.
            # Unknown slots replace previously guessed names instead of
            # allowing a stale position to masquerade as a current reading.
            self._disappear_confirm = 0
            return ("detected", matches)
        return ("no_augments", None)

    @property
    def last_detected(self) -> list[tuple[str, str, int]]:
        return list(self._last_detected)

    @property
    def has_detection(self) -> bool:
        return self._frozen_hash is not None


# -- Module-level singleton --
watcher = ScreenWatcher()


# -- Standalone functions (unchanged API for backwards compat) --


def is_available() -> bool:
    """Check if OCR system is ready."""
    if not OCR_AVAILABLE:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except (OSError, ImportError) as e:
        logger.debug("Tesseract not available: %s", e)
        return False


def screenshot_opted_in() -> bool:
    """Only a strict opt-in in config enables diagnostic card images."""
    from backend.config import config
    return config.get("ocr_debug_screenshots", False) is True


def _prune_screenshots(directory: Path) -> None:
    """Bound retention by both 72-hour age and maximum crop-file count."""
    now = time.time()
    paths = sorted(directory.glob("card_*.png"), key=lambda p: p.stat().st_mtime)
    for path in list(paths):
        try:
            if now - path.stat().st_mtime > MAX_SCREENSHOT_AGE_SECONDS:
                path.unlink()
                paths.remove(path)
        except OSError:
            pass
    while len(paths) > MAX_SCREENSHOTS:
        path = paths.pop(0)
        try:
            path.unlink()
        except OSError:
            pass


def _ensure_screenshot_dir() -> Path:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    _prune_screenshots(SCREENSHOT_DIR)
    return SCREENSHOT_DIR


def capture_augment_region(
    monitor_index: int = 1, *, league_window: LeagueWindow | None = None,
) -> "Image.Image | None":
    """Capture the augment region relative to the focused League client rect.

    The legacy monitor_index positional argument is ignored deliberately:
    never fall back to whole-monitor capture on lookup or focus failures.
    """
    global _logged_resolution
    if not OCR_AVAILABLE:
        return None

    game = league_window if league_window is not None else find_league_window()
    if game is None or not game.focused:
        return None
    if league_window is not None:
        # A watcher may have cached the HWND just before an Alt+Tab.
        current = find_league_window()
        if current is None or not current.focused or current.hwnd != game.hwnd:
            return None
    left, top, right, bottom = game.rect
    w, h = right - left, bottom - top
    if w <= 0 or h <= 0:
        return None
    region_fracs = get_augment_region(w, h)
    region = {
        "left": left + int(w * region_fracs[0]),
        "top": top + int(h * region_fracs[1]),
        "width": int(w * (region_fracs[2] - region_fracs[0])),
        "height": int(h * (region_fracs[3] - region_fracs[1])),
    }
    if region["width"] <= 0 or region["height"] <= 0:
        return None
    try:
        with mss.mss() as sct:
            screenshot = sct.grab(region)
            if not _logged_resolution:
                logger.info("League client: %dx%d, augment fractions=%s", w, h, region_fracs)
                _logged_resolution = True
            return Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
    except (OSError, ValueError) as e:
        logger.error("League client capture failed: %s", e)
        return None


def save_screenshot(
    img: "Image.Image",
    label: str = "",
    ocr_texts: list[str] | None = None,
    matches: list[tuple[str, str, int]] | None = None,
) -> Path | None:
    """Save only bounded card title crops from a focused League region.

    Legacy label/OCR text/matches arguments are intentionally ignored:
    they never enter filenames, images or logs. Full window/screen images
    cannot pass the exact focused client augment-region dimension check.
    """
    if not OCR_AVAILABLE or not screenshot_opted_in():
        return None
    game = find_league_window()
    if game is None or not game.focused:
        return None
    left, top, right, bottom = game.rect
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        return None
    a, b, c, d = get_augment_region(width, height)
    expected_size = (int(width * (c - a)), int(height * (d - b)))
    if img.size != expected_size or img.width < 150 or img.height < 50:
        logger.warning("Diagnostic image rejected: not a focused League augment region")
        return None

    # Pure, reviewed client-relative title geometry. The OCR *region* may
    # contain icons and other screen elements; persist only verified bounds.
    bands = title_bands_from_client_rect(game.rect)
    if bands is None:
        logger.debug("Diagnostic title crops unavailable for this client geometry")
        return None

    # The captured image origin is the OCR region within the focused client,
    # not the desktop or a third of the OCR strip.
    region_left = int(width * a)
    region_top = int(height * b)
    crops = []
    for slot, (x, y, band_width, band_height) in bands.items():
        lx, ly = x - region_left, y - region_top
        bounds = (lx, ly, lx + band_width, ly + band_height)
        if (lx < 0 or ly < 0 or bounds[2] > img.width
                or bounds[3] > img.height):
            # Fail closed if a custom OCR region excludes any title; never
            # silently clip or persist a non-title portion of the game.
            logger.debug("Diagnostic title band outside captured League region")
            return None
        crops.append((slot, bounds))

    try:
        directory = _ensure_screenshot_dir()
        stamp = time.time_ns()
        first: Path | None = None
        for index, (slot, bounds) in enumerate(crops):
            path = directory / f"card_{slot}_{stamp}_{index}.png"
            img.crop(bounds).save(path, "PNG")
            if first is None:
                first = path
        _prune_screenshots(directory)
        return first
    except OSError as exc:
        logger.warning("Card crop save failed: %s", type(exc).__name__)
        return None


def preprocess_for_ocr(img: "Image.Image") -> "Image.Image":
    """Enhance screenshot for better OCR accuracy on game UI."""
    w, h = img.size
    if w < 1500:
        img = img.resize((w * 2, h * 2), Image.LANCZOS)

    gray = img.convert("L")

    enhancer = ImageEnhance.Contrast(gray)
    gray = enhancer.enhance(2.5)

    gray = gray.filter(ImageFilter.SHARPEN)

    pixels = list(gray.getdata())
    avg = sum(pixels) / len(pixels) if pixels else 128
    if avg < 128:
        gray = ImageOps.invert(gray)

    return gray


def extract_text(img: "Image.Image") -> list[str]:
    """Run OCR on preprocessed image and return candidate text lines."""
    if not OCR_AVAILABLE:
        return []

    processed = preprocess_for_ocr(img)

    try:
        raw = pytesseract.image_to_string(
            processed,
            lang="eng",
            config="--psm 6 --oem 3",
        )
    except (OSError, RuntimeError) as e:
        logger.error("OCR failed: %s", e)
        return []

    lines = []
    for line in raw.split("\n"):
        cleaned = line.strip()
        if len(cleaned) >= MIN_TEXT_LEN and any(c.isalpha() for c in cleaned):
            lines.append(cleaned)

    return lines


def _normalize_augment_text(text: str) -> str:
    """Normalize OCR noise to the same alphabet as augment catalog names."""
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def match_augments(
    ocr_texts: list[str],
    augment_names: dict[str, str],
    threshold: int | None = None,
) -> list[tuple[str, str, int]]:
    """Match offered augments, including titles wrapped across OCR lines.

    Adjacent-line joining and normalization adapted from the pure matcher in
    zp96-cmd/mayhem-overlay/src/main/ocr-match.js (MIT declared in its package
    metadata; Copyright 2026 Zac Pitts; see THIRD_PARTY_NOTICES.md).
    Retains our existing rapidfuzz matcher and the 3-card maximum.
    """
    if not OCR_AVAILABLE or not ocr_texts or not augment_names:
        return []

    if threshold is None:
        try:
            from backend.config import config
            threshold = config.get("match_threshold", MATCH_THRESHOLD)
        except Exception:
            threshold = MATCH_THRESHOLD

    name_to_id: dict[str, str] = {}
    for aug_id, name in augment_names.items():
        normalized = _normalize_augment_text(name)
        if normalized:
            name_to_id[normalized] = str(aug_id)
    if not name_to_id:
        return []
    all_names = list(name_to_id)

    normalized_lines = [
        _normalize_augment_text(line) for line in ocr_texts
        if isinstance(line, str)
    ]
    normalized_lines = [line for line in normalized_lines if len(line) >= MIN_TEXT_LEN]

    # The Mayhem Overlay matcher joins neighbouring OCR lines when an augment
    # title wraps, rather than treating each line as a separate augment.
    joined_lines = [
        normalized_lines[index] + " " + normalized_lines[index + 1]
        for index in range(len(normalized_lines) - 1)
    ]
    texts = normalized_lines + joined_lines

    matches: dict[str, tuple[str, int]] = {}
    name_by_id = {str(aug_id): name for aug_id, name in augment_names.items()}

    for text in texts:
        variants = [text]
        words = text.split()
        # Existing fragment search, useful for text with borders or UI labels.
        for start in range(len(words)):
            for stop in range(start + 1, min(start + 6, len(words) + 1)):
                fragment = " ".join(words[start:stop])
                if len(fragment) >= MIN_TEXT_LEN:
                    variants.append(fragment)

        for variant in variants:
            result = process.extractOne(
                variant,
                all_names,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=threshold,
            )
            if result:
                normalized_name, score, _ = result
                aug_id = name_to_id[normalized_name]
                if aug_id not in matches or score > matches[aug_id][1]:
                    matches[aug_id] = (name_by_id[aug_id], int(score))

    sorted_matches = sorted(
        ((aid, name, score) for aid, (name, score) in matches.items()),
        key=lambda result: (-result[2], result[1]),
    )
    # An augment offer has three cards. Reject weak incidental labels when
    # three confident matches have already been found.
    strong = [item for item in sorted_matches if item[2] >= 85]
    return (strong if len(strong) >= 3 else sorted_matches)[:3]


def detect_augments(
    augment_names: dict[str, str],
    monitor_index: int = 1,
    save: bool = False,
) -> list[tuple[str, str, int]]:
    """Full pipeline: capture screen -> OCR -> match augments.

    For poll-loop usage, prefer ScreenWatcher.check() instead — it uses
    hashing to avoid redundant OCR calls.
    """
    if not is_available():
        logger.warning("OCR not available — Tesseract installed?")
        return []

    # Manual scans use the same strict position-locked OCR as the watcher.
    # Never infer card position from whole-region confidence-sorted matches.
    game = find_league_window()
    if game is None or not game.focused:
        return []
    img = capture_augment_region(monitor_index, league_window=game)
    if img is None:
        return []
    width = game.rect[2] - game.rect[0]
    height = game.rect[3] - game.rect[1]
    crops = crop_title_slots(img, game.rect, get_augment_region(width, height))
    if crops is None:
        return []
    matches = recognize_title_slots(crops, augment_names)
    if save:
        save_screenshot(img, label="manual_title_slots")
    return matches
