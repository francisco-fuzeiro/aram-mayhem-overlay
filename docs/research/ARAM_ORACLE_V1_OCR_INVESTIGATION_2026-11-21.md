# ARAM Oracle — OCR Engine Investigation V1

**Date:** 2026-11-21  
**Status:** Research only; V1 NOT AUTHORIZED for implementation  
**Repository:** `francisco-fuzeiro/aram-mayhem-overlay`  
**Reference under inspection:** `fix/n1-js-bootstrap` at `9f559d5d814e6b4dfd6e6140102ef297d36157f6` (read-only)  
**Protected work:** N1 native acceptance and draft PR #71. No repository writes, branches, commits, merges, CI reruns, or production code changes were made by this investigation.

## Executive decision

**Keep Tesseract as the authoritative production recognizer for now.** PP-OCRv4 ONNX is the historical front-runner, but the previously reported 26/26 is not an independently reproduced result. Benchmark the English-specialized `en_PP-OCRv5_mobile_rec` against that exact PP-OCRv4 model and the *current* Tesseract pipeline before any promotion. RapidOCR is chiefly an alternative wrapper/runtime for the Paddle recognizers, not a separate accuracy candidate unless a different model or preprocessing pipeline is specified. Do not start V1 while N1 remains open or without explicit user authorization.

## 1. Provenance and verification of the 26/26 claim

The historical experiment is recorded in `docs/plans/ARAM_2026-11-20/features/PLANO_FEATURES_2026-11-20.md` §3 and the V1 section of `features/blueprints_features/M-F_features.md`. The reference script is `features/blueprints_features/fixtures/paddle_eval_reference.py`. The binary title fixtures were found in `tests/fixtures/ocr_titles/` on the inspected N1 branch. Their ground truth is present in two JSON manifests. The correction blueprint's `fixtures/MANIFEST.md` supplies file sizes and truncated SHA-256 values. Individual source-image bytes, model bytes, and historical experiment stdout were not independently hashed or executed in this session.

**Correction to the source documentation:** the narrative "21 titles + 2 dialogs + 5 no-offer = 26" is arithmetically incorrect. The actual source manifests and `tests/test_real_title_crops_a2.py` define **19 named title images, 2 dialog negatives, and 5 no-offer negatives = 26 total**. The 21-image Tesseract A2 regression consists of **19 named titles + 2 dialogs**. This correction should be made in a future *authorized* documentation change; none was made here.

| Fixture group | Named titles | Dialog negatives | No-offer negatives | Total | Position evidence |
|---|---:|---:|---:|---:|---|
| `1440p/` | 11 | 2 | 0 | 13 | 3 left, 6 centre, 4 right (includes 2 centre dialogs) |
| `snips/` | 8 | 0 | 0 | 8 | Not geometry-calibrated; no physical slot annotation |
| `no_offer/` | 0 | 0 | 5 | 5 | 2 left, 1 centre, 2 right; all negative |
| **Total** | **19** | **2** | **5** | **26** | Incomplete native L/C/R coverage |

Historical reported test configuration:
- Model: `ch_PP-OCRv4_rec_infer.onnx` from `rapidocr-onnxruntime==1.4.4`, SHA-256 `48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b`, size 10,857,958 bytes; provenance and checksum are **recorded assertions, not independently re-hashed here**.
- Inference: Python `onnxruntime` reportedly version **1.29**, CPU. Input RGB, 48-pixel height, max 448 width, aspect-preserving resize, values scaled to [-1, 1], NCHW; CTC greedy decoding. Line splitting uses luminance threshold 150, min 3 bright pixels/row, min line height 6 and padding.
- Matching in the historical script strips all non-alphanumeric characters, including spaces, then uses RapidFuzz ratio ≥90 and margin ≥8. **This differs from production** `slot_title_ocr._normalize`, which preserves inter-word spaces. Consequently, the historical scores/margins cannot be assumed to be current production scores.
- Claimed historical results: **26/26 final matches with line splitting**, **11/26 without line splitting**; score 100/margin 29–52 on matched names; 21/21 image cases at 0.75×, 0.5× and 0.4×; JPEG quality 60 reportedly 21/21, 21/21 and 20/21 at those scales with no wrong accepted names; about 16 ms/crop on unspecified CPU; an approximately 0.2-second session load estimate. These are documentary claims, not new measurements.
- Current Tesseract A2 history: 21/21 image cases (19 positive titles, 2 negative dialogs), with Tesseract 5.3.4 in the historical manifest. The five no-offer negatives are **not part of the same A2 test**. Do not compare Tesseract "21/21" and Paddle "26/26" as if denominators were identical.
- No Silver rarity screenshots are present. The sample has repeated titles/crops, approximate Windows snips, no complete consecutive live three-card sequence, no real reroll evidence and no full DPI/animation/obstruction coverage.
- No per-image prediction stdout, process RSS/CPU logs, exact CPU identity, cold-start run distribution or independent v5 results were found in the inspected documentation and repository tree. A reproducible verification would require executing the pinned binary and retaining sanitized per-case output.

