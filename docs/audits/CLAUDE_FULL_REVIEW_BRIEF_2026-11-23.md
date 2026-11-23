# ARAM Oracle — independent Claude source, scoring, OCR and UX audit brief

**Requested:** 2026-11-23 by product owner. **Audit mode:** READ-ONLY initially; no edits, migrations, merges, dependency or OCR-promotion changes without separate user approval. **Reply language:** PT-PT. **Source-code documentation:** English. This file is the brief, **not an audit result**.

## Repository checkpoint and interpretation

- Intentional PUBLIC repository: https://github.com/francisco-fuzeiro/aram-mayhem-overlay
- Audit **draft PR #103 branch** `feat/f3-post-full-build-anvil-priorities-20261123` at known verified starting SHA `5c8d819ce6c14bff1b7ecf444c271b40fc2f7ce0`. Resolve latest live SHA and diff independently before beginning: never silently audit `main` as if it contained these changes.
- [Windows Actions #45173379783](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45173379783) at that exact SHA: **SUCCESS**, 2,054 Python PASS/27 SKIP, 87 JavaScript PASS, three JS syntax checks and 35 pinned real PP-OCRv4 PASS. **This is synthetic/research-fixture code validation, NOT current-patch native League, real shop, independent OCR holdout, accuracy or calibrated score success.**
- Dependency stack of draft PRs: #103 → #102 → #100 → #99 → #98 → #97 → #96 → #95 → #94 → #93 → #92 → #88 → #87 → #83 → #80 → #78 → #76. Draft #101 was closed as a redundant test-only experiment after finding #97; do not resurrect or count it as implemented. `main` remains at `ebc24c25937e4eeeff4000ea8d08d71d54f00bd0`, unmerged.
- Start with `AGENTS.md`, `.agents/skills/continue-aram-oracle/SKILL.md`, `docs/PROJECT_STATE.md`, `docs/TODO.md`, `docs/DEVELOPMENT_LOG.md`, `docs/IMPLEMENTATION_PHASES.md`, `docs/DESKTOP_ARCHITECTURE.md`, `docs/PLAYTEST_FINDINGS_2026-11-20.md`, `docs/audits/MAYHEM_SCORE_DATA_AUDIT_2026-11-22.md`, `docs/audits/F0_DIAGNOSIS_2026-11-22.md`, `docs/plans/ADAPTIVE_SCORING_ANVILS_PRODUCT_CONTRACT_2026-11-23.md`, `docs/audits/UX_AUDIT_SOURCE_NOTES_2026-11-23.md`.
- Live issues: [#49](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/issues/49) item eligibility/boots, [#82](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/issues/82) OCR, [#84](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/issues/84) score/data, [#85](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/issues/85) four cards, [#86](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/issues/86) automatic actual picked ID.

## Product truth the audit must preserve

1. **One dynamic and feasible build**, not several alternatives; actual chosen augments, inventory/components/boots, patch/mode eligibility, current gold, allies/enemies. After six acquired items, keep an optional justifiable movement-speed boot swap first and modelled Stat Anvil advice second. No fabricated Mayhem shop entitlement; old Ultra Hydra 226668 is now excluded by two-source source policy but the historical native incident's cause is not proven fixed.
2. **Augment full-roster adaptive classification**, NOT just local sorting of three offered cards: per champion/confirmed augments/current purchased items/enemy/allied composition; numeric 0.0–10.0 + defensible calibrated OP/S/A/B/C/D/E + comparable rank `#17/120` (example only). Rarity/pool/patch eligibility, modelled denominator, ties between rounded 8.7 examples, confidence/evidence/cold-start, and item synergies must be explicit. No hidden win-rate repackaging.
3. **Stat Anvils** can be purchased any time; on actually visible popup, OCR identifies the **specific** physical options, provides modelled score per option and disappears on close. #103 only supports conditional offline ranking and matching current three-slot ledger identities. **Automatic purchased-popup trigger does not exist**, and physical 4-card safety is unproven.
4. **Contextual overlay** with minimal permanent HUD, no interaction during combat, real augment/Anvil first, verified shop next, scoreboard optionally; Settings and diagnostics out of game. No shop-open inference from death or gold. User click-through and focus must remain safe.
5. **Riot and privacy:** check current actual Riot developer and licensed-data policy independently. Hiding win rate does not automatically make a dynamic rating lawful. No League input automation. Tesseract default, PP-OCRv4 opt-in; no model binaries, private screen captures/raw OCR, player names/IDs, credentials, sensitive local paths or copied protected assets in PUBLIC repo.

## Audit workstreams — questions to answer with exact source/line and repro

### P0 — Core correctness and lifecycle

- Trace physical client capture -> offer presence -> card count (3/4) -> title band -> OCR (Tesseract/optional v4) -> strict match 90/8 -> two-read/temporal/reroll -> match/epoch -> OfferLedger -> Pipeline -> websocket -> frontend. Prove or disprove wrong-accepted IDs, stale names after reroll, inconsistent source frames, focus loss, disconnected state, 3→4 transitions, previous match leakage and visible/closed offer persistence. Distinguish real user-observed incidents from synthetic tests and hypotheses.
- Verify **purchased Anvil popup** source: no level/respawn event may masquerade as actual purchase. Determine source-allowed approach and evidence/calibration required for 3/4 cards, timeouts, occlusion, changed option, purchase receipt/selected ID. Score none until exact current slots are physically verified. Keep unknown and inferred identity separate.
- Inspect #86: show/hide after confirmed disappearance vs positively identifying what was chosen; these are different requirements. Determine if permitted independent identity provider exists for standalone app; Overwolf GEP documentation is not standalone LCDA proof. If no permitted provider, retain honest fallback, never infer from click + OCR disappearance.
- Verify real #49 item classification, all item prerequisites/quests, inventory slot/recipe, true boot swap and next actionable purchase. `item_pool_v3` and #97–#102 UI fixes are offline contracts, **not actual Mayhem shop proof**.

### P0/P1 — Score and champion selection quality

- Current score audit: enumerate all Mayhem champion and augment catalog entries **by current patch, rarity, modelled/unmodelled, provenance**. Explain the 172 champion heuristic profiles, 25 custom synergies, 12-dimensional keyword parser, scaling-only models, any outdated/incomplete Arena descriptions, and required coverage. Do not assume prior counts still match current HEAD; measure them.
- `backend/engine/composite_score.py` without empirical input uses **35/60 synergy + 25/60 context** and outputs a rounded tenth, sample size 0/confidence 0. `augment_rating.py` maps heuristic raw signal through saturation `10*(1-exp(-max(raw,0)/1.2))`; `ranker.py` ranks **offered only**, not full roster, and item pool currently drives core-item suggestions but may not contribute to an augment's base score. Analyze actual ranking stability/ties/circular dependencies and how confirmed inventory, match context, team vs enemy and stat-specific synergy actually influence scores. Separate coverage, calibration and UI failures.
- Champion select `champion_select.py` S/A/B/C tiers are **provisional role/kit-fit bands**, not an experimentally validated Mayhem champion tier list. Audit self-vs-bench identity, current champion, teammate coverage and provisional labels; no fabricated source confidence.
- Propose defensible full-catalog ranking contract and calibration data options: same-rarity vs cross-rarity, rank among **modelled compatible** candidates, exact internal score before rounding, confidence and meaningful ties, label thresholds validated against independent holdout, patch rollover and weights vs chosen augment/owned items/enemies. A list of numeric standings from unreliable features is not a correct solution. Ask for legal/licensing and Riot review for any historical outcome data.
- `backend/engine/anvil_priorities.py` uses heuristic role/stat weights, 7 modelled dimensions and saturating `10*fit/(1+fit)` scores, no validated real options/amounts. Check missing options, whether low-quality title/keyword hints can claim modelled, conditional item effects, unknown enemies and overly strong role/HP boosts. Distinguish advisory stat preference from **ranking exact shown options**.

### P1 — Interaction, visibility and packaging

- Desktop Settings vs overlay; don't duplicate League HUD fields, cover rerolls or show full build during augment selection. Compare with historical UX audit but verify each current defect in actual branch.
- In-game click-through, event priority, champion select/offer/shop context, stale/popup close, resolution/DPI, Alt+Tab, Qt WebEngine, Windows focus/input. Mark unknown native behavior **NOT TESTED** rather than calling it broken.
- Validate real Windows app launch, overlay transparency, app assets, F1 server responsiveness, OCR CPU/RSS/fps, and only then consider D9–D11 installer and update security. No release recommendations from CI-only proof.

## Expected audit deliverables

Produce **one rigorous PT-PT report** using these sections:
1. **Executive verdict** (what really works offline, what is native FAIL/STOP, what is merely unverified; no exaggeration).
2. **Issue table**: P0/P1/P2; exact file:line/functions, reproduction steps, observable expected/actual, cause confidence and actual user impact; classify each as `PROVEN`, `USER-OBSERVED FAIL`, `SUSPECTED`, `BLOCKED` or `NOT TESTED`. Quote only source-safe technical excerpts.
3. **End-to-end trace**: especially OCR/offer/Anvil/picked augment and the single build/item-pool flow. Identify contract mismatches across Python JSON WS frontend.
4. **Scoring deep dive**: each mathematical formula, inputs and current provenance, how many champions/augments are truly evaluated, % unmodelled by rarity, testable examples with synthetic data, why 0.0–10.0 can be misleading, rank/tie/grade policy proposal, data requirements for meaningful strength. Avoid numerical performance claims unsupported by measurements.
5. **Anvils audit**: current implementation and exact missing detection/source, known vs unsupported stats, popup/3-or-4 card/close evidence and proposed safe integration.
6. **UX review** against contextual design, with concrete priority/visibility/overlay placement corrections.
7. **Riot/data licensing/privacy and Windows distribution gates**, source links/dates for any external verification.
8. **Prioritized executable remediation backlog** in small independent phases with precise files, tests-first RED scenario, expected GREEN invariant, CI/native acceptance, dependencies and stop conditions. Distinguish safe immediate offline fixes vs blocks requiring the user's controlled Windows evidence/approval.
9. **Disagreements/challenges to this brief** when code disproves it. Never adopt it blindly. Identify risky/overengineered parts and simplifications.
10. **Evidence appendix**: inspected SHA, tests actually executed with outputs, source citations, unverified assumptions, risks, known unresolved issues.

### Read-only execution and handoff

Do not edit application source, submit PRs, merge, install a dependency, download a model or ask for another live League game as a prerequisite to the initial audit. If repository write access is explicitly granted later, put the review artifact under `docs/audits/` in its own stacked draft PR with source and Windows checks, no user-private materials. Until then return the complete report in the conversation for owner review. Preserve all downstream work and flag any accidental data exposure. Avoid making a passing GitHub Windows workflow stand in for a real Mayhem playtest.
