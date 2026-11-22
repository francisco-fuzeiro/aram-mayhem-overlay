# ARAM Oracle — Functional recovery after first real-match N1 failure

**Recorded:** 2026-11-22  
**Status:** APPROVED ROADMAP / IMPLEMENTATION NOT STARTED  
**Scope:** First usable, safe ARAM Oracle experience; N1 correctness recovery before UX polish or feature expansion  
**Base:** N1 draft [#73](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/73) exact `0c51de315c4a30bde636369b7d1ed5bcef03a571`; parent #71 → #70 → #69 → #68. No merge into `main`.

## Decision from actual user-operated match

The user played a **real ARAM match** with the N1 desktop, without screenshots or captured diagnostic evidence (a deliberate choice not to interrupt the match). Their reported observations:

| Area | Evidence | Status | What cannot yet be inferred |
| --- | --- | --- | --- |
| Desktop self-start | Prior Windows user screenshot showed standalone Settings starting successfully on #73 | **PASS, narrow native preflight** | No guarantee for new installations or a changed patch |
| Champion select | Available bench champions recognized; **player's own current champion incorrect** | **FAIL, user-observed** | Whether LCU local cell, numeric-to-alias mapping, update timing or frontend presentation caused it |
| Augment offers | Intermittently recognized in the middle of the match; sometimes displayed apparently unrelated identities | **FAIL, user-observed** | Whether capture, spatial crop, OCR, matching, temporal gate, stale epoch or UI caused it |
| Builds | Suggested an item that did not seem contextually justified or useful | **FAIL, user-observed** | Whether the source was wrong champion/augment/inventory/context, item availability or ranking |
| Useful decisions | User could not identify a reliable or helpful recommendation | **FAIL, user-observed** | Objective recommendation quality without matching ground truth |
| Full N1 native acceptance | First real-match functional validation, but no per-event record | **FAIL / NOT ACCEPTED** | No numerical accuracy, false-positive rate, HUD/focus PASS or repeatability claim |

**Do not convert user-observed symptoms into proven software root causes.** This is sufficient to block product acceptance and justify an evidence-first recovery, not to assert how often a defect occurs. A subsequent user-operated **custom game** may gather sanitized observations deliberately; no request to interrupt competitive play.

**Operating rule:** when champion, offer identity, patch/item eligibility or required context is unknown, contradictory, stale or unconfirmed, abstain with a short reason. A wrong confident suggestion is worse than an explicit absence of advice. Do not make picks/buys automatically or bypass existing Riot/privacy/anti-cheat restrictions.

## Delivery and branch boundaries

- Keep **one smaller draft PR per bounded work unit**. F0 starts from the verified #73 N1 lineage (or its latest verified N1 descendant after checking open PRs); stack subsequent F0/F1/F2/F3/F4 PRs without altering `main`. Preserve existing parentage; never merge without explicit approval.
- F0 is **diagnostics/replay/evidence only**. No algorithm rewrites, OCR engine promotion, thresholds 90/8, WGC fallback modifications, in-game capture outside focus safety, HUD/layout overhauls, installer, scoring-feature expansion, or automatic game actions.
- Parallel OCR research is on a different stack: [#72](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/72) → [#74](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/74) → [#75](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/75). It must not edit N1 runtime, and N1 recovery must not implement OCR V1.2 without a separate explicit decision.
- Before a code PR: capture a failing controlled fixture/test (**RED**); implement only a proved correction; run complete Python, JS, syntax and Windows Actions on the **exact final head** (**GREEN**). Do not count CI as native acceptance.
- All diagnostics default **disabled** or opt-in, local-only, bounded and redacted. Do not publish raw game screenshots, player names, PUUIDs, lockfiles, auth secrets, machine paths, coordinates that reveal unrelated applications, or third-party data without approved provenance. An event ID may be a synthetic/ephemeral non-reversible reference; no remote telemetry.
- Maintain the N1 ledger, state, TODO, log and continuation skill at every meaningful work unit.

## F0 — Functional data-lineage audit and diagnostic contract (FIRST)

**Purpose:** determine where each wrong user-visible recommendation originates, before changing the score or OCR engine. Exits with actionable reproducible failing tests or explicit BLOCKED evidence, not a rewritten pipeline.

### F0.1 — Read-only source-to-UI map

- Map **champ select**: LCU session → `localPlayerCellId` / `myTeam[].cellId` / `championId` / `benchChampions` → numeric ID map → `summarize_champion_select` → API status → frontend selection/current badge.
- Map **augments**: allowed League foreground and capture backend → offer visibility/stage → screenshot coordinate transform and physical L/C/R title crops → raw OCR → normalized title → strict catalog match (90, 8) → double-read / epoch / stale / reroll gates → UI.
- Map **builds**: confirmed champion → confirmed chosen augments (not merely detected offers) → inventory/gold/slots/boot upgrade → verified two-source and patch-matched item pool → enemy and ally profiles → `Pipeline` / `suggest_build` → serialized reason and UI surface.
- Identify each stage's input contract, output, source, freshness, uncertainty, skip/abstain rule and actual instrumentation location. Flag any stage that silently assumes identity or returns a plausible value without evidence.

**Output:** a compact, versioned data-lineage table and fault tree in repo documentation, with source file/function anchors (not guesses).

### F0.2 — Minimal safe diagnostic events and replay fixtures

- Define a privacy-safe **local diagnostic envelope**, for example `feature`, `stage`, `status`, `reason_code`, `source_kind`, `data_version`, `offer_epoch`, `slot`, `confidence_band`, `age_ms` and a synthetic trace correlation token when justified. Explicitly mark unavailable fields; **never invent confidence**.
- Record only bounded enum/status information needed to disambiguate wrong local champion, bench identity, offer crop, accepted/rejected OCR, stale data, verified pool, and recommendation reason. Ensure events don't leak player identifiers, full OCR text, names, unredacted image bytes or lockfile credentials.
- Reuse existing diagnostic event/log infrastructure rather than creating a competing observability system. Keep screenshots **off by default** and never automatically capture hidden/unfocused desktop content.
- Build deterministic, sanitized fixtures for: local champion != bench, champion swap or late identity, unmapped champion ID, 3 physical augment slots, no offer/dialog, reroll of a single card, two-read/epoch stale response, missing verified item pool, owned inventory and enemy composition. New private examples require explicit local redaction and user approval before inclusion.

**Output:** RED tests to reveal each critical gap and a reproducible local replay/report with which the next phases can distinguish source failure vs UI error. No claims that newly made synthetic cases reproduce the user's unlogged match.

### F0.3 — Root-cause triage and decision gate

- Classify each reported failure **proven**, **suspected**, **blocked for evidence** or **not tested**.
- Report whether the wrong visible suggestion is caused by **source identity**, **capture/geometry**, **OCR raw**, **matching**, **temporal state**, **context assembly**, **eligibility**, **scoring**, or **presentation**, with concrete proof for any designation.
- Produce a ranked list of **small, independent F1/F2/F3 correction PRs**, each with one minimal RED scenario, acceptance criteria, and manual Windows check.
- F0 is complete only when diagnostic safety is tested, source-to-UI paths documented, source and UI IDs no longer conflated in fixtures, and the unresolved real-match observations are explicitly tracked. F0 completion **does not mean the overlay is usable**.

## F1 — Champion select: authoritative local identity

Split into separate tiny PRs only after F0 has established actual failure points:

- **F1.1:** LCU local-cell mapping, swaps/bench/team cases, numeric alias coverage, and missing local identity fail-closed; no bench candidate becomes `current` merely because it is a valid champion.
- **F1.2:** Live updates and frontend `current` badge synchronization; stale/late transitions should not display a previous player's champion or an unverified local pick.
- **F1.3:** Read-only status and optional local trace verification in user-controlled custom lobby. Clearly distinguish **own champion**, **swappable bench**, and **allies**. No champion pick actions.
- **Gate:** 100% correct local champion for a **declared fixed test matrix** including swap/missing data; no unverified identity shown as current; user Windows evidence before native PASS. This is not a promise of 100% across all future matches.

## F2 — Augment offer detection, physical slots, rerolls and confirmation

- **F2.1:** Verify **offer-present** cue and capture/focus/state transitions (including dialog/no offer); no UI hint based only on assumed champion levels or death.
- **F2.2:** Validate resolution/DPI/coordinate transforms and true physical **left / centre / right** crops; reject ambiguous 4-card Maestro unless separately supported.
- **F2.3:** Compare **raw OCR**, preprocessing/line splitting, strict title matching (90 and margin 8), duplicates and negative rejections with explicit stage reasons. Continue existing production Tesseract until independent V1.2 approval. Do not mistake benchmark success for live acceptance.
- **F2.4:** Reroll one slot at a time; double-read, offer epoch, stale results, confirmed identity, never infer an augment pick from disappearance. Only explicitly confirmed augments can influence builds.
- **Gate:** zero **wrong accepted IDs within a declared controlled test corpus**; uncertain cards safely abstain, valid cards resolve within existing six-second response target when measurable; native custom-game L/C/R and reroll evidence before acceptance.

## F3 — Explainable, feasible build recommendations

- **F3.1:** Prove every recommendation's source champion, confirmed augment list, inventory, gold, slots, boots, team/enemy context, current build style, and verified item patch/pool.
- **F3.2:** Attach safe reason codes and factor contributions to the current next item (without disguising win rates); diagnose why a candidate wins/loses. Compare with human-confirmed illustrative scenarios; do not change weights without evidence and permission.
- **F3.3:** Fail closed when champion/owned items/augment status/patch/shop eligibility are uncertain. No quest/augment-only, conditional or inaccessible items in an ordinary shop shortlist; no unavailable item suggested as purchasable. Boot replacement with movement-speed alternative is allowed only when grounded in verified item data and inventory.
- **Gate:** 0 invalid shop candidates among enumerated fixtures, every shown item has valid eligibility and an auditable reason, unknown inputs abstain, and Windows custom shop evidence before native PASS. Do not claim objective 'best build' without comparative outcome evidence.

## F4 — Contextual HUD and decision usefulness

**Only after F1–F3 gates.** Keep one AUGMENTS panel visible only on verified offers; short actionable suggestion near confirmed relevant event; shop/build when the shop-open signal is verifiable, not inferred from gold/death. Combat should remain minimal. Expand to details on request; avoid covering score, clock, gold, map or essential controls. Validate Alt+H/Alt+O, click-through, tray and focus rules without accidental gameplay input.

**Gate:** native custom-game evidence that panels appear and disappear for the correct reasons, no critical HUD occlusion, no stale suggestions after reroll/pick, and user finds actual decisions useful. Style/installer work is outside this recovery chain.

## Verification ladder, in order

1. **Unit and contract tests:** source identity, safe abstention, temporal/epoch rules, shop provenance and reason codes.
2. **Offline replay / approved fixtures:** original and negative controls; no wrong accepted IDs; exact sample denominators and source provenance.
3. **Local integration (without League):** LCU-shaped sanitized state → engine → API → JS UI; event tracing without private data.
4. **User-controlled custom match (Windows, optional OP.GG):** one grouped run with intentional champion/bench state, three-card offer, one reroll, confirmed augment, shop and HUD. Screenshots/logs only when consciously captured and redacted by user.
5. **Real match observation:** optional stability/usability after custom acceptance, with no obligation for player to capture screenshots mid-game.

Each level reports `PASS`, `FAIL`, `BLOCKED`, or `NOT TESTED` independently. A prior step passing does not override a real-game FAIL. Any native/game PASS requires direct device evidence.

## OCR cross-track decision, checked 2026-11-22

**Sources:**
- [V1 investigation #72](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/72)
- [V1.1 real benchmark and report #74](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/74), `docs/research/ARAM_ORACLE_V1_1_OCR_BENCHMARK_2026-11-22.md`; exact final report SHA `6f7168596b8dbdcc7df991499a20afee04005f3a`, [Actions #44976580610](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44976580610)
- [V1.1b next research gate / separate continuity skill #75](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/75), `docs/research/ARAM_ORACLE_V1_1B_NEXT_PHASE_GATE_2026-11-22.md`

The **original 26 cases are 19 titled augment crops + 2 dialog + 5 no-offer**; not 26 positive title reads. In the same historical data, Tesseract and PP-OCRv4 with line splitting each matched **19/19 IDs plus 7/7 correct negatives**; PP-OCRv4 *without* line splitting matched only 4/19 title IDs. RapidOCR v4 (same underlying v4 weights) also matched all cases. Tested PP-OCRv5 English split matched **8/19 positive title IDs** at original resolution and correctly rejected 7/7 negatives. All 1,456 derived/engine observations reported **no accepted wrong IDs**, but derived resizes/JPEGs are not independent evidence, and this does **not** rebut the user's live wrong-ID symptoms.

On the independent **Linux** executor (not the user's Windows), measured mean/p95 OCR time per original crop: Tesseract **113.22/210.40 ms**; direct v4 with line splitting **40.38/58.86 ms**. This supports researching v4 for latency, **not** proving better in-game accuracy. Models have verified SHA-256; OCR matching must preserve `strict_match_title` threshold **90 / margin 8** until separately authorized. Future **V1.1b** focuses on independent unseen holdout, safety failure taxonomy, preprocessing and opt-in Windows readiness, **without changing production**. **V1.2 engine promotion is NO-GO and needs separate user approval** after N1/native/holdout/policy gates. F2 may consume research evidence read-only; must not modify or cherry-pick results on #72/#74/#75.

## Immediate next step

**Start F0.1 as a separate authorized implementation conversation**, after reading current refs and any newer N1/OCR drafts. Baseline should be the final documentation-only recovery plan child of #73, verified on its own exact SHA. The first F0 PR should map source-to-UI lineage, introduce only minimal safe diagnostic contract/tests and deliver concrete reproducible uncertainty classification. It should **not** attempt to fix F1/F2/F3 simultaneously.