**Current benchmark execution status:** NOT RUN. The isolated environment has Tesseract and Pillow/Numpy/RapidFuzz, but lacks ONNX Runtime and the model binaries; the GitHub connector can read repository metadata/text but does not mount those binary fixtures into this runner, and the runner has no direct public network resolution. Thus no fair side-by-side test was executable here. Repository fixture availability should not be confused with current benchmark-runner file availability.

## 2. Candidate engines and available evidence

| Candidate | ARAM baseline: named / negatives | Speed and distribution evidence | Status |
|---|---|---|---|
| Tesseract current path (`pytesseract`, `eng`, PSM 7 then 6) | Historical **19/19** titles and **2/2** dialogs in A2; 5 additional negatives not assessed in that regression | No measured current p50/p95/cold-start/RSS/installer size. Separate executable and `eng.traineddata` unless bundled. Apache-2.0. CPU; Windows install or portable packaging possible, packaging not validated. | **KEEP authoritative** |
| `ch_PP-OCRv4_rec_infer.onnx` + direct ONNX Runtime CPU | Historical **19/19** titles + **7/7** negatives, with separate line-splitting/matching; no fresh reproduction | Reported ~16 ms/crop, model 10.86 MB, 0.2 s load estimate. Runtime and total installed size unmeasured. ONNX Runtime MIT; Paddle-derived model/third-party notices require validation. | **Benchmark challenger A** |
| `en_PP-OCRv5_mobile_rec` + ONNX Runtime CPU | **NOT TESTED** on Oracle data | Official PaddleOCR reports 85.25% on its own English recognition evaluation set vs 70.39% for `en_PP-OCRv4_mobile_rec` (both 7.5 MB). NOT transferable to the game's title crops. Validate model conversion, charset and decoder, exact hash, runtime and memory. | **Benchmark challenger B** |
| RapidOCR (`rapidocr` with ONNX Runtime), recognizer-only | **NOT TESTED** | Apache-2.0 wrapper; supports PP-OCRv4 and English PP-OCRv5 models. By default may load detection/orientation components; disable them for pre-cropped titles, disable network download at runtime and freeze assets. Measure *overhead for the same model* separately. | **Optional runtime comparison** |

Official PaddleOCR results are external reference figures, **not** a head-to-head ARAM experiment. GPU inference is supported through selected ONNX Runtime execution providers; CPU with one inference thread should be the first Windows target to avoid competing with League. DirectML/Windows ML GPU acceleration is optional and requires actual device/driver testing. All candidates can be designed for fully offline inference without administrator privileges *after appropriate packaging*; this is a design feasibility statement, not an accepted installer test.

A newer PP-OCRv6 family exists as of 2026. It is **excluded from this V1 candidate set** until a concrete, reproducible improvement on small League titles justifies extra scope.

## 3. Mandatory benchmark methodology

### A — Retrospective 26-image set (fixed, not an independent generalization set)
1. Load the **same** exact images and human-reviewed ground truths, SHA-256 verify every input and log source path/image dimensions; keep complete screenshots and personal data out of CI.
2. Freeze each recognizer's concrete model SHA-256, runtime version, character dictionary, preprocessing, ONNX providers and CPU thread count. Preload once, then distinguish model load from warm inference.
3. Report two experiments to avoid confounding:
   - **Recognition-only:** same title-line crops where feasible; raw string exactness after canonical whitespace/case normalization, plus CER for diagnostics.
   - **End-to-end pipeline:** each engine's documented production preprocessing followed by **the exact unchanged** `strict_match_title` (threshold 90, margin 8, same 328-item catalog) and unknown rejection.
