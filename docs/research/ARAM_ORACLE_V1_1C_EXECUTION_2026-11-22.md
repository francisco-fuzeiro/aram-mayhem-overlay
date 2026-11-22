# ARAM Oracle OCR V1.1c — native readiness, safety and V1.2 decision ledger

**Date:** 2026-11-22. **Phase:** V1.1c research only.
**Branch:** research/v1-1c-ocr-native-readiness-20261122.
**Draft PR:** https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/79
**Exact research parent:** V1.1b draft #77 at d95a29d443304d26bc14807d2033a50698cbd8ac.
**Reference gameplay matcher:** immutable N1 7624b27c1d025c4183c2a78aa11609dda45ecf71.
**Production recognizer:** Tesseract unchanged. **V1.2: NO-GO**.

## 1. Provenance and completed V1.1b closure

Reference CI https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44980628428
completed SUCCESS on exact #77 SHA d95a29d443304d26bc14807d2033a50698cbd8ac:
Linux pure safety PASS; Windows 2022 pure safety PASS; Linux real pinned
ONNX inference and resource profile PASS; Windows 2022 pinned real
inference and profile PASS. Canonical **numeric** returned IDs were
compared against the catalog IDs derived from human-confirmed titles.
This does not independently verify all current Riot/League alias-ID
definitions. All measured runs use the unchanged 90/8 title matcher.

The V1.1b benchmark reported real recognizer checksums:
- v4 SHA-256: 48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b
- English v5 SHA-256: c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8
- v4 ONNX 10,857,958 bytes; English v5 ONNX 7,872,351 bytes.

The original source of truth is the V1.1b execution ledger and its
artifacts, not a repeated current-match measurement. Numeric entries
below are inherited observations from the successful exact V1.1b study.

## 2. Known original, transformed, synthetic and independent evidence

| Dataset / condition | Correct canonical title IDs | Correct negative rejections | Wrong accepted | Negative false positives | Safe title rejections | Raw exact |
|---|---:|---:|---:|---:|---:|---:|
| Originals — Tesseract | 19/19 | 7/7 | 0 | 0 | 0 | 19/19 |
| Originals — direct v4 fixed split | 19/19 | 7/7 | 0 | 0 | 0 | 17/19 |
| Originals — direct v4 adaptive split | 19/19 | 7/7 | 0 | 0 | 0 | 19/19 |
| Originals — RapidOCR v4 same weights | 19/19 | 7/7 | 0 | 0 | 0 | 19/19 |
| Originals — English v5 tested | 8/19 | 7/7 | 0 | 0 | 11 | 8/19 |

Every original condition uses the **same 26 retrospective PNGs**,
including 19 augment title crops, two dialogs and five no-offer samples;
the 19 positive titles include two two-line originals. RapidOCR v4 uses
the *same pinned v4 weights*, with a different preprocessor. Direct
BGR/OpenCV/ceil/adaptive preprocessing matched the pinned RapidOCR
input tensors on 36/36 line chunks, with zero maximum absolute tensor
difference, and 19/36 required wider than fixed width 448.

**Transformed derived images:** historical V1.1 had 1,456 correlated
engine/scale/compression decisions, not 1,456 independent samples.
Across the evaluated historical conditions no incorrect accepted ID
or negative-image false positive was reported. At derived 40% JPEG60,
Tesseract safely rejected two Donation occurrences; direct v4 and
RapidOCR v4 safely rejected one Get Jinxed each. English v5 sometimes
reached 17/19 titles on some derived resizes, *not* the original 19/19.

**Synthetic text-only:** 328/328 exact catalog titles accepted under
90/8; corrupted-title stress generated 124 safe rejections and 0 wrong
accepted numeric IDs. This is **not** image OCR, visual offer detection,
a real match or independent game evidence. An exact augment title in a
hypothetical no-offer dialog would pass the matcher alone, reinforcing
the importance of separately proven offer-presence fencing.

