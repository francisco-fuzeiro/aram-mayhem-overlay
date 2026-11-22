# OCR V1.2c — Controlled native Windows / League validation

**Prepared:** 2026-11-22. **State:** protocol READY, all native cases **NOT TESTED**. Documentation preparation is not a gameplay result, test execution, an accuracy claim, or approval to promote PP-OCRv4.

**Scope:** public repository `francisco-fuzeiro/aram-mayhem-overlay`, `feat/ocr-v12-ppocrv4-optin-20261122`, open **draft PR #83** stacked directly on F1 draft #80, issue #82. Preserve the F1 / F0 stacked bases, other OCR research branches, and `main`. No merge. F1.3 native self-champion checks are separate and remain open. This protocol can be used only in a deliberately controlled, client-supported custom ARAM Mayhem session. If that mode is unavailable, mark the live gate BLOCKED; do not substitute or demand a normal competitive match.

## Safety and non-collection contract

- The user runs all native steps on their own Windows PC. **No automation of League input**, client injection, process memory access, API lockfile extraction, interactions with OP.GG, or continuous screenshot capture.
- Keep original League/account identities, full diagnostic journals, raw OCR transcripts, screenshots, title crops, filesystem paths, tokens, and unreviewed third-party assets **LOCAL**, outside the Git checkout. Do not upload them or paste them into the public issue/PR.
- The existing `ARAM_ORACLE_F0_TRACE=1` is **optional**, off by default, bounded, and local-only. It contains whitelisted reasons, physical slot rectangles relative to the verified client, and validated public catalog numeric IDs; use only with consent. Never enable a debug-screenshot or raw OCR collection option just for this protocol.
- Observe native card titles visually on the user PC and compare to Oracle; share **counts, per-case PASS/FAIL/BLOCKED/NOT TESTED, durations and coarse resource metrics only**. A mismatch can be described as `wrong accepted slot` without exposing a title or player identity. If investigation requires private evidence, retain it locally pending separate consent and safe workflow.
- Do not corrupt or delete installed models to test fallback. Do not weaken strict match **90 / 8**, original physical left / centre / right order, double-read confirmation, focus/capture evidence, single-slot reroll fencing, offer epochs or stale rejection.
- Any accepted **wrong numeric augment ID** or false positive on a negative scene is a **STOP/FAIL**. Do not recommend promotion to default. A safe rejection is not the same as a correct detection.

## Local environment preflight (without starting a match)

1. Check working tree is clean (`git status --short`). Fetch only after ensuring local changes will not be overwritten. On the target branch, compare `git rev-parse HEAD` with the **latest exact SHA on PR #83** and its completed Windows Actions; never use the older SHA from this protocol if PR #83 advanced.
2. Confirm Python 3.11, existing Tesseract with `eng` language and the same desktop launch path previously used for N1. Do not infer that a successful cold start on cached data proves the absent-cache startup path.
3. In Windows PowerShell, install optional dependencies explicitly: `python -m pip install -e ".[ocr-v4,overlay]"`. Verify the model offline with `python -m scripts.setup_ppocr_v4 --check`. If missing, the user may explicitly run `python -m scripts.setup_ppocr_v4` (this action downloads only a pinned public wheel); rerun `--check`. Never put the 10,857,958-byte ONNX file in Git.
4. Start once with Tesseract default (**remove** the opt-in env var in that terminal: `Remove-Item Env:ARAM_ORACLE_OCR_ENGINE -ErrorAction SilentlyContinue`; `python -m backend.desktop`). Check Settings/overlay/tray readiness and that OCR readiness is not misreported as actual match success. Quit cleanly before switching engine.
5. Start separately with `$env:ARAM_ORACLE_OCR_ENGINE = "ppocrv4"` then `python -m backend.desktop`. Check that the hash-verified model is available and the current process was restarted. Never switch OCR engine mid-offer/mid-game. If v4 is unavailable, Tesseract fallback is a dependency-survival check, **not** proof the v4 model worked.
6. Verify that a permitted **custom ARAM Mayhem** lobby is actually available. Check the current client directly; an older patch note or menu description does not prove current availability. Keep OP.GG closed for the first baseline; open it only in the explicit coexistence case, without copying any of its assets/code.

## Fixed matrix — all native cases initially NOT TESTED

| ID | Controlled user observation | Strict acceptance / evidence to record | Native state |
| --- | --- | --- | --- |
| **V12-N00** | Exact local checkout, Tesseract default, verified v4 model, separate opt-in launch | SHA matches PR #83; model check passes; opt-in uses restart; local desktop starts without forced remote data | **NOT TESTED** |
| **V12-N01** | Offer with three visible cards simultaneously | Every *accepted* title is mapped to its **actual physical** L/C/R card; no order-sorted swaps; unknowns abstain. Record eligible / accepted-correct / accepted-wrong / abstained | **NOT TESTED** |
| **V12-N02** | Manually reroll only left card, repeat for centre and right if possible | Only changed physical card identity refreshes, other two remain aligned; old card never persists as newly accepted. Count each possible slot separately | **NOT TESTED** |
| **V12-N03** | Naturally encountered wrapped/two-line titles and Silver cards | Recognize safely or explicitly abstain; never assemble half-title into a wrong canonical ID. If such a card never occurs, **NOT TESTED** | **NOT TESTED** |
| **V12-N04** | Normal no-offer, open dialog, animation or other in-client occlusion | Zero accepted augment IDs when an offer is unverified; uncertain/suspended state hides advice; no fabricated closure or choice. Dialog only if naturally/consensually accessible | **NOT TESTED** |
| **V12-N05** | Choice closure, subsequent offer, temporal double-read and match boundary | No recommendations for prior epochs/closed choices, no stale resurrection; manual choice never inferred from OCR alone | **NOT TESTED** |
| **V12-N06** | Ordinary Alt+Tab / League focus loss and return, window borderless | Focus loss suspends capture/marks unknown; return requires fresh proof, no stale visible recommendation; no click/keyboard interception | **NOT TESTED** |
| **V12-N07** | Run with OP.GG concurrently in a separate custom session | Oracle and OP.GG can coexist without focus, transparency, positioning, capture or FPS regression; if conflict, record FAIL without copying OP.GG assets | **NOT TESTED** |
| **V12-N08** | Resource measurements and responsiveness | Measure baseline with Oracle closed, Tesseract and v4 separately: approximate CPU %, working-set/RSS MB, League FPS band, elapsed first-six-second detection and response after reroll. Record device resolution and DPI **categories**, not PC identity | **NOT TESTED** |
| **V12-N09** | Independent unseen live session(s) after the frozen 26-image research corpus | Count new three-card offers, negative scenes and line-wraps separately; no reuse of historical 19 titles/7 negatives as independent holdout. Never publish crops or player details | **NOT TESTED** |
| **V12-N10** | Safely quit experimental v4 and restart without opt-in env var | Default Tesseract still works; Settings retains pregame-only policy; no engine change during a running match | **NOT TESTED** |

