# OCR V1.1c — isolated Windows and independent holdout

Research only; no OCR promotion or production changes. Never upload private
captures, manifest files, local results or raw OCR without an explicit privacy
review. Tesseract remains the installed product recognizer. V1.2 NO-GO.

## One-command Windows benchmark

From an existing repository checkout, use PowerShell:

~~~powershell
git fetch origin
git switch research/v1-1c-ocr-native-readiness-20261122
powershell -NoProfile -ExecutionPolicy Bypass -File .\benchmarks\ocr_v11c\Run-OCRBenchmark.ps1
~~~

Prerequisites: Git for Windows, Python 3.11, and Tesseract OCR including its
English language data. These system programs are **detected, not
automatically installed**. On first use the script creates a Python 3.11 venv
outside the repository, installs pinned benchmark-only Python packages, checks
a fixed reference Git SHA, downloads pinned v4/v5 ONNX weights, verifies their
full SHA-256 values and checks the source fixture hashes. Initial setup needs
internet access. All subsequent inference is local.

Run later with **no download or network setup**:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\benchmarks\ocr_v11c\Run-OCRBenchmark.ps1 -Offline
~~~

Tesseract installed outside the default location can be passed with
-TesseractExe "C:\path\to\tesseract.exe". The temporary PowerShell execution
policy applies only to that process.

The script runs existing safety tests, the separate synthetic matcher stress,
controlled original-crop comparisons, and four separate isolated worker
processes. It measures 26 old original images and eight three-crop batches:
cold-ready time, ONNX session load, per-crop and three-crop
mean/p50/p95/max, sampled CPU seconds, peak sampled process-tree RSS,
observed subprocesses, pinned model bytes and installed dependency bytes.
It creates a readable REPORT.md and machine JSON inside
%LOCALAPPDATA%\ARAMOracle\OCR-V11c\results\<timestamp>.
No new images, private labels or logs are uploaded. The script does not
launch League, Vanguard, OP.GG, WGC or any product executable. A successful
offline run **does not** validate game FPS, first-six-second live response or
the installed desktop application.

## Human-labeled new samples — never automatically captured

Holdout: **BLOCKED** until new approved captures are supplied locally.

During a user-operated ARAM Mayhem session, manually capture an offer and
crop three **physical card titles** from the exact same screenshot (left,
centre, right). Label the true title visually before running OCR. Record
rarity including Silver, two-line titles, individual rerolls, dialogs and
no-offer negatives. Make additional frames for unilateral rerolls, animation,
closing offers, focus/Alt+Tab, different DPI/resolution/HUD configurations,
and League with OP.GG simultaneously enabled. Never combine cards from two
different frames into one measured complete offer.

Screenshots and crops must remain in a private directory outside the Git
repository. Do not include account names, chat, player identifiers or
unrelated desktop content. Use pseudonymous source_session, source_frame,
offer_id identifiers. Each unique session must be assigned wholly to
development or wholly to holdout **before** examining engine predictions.

Prepare human_labels.csv next to your private crop folder. Columns:

~~~csv
file,source_session,source_frame,offer_id,slot,category,expected,rarity,two_line,split,privacy_approved
left.png,session001,frame001,offer001,left,title,Donation,Silver,false,development,yes
centre.png,session001,frame001,offer001,centre,title,Blunt Force,Silver,false,development,yes
right.png,session001,frame001,offer001,right,title,Erosion,Silver,false,development,yes
quiet.png,session002,frame002,,left,no_offer,,Unknown,false,holdout,yes
~~~

This table is a **schema illustration only**, not new game observations.
Replace the titles and metadata with human-verified actual contents; use
privacy_approved=yes only after checking the corresponding image. For
dialog/no-offer cases, expected is blank. Rerolls get a new source_frame,
even when the logical offer_id remains the same.

Generate independent SHA-verified manifests locally after the one-command
setup:

~~~powershell
$python = "$env:LOCALAPPDATA\ARAMOracle\OCR-V11c\venv\Scripts\python.exe"
$reference = "$env:LOCALAPPDATA\ARAMOracle\OCR-V11c\reference"
& $python -m benchmarks.ocr_v11c.manifest --labels "D:\OCR-Private\human_labels.csv" --root "D:\OCR-Private\crops" --reference $reference --out "D:\OCR-Private\labels"
~~~

The preparer requires approval and human labels, rejects reused frozen SHA,
identical encoded bytes, identical decoded pixels, duplicate source-frame
slots, unsafe paths, missing provenance and session leakage across splits.
A different-quality JPEG or neighboring screenshot can still be a derived
sample without being detected automatically: label provenance honestly.

The script creates PRIVATE development.manifest.json, holdout.manifest.json
and holdout.sha256. The latter seals the canonical manifest contents; it is
not proof of correct labels or unseen provenance. Run the existing holdout
evaluator **only on development first**:

~~~powershell
& $python -m benchmarks.ocr_v11b.run_holdout --reference $reference --models "$env:LOCALAPPDATA\ARAMOracle\OCR-V11c\models" --manifest "D:\OCR-Private\labels\development.manifest.json" --holdout-root "D:\OCR-Private\crops" --out "D:\OCR-Private\results\development-ocr.json"
~~~

Prefer the seal-checked V1.1c wrapper for both evaluation splits:

~~~powershell
& $python -m benchmarks.ocr_v11c.evaluate_local --labels-dir "D:\OCR-Private\labels" --reference $reference --models "$env:LOCALAPPDATA\ARAMOracle\OCR-V11c\models" --holdout-root "D:\OCR-Private\crops" --out "D:\OCR-Private\results\development-ocr.json"
~~~

After freezing candidate/configuration and reviewing all human labels, an
**explicit release action** is required for the sealed unseen holdout:

~~~powershell
& $python -m benchmarks.ocr_v11c.evaluate_local --labels-dir "D:\OCR-Private\labels" --reference $reference --models "$env:LOCALAPPDATA\ARAMOracle\OCR-V11c\models" --holdout-root "D:\OCR-Private\crops" --split holdout --unlock-holdout --out "D:\OCR-Private\results\holdout-ocr.json"
~~~

The wrapper verifies the holdout SHA-256 seal and rejects any private input
or output inside the Git checkout. Never publish the local reports: they
may contain human title labels and raw OCR text. Empty holdout = BLOCKED,
not an inferred zero-error success. The seal detects manifest edits, but
cannot detect mislabeled game frames or prove statistical independence.

## Interpretation and gate

Reported totals must separate retrospective original, transformed-derived,
synthetic text-only and genuinely new independent sessions; multiple crops
from one frame remain correlated. The holdout evaluator compares raw OCR,
normalized text, strict 90/8 catalog matching and numerical canonical IDs;
counts incorrect accepted IDs, negative false positives and safe rejections;
reports position, rarity, two-line and **same-frame-only** three-card counts.

Direct PP-OCRv4 with line splitting is the leading *offline* candidate.
Adaptive v4 and RapidOCR v4 achieve more exact raw text on the historical
set, but share model weights. English v5 showed 11 safe title rejections
on those originals. Confidence in unseen live offers is LOW. Do not start
V1.2 until new unseen safety coverage, native Windows League/OP.GG/WGC
evidence, N1 acceptance, Riot policy review and explicit approval.