**Independent unseen game samples:** 0 newly supplied or approved;
**BLOCKED**, no measured independent accuracy or false-positive rate.
Do not substitute newer preprocessing variants, altered JPEGs or
consecutive cropped titles from the same frame as independent offers.
The historical 19 successes have only LOW statistical generalizability.
For zero errors in 19 genuinely independent Bernoulli trials the
one-sided 95% upper bound would still be around 14.6%; seven negatives
would permit around 34.8%. Even those mathematical illustrations are
too optimistic for correlated non-random retrospective images.

## 3. Isolated performance, not a native game measurement

Measured on V1.1b Linux GitHub Actions and disposable Windows Actions
VMs, 26 original crops, eight artificial sequential three-crop batches,
one isolated process per engine. Separate ablation runs must not be
mistaken for these profiling results.

| Host / recognizer | Crop mean/p50/p95/max ms | Three crops mean/p95 ms | Cold ready ms | Model load ms | Peak sampled RSS MiB | Process-tree CPU seconds |
|---|---|---|---:|---:|---:|---:|
| Linux Tesseract | 117.0/81.9/223.4/258.8 | 241.0/252.9 | 201.6 | N/A | 89.0 | 5.41 |
| Linux direct v4 fixed | 40.4/57.8/58.5/87.3 | 176.4/178.7 | 230.0 | 56.9 | 109.2 | 2.85 |
| Linux RapidOCR v4 | 57.1/70.5/138.1/160.8 | 220.0/221.1 | 250.8 | 62.4 | 169.0 | 3.71 |
| Linux English v5 | 21.8/31.1/31.9/46.3 | 96.6/97.6 | 211.2 | 42.3 | 105.0 | 1.66 |
| Windows Actions Tesseract | 150.1/100.7/276.5/490.8 | 289.6/291.3 | 240.1 | N/A | 65.3 | 6.64 |
| Windows Actions direct v4 fixed | 49.8/71.2/72.5/107.7 | 217.1/218.8 | 388.4 | 112.4 | 85.3 | 3.72 |
| Windows Actions RapidOCR v4 | 95.3/87.5/273.4/321.7 | 258.7/259.6 | 431.9 | 119.8 | 93.5 | 5.53 |
| Windows Actions English v5 | 32.5/46.4/47.8/69.0 | 140.6/142.0 | 364.3 | 101.2 | 75.2 | 2.59 |

Tesseract spawns short subprocesses, some of which may be missed by
10-ms sampling. RSS process-tree sums can double count shared mappings.
Reported CPU times are total sampled process-tree CPU and cannot be
interpreted as extra game CPU. Fixed direct v4 was faster than the
RapidOCR wrapper on both measured hosts but its relative speed in
League is unmeasured; adaptive direct v4 cold/start CPU/RSS is not
yet separately profiled in this table. There is no measured Windows
installer incremental payload or native full-app cold start.

## 4. V1.1c implemented research-only tools and tests

- benchmarks/ocr_v11c/Run-OCRBenchmark.ps1: user-opt-in, one-command
  Windows 3.11 / English Tesseract preflight, separate cached venv,
  exact pinned SHA models, read-only reference and original-only tests,
  synthetic stress, controlled variants, isolated process timing,
  CPU/RSS and readable local report. Internet may be used **once for
  setup**; offline inference uses verified local data. -Offline forbids
  downloads and missing cache silently becoming online requests.
- benchmarks/ocr_v11c/manifest.py: human-verified CSV labels before
  prediction; local dev vs sealed holdout, session split, raw/full
  SHA-256, decoded-pixel duplicates, frame/slot duplicates and explicit
  privacy approval. No uploads or game process interaction.
