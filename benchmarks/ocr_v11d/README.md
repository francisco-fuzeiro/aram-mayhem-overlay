# OCR V1.1d — private native Windows lab and human-labeled captures

**Research only.** Never ship this folder with the installed overlay. No game
process, screen capture, input hook, OCR engine swap, telemetry or uploads.
Tesseract remains in production. V1.2 remains **NO-GO**.

## One-time separate checkout (PowerShell, from your existing Git clone)

Do not switch/reset your existing League or N1 worktree:

```powershell
git fetch origin research/v1-1d-ocr-native-labeler-20261122
git -c core.autocrlf=false worktree add --detach ..\aram-oracle-v11d origin/research/v1-1d-ocr-native-labeler-20261122
Set-Location ..\aram-oracle-v11d
```

**One principal command** from the new worktree, using PowerShell 5.1 or later:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\benchmarks\ocr_v11d\Start-OCRLab.ps1
```

The launcher calls the **existing** audited V1.1c benchmark and only then
opens the local graphical labeler. First use requires Internet solely for
V1.1c pinned setup (Python benchmark-only packages, reference and models).
Requirements: Git for Windows, Python **3.11 from python.org with Tcl/Tk**,
Tesseract OCR plus English `eng` data. The launcher does NOT install any of
those system executables. The V1.1c script checks exact model SHA-256 and
pinned dependency versions and runs isolated tests, controlled historical
images, synthetic text stress and five independent engine profiles.
V1.1d does not implement or override those mechanisms.

Useful later commands from the same checkout:

```powershell
# Reuse offline caches and run the benchmark before opening labeler
powershell -NoProfile -ExecutionPolicy Bypass -File .\benchmarks\ocr_v11d\Start-OCRLab.ps1 -Offline
# Just open the local labeler; no benchmarks or network setup
powershell -NoProfile -ExecutionPolicy Bypass -File .\benchmarks\ocr_v11d\Start-OCRLab.ps1 -LabelsOnly
# Benchmark without opening the GUI
powershell -NoProfile -ExecutionPolicy Bypass -File .\benchmarks\ocr_v11d\Start-OCRLab.ps1 -BenchOnly
```

Pass `-TesseractExe "C:\path\tesseract.exe"` when using a nonstandard
Tesseract installation; `-OutputRoot` is optional for a custom private lab
outside all Git repositories. For a machine that blocks Windows PowerShell,
run the PowerShell executable explicitly; no permanent execution-policy
change or elevation is required by the script.

### What happens locally

1. Select an **already captured image** with the file dialog. No automatic
   League, Vanguard, OP.GG, WGC or monitor capture occurs.
2. Drag the visible **title region** of the left card; choose its physical
   slot, rarity, two-line flag and **exact** canonical augment from the
   pinned verified 328-name catalog. Click **Add this crop**. Repeat for
   centre and right from the **same image**. Unknown titles must not be
   guessed or silently mapped to the nearest name.
3. Mark the scene (offer/reroll/transition/animation/dialog/no-offer),
   rerolled slot, focus/Alt+Tab, OP.GG present and manually observed DPI.
   Resolution comes from the screenshot dimensions. A reroll gets a **new
   frame ID**, even when it is the same logical offer. Dialog and no-offer
   regions have no expected title.
4. Use **Review + confirm frame**. Approval means that every crop is manually
   verified, no private player names/chat/account identifiers are present,
   and the entire pseudonymous session has been assigned *either*
   development *or* holdout **before viewing predictions**. Without this
   confirmation nothing is saved. The UI checks existing duplicates, exact
   reference-byte reuse, decoded pixels, slot/frame and session leakage.
5. **Prepare private manifests** delegates to the existing V1.1c manifest
   producer. This verifies SHA, provenance, consent and duplicates and seals
   the holdout. Preparing manifests does **not** execute OCR. Then press
   **Run OCR on DEVELOPMENT ONLY** for an explicitly confirmed local comparison.
   The UI deliberately has **no release-holdout button**.

All private files remain in
`%LOCALAPPDATA%\ARAMOracle\OCR-V11c\private-captures\` (unless
`-OutputRoot` is deliberately set):
`human_labels.csv`, `crops\`, `labels\`, `results\`.
Performance benchmark results (including `REPORT.md`) remain in the
separate V1.1c `results\<timestamp>\` location. Nothing is uploaded.

**Never commit, paste or attach** those images, screenshots, CSVs, source
paths, personal device profiles or detailed OCR audit JSON to GitHub.
The repository is currently **public**, even though the local worktree and
new captures are private. The original screenshots are not duplicated:
only manually selected title/negative crops are written to the private lab.

## Evidence boundaries and release gate

- Original/derived/synthetic evidence remains exactly the historical
  V1.1b/V1.1c measured data. No V1.1d image scores, new Windows numbers,
  false-positive rates or holdout conclusions exist until the user actually
  runs the local tools and independently approves captures.
- Human confirmation is not proof of independent sampling. Adjacent frames,
  a recompressed screenshot, or three cards from one frame are correlated;
  sessions are the split unit. The existing manifest gate only detects
  **exact** bytes/pixels plus original hash reuse. Manual provenance review
  is still required for recrops/near-duplicates.
- Only evaluate sealed holdout after freezing the candidate and doing a
  separate explicit unlock via V1.1c `evaluate_local --split holdout
  --unlock-holdout`. The GUI does not unlock or automatically run holdout.
- Score identity safety separately from raw text and normalized text:
  `strict_match_title`, unmodified threshold 90 and margin 8, canonical
  numeric IDs, wrong non-null IDs, negative false positives and safe
  rejections. The existing evaluator records per-slot, rarity, two-line,
  complete same-frame offers and per-case raw/normalized audit data.
- App-level League, first-six-second response, FPS, focus, DPI and OP.GG
  compatibility **cannot** be proven by this crop-only offline lab.
  User-device experiments and N1 native acceptance remain separate.
- If actual new samples have not been confirmed and sealed, independent
  holdout is **BLOCKED**. No automatic V1.2 promotion or runtime change.

## Tests

```powershell
$python = "$env:LOCALAPPDATA\ARAMOracle\OCR-V11c\venv\Scripts\python.exe"
& $python -m pytest -q benchmarks/ocr_v11d/test_label_core.py
```

The draft PR has independent Linux/Windows pure safety CI, without repeating
the prior pinned model benchmarks just to exercise a Tk UI. A successful
CI parse/compile does not certify GUI usability on the user's Windows desktop.
