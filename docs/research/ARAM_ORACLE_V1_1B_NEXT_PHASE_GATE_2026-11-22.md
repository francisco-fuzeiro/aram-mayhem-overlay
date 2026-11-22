# ARAM Oracle — V1.1b next-phase authorization gate

**Recorded:** 2026-11-22  
**Status:** Next eligible RESEARCH phase; implementation of V1.2 NOT AUTHORIZED  
**Parent evidence:** V1.0 draft PR #72, measured V1.1 draft PR #74  
**Protected:** N1 draft PR #71 and `main`

## Objective

Close as much as possible of the remaining V1.1 **external-validity** and **runtime-feasibility** uncertainty without modifying the installed overlay or the current Tesseract recognizer. The next work unit is called **V1.1b: Independent Holdout and Native Readiness**. It is not V1.2, not a production feature, and it does not itself approve promotion.

## Starting evidence

- [Independent V1.1 measured report](ARAM_ORACLE_V1_1_OCR_BENCHMARK_2026-11-22.md).
- [V1.0 research](ARAM_ORACLE_V1_OCR_INVESTIGATION_2026-11-21.md).
- Measured benchmark commit `c1e6db237ded9e5aaf1ddb6a523eecff02021d7e`, Actions [#44976307190](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44976307190); V1.1 full report SHA `6f7168596b8dbdcc7df991499a20afee04005f3a`, exact-head Actions [#44976580610](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44976580610).
- Reproduced: v4 split 26/26; unsplit 11/26; production Tesseract also 26/26 on the retrospective set; RapidOCR v4 also 26/26; tested v5 English only 15/26. **26 observations are not a live match acceptance test.**
- Integrity tests 9/9 PASS. Models are pinned and verified with full 64-character SHA-256; approved fixture manifest checks use historical 16-character SHA-256 prefixes and recorded new full digests. Keep these statements distinct.
- No new independent unseen offers and no native Windows/League/OP.GG OCR comparison have been demonstrated.

## Work packages (research-only)

### V1.1b-A — Independent holdout and data integrity

Inventory any newly user-approved samples **outside** the original 26 and all their transformed copies. Before committing, establish source, human-confirmed title/slot/negative labeling, uniqueness, original pixel provenance and privacy approval. Never publish private screenshots or logs. If new samples are unavailable, mark holdout BLOCKED while completing other evidence-building work. Derivative crops, resizes, compression and synthetic adversarial controls are useful robustness tests but **not independent samples**.

### V1.1b-B — Safety error taxonomy

On the same aligned cases and 328-item catalog, evaluate **raw text**, normalized text, accepted match (score 90 / margin 8), wrong non-null IDs (highest severity), negative false positives, correct negatives, false rejections, left/centre/right physical slots, short/multi-line titles and failure/occlusion. Store every divergence and whether it is an OCR, line split, normalization, tie/duplicate, or matching problem. Failing safely must be reported separately from a false identity.

### V1.1b-C — Controlled candidate-preprocessing audit

Compare v4 direct with rapidocr-onnxruntime recognizer-only on identical pinned v4 weights. Isolate differences in image color order, preprocessing, resize/pad, dictionary and decoding. Explore **documented** v5 English preprocessing/decoder variants separately without cherry-picking on the same 26 cases as proof of unseen accuracy. Never relabel RapidOCR as a new model. Preserve the current `strict_match_title` 90/8 in all product-comparable results.

### V1.1b-D — Windows readiness and performance

Prepare an **opt-in** local benchmark command using approved data to profile the user's Windows machine: Tesseract executable/version, Python packages, actual model loading/cold-start, warm-up, p50/p95/max crop, three sequential crops, preprocessing, matching, CPU process tree (including Tesseract subprocesses), peak RSS and installed-file footprint. Do not change existing app dependencies or launch League/Vanguard automatically. Record any Windows/League/OP.GG/game capture tests as NOT TESTED until the user's independent device evidence is returned; do not infer native success from Linux or Windows Actions.

### V1.1b-E — Decision and continuity

Maintain tests-first RED→GREEN, use isolated Actions when local dependencies fail, pin dependencies and model SHA, retain sanitized case-by-case evidence and exact-final-commit CI. Provide a paired comparison and uncertainty-aware verdict. Update only the independent research branch/PR and research handoff documents. Do not touch N1 branches, `main`, application code or runtime settings.

## Exit criteria / GO-NO-GO

A V1.1b report can be marked **research complete** only when its executed tests are GREEN, its measured/untested coverage is accurate, and all observed wrong accepted IDs and negative false positives have individual evidence and risk analysis. A missing independent holdout, unvalidated Windows runtime or N1 native acceptance remains an explicit blocker: never fabricate PASS or an acceptance percentage.

**GO for starting V1.2 is a separate future decision**, and requires sufficiently representative independent safe-recognition evidence, full negative/adversarial coverage, acceptable measured device footprint, N1 native acceptance and Riot policy review as applicable **plus a separate explicit user instruction**. No automatic promotion even if V1.1b proves promising. Current state: **V1.2 NO-GO**.

## Repository scope and precedence

The original `AGENTS.md` and general `continue-aram-oracle` skill live on the N1 branch; this research PR stack does not duplicate or replace those files. The research-specific continuity skill `.agents/skills/continue-aram-oracle-ocr/SKILL.md` applies to OCR research requests. Read the general rules from the current N1 ref **read-only**. Keep technical documentation and Git commits in English, user communication in PT-PT.
