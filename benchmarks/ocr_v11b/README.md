# ARAM Oracle V1.1b — isolated research bench

This directory is **not a product dependency**. It does not launch League,
inject into the game, change WGC, replace Tesseract, adjust matching thresholds,
modify native settings, or create any V1.2 adapter. Production remains unchanged.

## Provenance and permitted datasets

- **Frozen originals**: precisely 26 previously approved crops in the pinned
  read-only N1 Git snapshot `7624b27c1d025c4183c2a78aa11609dda45ecf71`
  (19 titles, two dialogs, five no-offer cases). SHA-256 prefixes in the
  archival fixture index are 16 characters; complete file hashes are freshly
  computed by `read_cases`. Never describe these as new independent observations.
- **Derived**: scale/JPEG transforms from V1.1; refer to its 1,456 correlated
  observations and full annex; V1.1b preprocessing ablations are run on the
  frozen originals, *not* counted as new holdout samples.
- **Synthetic**: one explicit matching-only adversarial probe. It illustrates
  a title matcher accepting a catalog title even when the *hypothetical*
  context has no visible offer. This is not a real OCR false positive,
  screenshot, or independently tested visual detector.
- **Independent holdout**: NONE supplied/approved on 2026-11-22, **BLOCKED**.
  A local-only independent holdout runner is provided for future consented
  material, but its presence is not evidence that new data were collected.

No user screenshots, private crop hashes, paths, raw OCR logs or credentials
may be put into PRs or CI artifacts. The test scripts do not write images.
Any future holdout must be genuinely new, have human-labeled physical
slots/title vs dialog/no-offer ground truth and separate privacy approval.

## Exact experiment setup

| Component | Pin |
|---|---|
| Reference production matcher | N1 SHA `7624b27c1d025c4183c2a78aa11609dda45ecf71`; `strict_match_title` threshold **90**, margin **8** |
| Augment catalog | exactly 328 approved historical entries |
| v4 ONNX model | `48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b` |
| v5 English ONNX model | `c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8` |
| ONNX Runtime | 1.20.1 CPU, single-threaded |
| RapidOCR recognizer wrapper | rapidocr-onnxruntime 1.4.4 using **the same v4 weights** |
| Python | 3.11; NumPy 1.26.4; Pillow 11.1.0; OpenCV headless 4.10.0.84; RapidFuzz 3.12.2; pytesseract 0.3.13; psutil 6.1.1; mss 10.0.0 |

`controlled.py` varies **only** RGB/BGR channel order, PIL bilinear /
OpenCV linear resampling, round/ceil scaled width and (for one v4
comparison) adaptive recognition width. This separates the original
direct PIL/RGB policy from the historical RapidOCR v1.4.4 BGR/OpenCV/ceil/
adaptive-width policy. The runner also checks numerical input-tensor
parity against the actual pinned RapidOCR recognizer. Every
v4/v5 direct candidate uses the same zero padded normalized tensor and CTC
dictionary / decoder per ONNX model. These ablations can narrow hypotheses
about wrapper differences; they cannot prove that RapidOCR uses identical
internal resizing or that English v5 has its best possible decoder. Do not
select a candidate based on these same 26 old images.

## Windows PC: opt-in, offline benchmark

Run in PowerShell from the **existing repository checkout on the V1.1b branch**.
All assets and output are deliberately kept **outside the repository**.
No product dependencies or user Settings will be changed.

```powershell
git fetch origin
git -c core.autocrlf=false worktree add --detach ..\aram-oracle-ocr-reference 7624b27c1d025c4183c2a78aa11609dda45ecf71
py -3.11 -m venv ..\aram-oracle-v11b-venv
..\aram-oracle-v11b-venv\Scripts\Activate.ps1

python -m pip install "pytest==8.3.5" "onnxruntime==1.20.1" "rapidocr-onnxruntime==1.4.4" "numpy==1.26.4" "Pillow==11.1.0" "rapidfuzz==3.12.2" "pytesseract==0.3.13" "psutil==6.1.1" "opencv-python-headless==4.10.0.84" "mss==10.0.0"
python -m pytest -q benchmarks/ocr_v11b/test_validation.py benchmarks/ocr_v11b/test_controlled.py
python benchmarks/ocr_v11/fetch_models.py ..\aram-oracle-ocr-models
python -m benchmarks.ocr_v11b.profile_windows --reference ..\aram-oracle-ocr-reference --models ..\aram-oracle-ocr-models --out ..\aram-oracle-v11b-local\windows_profile.json
```

