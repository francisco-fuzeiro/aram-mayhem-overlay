---
name: continue-aram-oracle-ocr
description: Continue the ARAM Oracle independent OCR V1 research safely across chats, with evidence gates before any V1.2 authorization.
---

# ARAM Oracle OCR Research — Continuity and Next-Phase Rule

## 2026-11-22 — Active V1.1b implementation handoff (research-only)

**Current V1.1b child:** `research/v1-1b-ocr-safety-windows-20261122`, [draft PR #77](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/77), directly stacked on rules draft #75. **DO NOT MERGE.** All changed paths are `benchmarks/ocr_v11b/`, `.github/workflows/ocr-benchmark-v11b.yml`, this research skill and its execution ledger. No product runtime, N1, #71, main, matching policy, WGC, stale/epochs, or OfferLedger was changed. Tesseract remains authoritative.

**First mandatory read for next session:** `docs/research/ARAM_ORACLE_V1_1B_EXECUTION_2026-11-22.md` and `benchmarks/ocr_v11b/README.md` from PR #77, followed by current exact branch HEAD and its GitHub Actions jobs/artifacts. Then recheck this skill's original mandatory startup list below. The ledger is explicit about archival V1.1 evidence versus measured V1.1b experiments.

**Test-first record:** tests-only missing-module RED `5bd3fa1365bf387590cb10d01775e0e728d07a43` [Actions #44979601783](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44979601783); first integrity GREEN `33e2647d265f1721aa4ae80c172c135682d17933` [Actions #44979628353](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44979628353). Extended safety unit tests have passed on Linux and disposable Windows Actions VMs. The initial Windows real-model run exposed CRLF conversion of pinned JSON fixtures; its safe hash gate failed before inference, and the workflow was corrected with `core.autocrlf=false` before reference checkout. Recheck the **newest** CI, not only past GREEN.

**New research lab:** strict original SHA/consent/duplicate validation and local-only holdout runner; model-specific RGB/BGR + PIL/OpenCV + round/ceil and dynamic v4 width ablation; direct tensor parity against pinned RapidOCR 1.4.4; synthetic-text-only title matcher safety stress; isolated child-process CPU/RSS/cold-ready profiling and sanitized Windows/Linux CI metrics. Real models pinned to the V1.1 SHA values below. CI VM results never represent the user's personal Windows device.

**Remaining blockers:** no user-approved genuinely independent holdout has been supplied (**BLOCKED**); no real user's League/WGC/OP.GG/Alt+Tab/reroll/DPI/first-six-seconds and N1 native acceptance; Riot/policy gate unresolved. V1.2 **NO-GO** even if automated jobs succeed. Only user can separately authorize a future promotion. No new capture/log may enter the public repository without explicit privacy review.


## Mandatory rule (2026-11-22)

**The next eligible research phase is V1.1b — independent holdout, safety validation and Windows-readiness measurements. It is NOT V1.2 integration.** The V1.1 benchmark result is an offline reproduction, not permission to change the production OCR engine. The production recognizer remains **Tesseract**. Changing it, including shadow/compare runtime integration, requires a separate explicitly approved V1.2 task after all applicable gates are verified.

When the user starts a chat with **"ARAM Oracle: continuar OCR"**, fetch current GitHub refs, this skill, and the documents listed below before beginning. When the user says **"ARAM Oracle: preparar passagem OCR"**, update the research-only continuity/evidence ledger and return a new-chat prompt. These are chat conventions, not background jobs or executable slash commands.

## Source of truth and mandatory startup reads

1. Repository: `francisco-fuzeiro/aram-mayhem-overlay`.
2. V1.0 research: `docs/research/ARAM_ORACLE_V1_OCR_INVESTIGATION_2026-11-21.md` (draft #72).
3. Measured V1.1 evidence: `docs/research/ARAM_ORACLE_V1_1_OCR_BENCHMARK_2026-11-22.md` (draft #74).
4. This phase's gate: `docs/research/ARAM_ORACLE_V1_1B_NEXT_PHASE_GATE_2026-11-22.md`.
5. Isolated runner: `benchmarks/ocr_v11/{runner.py,test_runner.py,fetch_models.py,render_report.py}`; workflow `.github/workflows/ocr-benchmark-v11.yml`.
6. Baseline N1 sources **from their N1 branch** `fix/n1-js-bootstrap` / draft #71, SHA `7624b27c1d025c4183c2a78aa11609dda45ecf71`: `AGENTS.md`, `.agents/skills/continue-aram-oracle/SKILL.md`, `docs/PROJECT_STATE.md`, `docs/TODO.md`, `docs/DEVELOPMENT_LOG.md`, `docs/IMPLEMENTATION_PHASES.md`, `docs/N1_NATIVE_ACCEPTANCE.md`; inspect current production `slot_title_ocr.py`, `screen_ocr.py`, matching, temporal/epoch/stale contracts and OfferLedger read-only. Recheck the live branch/PR states; a frozen SHA is provenance, not a substitute for newer evidence.
7. The v3 index, audit and global rules; read only the **V1** section of `M-F_features.md`, not implementable feature blueprints outside scope.

**Branching:** #74 research branch `research/v1-1-ocr-independent-benchmark-20261122` at measured docs SHA `6f7168596b8dbdcc7df991499a20afee04005f3a`; its base is #72. Keep N1 #71 and `main` untouched. For V1.1b execution create a new isolated research child branch/draft PR only after validating current refs. This rules-only handoff is a child docs PR and does not itself start V1.1b.

## Verified V1.1 result and its limits

- **26/26** PP-OCRv4 with line segmentation and either historical or current 90/8 matching, **11/26** without segmentation, on **19 title + 2 dialogue + 5 no-offer** retrospectively approved PNGs.
- The same original images: Tesseract 19/19 titles; direct v4 19/19 matched (17/19 raw exact); RapidOCR using the same v4 weights 19/19 matched (19/19 raw exact); tested English v5 configuration 8/19 matched. The **1,456 engine/transform observations are correlated**, not 1,456 independent images. Zero wrong accepted IDs in this closed set does not estimate live false-positive rate.
- Confirm pinned binaries before inference: v4 SHA-256 `48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b`, v5 English SHA-256 `c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8`. Exact v4 source is `rapidocr-onnxruntime==1.4.4`.
- Historical v3 fixture hashes are **truncated 16-character prefixes**; fully computed fixture SHA-256 values live in the V1.1 `cases.json` evidence. Do not claim the archival reference used complete 64-character hashes.
- Benchmark latency/memory was observed on a Linux GitHub runner, not the user's Windows/League/OP.GG setup. V5 preprocessing sensitivity and the RapidOCR/direct preprocessing difference require isolation before model conclusions.
- N1 post-fix native Windows/League acceptance remains OPEN; do not infer PASS from Actions. Riot public-release policy review remains a separate blocker.

## V1.1b permissions and absolute boundaries

Allowed: **isolated benchmarks and tests**, pinned dependency/model retrieval, read-only inspection, user-approved privacy-reviewed independent holdouts, synthetic adversarial controls clearly labeled synthetic, and documentation of measured results. If relevant tools are available, actually run tests and resolve benchmark setup failures rather than ending with a research plan.

Not allowed: any production file/change, alternate default OCR, live runtime compare/shadow path, altered 90/8 thresholds, WGC/geometry/fallback changes, temporal confirmation, epochs/stale logic, OfferLedger, builds/recommendations, gameplay automation, N1 branches/PRs, merge to `main`, new app/runtime dependencies, V1.2 implementation, or claiming native Windows PASS without user-device evidence.

Repository currently public: do not commit user/private captures, gameplay logs, names, machine paths, credentials, unapproved images, or model binaries. Reuse only approved fixtures; request privacy review before committing any genuinely new screenshots. Synthetic crops and scaled versions of existing crops must **not** be presented as independent holdout samples.

## Stop/decision gates

1. Validate original frozen-image benchmark and real model/decoder checksums at the exact tested SHA.
2. Independently evaluate real unseen/holdout samples **if available with explicit user approval**. Report denominators, duplicates, positions, rarity, two-line, false positives, wrong non-null identities and abstentions. Missing holdout = `BLOCKED`, not inferred PASS.
3. Investigate errors and preprocessing variants (especially v5 English and RapidOCR) in separate clearly tagged conditions. Always compare original/raw vs normalization vs current strict matching 90/8. Never change thresholds for a better-looking score.
4. Where possible evaluate genuine native Windows startup, per-crop/three-crop p50/p95, CPU, RSS, UI capture/focus/DPI and League/OP.GG interference **on the user's device only with consent**. Otherwise mark `NOT TESTED`.
5. RED-first guard tests; real-model GREEN, full case-level error log, pinned versions/hashes and exact-final-SHA CI. Don't substitute mocks/skips for model inference.
6. No wrong accepted ID takes priority over the acceptance ratio; safe `None` is preferable. Explain statistical uncertainty and failure modes, not just aggregate accuracy.
7. **V1.2 stays NO-GO until appropriate N1 native validation, independent/negative safety evidence, measured Windows feasibility, policy gate and separate explicit user authorization.** Do not auto-start V1.2 even if research gates pass.

## Required handoff

Write a concise factual research entry with branch, draft PR, exact SHA, CI links, fixtures and model hashes, original/derived/holdout denominators, independent-vs-correlated labeling, all false positives and wrong IDs, per-position and two-line outcomes, performance/footprint caveats, Windows-specific outstanding cases, and an explicit GO/NO-GO recommendation. Keep code/docs/commits in English; talk to the user in PT-PT. Maintain the draft PR until validated.
