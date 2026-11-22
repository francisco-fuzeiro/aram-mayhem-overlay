# ARAM Oracle OCR V1.1d — native Windows lab and independent capture gate

**Date:** 2026-11-22. **Scope:** isolated research-only utilities.
**Branch:** `research/v1-1d-ocr-native-labeler-20261122`.
**Draft PR:** https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/81
**Exact parent:** draft #79 `eb96f7bb34f3f8bdac146440d21f927098b79925`.
**No merge; no V1.2; Tesseract remains in production.**

## 1. Verified inherited CI and provenance

PR #79 was checked at its **exact final SHA**:
https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44982899154
completed SUCCESS with Linux/Windows safety, pinned real inference and
Windows isolated launcher cold/offline verification, all four jobs GREEN.
V1.1b #77, V1.1 #74, V1.0 #72, rules #75 and N1 #71 remain open drafts.
Repository metadata reports **public visibility**, so zero new screenshot,
private log, model binary or user data may be committed.

Frozen datasets, catalog, strict 90/8 matcher and model checksums remain
as recorded in V1.1b/V1.1c. The full source of truth is the existing
execution/benchmark documentation, not a new V1.1d inference claim.

### Previously measured V1.1b/V1.1c original-only safety (not rerun here)

| Candidate (same 26 retrospective original crops) | Correct title IDs | Negative rejections | Wrong accepted IDs | Negative false positives | Safe title abstentions | Raw exact |
|---|---:|---:|---:|---:|---:|---:|
| Tesseract | 19/19 | 7/7 | 0 | 0 | 0 | 19/19 |
| Direct v4 fixed | 19/19 | 7/7 | 0 | 0 | 0 | 17/19 |
| Direct v4 adaptive | 19/19 | 7/7 | 0 | 0 | 0 | 19/19 |
| RapidOCR v4, same weights | 19/19 | 7/7 | 0 | 0 | 0 | 19/19 |
| English v5, tested preprocessing | 8/19 | 7/7 | 0 | 0 | 11 | 8/19 |

- Previously measured **derived transforms**: 1,456 correlated observations
  of the same originals; not independent. Previously measured **synthetic
  text**: 124 safe rejections and no wrong accepted ID in the specified
  stress test; not visual OCR or gameplay.
- Newly approved independent holdout during V1.1d: **0, BLOCKED**.
- New V1.1d model benchmarks: **NOT EXECUTED**. We intentionally avoid
  repeating verified frozen historical inference without a change in the
  algorithm or benchmark runner. V1.1d CI tests local GUI/core only.

### Archived Windows Actions V1.1c isolated native-process profile

Same disposable Windows 2022 Actions VM, not the user's PC. Profile
from the cached-offline run (documented in the V1.1c ledger):

| Engine | Crop mean ms | Crop p95 ms | Three crops mean ms | Cold ready ms | CPU s | Sampled RSS MiB |
|---|---:|---:|---:|---:|---:|---:|
| Tesseract | 175.640 | 282.918 | 376.391 | 293.483 | 8.984 | 67.89 |
| PP-OCRv4 fixed | 67.290 | 99.468 | 294.151 | 488.405 | 4.938 | 84.00 |
| PP-OCRv4 adaptive | 84.195 | 175.058 | 339.175 | 484.691 | 5.875 | 106.87 |
| RapidOCR v4 | 122.525 | 340.151 | 350.034 | 559.863 | 7.125 | 96.08 |
| English v5 | 42.039 | 61.651 | 185.029 | 458.186 | 3.375 | 78.53 |

Cold ready is isolated process readiness, not real app cold start. CPU
seconds and process-tree RSS are sampled during the test and not FPS/
background-CPU impact estimates. Numeric scores from the user's Windows:
**NONE PROVIDED, NOT TESTED**.

## 2. Implemented V1.1d isolated research

- `benchmarks/ocr_v11d/Start-OCRLab.ps1`: a single command from a
  separate, detached checkout delegates to the unchanged V1.1c benchmark
  before launching the local label UI. `-Offline`, `-BenchOnly`,
  `-LabelsOnly`, `-OutputRoot`, and `-TesseractExe` avoid reimplementing
  any pinned preflight, models, hashes or profiler. Full Tkinter Python
  3.11 is required; no system installation or privilege change.
- `label_ui.py`: local Tk still-image import, preview, drag-to-crop
  per visible title, full-screen source resolution metadata, manually
  selected canonical augment title from the pinned 328-name catalog,
  physical left/centre/right, rarity, two lines, reroll, scene (animation,
  transition, dialog/no-offer), Alt+Tab/focus, OP.GG present, DPI. Human
  confirmation requires explicit privacy review and split selection
  **before any OCR**. One screenshot => one source_frame for all included
  slots; each reroll screenshot uses a new source_frame, same offer optional.
