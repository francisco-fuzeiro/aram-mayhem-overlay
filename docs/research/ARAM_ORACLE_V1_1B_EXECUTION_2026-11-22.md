# ARAM Oracle V1.1b — OCR safety and Windows readiness execution ledger

**Date:** 2026-11-22
**Branch:** `research/v1-1b-ocr-safety-windows-20261122`
**Draft PR:** [#77](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/77)
**Parent:** rules-only draft #75, itself stacked on measured V1.1 draft #74, then investigation draft #72.
**Production engine:** Tesseract **unchanged**. **V1.2: NO-GO**.
**Protected:** N1 draft #71, `main`, product runtime, 90/8 matcher, WGC, epochs/stale, OfferLedger, builds and UI.

## 1. Evidence provenance

The historical V1.1 real inference is documented in
[the exact-head benchmark](ARAM_ORACLE_V1_1_OCR_BENCHMARK_2026-11-22.md)
and Actions [#44976580610](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44976580610).
Its approved dataset is **26 frozen PNGs**: 19 title observations, two dialogs
and five no-offer negatives. The 1,456 earlier engine/transform evaluations
are strongly correlated repeated views of that same dataset. V1.1b does not
relabel them as 1,456 independent observations.

| V1.1 original condition (previously measured) | Titles accepted correctly | Correct negatives | Wrong accepted IDs | Raw exact |
|---|---:|---:|---:|---:|
| Tesseract PSM7 then PSM6 (production) | 19/19 | 7/7 | 0 | 19/19 |
| v4 ONNX with historical line split and fixed 90/8 | 19/19 | 7/7 | 0 | 17/19 |
| v4 ONNX with no line split | 4/19 | 7/7 | 0 | 0/19 |
| RapidOCR v4 recognizer-only, **same v4 weights** | 19/19 | 7/7 | 0 | 19/19 |
| English v5 ONNX, direct reference preprocessing | 8/19 | 7/7 | 0 | 8/19 |

- Repeated original and transformed V1.1 conditions: zero wrong accepted IDs
  and zero negative false positives; those are dataset-specific observations.
- Notable derived-only safe false rejections: 40% JPEG60 v4/Rapid v4 each
  rejects one `Get Jinxed`; Tesseract rejects two `Donation` occurrences.
  English v5 improves to 17/19 on some derived resizes; these are
  **preprocessing hypotheses**, not independent successes.
- Two-line original titles: v4/Rapid/Tesseract 2/2, English v5 0/2.
  Assigned original title positions: left 3, centre 4, right 4; eight other
  title snips are not physical slot assignments.

## 2. New V1.1b isolated research implementation

- `benchmarks/ocr_v11b/validation.py`: metadata/provenance/consent gates
  for true independent holdout, original hash re-use protection, duplicate
  detection, separate wrong-ID/negative-FP/abstention counting.
- `test_validation.py` and `test_controlled.py`: test-first integrity
  and tensor preprocessing contracts, including Windows Actions smoke tests.
- `controlled.py` and `run_inference.py`: real pinned ONNX 26-image
  preprocessing ablations; compare RGB/BGR, PIL/OpenCV,
  round/ceil recognition widths and v4 adaptive width against the exact
  RapidOCR 1.4.4 recognizer. No replacement model, decoder guess, runtime
  integration or matching threshold modification.
- `stress_matcher.py`: deterministic **synthetic text only** noisy-title
  attacks against the current pinned strict matcher. These are useful
  adversarial risk probes, never treated as OCR samples, real-world false
  positive rates or independent evidence.
- `run_holdout.py`: **local-only**, SHA-verified, user-approved unseen
  holdout recognition with per-slot/per-offer safety accounting. No approved
  new holdout samples have been supplied; **BLOCKED, not executed**.
- `profile_windows.py`: opt-in separate-process readiness benchmark with
  model load, cold process readiness, warm per-crop/three-crop distributions,
  processing/matching, sampled CPU/RSS including process children, model/
  installed-distribution byte sizes. Does not open League or add app deps.
- `summarize.py` and `.github/workflows/ocr-benchmark-v11b.yml`:
  pinned model downloads, Windows/Linux Actions, isolated metrics artifacts
  and privacy-safe aggregate logging; runners are **not the user's PC**.

### Model checks

- Direct PP-OCRv4 ONNX SHA-256:
  `48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b`.
- English PP-OCRv5 ONNX SHA-256:
  `c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8`.
- Reference exact pinned N1 SHA:
  `7624b27c1d025c4183c2a78aa11609dda45ecf71`.
- RapidOCR v4 is **not a separate model**. Its tag `v1.4.4` source
  documents BGR OpenCV input, width rounded upward via `ceil`,
  adaptable recognition width, `[-1,1]` normalization, zero padding
  and CTC decoding (external exact tag:
  https://github.com/RapidAI/RapidOCR/blob/v1.4.4/python/rapidocr_onnxruntime/ch_ppocr_rec/text_recognize.py).
  Tensor comparison against this pinned implementation must be checked
  on actual inference output, rather than treating modern RapidOCR main
  code as historical evidence.

## 3. Actual test progression

- **RED on test-only SHA** `5bd3fa1365bf387590cb10d01775e0e728d07a43`:
  [Windows/Linux Actions #44979601783](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44979601783)
  failed on the intentionally missing provenance/safety module.
- **Initial GREEN** `33e2647d265f1721aa4ae80c172c135682d17933`:
  [Actions #44979628353](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44979628353)
  passed the provenance/false-identity integrity tests.
- **Extended safety-test setup failure**: OpenCV-dependent pure test was
  missing its package in the isolated safety job; fixed in workflow (no
  product changes). Linux and Windows safety jobs subsequently passed.
- **Windows fixture-byte pitfall**: automatic CRLF checkout conversion
  altered the ground truth JSON size/hash on a disposable Windows Actions
  runner. The pinned data checker rejected it, as intended. Fix: set
  `core.autocrlf=false` *before the read-only reference checkout*.
  This is a reproducibility/infrastructure correction, not an OCR result.
- **Early V1.1b real Linux controlled run** on original frozen crops,
  [Actions #44979983066](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44979983066):
  v4 RGB/BGR × PIL/OpenCV 19/19 matched, 7/7 negatives rejected, zero
  wrong IDs/false positives; English v5 same four color/interpolation
  variants 8/19 matched with 11 safe rejects, 7/7 correct negatives.
  This run predates the newer ceil/adaptive-width experiments and is
  **not** final exact-head verification.

**Final exact-head CI, final ceil/adaptive preprocessing parity,
synthetic text stress and isolated CPU/RSS numerical annex:** record after
the corresponding latest run completes and is reviewed. Do not infer PASS
from a queued or incomplete job.

## 4. Statistical limitations and safety

There is **no newly approved independent offer**, hence the independent
holdout is `BLOCKED`. Merely using a different engine/configuration on the
same 26 images, synthetic text, three crops from the same frame, or resizing
does not increase the independent sample size.

Even 0 observed errors in 19 historical positives gives a one-sided 95%
binomial upper bound of approximately **14.6%** for a hypothetical
independent identically distributed wrong-accepted event. Seven negatives
give approximately **34.8%**; those bounds are optimistic because the
retrospective samples are not representative nor independent in the sense
required for new-match performance. These are mathematical illustrations,
**not** live error-rate estimates.

A title matcher can accept an exact augment name even if that text appears
in a hypothetical dialog rather than an offer. This **synthetic matching
probe** underlines the indispensable existing presence/capture/temporal
guards; it does not imply an observed false-positive in a live game.
Correct safe abstentions and wrong accepted identities must always be
reported separately.

## 5. Device/policy blockers and decision

**NOT TESTED on the user's Windows:** true native League OCR timing
from card arrival (<=6 seconds), WGC capture proof, left/centre/right
multi-card association, unilateral rerolls, Silver and rarity coverage,
animating/overlapping dialogs, OP.GG interference, focus/Alt+Tab,
DPI/resolution/HUD variations, game-load CPU/RSS/FPS, installer cold start
and non-admin offline use. Windows Actions VM experiments are isolated
benchmarks, not substitutes.

**N1 native acceptance** for draft PR #71 is still OPEN and protected.
Riot public distribution/policy gate is unresolved. No engine or
recommendation promotion is authorized.

**Current decision: NO-GO to start V1.2.** The prior evidence made direct
PP-OCRv4 with line splitting the leading offline challenger, but a
candidate recommendation must account for final V1.1b measurements and
still carries **LOW confidence for unseen live matches**. Tesseract stays
authoritative. Only propose V1.2 later upon a sufficiently representative
approved independent holdout, negative/adversarial safety evidence,
measured user-Windows feasibility, N1 native acceptance, policy review
and explicit separate user approval.

## 6. Next chat continuity

Begin with `.agents/skills/continue-aram-oracle-ocr/SKILL.md` on this
research branch, this ledger, the V1.1 evidence, and current exact-head
Actions/PR status. Continue only unfulfilled V1.1b gates, never change
production or infer success from mere CI initiation. Use
`benchmarks/ocr_v11b/README.md` for opt-in local Windows commands and
private holdout instructions. Keep PR #77 draft and do not merge.