4. Produce one row per case: fixture hash, expected name/None, physical slot if known, source scale/quality, raw OCR prediction, canonical prediction ID/None, score, margin, false-positive/confusion/abstention category, crop latency and batch latency. The benchmark's private results must not leak raw game images or player data.
5. Repeat on the same images at fixed 1.0, 0.75, 0.5 and 0.4 scale, JPEG q60, plus controlled DPI resampling. Label these **derived transformations**, not 4 independent real-world samples. Run cold starts separately from warm runs.
6. Specifically test a no-title black crop, dialog text over a card, empty/no-offer crop, 2-line wrapped text, lookalike titles and duplicated OCR names in two physical slots. No invisible card should receive a non-null ID.

### B — New independent set (future collection, different sessions)
- Prefer at least 50 fully ground-truthed *offers* (up to 150 card identities), including ≥10 Silver offers and meaningful Gold/Prismatic coverage, with multiple League sessions and 1080p/1440p and varied DPI/HUD settings. These are **proposed sampling targets**, not previous measurements or guaranteed statistical power.
- Include full 3-slot L/C/R frames, at least 10 unilateral rerolls, animation transition windows, dialogs, hover/occlusions, Alt+Tab, minimized/off-focus sessions, missing or changed WGC frames, near-duplicate names, tiny rendered fonts and cases where Tesseract and Paddle disagree.
- Use observations and human-labelled ground truth captured **before** comparing engine predictions; separate development/tuning cases from a locked hold-out to avoid tuning to known fixtures.
- For each engine compute exact raw-title accuracy, matched-ID correct, wrong-non-null rate, abstentions, false positives on no-offer/dialog, confusion matrix and per-rarity/per-slot counts. Show both micro and per-offer "all 3 correct" rates. Compare paired cases, not unrelated accuracies.

### C — Native in-game acceptance (cannot be inferred from CI)
- N1 remains a separate, unfinished Windows gate. In V1 shadow mode only, evaluate at least 30 real offers, include Silver, verify three mapped slots and individual rerolls; record original Tesseract decisions, Paddle candidate output, epoch and capture proof while never displaying or applying candidate decisions.
- Verify first unchanged three-card offer recognized within six seconds, including capture and temporal verification; measure elapsed time from observed card appearance to all recognized slots, not just isolated model inference.
- Test CPU/RAM impact while League and OP.GG run; full-screen/borderless, multiple DPI values, foreground transitions and WGC protection. A native PASS requires user-device evidence on the **exact candidate revision**, and cannot be claimed here.

**Timing and resource outputs (currently NOT MEASURED):** initial model creation/loading; warm model-only crop mean/p50/p95/max; full preprocessing+matching crop mean/p95/max; contiguous 3-card batch mean/p95/max; CPU percent above baseline, peak process RSS, GPU utilization if used, compressed/uncompressed installation delta, and whether an offline launch works as a normal user. Suggested engineering budgets for the future gate—not existing requirements—are a 3-card OCR p95 ≤250 ms, worst-case ≤500 ms, extra steady CPU ≤5 percentage points, and extra RSS ≤150 MB. The governing non-negotiable functional deadline remains the <=6-second *native* N1 detection window. Thresholds should be finalized against the actual Windows machine and must not incentivize unsafe confidence/confirmation shortcuts.

## 4. Integration architecture: minimum safe change

```text
WGC frame + fresh CaptureProof (or explicitly permitted safe mss_zorder)
  -> verified League client ROI -> physical left/centre/right title crops
  -> stable per-slot observations / controlled image hashes
  -> [OCR adapter: Tesseract | PP-OCRv4-ONNX | PP-OCRv5-English-ONNX]
       -> recognizer-specific preprocessing + raw lines
       -> current strict_match_title(catalog, threshold=90, margin=8)
  -> existing SlotTemporalTracker: 2 fresh stable readings, independently per L/C/R
  -> current capture/offer epoch and stale fencing
  -> offer identity only -> explicit user confirmation (OfferLedger)
  -> active_augment_ids() -> build recomputation
```

The adapter should return recognition **evidence**, not gameplay choices: engine ID, recognized text for in-process matching, measured duration and failure code. Preserve `SlotMatches` order/shape and existing pure matcher semantics. Comparison mode must use the same captured frames and an epoch-tagged copy, with Tesseract authoritative; the candidate runs in a bounded shadow lane and emits privacy-safe events containing IDs/agree/latency only. If inference finishes after an epoch transition, discard it. If there is a capture-proven invalid frame, no model should process it. Avoid a second capture stack and avoid changing `ScreenWatcher` scheduling/suspend contracts to accommodate an OCR model.

**Do not change:** WGC freshness and z-order fallback rules; per-card physical mapping; independent reroll checks; mandatory two reads; stale status clearing only on fresh complete re-verification or closed offer; offer/epoch checks on every mutation; manual identify vs manual confirm; no game inputs; only confirmed augments affecting builds; safe Settings diagnostics and user privacy; Riot policy restrictions.