- `label_core.py`: private crops and CSV, input geometry/category/catalog
  verification, strict session-based development/holdout separation,
  duplicate bytes/pixels and duplicate slot/frame checks, frozen original
  hashes, atomic CSV append, fail-closed on non-confirmation. Paths stay
  under private Windows LOCALAPPDATA, not the Git checkout. No capture
  automation, game process access, network, OCR at import/preview/confirm.
- `context_report.py`: only after **explicitly** running the existing
  sealed development evaluator, join private human CSV to the manifest
  using case identifiers/provenance validation and summarize existing
  per-case decisions by rarity, physical slot, two-line, category, scene,
  reroll, focus, DPI and OP.GG. Five engines are required, including both
  direct v4 variants. Never invent missing image inference.
- The existing V1.1c `manifest` prepares/dev-seals the split, and
  `evaluate_local` remains the **only** OCR invocation. The GUI omits
  holdout unlock. For independently approved sealed holdout, retain the
  explicit V1.1c CLI release protocol. No changes to V1.1b OCR model,
  matcher, capture, WGC, game or product code.

## 3. Test-first and validation evidence

- Tests-only RED SHA `6bec37184b65c44e7a8b6b8fdb75d80c67779714`,
  https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44991963627:
  both Ubuntu and Windows fail at the expected import of the still-missing
  isolated label_core; **not** an unrelated test failure.
- Initial local-label core/GUI/launcher GREEN SHA
  `0e2cb63cc106ad475dba01fa85e27e6fc150086c`,
  https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44992087157:
  Ubuntu and Windows labeler-safety jobs completed SUCCESS. This test
  set verifies synthetic in-memory inputs and syntax, **not** the native
  desktop UI, Windows-installed Tesseract or any actual League session.
- Final branch SHA and exact-head Linux/Windows safety CI:
  **RECHECK AFTER FINAL DOCUMENTATION COMMIT.**
- Native user PC benchmark: **NOT TESTED**. Tk GUI interactive usability:
  **NOT TESTED on user device**. New manual screenshots: **BLOCKED**.
  New independent per-scenario inference results: **BLOCKED**.

The new tests cannot be misrepresented as independent title recognition
trials. No automatic game capture, upload or live OCR substitution exists.

## 4. Next user actions and release checklist

1. Use `benchmarks/ocr_v11d/README.md` to make a detached new worktree
   and invoke the single Windows command. Record only locally the report
   under `%LOCALAPPDATA%\ARAMOracle\OCR-V11c\results\<timestamp>\`.
   Do not paste private report until specifically reviewed/redacted.
2. Import screenshots of actual independent sessions. Crop each of the
   three offered titles from the **same frame**, assign correct canonical
   augment, rarity, two-line, reroll and visible context. Include
   transition/dialog/no-offer negatives, OP.GG simultaneous, Alt+Tab,
   1080p/1440p and different DPI, as genuinely observed, not fabricated.
3. Explicitly approve each image's ground truth/privacy, assign whole
   sessions to development/holdout before predictions, and generate/seal
   manifests locally; evaluate development first. The remaining holdout
   must remain unseen until candidate freeze and explicit unlock.
4. Compare full case-level evidence (raw, normalized, strict 90/8, numeric
   ID) for all five engines. Wrong accepted ID or negative false positive
   is a blocking safety event. Report false rejections separately.
5. Measure cold start, CPU, RSS and latency on the user's PC. That does
   **not** in itself validate League/WGC first-six-second behavior,
   transition availability, FPS, OP.GG or focus handling, which require
   separate N1/native user-operated evidence.

**Leading offline candidate:** direct PP-OCRv4 fixed line split;
**confidence HIGH** on frozen reproducibility, **MODERATE** on relative
isolated Windows Actions performance, **LOW** on independent real play,
deployment and user-device compatibility. Adaptive matches 19/19 raw
text but cost more on the measured disposable VM. Maintenance/installer
footprint has not been measured on the user's PC. Tesseract stays the
installed recognizer.

**GO:** permit only further local sampling, benchmark and research
diagnostics. **NO-GO** to V1.2 promotion. Require representative,
multi-session sealed independent holdout across positions/rarity/
difficult titles/negatives/rerolls with zero wrong non-null identities
and zero negative false positives; actual user's Windows/League/OP.GG
performance and UX evidence; N1 native acceptance; Riot policy review;
and a separately authorized V1.2. Never merge automatically.
