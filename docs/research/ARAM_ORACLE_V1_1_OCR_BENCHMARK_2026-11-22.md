# ARAM Oracle V1.1 — Independent reproduction, benchmark and decision

**Date:** 2026-11-22. **Status:** OFFLINE REPRODUCTION MEASURED; NO ENGINE PROMOTION; V1.2 NOT AUTHORIZED.

## Provenance and integrity
- Research branch: `research/v1-1-ocr-independent-benchmark-20261122`, draft PR #74 stacked on draft PR #72; production and N1 #71 were not edited.
- Exact read-only production matching and approved fixture snapshot: `7624b27c1d025c4183c2a78aa11609dda45ecf71`.
- Executed benchmark runner SHA: `c1e6db237ded9e5aaf1ddb6a523eecff02021d7e`; exact push [successful GitHub Actions run #44976307190](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44976307190). The check ran nine integrity tests and real inference; the sanitized JSON and report are attached as its artifact.
- Tests-only RED: `42c54cc574db205d1338f3fa393d2b5afc49c617`, [run #44974964103](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44974964103): 9 expected failures. Final runner GREEN: 9 unit integrity tests passed, full real inference completed, 1,456 per-case/condition records and complete artifact produced; no skipped/invented model inferences.
- The v4 model is extracted from the exact `rapidocr-onnxruntime==1.4.4` distribution wheel and verified at its full SHA-256. V5 English is downloaded from the model-publisher versioned RapidOCR v3.9.2 ModelScope path and verified at its full SHA-256. Character dictionaries are read from ONNX metadata, with strict runtime CTC class-count checks: **v4: 6625 classes**, **v5: 438 classes**. A mismatched file/model/decoder fails closed.
- All 26 approved PNGs, two ground-truth JSONs and the 328-entry catalog are checked against the archived v3 size/SHA-256 prefix manifest; full SHA-256 values for each image are recorded in `cases.json`. This archival manifest has 16-character SHA-256 prefixes, NOT complete expected digests; don't overstate those checks as full-length reference comparisons. Full ONNX model SHA-256 checks do use all 64 hexadecimal characters.

## Independent findings
- **Historical v4 claim reproduced:** 19/19 correct title IDs + 7/7 negative rejections = **26/26**, with line splitting, both with the historical matching and today's production `strict_match_title` (fixed threshold 90, margin 8). Without line splitting, 4/19 titles + 7/7 negatives = **11/26**. This is the original retrospective dataset, not a generalization result.
- **Raw recognition vs final match:** current Tesseract raw 19/19; direct v4 raw 17/19 and final 19/19 (two `Take'em Down Down Down` samples acquire punctuation noise, corrected by production normalization); RapidOCR v4 raw 19/19 and final 19/19; v5 English raw/final 8/19 on originals. Normalization and matching must never be conflated with raw engine accuracy.
- **Safety:** zero wrong IDs accepted and zero false-positive negative images over all 1,456 engine/transform observations. The dependent conditions do NOT prove a low live false-positive rate; priority remains safe rejection rather than an erroneous card identity.
- **Degradation:** on derived 40% JPEG60, v4 direct/RapidOCR each safely reject `Get Jinxed` once (18/19 titles correct), whereas Tesseract safely rejects two `Donation` occurrences (17/19). V5 English rises to 17/19 on 75%/50%/40% variants (2 two-line `Take'em Down Down Down` rejections persist); this is sensitivity to preprocessing, not proof that the v5 architecture is universally worse.
- **Physical positions:** left 3, centre 4, right 4 positive original 1440p crops are individually correct for Tesseract/v4/RapidOCR. Eight snips are not calibrated to any physical card slot. Two double-line examples are correct for Tesseract/v4/RapidOCR; v5 English rejects them. Seven original negative images (two dialog, five no-offer) are rejected by all.
- **Performance:** Intel Xeon 6975P-C GitHub-hosted Linux VM, 4 logical cores, Python 3.11.18, Tesseract 5.3.4, ONNX Runtime 1.20.1 CPU/one thread. Measured in this runner on original PNGs: mean/p95 total crop latency Tesseract **113.22/210.40 ms**, v4 direct split **40.38/58.86 ms**, v5 English **20.81/31.09 ms**, RapidOCR same v4 weights **54.43/121.42 ms**. Eight consecutive-three-crop repetitions: **230.40**, **175.56**, **90.75**, **223.56 ms** mean respectively. Measurements are NOT benchmarks on the user's Windows PC and do not represent live gaming load.
- **Model session loads:** v4 56.628 ms, English v5 36.759 ms, RapidOCR v4 52.240 ms. Those are loader stage times, NOT complete cold process startup including imports and dependencies. One shared process held every loaded model; RSS snapshots are NOT isolated memory footprints. System CPU for child Tesseract processes is not correctly represented by Python-parent-only process CPU.
- **Installed distribution sizes:** ONNX Runtime 39.88 MiB, RapidOCR ONNX package 15.65 MiB, NumPy 74.40 MiB, Pillow 13.43 MiB, RapidFuzz 11.73 MiB, psutil 2.25 MiB, pytesseract 0.07 MiB on the Linux runner. Some are existing/shared dependencies. An incremental Windows installation or installer payload was not measured.
- **RapidOCR significance:** same pinned v4 weights; recognizer-only, not a separate model-accuracy candidate. On original crops it yields 19/19 raw text against 17/19 for the direct RGB reference; its own recognizer preprocessing differs, which may explain the observed improvement. On this executor direct v4 was faster than the wrapper. No evidence of an overall RapidOCR advantage sufficient for automatic promotion.

## Decision and remaining gate
**Reproduction: PASS (high confidence for this retrospective dataset). Candidate ranking for isolated follow-up: PP-OCRv4 direct with line splitting, first; RapidOCR v4 for preprocessing investigation; retain Tesseract as unchanged production engine. Confidence for unseen in-game offers remains LOW.**

**V1.2 initiation: NO-GO now**, until independent unseen/holdout offers, native Windows/League/OP.GG measurements, full three-card sequences, rerolls, capture focus/DPI robustness, and N1 native acceptance have evidence and the user separately authorizes V1.2. Riot policy/public distribution validation remains an independent gate. PR #71 and N1 remain open and unchanged. There is no engine promotion, no main merge, no production dependency added, and no new gameplay code.

## Complete measured per-case and metric annex

The annex below is generated from actual `summary.json` and `cases.json` (not from the historical claims). Every original error and every derived false rejection is listed, including the score and margin.

---

# ARAM Oracle V1.1 — Measured OCR comparison

Generated from real frozen-asset inference. This is not a historical estimate.
**Source snapshot:** `7624b27c1d025c4183c2a78aa11609dda45ecf71`
**CPU/OS:** x86_64, 4 logical cores, Linux-7.0.0-1014-aws-x86_64-with-glibc2.39
**Python/Tesseract:** 3.11.18 / 5.3.4
**ONNX:** 1.20.1; CPUExecutionProvider, one thread
**Models:** v4 `48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b`, v5 English `c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8`
**Verified original fixtures:** {'title': 19, 'dialog': 2, 'no_offer': 5} from a fixed 26-image set; 328 catalog names

## Original 100% PNGs — decision-level accuracy

| Engine | Titles correct/19 | Accepted wrong | Negative rejected/7 | False positive | False rejection | Raw exact/19 | Mean ms | P95 ms | Max ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| tesseract | 19/19 | 0 | 7/7 | 0 | 0 | 19/19 | 113.22 | 210.40 | 246.66 |
| ppocrv4_split | 19/19 | 0 | 7/7 | 0 | 0 | 17/19 | 40.38 | 58.86 | 86.47 |
| ppocrv4_full | 4/19 | 0 | 7/7 | 0 | 15 | 0/19 | 28.94 | 29.22 | 29.25 |
| ppocrv4_historical_split | 19/19 | 0 | 7/7 | 0 | 0 | 17/19 | 39.96 | 58.24 | 86.11 |
| ppocrv4_historical_full | 4/19 | 0 | 7/7 | 0 | 15 | 0/19 | 29.02 | 29.38 | 29.39 |
| ppocrv5_en_split | 8/19 | 0 | 7/7 | 0 | 11 | 8/19 | 20.81 | 31.09 | 44.77 |
| rapidocr_v4_split | 19/19 | 0 | 7/7 | 0 | 0 | 19/19 | 54.43 | 121.42 | 134.68 |

## Derived transformations (not independent samples)

| Engine | Scale | Compression | Correct titles/19 | Wrong accepted | Negative rejection/7 | FP | Abstained title | Raw exact/19 | Mean ms | P95 ms |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| tesseract | 1.00 | PNG | 19 | 0 | 7 | 0 | 0 | 19 | 113.22 | 210.40 |
| tesseract | 1.00 | JPEG60 | 19 | 0 | 7 | 0 | 0 | 19 | 114.31 | 220.34 |
| tesseract | 0.75 | PNG | 19 | 0 | 7 | 0 | 0 | 19 | 104.69 | 179.34 |
| tesseract | 0.75 | JPEG60 | 19 | 0 | 7 | 0 | 0 | 19 | 105.12 | 179.66 |
| tesseract | 0.50 | PNG | 19 | 0 | 7 | 0 | 0 | 14 | 95.95 | 148.89 |
| tesseract | 0.50 | JPEG60 | 19 | 0 | 7 | 0 | 0 | 14 | 103.56 | 151.76 |
| tesseract | 0.40 | PNG | 17 | 0 | 7 | 0 | 2 | 14 | 101.92 | 147.51 |
| tesseract | 0.40 | JPEG60 | 17 | 0 | 7 | 0 | 2 | 14 | 102.84 | 149.66 |
| ppocrv4_split | 1.00 | PNG | 19 | 0 | 7 | 0 | 0 | 17 | 40.38 | 58.86 |
| ppocrv4_split | 1.00 | JPEG60 | 19 | 0 | 7 | 0 | 0 | 13 | 39.06 | 58.39 |
| ppocrv4_split | 0.75 | PNG | 19 | 0 | 7 | 0 | 0 | 7 | 25.88 | 57.98 |
| ppocrv4_split | 0.75 | JPEG60 | 19 | 0 | 7 | 0 | 0 | 10 | 25.83 | 57.75 |
| ppocrv4_split | 0.50 | PNG | 19 | 0 | 7 | 0 | 0 | 6 | 23.57 | 57.76 |
| ppocrv4_split | 0.50 | JPEG60 | 19 | 0 | 7 | 0 | 0 | 9 | 23.50 | 57.77 |
| ppocrv4_split | 0.40 | PNG | 19 | 0 | 7 | 0 | 0 | 8 | 23.55 | 57.84 |
| ppocrv4_split | 0.40 | JPEG60 | 18 | 0 | 7 | 0 | 1 | 9 | 23.55 | 57.80 |
| ppocrv4_full | 1.00 | PNG | 4 | 0 | 7 | 0 | 15 | 0 | 28.94 | 29.22 |
| ppocrv4_full | 1.00 | JPEG60 | 4 | 0 | 7 | 0 | 15 | 0 | 28.95 | 29.28 |
| ppocrv4_full | 0.75 | PNG | 4 | 0 | 7 | 0 | 15 | 0 | 28.93 | 29.29 |
| ppocrv4_full | 0.75 | JPEG60 | 6 | 0 | 7 | 0 | 13 | 0 | 28.96 | 29.21 |
| ppocrv4_full | 0.50 | PNG | 4 | 0 | 7 | 0 | 15 | 0 | 28.83 | 29.16 |
| ppocrv4_full | 0.50 | JPEG60 | 3 | 0 | 7 | 0 | 16 | 1 | 28.80 | 29.13 |
| ppocrv4_full | 0.40 | PNG | 4 | 0 | 7 | 0 | 15 | 1 | 28.86 | 29.16 |
| ppocrv4_full | 0.40 | JPEG60 | 3 | 0 | 7 | 0 | 16 | 1 | 28.87 | 29.27 |
| ppocrv4_historical_split | 1.00 | PNG | 19 | 0 | 7 | 0 | 0 | 17 | 39.96 | 58.24 |
| ppocrv4_historical_split | 1.00 | JPEG60 | 19 | 0 | 7 | 0 | 0 | 13 | 38.89 | 58.11 |
| ppocrv4_historical_split | 0.75 | PNG | 19 | 0 | 7 | 0 | 0 | 7 | 25.74 | 57.44 |
| ppocrv4_historical_split | 0.75 | JPEG60 | 19 | 0 | 7 | 0 | 0 | 10 | 25.67 | 57.55 |
| ppocrv4_historical_split | 0.50 | PNG | 19 | 0 | 7 | 0 | 0 | 6 | 23.43 | 57.36 |
| ppocrv4_historical_split | 0.50 | JPEG60 | 19 | 0 | 7 | 0 | 0 | 9 | 23.39 | 57.18 |
| ppocrv4_historical_split | 0.40 | PNG | 19 | 0 | 7 | 0 | 0 | 8 | 23.39 | 57.35 |
| ppocrv4_historical_split | 0.40 | JPEG60 | 18 | 0 | 7 | 0 | 1 | 9 | 23.35 | 57.33 |
| ppocrv4_historical_full | 1.00 | PNG | 4 | 0 | 7 | 0 | 15 | 0 | 29.02 | 29.38 |
| ppocrv4_historical_full | 1.00 | JPEG60 | 4 | 0 | 7 | 0 | 15 | 0 | 29.13 | 29.72 |
| ppocrv4_historical_full | 0.75 | PNG | 4 | 0 | 7 | 0 | 15 | 0 | 29.15 | 29.49 |
| ppocrv4_historical_full | 0.75 | JPEG60 | 6 | 0 | 7 | 0 | 13 | 0 | 29.00 | 29.41 |
| ppocrv4_historical_full | 0.50 | PNG | 4 | 0 | 7 | 0 | 15 | 0 | 28.91 | 29.33 |
| ppocrv4_historical_full | 0.50 | JPEG60 | 3 | 0 | 7 | 0 | 16 | 1 | 28.91 | 29.22 |
| ppocrv4_historical_full | 0.40 | PNG | 4 | 0 | 7 | 0 | 15 | 1 | 28.93 | 29.33 |
| ppocrv4_historical_full | 0.40 | JPEG60 | 3 | 0 | 7 | 0 | 16 | 1 | 28.96 | 29.29 |
| ppocrv5_en_split | 1.00 | PNG | 8 | 0 | 7 | 0 | 11 | 8 | 20.81 | 31.09 |
| ppocrv5_en_split | 1.00 | JPEG60 | 11 | 0 | 7 | 0 | 8 | 11 | 20.27 | 30.38 |
| ppocrv5_en_split | 0.75 | PNG | 17 | 0 | 7 | 0 | 2 | 17 | 13.44 | 29.69 |
| ppocrv5_en_split | 0.75 | JPEG60 | 17 | 0 | 7 | 0 | 2 | 17 | 13.43 | 29.53 |
| ppocrv5_en_split | 0.50 | PNG | 17 | 0 | 7 | 0 | 2 | 17 | 12.21 | 29.56 |
| ppocrv5_en_split | 0.50 | JPEG60 | 17 | 0 | 7 | 0 | 2 | 17 | 12.27 | 29.66 |
| ppocrv5_en_split | 0.40 | PNG | 17 | 0 | 7 | 0 | 2 | 17 | 12.20 | 29.69 |
| ppocrv5_en_split | 0.40 | JPEG60 | 17 | 0 | 7 | 0 | 2 | 17 | 12.20 | 29.65 |
| rapidocr_v4_split | 1.00 | PNG | 19 | 0 | 7 | 0 | 0 | 19 | 54.43 | 121.42 |
| rapidocr_v4_split | 1.00 | JPEG60 | 19 | 0 | 7 | 0 | 0 | 12 | 56.15 | 118.22 |
| rapidocr_v4_split | 0.75 | PNG | 19 | 0 | 7 | 0 | 0 | 7 | 27.65 | 65.44 |
| rapidocr_v4_split | 0.75 | JPEG60 | 19 | 0 | 7 | 0 | 0 | 10 | 28.07 | 65.22 |
| rapidocr_v4_split | 0.50 | PNG | 19 | 0 | 7 | 0 | 0 | 6 | 24.11 | 62.67 |
| rapidocr_v4_split | 0.50 | JPEG60 | 19 | 0 | 7 | 0 | 0 | 8 | 24.03 | 62.67 |
| rapidocr_v4_split | 0.40 | PNG | 19 | 0 | 7 | 0 | 0 | 10 | 23.84 | 59.57 |
| rapidocr_v4_split | 0.40 | JPEG60 | 18 | 0 | 7 | 0 | 1 | 9 | 23.78 | 59.88 |

## Installed Python distribution sizes (isolated Linux executor)

| Distribution | Installed files MiB | Pinned version |
|---|---:|---|
| numpy | 74.40 | 1.26.4 |
| onnxruntime | 39.88 | 1.20.1 |
| pillow | 13.43 | 11.1.0 |
| psutil | 2.25 | 6.1.1 |
| pytesseract | 0.07 | 0.3.13 |
| rapidfuzz | 11.73 | 3.12.2 |
| rapidocr-onnxruntime | 15.65 | 1.4.4 |

These distribution sizes include vendor code/models and possible shared dependencies; they are **not** incremental packaged executable sizes or Windows installation measurements.


## Position and two-line comparisons (original only)

| Engine | Slot | Titles correct / titles | Negatives rejected / negatives | Wrong IDs |
|---|---|---:|---:|---:|
| ppocrv4_full | left | 0/3 | 2/2 | 0 |
| ppocrv4_full | centre | 0/4 | 3/3 | 0 |
| ppocrv4_full | right | 3/4 | 2/2 | 0 |
| ppocrv4_full | unassigned_snip | 1/8 | 0/0 | 0 |
| ppocrv4_historical_full | left | 0/3 | 2/2 | 0 |
| ppocrv4_historical_full | centre | 0/4 | 3/3 | 0 |
| ppocrv4_historical_full | right | 3/4 | 2/2 | 0 |
| ppocrv4_historical_full | unassigned_snip | 1/8 | 0/0 | 0 |
| ppocrv4_historical_split | left | 3/3 | 2/2 | 0 |
| ppocrv4_historical_split | centre | 4/4 | 3/3 | 0 |
| ppocrv4_historical_split | right | 4/4 | 2/2 | 0 |
| ppocrv4_historical_split | unassigned_snip | 8/8 | 0/0 | 0 |
| ppocrv4_split | left | 3/3 | 2/2 | 0 |
| ppocrv4_split | centre | 4/4 | 3/3 | 0 |
| ppocrv4_split | right | 4/4 | 2/2 | 0 |
| ppocrv4_split | unassigned_snip | 8/8 | 0/0 | 0 |
| ppocrv5_en_split | left | 2/3 | 2/2 | 0 |
| ppocrv5_en_split | centre | 0/4 | 3/3 | 0 |
| ppocrv5_en_split | right | 0/4 | 2/2 | 0 |
| ppocrv5_en_split | unassigned_snip | 6/8 | 0/0 | 0 |
| rapidocr_v4_split | left | 3/3 | 2/2 | 0 |
| rapidocr_v4_split | centre | 4/4 | 3/3 | 0 |
| rapidocr_v4_split | right | 4/4 | 2/2 | 0 |
| rapidocr_v4_split | unassigned_snip | 8/8 | 0/0 | 0 |
| tesseract | left | 3/3 | 2/2 | 0 |
| tesseract | centre | 4/4 | 3/3 | 0 |
| tesseract | right | 4/4 | 2/2 | 0 |
| tesseract | unassigned_snip | 8/8 | 0/0 | 0 |

## Two-line original titles

| Engine | Correct / 2 | Wrong ID | Rejection |
|---|---:|---:|---:|
| ppocrv4_full | 0/2 | 0 | 2 |
| ppocrv4_historical_full | 0/2 | 0 | 2 |
| ppocrv4_historical_split | 2/2 | 0 | 0 |
| ppocrv4_split | 2/2 | 0 | 0 |
| ppocrv5_en_split | 0/2 | 0 | 2 |
| rapidocr_v4_split | 2/2 | 0 | 0 |
| tesseract | 2/2 | 0 | 0 |

## Resource usage and three consecutive crops

| Engine | Model load ms | 3-crop mean ms | 3-crop p95 ms | 3-crop max ms | CPU time s | CPU share of one core % | RSS after run MiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| ppocrv4_full | 56.628 | 88.313 | 88.909 | 88.909 | 6.22 | 99.84 | 200.9 |
| ppocrv4_historical_full | 56.628 | 88.461 | 88.675 | 88.675 | 6.24 | 99.9 | 201.2 |
| ppocrv4_historical_split | 56.628 | 175.444 | 175.965 | 175.965 | 6.04 | 100.26 | 201.0 |
| ppocrv4_split | 56.628 | 175.561 | 176.592 | 176.592 | 6.07 | 99.96 | 200.8 |
| ppocrv5_en_split | 36.759 | 90.753 | 92.309 | 92.309 | 3.22 | 99.98 | 201.3 |
| rapidocr_v4_split | 52.24 | 223.564 | 224.202 | 224.202 | 6.99 | 100.09 | 215.4 |
| tesseract | N/A | 230.396 | 239.084 | 239.084 | 1.88 | 7.52 | 200.7 |

Resources use one shared Python process with all models loaded, so RSS is NOT isolated per-engine incremental memory or an installed Windows footprint. Cold model load is measured once, not a cold-start distribution. 3-crop batches are artificial consecutive fixture calls, not real offers.

## Matching, raw recognition and safety diagnostics

- **ppocrv4_full:** 0 raw mismatches recovered by normalization; 4 by fuzzy matching below 100; 0 exact raw titles rejected or wrongly identified.
  - `1440p/region_1795025142_right.png`: expected='Donation', raw='Donaion', chosen='Donation', score=93.333, margin=36.19
  - `1440p/ocr_1795025241_right.png`: expected='Donation', raw='Donaion', chosen='Donation', score=93.333, margin=36.19
  - `1440p/ocr_1795025015_right.png`: expected='Donation', raw='Donaion', chosen='Donation', score=93.333, margin=36.19
  - `snips/snip_023747_ravenousbind.png`: expected='Ravenous Bind', raw='avenous ind', chosen='Ravenous Bind', score=91.667, margin=36.111
- **ppocrv4_historical_full:** 0 raw mismatches recovered by normalization; 4 by fuzzy matching below 100; 0 exact raw titles rejected or wrongly identified.
  - `1440p/region_1795025142_right.png`: expected='Donation', raw='Donaion', chosen='Donation', score=93.333, margin=30.833
  - `1440p/ocr_1795025241_right.png`: expected='Donation', raw='Donaion', chosen='Donation', score=93.333, margin=30.833
  - `1440p/ocr_1795025015_right.png`: expected='Donation', raw='Donaion', chosen='Donation', score=93.333, margin=30.833
  - `snips/snip_023747_ravenousbind.png`: expected='Ravenous Bind', raw='avenous ind', chosen='Ravenous Bind', score=90.909, margin=32.086
- **ppocrv4_historical_split:** 2 raw mismatches recovered by normalization; 0 by fuzzy matching below 100; 0 exact raw titles rejected or wrongly identified.
  - `snips/snip_015021_takeemdowndowndown.png`: expected="Take'em Down Down Down", raw="Take'em Down Down .Down", chosen="Take'em Down Down Down", score=100.0, margin=46.667
  - `snips/snip_015907_takeemdowndowndown.png`: expected="Take'em Down Down Down", raw="Take'em Down Down .Down", chosen="Take'em Down Down Down", score=100.0, margin=46.667
- **ppocrv4_split:** 2 raw mismatches recovered by normalization; 0 by fuzzy matching below 100; 0 exact raw titles rejected or wrongly identified.
  - `snips/snip_015021_takeemdowndowndown.png`: expected="Take'em Down Down Down", raw="Take'em Down Down .Down", chosen="Take'em Down Down Down", score=100.0, margin=48.571
  - `snips/snip_015907_takeemdowndowndown.png`: expected="Take'em Down Down Down", raw="Take'em Down Down .Down", chosen="Take'em Down Down Down", score=100.0, margin=48.571
- **ppocrv5_en_split:** 0 raw mismatches recovered by normalization; 0 by fuzzy matching below 100; 0 exact raw titles rejected or wrongly identified.
- **rapidocr_v4_split:** 0 raw mismatches recovered by normalization; 0 by fuzzy matching below 100; 0 exact raw titles rejected or wrongly identified.
- **tesseract:** 0 raw mismatches recovered by normalization; 0 by fuzzy matching below 100; 0 exact raw titles rejected or wrongly identified.

## Individual errors — all original images

- ppocrv4_full `1440p/region_1795025142_left.png`: false_rejection expected='Impassable' raw='linasle' actual=None score=58.824 margin=1.681
- ppocrv4_full `1440p/region_1795025142_centre.png`: false_rejection expected='Shark Bait' raw='SsakBait' actual=None score=77.778 margin=15.278
- ppocrv4_full `1440p/ocr_1795024923_centre.png`: false_rejection expected='Upgrade Stormsurge' raw='Upgrae sormsuses' actual=None score=82.353 margin=17.837
- ppocrv4_full `1440p/ocr_1795024923_right.png`: false_rejection expected='Tooth Fairy' raw='ohair' actual=None score=62.5 margin=12.5
- ppocrv4_full `1440p/ocr_1795025241_left.png`: false_rejection expected='Get Jinxed' raw='elie' actual=None score=50.0 margin=0.0
- ppocrv4_full `1440p/ocr_1795025241_centre.png`: false_rejection expected='Shark Bait' raw='SsakBait' actual=None score=77.778 margin=15.278
- ppocrv4_full `1440p/ocr_1795025015_left.png`: false_rejection expected='Impassable' raw='linasle' actual=None score=58.824 margin=1.681
- ppocrv4_full `1440p/ocr_1795025015_centre.png`: false_rejection expected='Upgrade Stormsurge' raw='Upgrae sormsuses' actual=None score=82.353 margin=17.837
- ppocrv4_full `snips/snip_121107_goliath.png`: false_rejection expected='Goliath' raw='Goflath' actual=None score=85.714 margin=24.176
- ppocrv4_full `snips/snip_121107_backtobasics.png`: false_rejection expected='Back To Basics' raw='Back T Bses' actual=None score=80.0 margin=30.0
- ppocrv4_full `snips/snip_121107_biggestsnowballever.png`: false_rejection expected='Biggest Snowball Ever' raw='Bigesowsal er' actual=None score=70.588 margin=16.742
- ppocrv4_full `snips/snip_023747_enpassant.png`: false_rejection expected='En Passant' raw='n Pasn' actual=None score=75.0 margin=27.941
- ppocrv4_full `snips/snip_023747_itskillingtime.png`: false_rejection expected="It's Killing Time" raw="I's lig Tin e" actual=None score=73.333 margin=1.333
- ppocrv4_full `snips/snip_015021_takeemdowndowndown.png`: false_rejection expected="Take'em Down Down Down" raw='Takem Down Down' actual=None score=81.081 margin=16.795
- ppocrv4_full `snips/snip_015907_takeemdowndowndown.png`: false_rejection expected="Take'em Down Down Down" raw='Takem Down Down' actual=None score=81.081 margin=16.795
- ppocrv4_historical_full `1440p/region_1795025142_left.png`: false_rejection expected='Impassable' raw='linasle' actual=None score=58.824 margin=1.681
- ppocrv4_historical_full `1440p/region_1795025142_centre.png`: false_rejection expected='Shark Bait' raw='SsakBait' actual=None score=82.353 margin=19.853
- ppocrv4_historical_full `1440p/ocr_1795024923_centre.png`: false_rejection expected='Upgrade Stormsurge' raw='Upgrae sormsuses' actual=None score=81.25 margin=19.181
- ppocrv4_historical_full `1440p/ocr_1795024923_right.png`: false_rejection expected='Tooth Fairy' raw='ohair' actual=None score=66.667 margin=13.333
- ppocrv4_historical_full `1440p/ocr_1795025241_left.png`: false_rejection expected='Get Jinxed' raw='elie' actual=None score=50.0 margin=0.0
- ppocrv4_historical_full `1440p/ocr_1795025241_centre.png`: false_rejection expected='Shark Bait' raw='SsakBait' actual=None score=82.353 margin=19.853
- ppocrv4_historical_full `1440p/ocr_1795025015_left.png`: false_rejection expected='Impassable' raw='linasle' actual=None score=58.824 margin=1.681
- ppocrv4_historical_full `1440p/ocr_1795025015_centre.png`: false_rejection expected='Upgrade Stormsurge' raw='Upgrae sormsuses' actual=None score=81.25 margin=19.181
- ppocrv4_historical_full `snips/snip_121107_goliath.png`: false_rejection expected='Goliath' raw='Goflath' actual=None score=85.714 margin=24.176
- ppocrv4_historical_full `snips/snip_121107_backtobasics.png`: false_rejection expected='Back To Basics' raw='Back T Bses' actual=None score=76.19 margin=28.571
- ppocrv4_historical_full `snips/snip_121107_biggestsnowballever.png`: false_rejection expected='Biggest Snowball Ever' raw='Bigesowsal er' actual=None score=70.968 margin=16.422
- ppocrv4_historical_full `snips/snip_023747_enpassant.png`: false_rejection expected='En Passant' raw='n Pasn' actual=None score=71.429 margin=21.429
- ppocrv4_historical_full `snips/snip_023747_itskillingtime.png`: false_rejection expected="It's Killing Time" raw="I's lig Tin e" actual=None score=69.565 margin=2.899
- ppocrv4_historical_full `snips/snip_015021_takeemdowndowndown.png`: false_rejection expected="Take'em Down Down Down" raw='Takem Down Down' actual=None score=83.871 margin=19.871
- ppocrv4_historical_full `snips/snip_015907_takeemdowndowndown.png`: false_rejection expected="Take'em Down Down Down" raw='Takem Down Down' actual=None score=83.871 margin=19.871
- ppocrv5_en_split `1440p/region_1795025142_centre.png`: false_rejection expected='Shark Bait' raw='Shark Bait cYanmantaYelowb' actual=None score=55.556 margin=9.402
- ppocrv5_en_split `1440p/region_1795025142_right.png`: false_rejection expected='Donation' raw='Donation cYanmantYelowb' actual=None score=51.613 margin=0.549
- ppocrv5_en_split `1440p/ocr_1795024923_centre.png`: false_rejection expected='Upgrade Stormsurge' raw='Upgrade Stormsurge cYanmaGYellowb' actual=None score=70.588 margin=10.588
- ppocrv5_en_split `1440p/ocr_1795024923_right.png`: false_rejection expected='Tooth Fairy' raw='Tooth Fairy cYanmaGentalowb' actual=None score=57.895 margin=13.45
- ppocrv5_en_split `1440p/ocr_1795025241_left.png`: false_rejection expected='Get Jinxed' raw='Get Jinxed cYanmantaYelowb' actual=None score=55.556 margin=11.556
- ppocrv5_en_split `1440p/ocr_1795025241_centre.png`: false_rejection expected='Shark Bait' raw='Shark Bait cYanmantaYelowb' actual=None score=55.556 margin=9.402
- ppocrv5_en_split `1440p/ocr_1795025241_right.png`: false_rejection expected='Donation' raw='Donation cYanmantYelowb' actual=None score=51.613 margin=0.549
- ppocrv5_en_split `1440p/ocr_1795025015_centre.png`: false_rejection expected='Upgrade Stormsurge' raw='Upgrade Stormsurge cYanmaGYellowb' actual=None score=70.588 margin=10.588
- ppocrv5_en_split `1440p/ocr_1795025015_right.png`: false_rejection expected='Donation' raw='Donation cYanmantYelowb' actual=None score=51.613 margin=0.549
- ppocrv5_en_split `snips/snip_015021_takeemdowndowndown.png`: false_rejection expected="Take'em Down Down Down" raw="Take'em Down Down" actual=None score=87.179 margin=27.179
- ppocrv5_en_split `snips/snip_015907_takeemdowndowndown.png`: false_rejection expected="Take'em Down Down Down" raw="Take'em Down Down" actual=None score=87.179 margin=27.179

## Individual errors — derived transformations

Total transformed-case errors over all engines/conditions: **237**. These are correlated transformations of the same source crops.
- tesseract `1440p/region_1795025142_right.png` scale=0.4 PNG: false_rejection; expected='Donation'; raw='a FF\n'; actual=None; score=42.857; margin=2.857
- tesseract `1440p/region_1795025142_right.png` scale=0.4 JPEG60: false_rejection; expected='Donation'; raw='‘ein =\n'; actual=None; score=60.0; margin=5.455
- tesseract `1440p/ocr_1795025015_right.png` scale=0.4 PNG: false_rejection; expected='Donation'; raw='a FF\n'; actual=None; score=42.857; margin=2.857
- tesseract `1440p/ocr_1795025015_right.png` scale=0.4 JPEG60: false_rejection; expected='Donation'; raw='‘ein =\n'; actual=None; score=60.0; margin=5.455
- ppocrv4_split `1440p/ocr_1795025241_left.png` scale=0.4 JPEG60: false_rejection; expected='Get Jinxed'; raw='Getlinxed'; actual=None; score=84.211; margin=24.211
- ppocrv4_full `1440p/region_1795025142_left.png` scale=1.0 JPEG60: false_rejection; expected='Impassable'; raw='Iinasle'; actual=None; score=58.824; margin=1.681
- ppocrv4_full `1440p/region_1795025142_left.png` scale=0.75 PNG: false_rejection; expected='Impassable'; raw='inasle'; actual=None; score=62.5; margin=0.962
- ppocrv4_full `1440p/region_1795025142_left.png` scale=0.75 JPEG60: false_rejection; expected='Impassable'; raw='inasle'; actual=None; score=62.5; margin=0.962
- ppocrv4_full `1440p/region_1795025142_left.png` scale=0.5 PNG: false_rejection; expected='Impassable'; raw='linasle'; actual=None; score=58.824; margin=1.681
- ppocrv4_full `1440p/region_1795025142_left.png` scale=0.5 JPEG60: false_rejection; expected='Impassable'; raw='imnasle'; actual=None; score=70.588; margin=13.445
- ppocrv4_full `1440p/region_1795025142_left.png` scale=0.4 PNG: false_rejection; expected='Impassable'; raw='linasle'; actual=None; score=58.824; margin=1.681
- ppocrv4_full `1440p/region_1795025142_left.png` scale=0.4 JPEG60: false_rejection; expected='Impassable'; raw='Sinpasle'; actual=None; score=66.667; margin=13.333
- ppocrv4_full `1440p/region_1795025142_centre.png` scale=1.0 JPEG60: false_rejection; expected='Shark Bait'; raw='sa at'; actual=None; score=66.667; margin=6.667
- ppocrv4_full `1440p/region_1795025142_centre.png` scale=0.75 PNG: false_rejection; expected='Shark Bait'; raw='sak ait'; actual=None; score=82.353; margin=19.853
- ppocrv4_full `1440p/region_1795025142_centre.png` scale=0.75 JPEG60: false_rejection; expected='Shark Bait'; raw='sakBait'; actual=None; score=82.353; margin=15.686
- ppocrv4_full `1440p/region_1795025142_centre.png` scale=0.5 PNG: false_rejection; expected='Shark Bait'; raw='SsakBait'; actual=None; score=77.778; margin=15.278
- ppocrv4_full `1440p/region_1795025142_centre.png` scale=0.5 JPEG60: false_rejection; expected='Shark Bait'; raw='sak a'; actual=None; score=66.667; margin=9.524
- ppocrv4_full `1440p/region_1795025142_centre.png` scale=0.4 PNG: false_rejection; expected='Shark Bait'; raw='ha ai'; actual=None; score=66.667; margin=9.524
- ppocrv4_full `1440p/region_1795025142_centre.png` scale=0.4 JPEG60: false_rejection; expected='Shark Bait'; raw='shak ai'; actual=None; score=82.353; margin=19.853
- ppocrv4_full `1440p/region_1795025142_right.png` scale=0.5 JPEG60: false_rejection; expected='Donation'; raw='Donafon'; actual=None; score=80.0; margin=25.455
- ppocrv4_full `1440p/region_1795025142_right.png` scale=0.4 JPEG60: false_rejection; expected='Donation'; raw='Donafen'; actual=None; score=66.667; margin=16.667
- ppocrv4_full `1440p/ocr_1795024923_centre.png` scale=1.0 JPEG60: false_rejection; expected='Upgrade Stormsurge'; raw='Upgrad sormsuse'; actual=None; score=84.848; margin=20.563
- ppocrv4_full `1440p/ocr_1795024923_centre.png` scale=0.75 PNG: false_rejection; expected='Upgrade Stormsurge'; raw='Upgrae sormsuse'; actual=None; score=84.848; margin=20.563
- ppocrv4_full `1440p/ocr_1795024923_centre.png` scale=0.5 PNG: false_rejection; expected='Upgrade Stormsurge'; raw='Upgrae sormsuses'; actual=None; score=82.353; margin=17.837
- ppocrv4_full `1440p/ocr_1795024923_centre.png` scale=0.4 PNG: false_rejection; expected='Upgrade Stormsurge'; raw='Upgeae sorsurse'; actual=None; score=78.788; margin=16.719
- ppocrv4_full `1440p/ocr_1795024923_centre.png` scale=0.4 JPEG60: false_rejection; expected='Upgrade Stormsurge'; raw='Upeae sorsure'; actual=None; score=77.419; margin=20.276
- ppocrv4_full `1440p/ocr_1795024923_right.png` scale=1.0 JPEG60: false_rejection; expected='Tooth Fairy'; raw='ohair'; actual=None; score=62.5; margin=12.5
- ppocrv4_full `1440p/ocr_1795024923_right.png` scale=0.75 PNG: false_rejection; expected='Tooth Fairy'; raw='ohair'; actual=None; score=62.5; margin=12.5
- ppocrv4_full `1440p/ocr_1795024923_right.png` scale=0.75 JPEG60: false_rejection; expected='Tooth Fairy'; raw='ohairy'; actual=None; score=70.588; margin=16.043
- ppocrv4_full `1440p/ocr_1795024923_right.png` scale=0.5 PNG: false_rejection; expected='Tooth Fairy'; raw='ohair'; actual=None; score=62.5; margin=12.5
- ppocrv4_full `1440p/ocr_1795024923_right.png` scale=0.5 JPEG60: false_rejection; expected='Tooth Fairy'; raw='ohair'; actual=None; score=62.5; margin=12.5
- ppocrv4_full `1440p/ocr_1795024923_right.png` scale=0.4 PNG: false_rejection; expected='Tooth Fairy'; raw='Tohary'; actual=None; score=70.588; margin=16.043
- ppocrv4_full `1440p/ocr_1795024923_right.png` scale=0.4 JPEG60: false_rejection; expected='Tooth Fairy'; raw='Tohairy'; actual=None; score=77.778; margin=27.778
- ppocrv4_full `1440p/ocr_1795025241_left.png` scale=1.0 JPEG60: false_rejection; expected='Get Jinxed'; raw='elie'; actual=None; score=50.0; margin=0.0
- ppocrv4_full `1440p/ocr_1795025241_left.png` scale=0.75 PNG: false_rejection; expected='Get Jinxed'; raw='elie'; actual=None; score=50.0; margin=0.0
- ppocrv4_full `1440p/ocr_1795025241_left.png` scale=0.75 JPEG60: false_rejection; expected='Get Jinxed'; raw='elie'; actual=None; score=50.0; margin=0.0
- ppocrv4_full `1440p/ocr_1795025241_left.png` scale=0.5 PNG: false_rejection; expected='Get Jinxed'; raw='elie'; actual=None; score=50.0; margin=0.0
- ppocrv4_full `1440p/ocr_1795025241_left.png` scale=0.5 JPEG60: false_rejection; expected='Get Jinxed'; raw='celie'; actual=None; score=50.0; margin=2.941
- ppocrv4_full `1440p/ocr_1795025241_left.png` scale=0.4 PNG: false_rejection; expected='Get Jinxed'; raw='e ixed'; actual=None; score=75.0; margin=16.176
- ppocrv4_full `1440p/ocr_1795025241_left.png` scale=0.4 JPEG60: false_rejection; expected='Get Jinxed'; raw='Celised'; actual=None; score=54.545; margin=1.212
- ppocrv4_full `1440p/ocr_1795025241_centre.png` scale=1.0 JPEG60: false_rejection; expected='Shark Bait'; raw='sa at'; actual=None; score=66.667; margin=6.667
- ppocrv4_full `1440p/ocr_1795025241_centre.png` scale=0.75 PNG: false_rejection; expected='Shark Bait'; raw='sak ait'; actual=None; score=82.353; margin=19.853
- ppocrv4_full `1440p/ocr_1795025241_centre.png` scale=0.75 JPEG60: false_rejection; expected='Shark Bait'; raw='sakBait'; actual=None; score=82.353; margin=15.686
- ppocrv4_full `1440p/ocr_1795025241_centre.png` scale=0.5 PNG: false_rejection; expected='Shark Bait'; raw='SsakBait'; actual=None; score=77.778; margin=15.278
- ppocrv4_full `1440p/ocr_1795025241_centre.png` scale=0.5 JPEG60: false_rejection; expected='Shark Bait'; raw='sak a'; actual=None; score=66.667; margin=9.524
- ppocrv4_full `1440p/ocr_1795025241_centre.png` scale=0.4 PNG: false_rejection; expected='Shark Bait'; raw='ha ai'; actual=None; score=66.667; margin=9.524
- ppocrv4_full `1440p/ocr_1795025241_centre.png` scale=0.4 JPEG60: false_rejection; expected='Shark Bait'; raw='shak ai'; actual=None; score=82.353; margin=19.853
- ppocrv4_full `1440p/ocr_1795025241_right.png` scale=0.5 JPEG60: false_rejection; expected='Donation'; raw='Donafon'; actual=None; score=80.0; margin=25.455
- ppocrv4_full `1440p/ocr_1795025241_right.png` scale=0.4 JPEG60: false_rejection; expected='Donation'; raw='Donafen'; actual=None; score=66.667; margin=16.667
- ppocrv4_full `1440p/ocr_1795025015_left.png` scale=1.0 JPEG60: false_rejection; expected='Impassable'; raw='Iinasle'; actual=None; score=58.824; margin=1.681
- ppocrv4_full `1440p/ocr_1795025015_left.png` scale=0.75 PNG: false_rejection; expected='Impassable'; raw='inasle'; actual=None; score=62.5; margin=0.962
- ppocrv4_full `1440p/ocr_1795025015_left.png` scale=0.75 JPEG60: false_rejection; expected='Impassable'; raw='inasle'; actual=None; score=62.5; margin=0.962
- ppocrv4_full `1440p/ocr_1795025015_left.png` scale=0.5 PNG: false_rejection; expected='Impassable'; raw='linasle'; actual=None; score=58.824; margin=1.681
- ppocrv4_full `1440p/ocr_1795025015_left.png` scale=0.5 JPEG60: false_rejection; expected='Impassable'; raw='imnasle'; actual=None; score=70.588; margin=13.445
- ppocrv4_full `1440p/ocr_1795025015_left.png` scale=0.4 PNG: false_rejection; expected='Impassable'; raw='linasle'; actual=None; score=58.824; margin=1.681
- ppocrv4_full `1440p/ocr_1795025015_left.png` scale=0.4 JPEG60: false_rejection; expected='Impassable'; raw='Sinpasle'; actual=None; score=66.667; margin=13.333
- ppocrv4_full `1440p/ocr_1795025015_centre.png` scale=1.0 JPEG60: false_rejection; expected='Upgrade Stormsurge'; raw='Upgrad sormsuse'; actual=None; score=84.848; margin=20.563
- ppocrv4_full `1440p/ocr_1795025015_centre.png` scale=0.75 PNG: false_rejection; expected='Upgrade Stormsurge'; raw='Upgrae sormsuse'; actual=None; score=84.848; margin=20.563
- ppocrv4_full `1440p/ocr_1795025015_centre.png` scale=0.5 PNG: false_rejection; expected='Upgrade Stormsurge'; raw='Upgrae sormsuses'; actual=None; score=82.353; margin=17.837
- ppocrv4_full `1440p/ocr_1795025015_centre.png` scale=0.4 PNG: false_rejection; expected='Upgrade Stormsurge'; raw='Upgeae sorsurse'; actual=None; score=78.788; margin=16.719
- ppocrv4_full `1440p/ocr_1795025015_centre.png` scale=0.4 JPEG60: false_rejection; expected='Upgrade Stormsurge'; raw='Upeae sorsure'; actual=None; score=77.419; margin=20.276
- ppocrv4_full `1440p/ocr_1795025015_right.png` scale=0.5 JPEG60: false_rejection; expected='Donation'; raw='Donafon'; actual=None; score=80.0; margin=25.455
- ppocrv4_full `1440p/ocr_1795025015_right.png` scale=0.4 JPEG60: false_rejection; expected='Donation'; raw='Donafen'; actual=None; score=66.667; margin=16.667
- ppocrv4_full `snips/snip_121107_goliath.png` scale=1.0 JPEG60: false_rejection; expected='Goliath'; raw='oflat'; actual=None; score=66.667; margin=9.524
- ppocrv4_full `snips/snip_121107_goliath.png` scale=0.75 PNG: false_rejection; expected='Goliath'; raw='Gofiath'; actual=None; score=85.714; margin=31.169
- ppocrv4_full `snips/snip_121107_goliath.png` scale=0.75 JPEG60: false_rejection; expected='Goliath'; raw='Golat'; actual=None; score=83.333; margin=26.19
- ppocrv4_full `snips/snip_121107_goliath.png` scale=0.5 PNG: false_rejection; expected='Goliath'; raw='Goflath'; actual=None; score=85.714; margin=24.176
- ppocrv4_full `snips/snip_121107_goliath.png` scale=0.5 JPEG60: false_rejection; expected='Goliath'; raw='Coflath'; actual=None; score=71.429; margin=9.89
- ppocrv4_full `snips/snip_121107_backtobasics.png` scale=1.0 JPEG60: false_rejection; expected='Back To Basics'; raw='Back T Bses'; actual=None; score=80.0; margin=30.0
- ppocrv4_full `snips/snip_121107_backtobasics.png` scale=0.75 PNG: false_rejection; expected='Back To Basics'; raw='Back T Bses'; actual=None; score=80.0; margin=30.0
- ppocrv4_full `snips/snip_121107_backtobasics.png` scale=0.75 JPEG60: false_rejection; expected='Back To Basics'; raw='Back T Bse'; actual=None; score=75.0; margin=26.724
- ppocrv4_full `snips/snip_121107_backtobasics.png` scale=0.5 PNG: false_rejection; expected='Back To Basics'; raw='Back T Bses'; actual=None; score=80.0; margin=30.0
- ppocrv4_full `snips/snip_121107_backtobasics.png` scale=0.5 JPEG60: false_rejection; expected='Back To Basics'; raw='Back T Basies'; actual=None; score=88.889; margin=35.948
- ppocrv4_full `snips/snip_121107_backtobasics.png` scale=0.4 PNG: false_rejection; expected='Back To Basics'; raw='Back To Bse s'; actual=None; score=81.481; margin=31.481
- ppocrv4_full `snips/snip_121107_backtobasics.png` scale=0.4 JPEG60: false_rejection; expected='Back To Basics'; raw='Back T Basies'; actual=None; score=88.889; margin=35.948
- ppocrv4_full `snips/snip_121107_biggestsnowballever.png` scale=1.0 JPEG60: false_rejection; expected='Biggest Snowball Ever'; raw='Bigesowbal er'; actual=None; score=76.471; margin=21.298
- ppocrv4_full `snips/snip_121107_biggestsnowballever.png` scale=0.75 PNG: false_rejection; expected='Biggest Snowball Ever'; raw='Bigesowsal ver'; actual=None; score=74.286; margin=22.434
- ppocrv4_full `snips/snip_121107_biggestsnowballever.png` scale=0.75 JPEG60: false_rejection; expected='Biggest Snowball Ever'; raw='Bigesowbal ver'; actual=None; score=80.0; margin=26.667
- ppocrv4_full `snips/snip_121107_biggestsnowballever.png` scale=0.5 PNG: false_rejection; expected='Biggest Snowball Ever'; raw='Bigesowsal er'; actual=None; score=70.588; margin=16.742
- ppocrv4_full `snips/snip_121107_biggestsnowballever.png` scale=0.5 JPEG60: false_rejection; expected='Biggest Snowball Ever'; raw='SBigesowbalever'; actual=None; score=77.778; margin=27.778
- ppocrv4_full `snips/snip_121107_biggestsnowballever.png` scale=0.4 PNG: false_rejection; expected='Biggest Snowball Ever'; raw='Bigesowsalever'; actual=None; score=74.286; margin=22.857
- ppocrv4_full `snips/snip_121107_biggestsnowballever.png` scale=0.4 JPEG60: false_rejection; expected='Biggest Snowball Ever'; raw='SBigetsowbalever'; actual=None; score=81.081; margin=32.432
- ppocrv4_full `snips/snip_023747_enpassant.png` scale=1.0 JPEG60: false_rejection; expected='En Passant'; raw='En Pasn'; actual=None; score=82.353; margin=26.797
- ppocrv4_full `snips/snip_023747_enpassant.png` scale=0.75 PNG: false_rejection; expected='En Passant'; raw='n Pasn'; actual=None; score=75.0; margin=27.941
- ppocrv4_full `snips/snip_023747_enpassant.png` scale=0.75 JPEG60: false_rejection; expected='En Passant'; raw='n Pasn'; actual=None; score=75.0; margin=27.941
- ppocrv4_full `snips/snip_023747_enpassant.png` scale=0.5 PNG: false_rejection; expected='En Passant'; raw='n Pasn'; actual=None; score=75.0; margin=27.941
- ppocrv4_full `snips/snip_023747_enpassant.png` scale=0.5 JPEG60: false_rejection; expected='En Passant'; raw='En Pasnt'; actual=None; score=88.889; margin=30.065
- ppocrv4_full `snips/snip_023747_enpassant.png` scale=0.4 PNG: false_rejection; expected='En Passant'; raw='n Passan'; actual=None; score=88.889; margin=33.333
- ppocrv4_full `snips/snip_023747_ravenousbind.png` scale=0.4 PNG: false_rejection; expected='Ravenous Bind'; raw='avenous in'; actual=None; score=86.957; margin=28.133
- ppocrv4_full `snips/snip_023747_itskillingtime.png` scale=1.0 JPEG60: false_rejection; expected="It's Killing Time"; raw="I's ilig Tin e"; actual=None; score=77.419; margin=8.189
- ppocrv4_full `snips/snip_023747_itskillingtime.png` scale=0.75 PNG: false_rejection; expected="It's Killing Time"; raw="I's lig Tin e"; actual=None; score=73.333; margin=1.333
- ppocrv4_full `snips/snip_023747_itskillingtime.png` scale=0.75 JPEG60: false_rejection; expected="It's Killing Time"; raw="I's lig Tin e"; actual=None; score=73.333; margin=1.333
- ppocrv4_full `snips/snip_023747_itskillingtime.png` scale=0.5 PNG: false_rejection; expected="It's Killing Time"; raw="I's lig Tin e"; actual=None; score=73.333; margin=1.333
- ppocrv4_full `snips/snip_023747_itskillingtime.png` scale=0.5 JPEG60: false_rejection; expected="It's Killing Time"; raw='Ies ilig Ti e'; actual=None; score=73.333; margin=9.333
- ppocrv4_full `snips/snip_023747_itskillingtime.png` scale=0.4 PNG: false_rejection; expected="It's Killing Time"; raw='Its ilin Ti e'; actual=None; score=80.0; margin=16.0
- ppocrv4_full `snips/snip_023747_itskillingtime.png` scale=0.4 JPEG60: false_rejection; expected="It's Killing Time"; raw='Ieskilin Time'; actual=None; score=80.0; margin=10.435
- ppocrv4_full `snips/snip_015021_takeemdowndowndown.png` scale=1.0 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw='Takem Down Down'; actual=None; score=81.081; margin=16.795
- ppocrv4_full `snips/snip_015021_takeemdowndowndown.png` scale=0.75 PNG: false_rejection; expected="Take'em Down Down Down"; raw='Takem Down Down'; actual=None; score=81.081; margin=16.795
- ppocrv4_full `snips/snip_015021_takeemdowndowndown.png` scale=0.75 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw='Takem Down Down'; actual=None; score=81.081; margin=16.795
- ppocrv4_full `snips/snip_015021_takeemdowndowndown.png` scale=0.5 PNG: false_rejection; expected="Take'em Down Down Down"; raw='Takem Down Down'; actual=None; score=81.081; margin=16.795
- ppocrv4_full `snips/snip_015021_takeemdowndowndown.png` scale=0.5 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw='Takem Down Dowm'; actual=None; score=75.676; margin=18.533
- ppocrv4_full `snips/snip_015021_takeemdowndowndown.png` scale=0.4 PNG: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down"; actual=None; score=87.179; margin=27.179
- ppocrv4_full `snips/snip_015021_takeemdowndowndown.png` scale=0.4 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw='TakemDown Dowin'; actual=None; score=75.676; margin=18.533
- ppocrv4_full `snips/snip_015907_takeemdowndowndown.png` scale=1.0 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down"; actual=None; score=87.179; margin=27.179
- ppocrv4_full `snips/snip_015907_takeemdowndowndown.png` scale=0.75 PNG: false_rejection; expected="Take'em Down Down Down"; raw='Takem Down Down'; actual=None; score=81.081; margin=16.795
- ppocrv4_full `snips/snip_015907_takeemdowndowndown.png` scale=0.75 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw='Takem Down Down'; actual=None; score=81.081; margin=16.795
- ppocrv4_full `snips/snip_015907_takeemdowndowndown.png` scale=0.5 PNG: false_rejection; expected="Take'em Down Down Down"; raw='Takem Down Down'; actual=None; score=81.081; margin=16.795
- ppocrv4_full `snips/snip_015907_takeemdowndowndown.png` scale=0.5 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw='TakemDown Down'; actual=None; score=77.778; margin=18.519
- ppocrv4_full `snips/snip_015907_takeemdowndowndown.png` scale=0.4 PNG: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down"; actual=None; score=87.179; margin=27.179
- ppocrv4_full `snips/snip_015907_takeemdowndowndown.png` scale=0.4 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw='TakemDown Dowin'; actual=None; score=75.676; margin=18.533
- ppocrv4_historical_split `1440p/ocr_1795025241_left.png` scale=0.4 JPEG60: false_rejection; expected='Get Jinxed'; raw='Getlinxed'; actual=None; score=88.889; margin=25.731
- ppocrv4_historical_full `1440p/region_1795025142_left.png` scale=1.0 JPEG60: false_rejection; expected='Impassable'; raw='Iinasle'; actual=None; score=58.824; margin=1.681
- ppocrv4_historical_full `1440p/region_1795025142_left.png` scale=0.75 PNG: false_rejection; expected='Impassable'; raw='inasle'; actual=None; score=62.5; margin=0.962
- ppocrv4_historical_full `1440p/region_1795025142_left.png` scale=0.75 JPEG60: false_rejection; expected='Impassable'; raw='inasle'; actual=None; score=62.5; margin=0.962
- ppocrv4_historical_full `1440p/region_1795025142_left.png` scale=0.5 PNG: false_rejection; expected='Impassable'; raw='linasle'; actual=None; score=58.824; margin=1.681
- ppocrv4_historical_full `1440p/region_1795025142_left.png` scale=0.5 JPEG60: false_rejection; expected='Impassable'; raw='imnasle'; actual=None; score=70.588; margin=13.445
- ppocrv4_historical_full `1440p/region_1795025142_left.png` scale=0.4 PNG: false_rejection; expected='Impassable'; raw='linasle'; actual=None; score=58.824; margin=1.681
- ppocrv4_historical_full `1440p/region_1795025142_left.png` scale=0.4 JPEG60: false_rejection; expected='Impassable'; raw='Sinpasle'; actual=None; score=66.667; margin=13.333
- ppocrv4_historical_full `1440p/region_1795025142_centre.png` scale=1.0 JPEG60: false_rejection; expected='Shark Bait'; raw='sa at'; actual=None; score=66.667; margin=0.0
- ppocrv4_historical_full `1440p/region_1795025142_centre.png` scale=0.75 PNG: false_rejection; expected='Shark Bait'; raw='sak ait'; actual=None; score=80.0; margin=21.176
- ppocrv4_historical_full `1440p/region_1795025142_centre.png` scale=0.75 JPEG60: false_rejection; expected='Shark Bait'; raw='sakBait'; actual=None; score=87.5; margin=20.833
- ppocrv4_historical_full `1440p/region_1795025142_centre.png` scale=0.5 PNG: false_rejection; expected='Shark Bait'; raw='SsakBait'; actual=None; score=82.353; margin=19.853
- ppocrv4_historical_full `1440p/region_1795025142_centre.png` scale=0.5 JPEG60: false_rejection; expected='Shark Bait'; raw='sak a'; actual=None; score=61.538; margin=1.538
- ppocrv4_historical_full `1440p/region_1795025142_centre.png` scale=0.4 PNG: false_rejection; expected='Shark Bait'; raw='ha ai'; actual=None; score=61.538; margin=11.538
- ppocrv4_historical_full `1440p/region_1795025142_centre.png` scale=0.4 JPEG60: false_rejection; expected='Shark Bait'; raw='shak ai'; actual=None; score=80.0; margin=22.857
- ppocrv4_historical_full `1440p/region_1795025142_right.png` scale=0.5 JPEG60: false_rejection; expected='Donation'; raw='Donafon'; actual=None; score=80.0; margin=24.444
- ppocrv4_historical_full `1440p/region_1795025142_right.png` scale=0.4 JPEG60: false_rejection; expected='Donation'; raw='Donafen'; actual=None; score=66.667; margin=11.111
- ppocrv4_historical_full `1440p/ocr_1795024923_centre.png` scale=1.0 JPEG60: false_rejection; expected='Upgrade Stormsurge'; raw='Upgrad sormsuse'; actual=None; score=83.871; margin=22.333
- ppocrv4_historical_full `1440p/ocr_1795024923_centre.png` scale=0.75 PNG: false_rejection; expected='Upgrade Stormsurge'; raw='Upgrae sormsuse'; actual=None; score=83.871; margin=22.333
- ppocrv4_historical_full `1440p/ocr_1795024923_centre.png` scale=0.5 PNG: false_rejection; expected='Upgrade Stormsurge'; raw='Upgrae sormsuses'; actual=None; score=81.25; margin=19.181
- ppocrv4_historical_full `1440p/ocr_1795024923_centre.png` scale=0.4 PNG: false_rejection; expected='Upgrade Stormsurge'; raw='Upgeae sorsurse'; actual=None; score=77.419; margin=18.16
- ppocrv4_historical_full `1440p/ocr_1795024923_centre.png` scale=0.4 JPEG60: false_rejection; expected='Upgrade Stormsurge'; raw='Upeae sorsure'; actual=None; score=75.862; margin=14.324
- ppocrv4_historical_full `1440p/ocr_1795024923_right.png` scale=1.0 JPEG60: false_rejection; expected='Tooth Fairy'; raw='ohair'; actual=None; score=66.667; margin=13.333
- ppocrv4_historical_full `1440p/ocr_1795024923_right.png` scale=0.75 PNG: false_rejection; expected='Tooth Fairy'; raw='ohair'; actual=None; score=66.667; margin=13.333
- ppocrv4_historical_full `1440p/ocr_1795024923_right.png` scale=0.75 JPEG60: false_rejection; expected='Tooth Fairy'; raw='ohairy'; actual=None; score=75.0; margin=20.455
- ppocrv4_historical_full `1440p/ocr_1795024923_right.png` scale=0.5 PNG: false_rejection; expected='Tooth Fairy'; raw='ohair'; actual=None; score=66.667; margin=13.333
- ppocrv4_historical_full `1440p/ocr_1795024923_right.png` scale=0.5 JPEG60: false_rejection; expected='Tooth Fairy'; raw='ohair'; actual=None; score=66.667; margin=13.333
- ppocrv4_historical_full `1440p/ocr_1795024923_right.png` scale=0.4 PNG: false_rejection; expected='Tooth Fairy'; raw='Tohary'; actual=None; score=75.0; margin=20.455
- ppocrv4_historical_full `1440p/ocr_1795024923_right.png` scale=0.4 JPEG60: false_rejection; expected='Tooth Fairy'; raw='Tohairy'; actual=None; score=82.353; margin=32.353
- ppocrv4_historical_full `1440p/ocr_1795025241_left.png` scale=1.0 JPEG60: false_rejection; expected='Get Jinxed'; raw='elie'; actual=None; score=50.0; margin=0.0
- ppocrv4_historical_full `1440p/ocr_1795025241_left.png` scale=0.75 PNG: false_rejection; expected='Get Jinxed'; raw='elie'; actual=None; score=50.0; margin=0.0
- ppocrv4_historical_full `1440p/ocr_1795025241_left.png` scale=0.75 JPEG60: false_rejection; expected='Get Jinxed'; raw='elie'; actual=None; score=50.0; margin=0.0
- ppocrv4_historical_full `1440p/ocr_1795025241_left.png` scale=0.5 PNG: false_rejection; expected='Get Jinxed'; raw='elie'; actual=None; score=50.0; margin=0.0
- ppocrv4_historical_full `1440p/ocr_1795025241_left.png` scale=0.5 JPEG60: false_rejection; expected='Get Jinxed'; raw='celie'; actual=None; score=50.0; margin=0.0
- ppocrv4_historical_full `1440p/ocr_1795025241_left.png` scale=0.4 PNG: false_rejection; expected='Get Jinxed'; raw='e ixed'; actual=None; score=71.429; margin=16.883
- ppocrv4_historical_full `1440p/ocr_1795025241_left.png` scale=0.4 JPEG60: false_rejection; expected='Get Jinxed'; raw='Celised'; actual=None; score=57.143; margin=2.597
- ppocrv4_historical_full `1440p/ocr_1795025241_centre.png` scale=1.0 JPEG60: false_rejection; expected='Shark Bait'; raw='sa at'; actual=None; score=66.667; margin=0.0
- ppocrv4_historical_full `1440p/ocr_1795025241_centre.png` scale=0.75 PNG: false_rejection; expected='Shark Bait'; raw='sak ait'; actual=None; score=80.0; margin=21.176
- ppocrv4_historical_full `1440p/ocr_1795025241_centre.png` scale=0.75 JPEG60: false_rejection; expected='Shark Bait'; raw='sakBait'; actual=None; score=87.5; margin=20.833
- ppocrv4_historical_full `1440p/ocr_1795025241_centre.png` scale=0.5 PNG: false_rejection; expected='Shark Bait'; raw='SsakBait'; actual=None; score=82.353; margin=19.853
- ppocrv4_historical_full `1440p/ocr_1795025241_centre.png` scale=0.5 JPEG60: false_rejection; expected='Shark Bait'; raw='sak a'; actual=None; score=61.538; margin=1.538
- ppocrv4_historical_full `1440p/ocr_1795025241_centre.png` scale=0.4 PNG: false_rejection; expected='Shark Bait'; raw='ha ai'; actual=None; score=61.538; margin=11.538
- ppocrv4_historical_full `1440p/ocr_1795025241_centre.png` scale=0.4 JPEG60: false_rejection; expected='Shark Bait'; raw='shak ai'; actual=None; score=80.0; margin=22.857
- ppocrv4_historical_full `1440p/ocr_1795025241_right.png` scale=0.5 JPEG60: false_rejection; expected='Donation'; raw='Donafon'; actual=None; score=80.0; margin=24.444
- ppocrv4_historical_full `1440p/ocr_1795025241_right.png` scale=0.4 JPEG60: false_rejection; expected='Donation'; raw='Donafen'; actual=None; score=66.667; margin=11.111
- ppocrv4_historical_full `1440p/ocr_1795025015_left.png` scale=1.0 JPEG60: false_rejection; expected='Impassable'; raw='Iinasle'; actual=None; score=58.824; margin=1.681
- ppocrv4_historical_full `1440p/ocr_1795025015_left.png` scale=0.75 PNG: false_rejection; expected='Impassable'; raw='inasle'; actual=None; score=62.5; margin=0.962
- ppocrv4_historical_full `1440p/ocr_1795025015_left.png` scale=0.75 JPEG60: false_rejection; expected='Impassable'; raw='inasle'; actual=None; score=62.5; margin=0.962
- ppocrv4_historical_full `1440p/ocr_1795025015_left.png` scale=0.5 PNG: false_rejection; expected='Impassable'; raw='linasle'; actual=None; score=58.824; margin=1.681
- ppocrv4_historical_full `1440p/ocr_1795025015_left.png` scale=0.5 JPEG60: false_rejection; expected='Impassable'; raw='imnasle'; actual=None; score=70.588; margin=13.445
- ppocrv4_historical_full `1440p/ocr_1795025015_left.png` scale=0.4 PNG: false_rejection; expected='Impassable'; raw='linasle'; actual=None; score=58.824; margin=1.681
- ppocrv4_historical_full `1440p/ocr_1795025015_left.png` scale=0.4 JPEG60: false_rejection; expected='Impassable'; raw='Sinpasle'; actual=None; score=66.667; margin=13.333
- ppocrv4_historical_full `1440p/ocr_1795025015_centre.png` scale=1.0 JPEG60: false_rejection; expected='Upgrade Stormsurge'; raw='Upgrad sormsuse'; actual=None; score=83.871; margin=22.333
- ppocrv4_historical_full `1440p/ocr_1795025015_centre.png` scale=0.75 PNG: false_rejection; expected='Upgrade Stormsurge'; raw='Upgrae sormsuse'; actual=None; score=83.871; margin=22.333
- ppocrv4_historical_full `1440p/ocr_1795025015_centre.png` scale=0.5 PNG: false_rejection; expected='Upgrade Stormsurge'; raw='Upgrae sormsuses'; actual=None; score=81.25; margin=19.181
- ppocrv4_historical_full `1440p/ocr_1795025015_centre.png` scale=0.4 PNG: false_rejection; expected='Upgrade Stormsurge'; raw='Upgeae sorsurse'; actual=None; score=77.419; margin=18.16
- ppocrv4_historical_full `1440p/ocr_1795025015_centre.png` scale=0.4 JPEG60: false_rejection; expected='Upgrade Stormsurge'; raw='Upeae sorsure'; actual=None; score=75.862; margin=14.324
- ppocrv4_historical_full `1440p/ocr_1795025015_right.png` scale=0.5 JPEG60: false_rejection; expected='Donation'; raw='Donafon'; actual=None; score=80.0; margin=24.444
- ppocrv4_historical_full `1440p/ocr_1795025015_right.png` scale=0.4 JPEG60: false_rejection; expected='Donation'; raw='Donafen'; actual=None; score=66.667; margin=11.111
- ppocrv4_historical_full `snips/snip_121107_goliath.png` scale=1.0 JPEG60: false_rejection; expected='Goliath'; raw='oflat'; actual=None; score=66.667; margin=9.524
- ppocrv4_historical_full `snips/snip_121107_goliath.png` scale=0.75 PNG: false_rejection; expected='Goliath'; raw='Gofiath'; actual=None; score=85.714; margin=31.169
- ppocrv4_historical_full `snips/snip_121107_goliath.png` scale=0.75 JPEG60: false_rejection; expected='Goliath'; raw='Golat'; actual=None; score=83.333; margin=26.19
- ppocrv4_historical_full `snips/snip_121107_goliath.png` scale=0.5 PNG: false_rejection; expected='Goliath'; raw='Goflath'; actual=None; score=85.714; margin=24.176
- ppocrv4_historical_full `snips/snip_121107_goliath.png` scale=0.5 JPEG60: false_rejection; expected='Goliath'; raw='Coflath'; actual=None; score=71.429; margin=9.89
- ppocrv4_historical_full `snips/snip_121107_backtobasics.png` scale=1.0 JPEG60: false_rejection; expected='Back To Basics'; raw='Back T Bses'; actual=None; score=76.19; margin=28.571
- ppocrv4_historical_full `snips/snip_121107_backtobasics.png` scale=0.75 PNG: false_rejection; expected='Back To Basics'; raw='Back T Bses'; actual=None; score=76.19; margin=28.571
- ppocrv4_historical_full `snips/snip_121107_backtobasics.png` scale=0.75 JPEG60: false_rejection; expected='Back To Basics'; raw='Back T Bse'; actual=None; score=70.0; margin=20.0
- ppocrv4_historical_full `snips/snip_121107_backtobasics.png` scale=0.5 PNG: false_rejection; expected='Back To Basics'; raw='Back T Bses'; actual=None; score=76.19; margin=28.571
- ppocrv4_historical_full `snips/snip_121107_backtobasics.png` scale=0.5 JPEG60: false_rejection; expected='Back To Basics'; raw='Back T Basies'; actual=None; score=86.957; margin=36.957
- ppocrv4_historical_full `snips/snip_121107_backtobasics.png` scale=0.4 PNG: false_rejection; expected='Back To Basics'; raw='Back To Bse s'; actual=None; score=81.818; margin=33.818
- ppocrv4_historical_full `snips/snip_121107_backtobasics.png` scale=0.4 JPEG60: false_rejection; expected='Back To Basics'; raw='Back T Basies'; actual=None; score=86.957; margin=36.957
- ppocrv4_historical_full `snips/snip_121107_biggestsnowballever.png` scale=1.0 JPEG60: false_rejection; expected='Biggest Snowball Ever'; raw='Bigesowbal er'; actual=None; score=77.419; margin=22.874
- ppocrv4_historical_full `snips/snip_121107_biggestsnowballever.png` scale=0.75 PNG: false_rejection; expected='Biggest Snowball Ever'; raw='Bigesowsal ver'; actual=None; score=75.0; margin=18.75
- ppocrv4_historical_full `snips/snip_121107_biggestsnowballever.png` scale=0.75 JPEG60: false_rejection; expected='Biggest Snowball Ever'; raw='Bigesowbal ver'; actual=None; score=81.25; margin=25.0
- ppocrv4_historical_full `snips/snip_121107_biggestsnowballever.png` scale=0.5 PNG: false_rejection; expected='Biggest Snowball Ever'; raw='Bigesowsal er'; actual=None; score=70.968; margin=16.422
- ppocrv4_historical_full `snips/snip_121107_biggestsnowballever.png` scale=0.5 JPEG60: false_rejection; expected='Biggest Snowball Ever'; raw='SBigesowbalever'; actual=None; score=82.353; margin=29.412
- ppocrv4_historical_full `snips/snip_121107_biggestsnowballever.png` scale=0.4 PNG: false_rejection; expected='Biggest Snowball Ever'; raw='Bigesowsalever'; actual=None; score=78.788; margin=24.242
- ppocrv4_historical_full `snips/snip_121107_biggestsnowballever.png` scale=0.4 JPEG60: false_rejection; expected='Biggest Snowball Ever'; raw='SBigetsowbalever'; actual=None; score=85.714; margin=34.286
- ppocrv4_historical_full `snips/snip_023747_enpassant.png` scale=1.0 JPEG60: false_rejection; expected='En Passant'; raw='En Pasn'; actual=None; score=80.0; margin=26.667
- ppocrv4_historical_full `snips/snip_023747_enpassant.png` scale=0.75 PNG: false_rejection; expected='En Passant'; raw='n Pasn'; actual=None; score=71.429; margin=21.429
- ppocrv4_historical_full `snips/snip_023747_enpassant.png` scale=0.75 JPEG60: false_rejection; expected='En Passant'; raw='n Pasn'; actual=None; score=71.429; margin=21.429
- ppocrv4_historical_full `snips/snip_023747_enpassant.png` scale=0.5 PNG: false_rejection; expected='En Passant'; raw='n Pasn'; actual=None; score=71.429; margin=21.429
- ppocrv4_historical_full `snips/snip_023747_enpassant.png` scale=0.5 JPEG60: false_rejection; expected='En Passant'; raw='En Pasnt'; actual=None; score=87.5; margin=34.167
- ppocrv4_historical_full `snips/snip_023747_enpassant.png` scale=0.4 PNG: false_rejection; expected='En Passant'; raw='n Passan'; actual=None; score=87.5; margin=28.676
- ppocrv4_historical_full `snips/snip_023747_ravenousbind.png` scale=0.4 PNG: false_rejection; expected='Ravenous Bind'; raw='avenous in'; actual=None; score=85.714; margin=23.214
- ppocrv4_historical_full `snips/snip_023747_itskillingtime.png` scale=1.0 JPEG60: false_rejection; expected="It's Killing Time"; raw="I's ilig Tin e"; actual=None; score=75.0; margin=11.842
- ppocrv4_historical_full `snips/snip_023747_itskillingtime.png` scale=0.75 PNG: false_rejection; expected="It's Killing Time"; raw="I's lig Tin e"; actual=None; score=69.565; margin=2.899
- ppocrv4_historical_full `snips/snip_023747_itskillingtime.png` scale=0.75 JPEG60: false_rejection; expected="It's Killing Time"; raw="I's lig Tin e"; actual=None; score=69.565; margin=2.899
- ppocrv4_historical_full `snips/snip_023747_itskillingtime.png` scale=0.5 PNG: false_rejection; expected="It's Killing Time"; raw="I's lig Tin e"; actual=None; score=69.565; margin=2.899
- ppocrv4_historical_full `snips/snip_023747_itskillingtime.png` scale=0.5 JPEG60: false_rejection; expected="It's Killing Time"; raw='Ies ilig Ti e'; actual=None; score=75.0; margin=11.842
- ppocrv4_historical_full `snips/snip_023747_itskillingtime.png` scale=0.4 PNG: false_rejection; expected="It's Killing Time"; raw='Its ilin Ti e'; actual=None; score=83.333; margin=20.175
- ppocrv4_historical_full `snips/snip_023747_itskillingtime.png` scale=0.4 JPEG60: false_rejection; expected="It's Killing Time"; raw='Ieskilin Time'; actual=None; score=84.615; margin=17.949
- ppocrv4_historical_full `snips/snip_015021_takeemdowndowndown.png` scale=1.0 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw='Takem Down Down'; actual=None; score=83.871; margin=19.871
- ppocrv4_historical_full `snips/snip_015021_takeemdowndowndown.png` scale=0.75 PNG: false_rejection; expected="Take'em Down Down Down"; raw='Takem Down Down'; actual=None; score=83.871; margin=19.871
- ppocrv4_historical_full `snips/snip_015021_takeemdowndowndown.png` scale=0.75 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw='Takem Down Down'; actual=None; score=83.871; margin=19.871
- ppocrv4_historical_full `snips/snip_015021_takeemdowndowndown.png` scale=0.5 PNG: false_rejection; expected="Take'em Down Down Down"; raw='Takem Down Down'; actual=None; score=83.871; margin=19.871
- ppocrv4_historical_full `snips/snip_015021_takeemdowndowndown.png` scale=0.5 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw='Takem Down Dowm'; actual=None; score=77.419; margin=21.419
- ppocrv4_historical_full `snips/snip_015021_takeemdowndowndown.png` scale=0.4 PNG: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down"; actual=None; score=87.5; margin=25.962
- ppocrv4_historical_full `snips/snip_015021_takeemdowndowndown.png` scale=0.4 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw='TakemDown Dowin'; actual=None; score=81.25; margin=19.712
- ppocrv4_historical_full `snips/snip_015907_takeemdowndowndown.png` scale=1.0 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down"; actual=None; score=87.5; margin=25.962
- ppocrv4_historical_full `snips/snip_015907_takeemdowndowndown.png` scale=0.75 PNG: false_rejection; expected="Take'em Down Down Down"; raw='Takem Down Down'; actual=None; score=83.871; margin=19.871
- ppocrv4_historical_full `snips/snip_015907_takeemdowndowndown.png` scale=0.75 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw='Takem Down Down'; actual=None; score=83.871; margin=19.871
- ppocrv4_historical_full `snips/snip_015907_takeemdowndowndown.png` scale=0.5 PNG: false_rejection; expected="Take'em Down Down Down"; raw='Takem Down Down'; actual=None; score=83.871; margin=19.871
- ppocrv4_historical_full `snips/snip_015907_takeemdowndowndown.png` scale=0.5 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw='TakemDown Down'; actual=None; score=83.871; margin=19.871
- ppocrv4_historical_full `snips/snip_015907_takeemdowndowndown.png` scale=0.4 PNG: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down"; actual=None; score=87.5; margin=25.962
- ppocrv4_historical_full `snips/snip_015907_takeemdowndowndown.png` scale=0.4 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw='TakemDown Dowin'; actual=None; score=81.25; margin=19.712
- ppocrv5_en_split `1440p/region_1795025142_centre.png` scale=1.0 JPEG60: false_rejection; expected='Shark Bait'; raw='Shark Bait cYanmn owb'; actual=None; score=64.516; margin=17.457
- ppocrv5_en_split `1440p/region_1795025142_right.png` scale=1.0 JPEG60: false_rejection; expected='Donation'; raw='Donation cYanmaGentaYellowb'; actual=None; score=54.902; margin=9.188
- ppocrv5_en_split `1440p/ocr_1795024923_right.png` scale=1.0 JPEG60: false_rejection; expected='Tooth Fairy'; raw='Tooth Fairy cYanmalowb'; actual=None; score=66.667; margin=25.49
- ppocrv5_en_split `1440p/ocr_1795025241_left.png` scale=1.0 JPEG60: false_rejection; expected='Get Jinxed'; raw='Get Jinxed cYanmowb'; actual=None; score=68.966; margin=22.299
- ppocrv5_en_split `1440p/ocr_1795025241_centre.png` scale=1.0 JPEG60: false_rejection; expected='Shark Bait'; raw='Shark Bait cYanmn owb'; actual=None; score=64.516; margin=17.457
- ppocrv5_en_split `1440p/ocr_1795025015_right.png` scale=1.0 JPEG60: false_rejection; expected='Donation'; raw='Donation cYanmaGentaYellowb'; actual=None; score=54.902; margin=9.188
- ppocrv5_en_split `snips/snip_015021_takeemdowndowndown.png` scale=1.0 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down"; actual=None; score=87.179; margin=27.179
- ppocrv5_en_split `snips/snip_015021_takeemdowndowndown.png` scale=0.75 PNG: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down canmaelow"; actual=None; score=81.633; margin=36.633
- ppocrv5_en_split `snips/snip_015021_takeemdowndowndown.png` scale=0.75 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down cYanmaGelow"; actual=None; score=78.431; margin=35.574
- ppocrv5_en_split `snips/snip_015021_takeemdowndowndown.png` scale=0.5 PNG: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down"; actual=None; score=87.179; margin=27.179
- ppocrv5_en_split `snips/snip_015021_takeemdowndowndown.png` scale=0.5 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down"; actual=None; score=87.179; margin=27.179
- ppocrv5_en_split `snips/snip_015021_takeemdowndowndown.png` scale=0.4 PNG: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down"; actual=None; score=87.179; margin=27.179
- ppocrv5_en_split `snips/snip_015021_takeemdowndowndown.png` scale=0.4 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down"; actual=None; score=87.179; margin=27.179
- ppocrv5_en_split `snips/snip_015907_takeemdowndowndown.png` scale=1.0 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down"; actual=None; score=87.179; margin=27.179
- ppocrv5_en_split `snips/snip_015907_takeemdowndowndown.png` scale=0.75 PNG: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down canmalow"; actual=None; score=83.333; margin=37.179
- ppocrv5_en_split `snips/snip_015907_takeemdowndowndown.png` scale=0.75 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down cYanmaGelow"; actual=None; score=78.431; margin=35.574
- ppocrv5_en_split `snips/snip_015907_takeemdowndowndown.png` scale=0.5 PNG: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down"; actual=None; score=87.179; margin=27.179
- ppocrv5_en_split `snips/snip_015907_takeemdowndowndown.png` scale=0.5 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down"; actual=None; score=87.179; margin=27.179
- ppocrv5_en_split `snips/snip_015907_takeemdowndowndown.png` scale=0.4 PNG: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down"; actual=None; score=87.179; margin=27.179
- ppocrv5_en_split `snips/snip_015907_takeemdowndowndown.png` scale=0.4 JPEG60: false_rejection; expected="Take'em Down Down Down"; raw="Take'em Down Down"; actual=None; score=87.179; margin=27.179
- rapidocr_v4_split `1440p/ocr_1795025241_left.png` scale=0.4 JPEG60: false_rejection; expected='Get Jinxed'; raw='Getlinxed'; actual=None; score=84.211; margin=24.211

## Paired divergences on original images

- `1440p/ocr_1795024923_centre.png` expected='Upgrade Stormsurge': ppocrv4_full=None, ppocrv4_historical_full=None, ppocrv4_historical_split='Upgrade Stormsurge', ppocrv4_split='Upgrade Stormsurge', ppocrv5_en_split=None, rapidocr_v4_split='Upgrade Stormsurge', tesseract='Upgrade Stormsurge'
- `1440p/ocr_1795024923_right.png` expected='Tooth Fairy': ppocrv4_full=None, ppocrv4_historical_full=None, ppocrv4_historical_split='Tooth Fairy', ppocrv4_split='Tooth Fairy', ppocrv5_en_split=None, rapidocr_v4_split='Tooth Fairy', tesseract='Tooth Fairy'
- `1440p/ocr_1795025015_centre.png` expected='Upgrade Stormsurge': ppocrv4_full=None, ppocrv4_historical_full=None, ppocrv4_historical_split='Upgrade Stormsurge', ppocrv4_split='Upgrade Stormsurge', ppocrv5_en_split=None, rapidocr_v4_split='Upgrade Stormsurge', tesseract='Upgrade Stormsurge'
- `1440p/ocr_1795025015_left.png` expected='Impassable': ppocrv4_full=None, ppocrv4_historical_full=None, ppocrv4_historical_split='Impassable', ppocrv4_split='Impassable', ppocrv5_en_split='Impassable', rapidocr_v4_split='Impassable', tesseract='Impassable'
- `1440p/ocr_1795025015_right.png` expected='Donation': ppocrv4_full='Donation', ppocrv4_historical_full='Donation', ppocrv4_historical_split='Donation', ppocrv4_split='Donation', ppocrv5_en_split=None, rapidocr_v4_split='Donation', tesseract='Donation'
- `1440p/ocr_1795025241_centre.png` expected='Shark Bait': ppocrv4_full=None, ppocrv4_historical_full=None, ppocrv4_historical_split='Shark Bait', ppocrv4_split='Shark Bait', ppocrv5_en_split=None, rapidocr_v4_split='Shark Bait', tesseract='Shark Bait'
- `1440p/ocr_1795025241_left.png` expected='Get Jinxed': ppocrv4_full=None, ppocrv4_historical_full=None, ppocrv4_historical_split='Get Jinxed', ppocrv4_split='Get Jinxed', ppocrv5_en_split=None, rapidocr_v4_split='Get Jinxed', tesseract='Get Jinxed'
- `1440p/ocr_1795025241_right.png` expected='Donation': ppocrv4_full='Donation', ppocrv4_historical_full='Donation', ppocrv4_historical_split='Donation', ppocrv4_split='Donation', ppocrv5_en_split=None, rapidocr_v4_split='Donation', tesseract='Donation'
- `1440p/region_1795025142_centre.png` expected='Shark Bait': ppocrv4_full=None, ppocrv4_historical_full=None, ppocrv4_historical_split='Shark Bait', ppocrv4_split='Shark Bait', ppocrv5_en_split=None, rapidocr_v4_split='Shark Bait', tesseract='Shark Bait'
- `1440p/region_1795025142_left.png` expected='Impassable': ppocrv4_full=None, ppocrv4_historical_full=None, ppocrv4_historical_split='Impassable', ppocrv4_split='Impassable', ppocrv5_en_split='Impassable', rapidocr_v4_split='Impassable', tesseract='Impassable'
- `1440p/region_1795025142_right.png` expected='Donation': ppocrv4_full='Donation', ppocrv4_historical_full='Donation', ppocrv4_historical_split='Donation', ppocrv4_split='Donation', ppocrv5_en_split=None, rapidocr_v4_split='Donation', tesseract='Donation'
- `snips/snip_015021_takeemdowndowndown.png` expected="Take'em Down Down Down": ppocrv4_full=None, ppocrv4_historical_full=None, ppocrv4_historical_split="Take'em Down Down Down", ppocrv4_split="Take'em Down Down Down", ppocrv5_en_split=None, rapidocr_v4_split="Take'em Down Down Down", tesseract="Take'em Down Down Down"
- `snips/snip_015907_takeemdowndowndown.png` expected="Take'em Down Down Down": ppocrv4_full=None, ppocrv4_historical_full=None, ppocrv4_historical_split="Take'em Down Down Down", ppocrv4_split="Take'em Down Down Down", ppocrv5_en_split=None, rapidocr_v4_split="Take'em Down Down Down", tesseract="Take'em Down Down Down"
- `snips/snip_023747_enpassant.png` expected='En Passant': ppocrv4_full=None, ppocrv4_historical_full=None, ppocrv4_historical_split='En Passant', ppocrv4_split='En Passant', ppocrv5_en_split='En Passant', rapidocr_v4_split='En Passant', tesseract='En Passant'
- `snips/snip_023747_itskillingtime.png` expected="It's Killing Time": ppocrv4_full=None, ppocrv4_historical_full=None, ppocrv4_historical_split="It's Killing Time", ppocrv4_split="It's Killing Time", ppocrv5_en_split="It's Killing Time", rapidocr_v4_split="It's Killing Time", tesseract="It's Killing Time"
- `snips/snip_121107_backtobasics.png` expected='Back To Basics': ppocrv4_full=None, ppocrv4_historical_full=None, ppocrv4_historical_split='Back To Basics', ppocrv4_split='Back To Basics', ppocrv5_en_split='Back To Basics', rapidocr_v4_split='Back To Basics', tesseract='Back To Basics'
- `snips/snip_121107_biggestsnowballever.png` expected='Biggest Snowball Ever': ppocrv4_full=None, ppocrv4_historical_full=None, ppocrv4_historical_split='Biggest Snowball Ever', ppocrv4_split='Biggest Snowball Ever', ppocrv5_en_split='Biggest Snowball Ever', rapidocr_v4_split='Biggest Snowball Ever', tesseract='Biggest Snowball Ever'
- `snips/snip_121107_goliath.png` expected='Goliath': ppocrv4_full=None, ppocrv4_historical_full=None, ppocrv4_historical_split='Goliath', ppocrv4_split='Goliath', ppocrv5_en_split='Goliath', rapidocr_v4_split='Goliath', tesseract='Goliath'

## Scope limitations

- 26 retrospective, non-independent images; original data contain repeated titles, two dialogs and five no-offer negatives; no Silver offer, full new triple, live reroll, or native Windows in-game evidence.
- The v5 English model has been evaluated with the benchmark's RGB resize / [-1,1] / CTC preprocessing and the same line splitter; do not infer all possible v5 production configurations from these measurements.
- No result changes the production Tesseract, current 90/8 matcher, capture or game state.
- Validate CPU/RSS/first-6-second behavior on the actual Windows/League/OP.GG device before contemplating promotion.