The `-c core.autocrlf=false` override is **per Git command**, not a
change to your normal Git settings. It preserves the byte-for-byte frozen
ground-truth JSON hashes on Windows (a default CRLF checkout would fail
the integrity gate correctly).

The model fetcher downloads exact weights **once** and verifies full SHA-256.
The profiling step requires the local Tesseract executable with English
language data installed; if needed, set `$env:TESSERACT_PATH` to the
known local executable, rather than changing global Windows settings.

The benchmark launches **separate Python subprocesses for each engine**. It
measures a fresh cold-ready process from spawn to pinned fixture+model load
before warmup; model-session load separately; 26 original per-crop readings
plus eight three-crop sequences, preprocessing and strict matching. It samples
total process-tree CPU and combined peak RSS, including short-lived Tesseract
subprocesses **when seen**. Sampling cannot guarantee capture of every
short subprocess, and summed RSS can count shared mappings twice.
Versioned installed distribution bytes and ONNX file bytes are reported.
It does **not** test League FPS, real WGC capture, OP.GG interference,
anti-cheat, user-facing latency or an actual packaged installer.

The `windows_profile.json` file contains aggregate counts and resources,
not crop images or OCR text. Review it locally before sharing. If the user
wishes to compare the exploratory candidate variants as well, execute:

```powershell
python -m benchmarks.ocr_v11b.run_inference --reference ..\aram-oracle-ocr-reference --models ..\aram-oracle-ocr-models --out ..\aram-oracle-v11b-local\experimental
```

Do not interpret Windows **GitHub Actions VM** outputs as measurements of
the user's PC. The Actions job does not open League.

## Local-only future independent holdout

The manifest must describe each *new* approved crop with: unique sample `id`,
`kind="independent"`, complete original `sha256`, `source_session`,
human-confirmed `expected` augment title or null, `category`
(`title`, `dialog`, `no_offer`), physical `slot`,
`privacy_approved=true`, and safe relative `file`. Optionally include
`offer_id`, `two_line` and `rarity`. Never put a path or user identifier in
sample IDs or session IDs.

**Do not upload the manifest or files to the public repository.** Keep them
outside the checkout, and run locally only once consent has been recorded:

```powershell
python -m benchmarks.ocr_v11b.run_holdout --reference ..\aram-oracle-ocr-reference --models ..\aram-oracle-ocr-models --manifest ..\private-holdout\manifest.json --holdout-root ..\private-holdout --out ..\private-holdout\local-ocr-results.json
```

All sample SHA-256 values are reverified from bytes before inference; the
manifest rejects known frozen original hashes, duplicate images, missing
session provenance, derived/synthetic sources and unapproved rows. The report
separates correct IDs, safe abstentions, wrong non-null IDs and negative false
positives, as well as per-physical-slot and complete three-card offers when
labeled. The labels and predictions remain **local only** until privacy review.

If new samples are unavailable, holdout remains `BLOCKED` without creating
fake data or reporting a zero-error rate as a live estimate.

## Safety gates and exit decision

An OCR model must not publish a title to the wrong physical card. Existing
production offer visibility, capture-proof, temporal two-read verification,
epoch/focus fences, duplicate suppression and OfferLedger remain untouched.
Fuzzy matching alone cannot prove card visibility; the synthetic matching-only
probe explicitly documents this threat model.

For **V1.2**, keep `NO-GO` pending independent holdout safety, real
League/OP.GG Windows performance/first-six-second evidence, full
left/centre/right and unilateral rerolls, N1 native validation, policy review,
and a separate explicit user authorization. The *best offline challenger*
does not automatically become the best integrated engine.


## Separate synthetic matcher stress (text only, not images)

For a deterministic audit of the unchanged 90/8 fuzzy matcher with
single-character corruptions, execute locally using the same pinned reference:

```powershell
python -m benchmarks.ocr_v11b.stress_matcher --reference ..\\aram-oracle-ocr-reference --out ..\\aram-oracle-v11b-local\\synthetic_stress.json
```

Wrong accepted IDs here describe **synthetic title-text corruption**, not
observed wrong image OCR associations or measured live false-positive rates.
The complete error classes are written to a local JSON. This experiment
must never be added to the independent holdout denominator.