### Tesseract fallback policy

Retain a **user-selectable, pre-session backup** during controlled rollout if packaging supports it and diagnostic value justifies its cost. Do **not** silently switch mid-offer on OCR disagreement or low confidence; unknown/disagreement should fail closed and request user confirmation/recovery. An automatic fallback could be considered only for a clearly logged initialization failure *before* any offer processing and only if Tesseract runtime readiness has independently passed. If final packaging proves a second OCR runtime too expensive or harmful, remove fallback by a separate evidence-backed decision. No unconditional permanent dual inference is recommended.

## 5. V1 implementation plan — explicitly **not started**

One authorized small draft PR per phase, stacked on the final approved N1 chain only after N1 is completed; each stage has test-first RED, then implementation GREEN, full suites and Windows Actions SUCCESS on the exact final SHA. Phase names below are planning suggestions rather than approvals.

| Subphase | Proposed narrow change | RED -> GREEN evidence |
|---|---|---|
| **V1.0** Evidence freeze | Correct ground-truth counts *after authorization*, manifest case IDs/hashes, pinned model and dependency BOM, repeatable offline benchmark runner | RED on missing/miscounted files and wrong hash; GREEN all 26 fixtures enumerated, no personal data |
| **V1.1** Repro only | Execute exact PP-OCRv4 historic model and Tesseract on 26 with current matching; retain sanitized per-case results. Run English v5 with its own decoder; compare raw vs matched correctness | RED fixture cases and explicit expected values first; GREEN reproducible per-case outputs with versions, no hidden skips |
| **V1.2** Adapter + preprocessing | `TitleRecognizer` protocol, Tesseract wrapper preserving current behavior, PP model loader with pinned SHA and lazy availability | RED for protocol, line-splitting, bad-hash, missing-model and two-line cases; GREEN matching/positions unchanged |
| **V1.3** Isolated shadow diagnostics | Bounded comparison lane, frozen input/epoch, typed diagnostic schema; Tesseract still decides | RED on mismatch, stale result, timeout and unavailable model; GREEN: no output/ledger/build mutation from challenger |
| **V1.4** Windows offline packaging proof | Run as a standard user with no network, model hash checked, CPU-only provider, controlled threads, Settings status | RED for missing/corrupted model and inability to start offline; GREEN on supported Windows configurations, measured startup/RSS/size |
| **V1.5** Independent test + native shadow gate | 50 independent offers planned, followed by 30 live shadow offers and N2-style checks after N1 | RED on wrong non-null, stale/epoch/reroll regressions; GREEN objective acceptance below with native evidence |
| **V1.6** Optional promotion | Only in a separately authorized change, choose better candidate as default; decide fallback policy | RED for rollback, mismatch and unavailable candidate; GREEN exact-head CI + full Windows native retest and easy rollback |

Recommended existing code touchpoints after authorization: `backend/collectors/slot_title_ocr.py` (current PSM 7/6), `screen_ocr.py`, `slot_temporal.py`, `window_capture.py` (read-only contract, no changes ideally), `backend/api/server.py`, `backend/preferences.py`, `backend/diagnostic_events.py`, and tests. The historical V1 blueprint proposes `ocr_engines.py`, `title_lines.py`, a local model fetch script, optional `ocr` dependency and third-party notices. Preserve or reduce scope rather than adding duplicate capture, state or matching components.

## 6. Promotion gates

**Hard gates:**
1. Same locked independent fixtures; title matched-ID accuracy ≥ currently validated Tesseract, not merely greater on the older 26. A candidate must not introduce a confirmed wrong non-null ID in native shadow, no-offer, dialog or reroll test cases; ambiguous results must abstain.
2. Physical L/C/R and independent rerolls correct after temporal verification, no duplicate-ID leakage, no wrong-epoch publication. Raw-title and matched-title errors analyzed separately, not concealed by fuzzy matching.
3. Preserve all existing two-read/WGC/stale/epoch/ledger tests; CI must report RED→GREEN and full exact-final-head Windows SUCCESS. No safe behavior may be relaxed for scores or timings.
4. **Native** three-card recognition within <=6 seconds and acceptable latency/resource budgets on Windows while League runs. CI-only is insufficient.
5. Bundled offline startup under non-admin permissions, model SHA/license/notices verified, no runtime downloads, deterministic fail-closed missing/corrupt model behavior.
6. Riot-policy review remains a distinct blocker for wider distribution. No model choice authorizes hidden data access or automated game input.

