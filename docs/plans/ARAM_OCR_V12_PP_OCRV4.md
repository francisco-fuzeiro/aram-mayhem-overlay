# ARAM Oracle — OCR V1.2 implementation and promotion gates

**Decision:** 2026-11-22. **User authorized implementation of PP-OCRv4.**
**Product branch:** `feat/ocr-v12-ppocrv4-optin-20261122` (draft PR #83, stacked on F1 draft #80). **Tracking:** issue #82.
**Repository visibility:** **PUBLIC by explicit user choice**; this is not a visibility defect. Never upload private game screenshots/holdout, OCR transcripts, user logs, secrets, or private paths. Keep assets in local application data.

## Exact candidate and integration

- Uses the **historical V1.1 direct PP-OCRv4 ONNX** path: RGB/PIL, 48x448 fixed width, BILINEAR, grayscale row segmentation of a supplied *title band*, CTC decoding with model's embedded character dictionary.
- Model is SHA256-pinned to `48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b` and exactly 10,857,958 bytes. CPU execution provider with one thread. No model is in Git.
- `backend/collectors/ppocr_v4.py` is a recognizer **only**: no screen capture, League reading, network, automatic choices or UI mutation.
- The production `recognize_title_slot` entrypoint routes to PP-OCRv4 **only when** `ARAM_ORACLE_OCR_ENGINE=ppocrv4` at process launch. The existing Tesseract engine is still the default. When v4 cannot start or its verified model is missing, Tesseract is used; when v4 returns unrecognized text, no secondary guess is accepted.
- Unchanged from N1/F0/F1 stack: original physical left/centre/right crops, geometry, WGC/capture/focus, strict catalog matcher threshold **90** and margin **8**, duplicate-position rejection, two independent temporal reads, reroll epochs, stale protection, OfferLedger and no automatic augment picks.

## Explicit setup (Windows, from repository root)

Use Python 3.11, an existing local Tesseract installation for default/fallback, and a terminal **before** starting ARAM Oracle:

```powershell
python -m pip install -e ".[ocr-v4,overlay]"
python -m scripts.setup_ppocr_v4
python -m scripts.setup_ppocr_v4 --check
$env:ARAM_ORACLE_OCR_ENGINE = "ppocrv4"
python -m backend.desktop
```

Restart the desktop process after changing the engine environment variable.
The setup tool may access the internet **only when explicitly run** to download the pinned public `rapidocr-onnxruntime==1.4.4` wheel. It extracts only the verified v4 ONNX model into `%LOCALAPPDATA%\ARAMOracle\models\ppocrv4.onnx` (or corresponding per-user Linux path). No gameplay download, no automatic screenshots, and no uploading data.

Rollback without reinstalling:

```powershell
Remove-Item Env:ARAM_ORACLE_OCR_ENGINE -ErrorAction SilentlyContinue
python -m backend.desktop
```

The experimental selection is not yet exposed in Settings. A future UI toggle must preserve the pre-game-only policy and this model-integrity gate.

## Evidence and acceptance

**Historical research, not a new game test:** #74/#77/#79 tested 26 original reviewed images (19 titles, 2 dialogs, 5 no-offer). Both Tesseract and direct fixed PP-OCRv4 got 19/19 canonical title IDs with 7/7 safe negatives, 0 accepted wrong IDs on that correlated set. V1.1c disposable Windows Actions mean per original crop: Tesseract 175.6ms vs direct fixed v4 67.3ms; *no user-device or FPS inference*.

**New V1.2 implementation tests:**
- Unit: model digest/bytes check, line splitting, strict CTC dimensions, opt-in/default/fallback, unknown abstention, fixed physical order and duplicate rejection.
- Separate Windows Actions real-model job: explicitly installs SHA-pinned ONNX, calls actual product slot entrypoint on all 26 original images with full 328-title catalog and verifies canonical numeric IDs/negative rejections.
- Full existing Python/JS/Settings regression job must pass on exact final PR head.
- Status is **NOT ACCEPTED** until CI final head is verified and user-operated native Windows/League evidence is collected.

**Native and deployment gates still OPEN:** independent unseen per-session holdout (three simultaneous cards, individual rerolls, two-line/Silver, dialogs/no-offer); source-frame and temporal verification; League/WGC/OP.GG/DPI/focus/Alt+Tab; CPU/RSS/FPS/first-six-second latency; N1 F1.3 and Riot policy review. Any accepted wrong ID requires investigation. No promotion to default, distribution, installer claim or merge before a separate explicit gate decision.

## Next work

1. Verify exact final SHA against Windows Python+JS suite AND pinned real-model integration job. Fix measured failures without weakening 90/8 or safety.
2. Run opt-in local Windows launch and verify model is present; compare real titles/three-card rerolls/unknowns and safe fallback while recording only sanitized consented traces.
3. Integrate pre-game engine setting and installer bundling only after validated native behavior and release gate.