- benchmarks/ocr_v11c/grouping.py and isolated holdout runner change:
  correct an assessment risk where reroll frames sharing an offer ID
  could be silently combined into one fictitious complete three-card
  success. Simultaneous offers now require all physical slots from
  **one session and one source_frame**, with duplicate slot rejection.
  A legacy holdout without frame evidence can never claim a complete
  three-card offer.
- Local-only holdout case audit now includes raw OCR, normalized OCR,
  the actual and expected canonical IDs, matching score, latency,
  rarity/slot/two-line aggregates and wrong/rejected error classes.
  These detailed private reports must **never** be uploaded.
- benchmarks/ocr_v11c/render_report.py: comprehensible summaries of
  warm per-crop and three-crop distributions, CPU, RSS and footprints;
  never claims user-device validation for CI outputs.
- benchmarks/ocr_v11c/test_v11c.py: test-first safety contracts for
  label consent, split leakage, duplicate SHA/pixels, frame grouping,
  and provenance in the readable report.
- .github/workflows/ocr-benchmark-v11b.yml extended on this **child
  branch only** for v11c Linux+Windows tests and PowerShell parser,
  preserving pinned real-model jobs.

The executable instructions and capture/test protocol are in
benchmarks/ocr_v11c/README.md. No new captures or labels have yet been
supplied by the user, and V1.1c did not run anything on the user's PC.

**Tests-first evidence:** missing-module RED on Linux and Windows at
bd5e97a20848423c2444d0aa5e20663b987a2e13,
https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44981391025.
Additional reroll-group regression tests were added before the grouping
implementation. Check later GitHub Actions on the exact final PR #79
HEAD for GREEN before research acceptance; CI logs, not commit
descriptions, determine PASS/FAIL.

## 5. Outstanding native and external validity gates

- **BLOCKED:** approved genuine unseen independent cropped title
  offers (all positions, rarity including Silver, two-line, close
  catalog names), carefully separated development and holdout sessions.
- **NOT TESTED on user Windows:** new local script, cached/offline mode,
  exact Python/Tesseract detection and real CPU/RSS/cold-start
  results. A Windows Actions VM is never this device.
- **NOT TESTED in League:** complete triple cards, unilateral
  rerolls/transition/animation, no-offer and dialogs, focus/Alt+Tab,
  capture/WGC, different DPI/resolution, OP.GG simultaneous load and
  response within the first six seconds; real FPS, app installer.
- **OPEN:** N1 native acceptance under draft #71, separate from OCR.
- **OPEN:** Riot policy / permitted scope of dynamic recommendations
  for any public overlay release, unrelated to this isolated benchmark.

## 6. Candidate selection and conditional future gate

**Best offline challenger: PP-OCRv4 direct with line splitting,
fixed width.** It matches 19/19 original canonical IDs while exhibiting
lower per-crop isolated latency than wrapper RapidOCR on the observed
Linux/Windows Actions machines. Adaptive-width v4 is worth a separate
native quality/cost comparison, because it matches RapidOCR's 19/19
raw-exact texts but requires wider tensors on many line chunks.
RapidOCR uses the same model weights and introduces wrapper maintenance;
English v5 is not competitive in the original tested configuration
(11 safe rejections). Tesseract remains production.

**Confidence:** HIGH for retrospective original reproduction and
tensor parity; MODERATE for isolated-runner *relative* latency; LOW
for unseen League OCR quality and user-device performance.

**V1.2 NO-GO.** To propose a future **separately authorized**
V1.2, require a fixed candidate/configuration, independent holdout
with zero wrong non-null IDs and zero negative false positives in a
representative multi-session test matrix, quantified uncertainty and
safe false-rejection costs, demonstrable same-frame three-card/reroll
behavior, actual user-Windows game load/startup/FPS and OP.GG evidence,
N1 native acceptance, and a Riot policy review. At least one accepted
wrong ID requires investigation, not promotion. No finite small set
proves a zero true error rate; use separate safety/abstention gates.
Never change strict matcher 90/8 or WGC/epochs in this research phase.