**Sampling target, not a claimed test result:** aim for at least 10 natural offers / 30 visible card exposures where feasible, covering three physical slots and one-slot rerolls; optional cases remain NOT TESTED if a supported custom lobby cannot reproduce them. Log accepted-correct, accepted-wrong, abstained and negative false-positive **counts**, never infer success from the denominator alone. Individual rerolls may add exposures; count them separately from base offers. Tesseract and v4 are different **sessions** unless a separately approved same-frame offline benchmark exists; do not describe unlike sessions as paired accuracy measurements.

## Recording CPU, memory, FPS and delay (manual, privacy-safe)

- Use Windows Task Manager / Performance Monitor to observe **Oracle process CPU % and working set MB**, with a stable idle baseline and while an actual offer is visible. Avoid capturing a general desktop or other people's content. Distinguish a peak from an approximate sustained range.
- Use the League client FPS readout on the device as a **band**, not a fabricated exact frame-time benchmark. Compare within similar controlled conditions and clearly state confounders (OP.GG, game scene, DPI, patch, hardware load). Record only coarse bands such as 60–90 or 90–120 FPS, never a precise claimed improvement without a measurement.
- Start the stopwatch visually when **the offer actually appears**, stop at the first stable (double-read) recommendation; separately time one-slot reroll. If first verified advice exceeds the existing six-second target, report FAIL/DEGRADED even if it eventually recognizes a title; do not assume latency from average cropped-image OCR time.
- A v4 model loading or fallback event is a pregame diagnostic, not permission to add gameplay-time network downloads. Note any focus flicker, delayed stale advice, blocked interaction or overlay obscuring the HUD.

## Sanitized report — manually fill after actual user-device session

```text
OCR V1.2c controlled native session (NO screenshots, names, paths, raw OCR)
Exact tested PR #83 HEAD SHA: [not yet verified locally]
Date / Windows resolution class / DPI class: [not tested]
Custom Mayhem available: unknown; session count: 0
Engine sessions: Tesseract=NOT TESTED; v4=NOT TESTED; OP.GG coexistence=NOT TESTED
V12-N00..N10: each NOT TESTED until directly observed
Natural offers: 0 observed | base-card exposures: 0 | independent holdout: 0
Accepted correct: NOT TESTED | accepted wrong: NOT TESTED | abstained: NOT TESTED
No-offer/dialog negative FP: NOT TESTED | one-slot reroll L/C/R: NOT TESTED
First stable advice within <=6s: NOT TESTED | reroll latency: NOT TESTED
Baseline / Tesseract / v4 CPU % and RSS MB: NOT TESTED
Baseline / Tesseract / v4 League FPS bands: NOT TESTED
Alt+Tab, stale epoch, two-line/Silver, OP.GG: NOT TESTED
Observed failure category only (no raw text): [none tested]
User conclusion: NOT TESTED
```

## Decision gates, failure handling, and next work

- **V1.2c cannot PASS from CI or protocol authoring.** Required: exact final Windows Actions on PR SHA, user-operated controlled Windows run, zero wrong accepted IDs in declared test set, zero false accepted negatives, physical L/C/R and reroll correctness, focus/epoch safety, measured latency/resources/OP.GG behavior, independent unseen evidence, and no release-policy blockers. A zero-count result means **NOT TESTED**, not zero failures.
- If custom Mayhem is unavailable, label native validation **BLOCKED**. If a wrong accepted ID or stale card is observed, stop promotion; record the sanitized failure category and reproduce with a private, consented local fixture and a deterministic **tests-only RED**. Patch the narrow proven defect, get targeted and full **GREEN** on a fresh SHA, and rerun the exact native case. Never relax match 90/8 or capture/temporal gates for a higher recognition count.
- **Settings/installer work is AFTER this gate**, not a hidden engine promotion. Future pregame-only Settings option: `Tesseract (default)` / `PP-OCRv4 (experimental)`, persisted using existing backend preference owner; show verified-model availability, safe start/restart requirement and Tesseract fallback; never switch a live OCR process mid-match. Installer hypothesis: explicit user-selected v4 model provisioning (no silent download), PyInstaller onedir + Inno Setup with separate model/license verification, signed release and rollback to default; measure package footprint on Windows first. No implementation of these features is claimed.
- Keep draft #83 stacked on draft #80; do not merge/modify `main`, F1, independent OCR research branches, or normal competitive League workflows. Riot public-release policy is a distinct unresolved gate.