**Historical blueprint's extra N2 comparison rule:** at least 30 normal live offers, `agree >= 98%`, zero distinct non-null Paddle-vs-Tesseract identities and at least one Silver offer. Retain this as a reference constraint, but **do not use agreement as a substitute for truth**. Explicit human ground truth and greater Silver coverage are recommended before promotion. A single Silver example is too weak to support claims of Silver robustness.

## 7. Blocking dependencies and Windows tasks

- **N1 still OPEN:** PR #71 is an unrelated draft for JavaScript bootstrap tests/repair, not permission to start V1. Do not edit N1/PR #71 or merge.
- **Model & runner:** capture exact PP-OCRv4 and English PP-OCRv5 models, decoder/charset configs, checksums, ONNX Runtime package and both image manifests in a benchmark-capable isolated environment. Current session could not execute or re-hash them; no newly measured statistics exist.
- **Native League:** user-operated Windows sessions needed for first-6-seconds detection, Silver, individual reroll, animations, multi-DPI, borderless + OP.GG, capture proof, stale transitions, CPU/RAM/GPU and installer/non-admin/offline proof.
- **Privacy:** connected GitHub metadata reports the repository as **public**, contrary to its description as private in the task. No visibility change was authorized. Keep full screenshots, raw logs and user identifiers local/private.
- **Policy:** public distribution and dynamic recommendations remain under Riot review; an OCR replacement does not resolve those restrictions.

## Reference links

Internal (read-only references at the examined branch):
- [Repository instructions](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/blob/fix/n1-js-bootstrap/AGENTS.md)
- [Project continuity skill](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/blob/fix/n1-js-bootstrap/.agents/skills/continue-aram-oracle/SKILL.md)
- [V3 blueprint index](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/blob/fix/n1-js-bootstrap/docs/plans/ARAM_2026-11-20/README.md)
- [V1 blueprint](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/blob/fix/n1-js-bootstrap/docs/plans/ARAM_2026-11-20/features/blueprints_features/M-F_features.md)
- [Historical experiment report](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/blob/fix/n1-js-bootstrap/docs/plans/ARAM_2026-11-20/features/PLANO_FEATURES_2026-11-20.md)
- [Paddle evaluation reference script](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/blob/fix/n1-js-bootstrap/docs/plans/ARAM_2026-11-20/features/blueprints_features/fixtures/paddle_eval_reference.py)
- [Correction fixture manifest](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/blob/fix/n1-js-bootstrap/docs/plans/ARAM_2026-11-20/corrections/blueprints/fixtures/MANIFEST.md)
- [Tesseract A2 real-image test](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/blob/fix/n1-js-bootstrap/tests/test_real_title_crops_a2.py)
- [Title OCR and current matching](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/blob/fix/n1-js-bootstrap/backend/collectors/slot_title_ocr.py)
- [WGC capture proof](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/blob/fix/n1-js-bootstrap/backend/collectors/window_capture.py)
- [Temporal validation](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/blob/fix/n1-js-bootstrap/backend/collectors/slot_temporal.py)
- [Confirmed-only offer ledger](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/blob/fix/n1-js-bootstrap/backend/workflow/offer_ledger.py)
- [N1 native acceptance](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/blob/fix/n1-js-bootstrap/docs/N1_NATIVE_ACCEPTANCE.md)
- [Open N1 PR #71](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/71)

External official sources:
- [PaddleOCR recognition model comparison, including English-specific v4/v5 sizes and metrics](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/module_usage/text_recognition.en.md)
- [PaddleOCR PP-OCRv5 technical introduction](https://www.paddleocr.ai/v3.3.0/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html)
- [RapidOCR official model list](https://github.com/RapidAI/RapidOCRDocs/blob/main/docs/model_list.md)
- [RapidOCR repository and Apache-2.0 licensing](https://github.com/RapidAI/RapidOCR)
- [RapidOCR installation: ONNX Runtime optional dependency in newer releases](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/install/)
- [rapidocr-onnxruntime 1.4.4 original PyPI wheel](https://pypi.org/project/rapidocr-onnxruntime/1.4.4/)
- [ONNX Runtime Windows providers](https://onnxruntime.ai/docs/get-started/with-windows.html)
- [ONNX Runtime MIT license](https://github.com/microsoft/onnxruntime/blob/main/LICENSE)
- [Tesseract documentation and Apache-2.0 license](https://tesseract-ocr.github.io/tessdoc/)