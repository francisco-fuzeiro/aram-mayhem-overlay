# ARAM Oracle — Product and UX TODO

> Canonical, persistent backlog for this repository. Created 2026-11-18 (Europe/Lisbon).
> Incorporates the **"Auditoria UX — ARAM Oracle"** discussion in the ChatGPT Overlay LoL project, the user-supplied `funcionalidades.md` specification, the first real in-game Jinx screenshot, and the current stacked PR history.
> The UX audit was recovered from the cross-chat discussion summary; this is an actionable synthesis, **not** a verbatim export of that conversation.

## Working rules

- **Priority:** P0 = missing core behavior or unsafe/confusing output; P1 = contextual experience and usefulness; P2 = polish/robustness.
- `[x]` means the narrowly worded *implementation* or *test* listed on that line has evidence. It **does not** imply live Windows validation. Separate unchecked validation tasks remain until real evidence exists.
- For each completed item, preserve the task ID, check it off, and add the PR/commit, test output or Windows observation to `docs/DEVELOPMENT_LOG.md`. Do not remove historical tasks.
- Keep `docs/PROJECT_STATE.md` synchronized. Run relevant Python/JavaScript tests and verify the **latest** Windows GitHub Actions run after changes. An unfinished/failed run is not a pass.
- The overlay must remain read-only with respect to League. No automatic selections or buys; only player-visible, permitted data. Do not enable experimental empirical augment ratings without Riot policy review.
- All application copy, code, and repository documentation are **English**; user-facing ChatGPT communication is **PT-PT**.
- **Merge gate:** All PRs #1–#12 remain stacked drafts; never merge `main` without explicit user approval.

## UX audit decision: event-driven companion, not a permanent dashboard

Target states and *expected* presentation (**not all implemented**):

| Context | Expected UX |
| --- | --- |
| Loading / no actionable event | Hidden or minimal non-interfering status |
| Active combat | Hidden or nearly invisible; no persistent giant lists |
| Three augment offers / reroll | **Highest priority**: 3 compact scored alternatives, clear uncertainty and short explanations |
| Shop open (when reliably observed) | Next feasible purchase + one optional alternative; no speculative auto-buy |
| Scoreboard (only if reliably and permissibly known) | Optional compact enemy/team summary |
| Death / respawn | Do not confuse respawn with an offer; update or reveal only relevant information |
| Champion Select | Small contextual rating/options panel; never interfere with selection |
| End of game | Close in-game advice; feedback lives on the separate Settings page |

If multiple contexts overlap, priority is **augment offer > shop > optional scoreboard**, and combat/visibility safety takes precedence when game context is uncertain. Until legitimate shop/scoreboard observability is confirmed, do not pretend to detect either.


## Approved Functional Fix Plan — M1 foundations / M2 execution (2026-11-18)

> The user-approved M1–M8 Functional Fix Implementation Plan supersedes A-FIX as the implementation order; historical A-FUNC and A-FIX IDs remain traceability references. The full plan and audit report are available on separate docs-only draft PR #19 (`docs/a-func-audit-report`), but are not present in the M1 baseline branch; keep that historical branch independent and use the approved A1–E3 sequence. Preserve the independent [documentation draft PR #18](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/18).

- [x] **M1 / P0.1 — Poll-loop test harness (code/CI only).** Extracted `poll_tick(state, deps, now)`; deterministic LCDA/LCU/OCR mocks; AUD-03a (passive level-up false pick), AUD-07 (transient LCDA game end), AUD-03d (health-based OCR close) are tracked with `xfail(strict=True)`. [Draft PR #20](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/20); [Windows Actions 44394538148](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44394538148): 306 Python passed, 3 xfailed, 18 Node passed. **Defects NOT fixed.**
- [x] **M1 / P0.2 — Frontend message harness (code/CI only).** Node DOM/WebSocket stubs exercise `handleMessage`, renderers, `game_ended`, `no_game`, disconnect, stale data and new champion. [Draft PR #21](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/21); [Windows headless CI 44395754449](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44395754449): 306 Python passed, 3 strict xfailed; 24 JS passed and 4 TODO (AUD-05/06 known defects). **F1–F5 are not fixed.**
- [x] **M1 / P0.3 — Structured diagnostics (code/CI only).** [Draft PR #22](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/22) implements strict-field JSONL diagnostics, queue/nonblocking worker, Windows `%LOCALAPPDATA%/ARAMOracle/logs` (or OS user state directory), 256 KiB/file × up to 4 files, whitelisted LCDA/OCR/inference/confirmation/match transitions, and disables automatic screenshots at OCR source and call sites. [Windows headless Actions 44398134318](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44398134318): 317 Python passed, 3 strict xfailed; 24 Node passed, 4 TODO. No real-game evidence.
- [ ] **M1 / Windows acceptance.** Real League client/Windows/Qt/OCR behavior needs separate evidence; headless Actions is not a playtest.
- [ ] **G4 security priority review:** Localhost API Host/Origin/authorization must be hardened before distribution; evaluate moving forward, without implementing in M1.
- [ ] **G1/G2 Mayhem data source:** Validate source, patch version and augment catalog coverage before M7 scoring accuracy acceptance.
- [ ] **A3 manual fallback:** Confirming an augment must not demand clicks during combat; design non-intrusive unresolved state without manufacturing a choice.

## M2 — Stop false outputs (approved plan in draft PR #19)

- [x] **M2 / A1 — No pick from stat changes (AUD-03a), code implementation.** [Draft PR #23](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/23) on `fix/m2-a1-no-stat-change-picks`, based on M1/P0.3. Converted the AUD-03a strict xfail to a normal assertion and added deterministic purchase, death/respawn and OCR-disappearance path tests **before** the code change. Passive champion stat changes no longer arm augmentation inference; actual OCR disappearance still uses the pre-existing confirmation path pending A3. [Windows headless code/test Actions 44401726776](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44401726776) passed: 321 Python, 2 xfailed, 24 JS, 4 TODO; final documentation-head CI is checked independently. Real-game validation remains open, and A1 is not a complete no-false-picks guarantee.
- [x] **M2 / A2 — Ignore damage for scan-window lifetime (AUD-03d), code/CI only.** [Draft PR #24](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/24), branch `fix/m2-a2-health-independent-ocr-window`, stacked on A1 draft PR #23. Tests-first commits `d88f472c` and `b1b60e91` demonstrated the health-close defect (low HP at level 7, damage with known cards, OCR disappearance, and structured diagnostic events), and promoted AUD-03d from strict xfail to a normal test. Fix `c42625c9` removes only the health-based close/confirmation/log branch in `poll_tick`; OCR-disappearance and actual pick handling remain pending A3. [Windows headless code Actions 44403646160](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44403646160) passed: **325 Python, 1 strict xfailed (AUD-07), 1 warning; 24 JS passed, 4 TODO**. Final documentation-head CI and real League/Windows gameplay acceptance are separate checks.
- [x] **M2 / A3 — Confirm picks, never infer an automatic choice (AUD-03a), code/CI only.** [Draft PR #25](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/25), branch `fix/m2-a3-confirm-not-infer-augment-picks`, stacked on A2 draft PR #24. Tests-first `86db6853`, `e0b51feb`, `1a509a5c` reproduced level/item-change and high-confidence false picks, all-catalog guessing and missing pending state. Implementation `9f729615` removes automatic augment/stat-anvil selection and requires user confirmation; 'likely' only if original observed cards, unchanged level/inventory and match confidence >= 0.6. Offer disappearance closes scanning, retains unresolved cards, and prevents duplicate confirmation/new scans until manual choice or reset. UI test `b6e2e675` and fix `a653c1f2` keep confirmation panel collapsed during combat and show honest no-OCR fallback. Manual-choice regression `f03a5d36`. [Windows headless code Actions 44406383857](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44406383857) succeeded (334 Python passed, 1 strict xfailed AUD-07, 26 JavaScript passed, 4 TODO); verify the final documentation-head CI independently. No real League game acceptance.
- [x] **M2 / E1 — Catalog word-boundary parsing, Donation hint, cache schema (AUD-04b/c), code/CI only.** [Draft PR #26](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/26), tests-first red [Actions 44408360190](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44408360190) (4 reproducible failures), fix [Actions 44408721703](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44408721703) (339 Python passed, 1 AUD-07 xfailed; 26 JS passed, 4 TODO). Correct whole-term detection and remove incorrect Donation HP hint; version augment caches and updater cache checks. E1 final documentation-head [Windows CI 44409175703](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44409175703) green; real Windows/League acceptance pending.
- [x] **M2 / E2 — Model coverage and provenance flags (AUD-04a/e), code/CI only.** [Draft PR #27](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/27) with 7 tests-first failures verified [Actions 44409504699](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44409504699), followed by [green code CI 44409785611](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44409785611): 346 Python, 1 AUD-07 xfailed; 26 JS, 4 TODO. Each augment computes `modelled` from nonzero contributions; provenance tracks override/name_hint/description_keywords/none; cache schema v3, round-trip and catalog report by provenance. E2 final documentation-head [Windows CI 44410150004](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44410150004) green; real Windows/League acceptance pending.
- [x] **M2 / E3 — Unrated, not fake 2.1/10; suppress unsafe rerolls (AUD-04 / F-AUD-04), code/CI only.** [Draft PR #28](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/28) on `fix/m2-e3-unrated-safe-rerolls`, stacked on E2. Red regression [Actions 44410844377](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44410844377): 6 Python failures reproducing existing false scores/rerolls. Code `e4b8c3bd`; test DOM-stub repair `5efa3628`. [Green complete code CI 44411567599](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44411567599): **354 Python passed, 1 AUD-07 xfailed, 1 warning; 28 JavaScript passed, 4 TODO**. Unmodelled scores become `None` / API JSON `null`; frontend reads “Not rated — insufficient data”; reroll only with three unique, modelled, finite ratings; existing numeric ratings preserved. **Documentation-head CI and Windows/League game acceptance remain separate.**
- [ ] **M2 / A1–A3 Windows gate.** Hold an offer through level-ups and item changes without phantom progress, then verify actual picked-card confirmation.
- [ ] **M2 / E1–E3 Windows gate.** Verify missing coverage renders 'Not rated' and suppresses misleading reroll advice.

## M3 — Match lifecycle (F1–F5 code/CI validated; native Windows/League gate open)

- [x] **M3/F1 — Classified LCDA off the event loop (AUD-01), code/CI only.** [Draft PR #29](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/29), tests-first [red 44414416010](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44414416010) (13 failures), [green code 44415046195](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44415046195) (367 Python, 1 AUD-07 xfailed; 28 JS, 4 TODO). Typed LCDAResult, classified statuses, worker-thread I/O and sanitized diagnostic transitions. Final documentation-head CI requires independent verification; no Windows/League acceptance.
- [x] **M3/F2 — Explicit Gameflow statuses (AUD-01), code/CI only.** [Draft PR #30](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/30) stacked on F1; tests-first red [44415699928](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44415699928) (6 failures), green code [44416355903](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44416355903) (374 Python, 1 AUD-07 xfailed; 28 JS, 4 TODO). Read-only LCU Gameflow session/phase, explicit seven-status broadcast, champion_unresolved and riotId-first with name fallback. Documentation-head CI and native Windows/League acceptance separate.
- [x] **M3/F3 — Debounced end and match identity (AUD-06/AUD-07), code/CI only.** [Draft PR #31](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/31) stacked on green F2. [Red 44417070655](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44417070655): 5 regressions; [green code 44417583673](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44417583673): **385 Python passed, no xfail; 28 JS passed, 4 TODO**. 3 consecutive LCDA misses over >=6s without contrary active Gameflow, or immediate authoritative Gameflow end; match identity from LCU or guarded local sequence with champion, local player and gameTime regression, resets augments/OCR state immediately; no 300s hold. Latest documentation-head CI and native Windows/League acceptance require separate checks.
- [x] **M3/F4 — Clear stale frontend match display (AUD-05/AUD-06), code/CI only.** [Draft PR #32](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/32) on F3, [red JS 44418231275](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44418231275) (9 failures), [green code 44418575069](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44418575069) (**385 Python, 37 JavaScript, 0 xfail/TODO**). clearMatchDisplayState() and match-id invalidate old headers, offers, builds, rerolls, confirmations; reconnect shows 'Reconnecting…' and keeps backend choices; stale clears only on fresh data. Final documentation-head CI and real League validation separate.
- [x] **M3/F5 — Lock-safe ordered WebSocket transport (AUD-12), code/CI only.** **2026-11-18 F5 code gate (CI validated):** Existing [draft PR #34](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/34), branch `fix/m3-f5-lockfree-ordered-websocket` stacked on F4 [PR #32](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/32) (final F4 [CI 44418948857](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44418948857) passed). F5 tests-first `b362e112` [red CI 44419363819](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44419363819): four failures. Final F5 code head `fff4ee7f` [Windows Actions 44423518242](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44423518242) succeeded: **395 Python passed, 37 JavaScript passed, zero xfail/TODO, one nonblocking warning**. OCR/confirmation payloads are serialized before broadcasts outside `GameState.lock`; polling serialized; bounded, ordered, asynchronous per-client WS queues handle slow/disconnected clients and direct ACKs; queue tasks terminate after draining. **Verify Actions on the new documentation head before commencing M4.** Native Windows/League game verification, G1/G2, G4 and Riot/licensing remain open.
- [ ] **M3 Windows/League acceptance.** Custom match loading, one transient LCDA miss, disconnect/reconnect, end and second match with a different champion, no carry-over. Headless CI alone does not certify the native client.

## M4 — League window capture and privacy (AUD-02a, AUD-09)

- [x] **M4/B1 — League game window locator (code/CI only).** Pure Win32/ctypes, read-only process identity, client rect in screen coordinates, foreground indicator; off-Windows/invalid/minimized returns None. [Draft PR #37](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/37), tests-first red [44425838372](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44425838372), code [44426045251](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44426045251): 405 Python and 37 JavaScript green. Final docs-head CI pending independent verification; live Windows geometry not accepted.
- [x] **M4/B2 — Focused League capture (AUD-02a), code/CI only.** Client-rect-only OCR; Alt+Tab emits `not_focused` without capture or OCR; prior slots remain stale until new focused OCR, test coverage for negative coordinates, refocus and frontend. [Draft PR #38](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/38), [RED 44426849243](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44426849243), [code GREEN 44427808226](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44427808226): 412 Python / 38 JS. Final docs-head gate pending; real Windows/League testing open.
- [x] **M4/B3 — Screenshot privacy (AUD-09), code and CI complete.** Explicit `ocr_debug_screenshots=false` default; focused League card-only PNGs, max 15 / 72h in user-data; manual and auto gate, no fullscreen helper, safe custom ROI / refreshed foreground. [Draft PR #39](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/39), [RED 44428396349](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44428396349), [code GREEN 44429328760](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44429328760): 424 Python / 38 JS. Final docs-head gate and native validation pending.
- [ ] **M4 Windows/League acceptance.** Verify native League windowed/borderless, 1440p/1080p if available, negative-secondary monitor, Alt+Tab, OCR focus and no saved desktop imagery. Headless CI is not evidence.

## M5 — OCR per-card recognition (AUD-02b / AUD-03b,c)

- [x] **M5/P0.4 code — Offline redacted fixture builder.** Three existing B3 card-title crops -> three metadata-stripped PNGs + exact `{left, centre, right: augment_id | null}` truth file; fail-closed input/geometry/overwrite validation and synthetic test suite. [Draft PR #40](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/40), [RED CI 44432045580](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44432045580), [code GREEN CI 44432340456](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44432340456): 451 Python and 38 JS passing; docs-head CI to be checked.
- [ ] **M5/P0.4 Windows fixture evidence.** Capture a permissioned Mayhem custom session at 1440p (1080p if possible): full offer, one reroll per card, double reroll of one card, dialogue over card, and offer absent. Verify actual titles remain visible in B3 crop bands; match to permitted local augment IDs or null; review redaction before retaining/submitting. No real images/truth data collected yet.
- [ ] **M5/C1 evidence gate (2026-11-19):** Verified PR #40 final CI [44432793973](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44432793973) green; repository has zero reviewed real title-band triplets/truth/position measurements. Collect 1440p/1080p (if available) real titles, rerolls/dialogue, and client-relative x/y/w/h bounding boxes with signed desktop offsets/mode before tests-first C1; no provisional geometry as truth.
- [ ] **M5/C1 — Calibrate per-card title geometry on real P0.4 fixtures.** Derive screen-relative and window-offset geometry from actual 1080p/1440p 16:9 evidence. Other aspect ratios remain unsupported until independently calibrated. New tests-first stacked draft PR only after fixture evidence.
- [ ] **M5/C2 — Strict per-card OCR.** `--psm 7`, catalog match confidence >=90 with >=8 point margin, otherwise `unknown`; never treat description/dialogue text as a title. Requires C1 real title band geometry.
- [ ] **M5/C3 — Per-slot hashing and verified rerolls.** Only changed card re-OCR, two consistent reads before acceptance, unreadable result becomes unknown with retry/backoff. Requires confirmed fixtures.
- [ ] **M5/C4 — Offer present/gone only from stable focused title-band evidence.** A dialogue cannot imply disappearance; user manually confirms actual pick. Requires C1–C3 acceptance.
- [ ] **M5 native Windows/League acceptance.** Ten offers (30 cards), every slot rerolled at least once, one twice, no mistaken visible names; all correct or `unknown`. No synthetic/headless claim of accuracy.

## P0 — Capture, state, correctness, safety

- [ ] **UX-001 — Explicit context/state controller.** Replace always-visible dashboard logic with stable, debounced states (loading, champion select, combat, augment offer, shop, scoreboard, death, post-game, disconnected). Test transitions, priorities, recovery and stale-event suppression without relying on hypothetical API fields.
- [ ] **UX-002 — Reliable three-option OCR in actual Mayhem.** Verify the Tesseract executable, screen capture crop at the user's DPI, all 3 current names/positions, confidence and failure recovery with real screenshots. Require repeatable correct results before auto-presenting scores.
- [ ] **UX-003 — Augment rerolls.** Recognize each *new* triple after a reroll, invalidate old offers without losing previously chosen augments, suppress duplicate/stale scans, and test real reroll timing.
- [ ] **UX-004 — Offer lifecycle.** Show the augment panel for a verified offer, prioritize it over build panels, hide it promptly after the choice, and avoid stale recommendations across respawns or consecutive matches.
- [ ] **UX-005 — Trustworthy shop-open source.** Investigate permitted shop-state signals; implement only with dependable detection or an explicit player-triggered fallback. Do not infer shop visibility from gold, death or guessed screen state.
- [ ] **UX-006 — Quiet overlay when no action is needed.** Hide/minimize during loading, combat, death and post-game as appropriate, without covering gameplay or capturing mouse input.
- [ ] **UX-007 — OCR failure path on Windows.** Validate that missing OCR clearly switches to a *temporary*, unambiguous manual augment workflow (including Alt+O), never leaves the player with a falsely "scanning"/blank card, and returns to click-through.
- [ ] **UX-008 — 0–10 augment scores in the actual offer panel.** Verify all three available choices receive contextual scores and provenance with champion, picks, items and visible opponents; incomplete data must cause an explicit low-confidence/unknown state, not fabricated precision.
- [ ] **UX-009 — Mayhem-purchasable item logic.** Validate current patch/mode item availability, purchasable components, price/gold, six slots, quest items, exclusivity, consumables, duplicate names, and the optional boots replacement. Never recommend a seventh item as a direct purchase.
- [ ] **UX-010 — Enemy data provenance and utility.** Verify visible item IDs against real LCDA samples; show incomplete-catalog confidence and actionable counter context, not seven unexplained "unknown" values or inaccessible enemy information.
- [ ] **UX-011 — Gameplay and Riot policy gate.** Review real-time recommendations, statistical evidence and UI copy against current Riot rules; keep `experimental_augment_evidence` disabled until cleared. Ensure no auto-select, hidden information or unlicensed code/assets.
- [ ] **UX-012 — State continuity and failure safety.** On WebSocket disconnect, game exit, new game and OCR timeout, clear or mark stale panels; preserve user preferences but reset only match-specific augments, and recover without requiring a manual restart.

## Functional audit gate — observed November 18 Windows playtest (before more interface work)

> Evidence and exact candidate source references: [FUNCTIONAL_AUDIT_HANDOFF_2026-11-18.md](FUNCTIONAL_AUDIT_HANDOFF_2026-11-18.md). User stopped feature implementation for a **Claude code/functionality audit**. D4b development/CI is complete; **real gameplay correctness is not**. These are independent P0 defects, not D4b feature failures to silently mark as fixed.

- [ ] **F-AUD-01 (P0):** Resolve intermittent `Waiting for game...` in a live **custom Mayhem** match after a successful Champion Select; validate LCDA game transition and error state.
- [ ] **F-AUD-02 (P0):** Correct wrong three offered augments (visible **Impassable / Upgrade Stormsurge / Tooth Fairy**, overlay **escAPAde / Restart / Mercy**) with reliable card-specific left/center/right identity, freshness, confidence and catalog validation.
- [ ] **F-AUD-03 (P0):** Automatically recognize **single-card rerolls**, invalidate replaced scores, and preserve unchanged offers; manual **Alt+O → Scan Screen** must be a fallback rather than required.
- [ ] **F-AUD-04 (P0):** Remove misleading uniform **2.1/10** for unknown/zero-contribution augments and consequential unjustified reroll suggestion; report insufficient data, not weak fit.
- [ ] **F-AUD-05 (P0):** Clear stale **Neeko / game time / gold** after game exit; test fresh game, WebSocket/LCDA failure and reconnection while preserving saved preferences.
- [ ] **F-AUD-06 (P0):** Audit stale OCR/WS offer generations, out-of-order updates, candidate reordering, previous-game state, and recommendation invalidation; add deterministic regressions.
- [ ] **F-AUD-07 (P1, deferred UI):** After reliable three-card OCR/scoring and game-state gates, display **minimal scores aligned above the actual League augment cards**, with correct screen/DPI placement and click-through. No guessing from sorted list positions.
- [ ] **A-FUNC.1 (audit):** Obtain an actual **Claude functional/code audit** against current repo head, with file/line evidence, confirmed/suspected causes, severity, missing fixtures and P0/P1/P2 defect backlog.
- [ ] **A-FUNC.2 (plan):** Define small independent bug-fix phases, deterministic tests and Windows capture evidence, before coding the next interface feature.
- [ ] **A-FUNC.3 (acceptance):** Correct P0 faults and validate three real offered cards, reroll, meaningful/unknown scores and clean game exit on a permitted Windows custom match.
- [ ] **A-FUNC.4 (UI gate):** Hold game-card-aligned in-game UI until the actual identity/score/offer lifecycle is reliable. Keep D5c **desktop Settings UX audit** a separate later phase.

**WIP safety:** `fix/postgame-stale-match-state` was created during this review with preliminary unverified state-cleanup code and one test file; this branch is **unmerged, not part of PR #17, not validated and not a resolved issue**. Do not promote it silently. Review separately during the audit.

## P1 — Contextual UI and pre-game flow

- [ ] **UX-101 — Augment choice micro-panel.** Replace a large expandable list with 3 simultaneously visible, ordered cards (name, contextual 0–10 rating, data confidence and one-line reason) during a detected offer. Make alternative choices obvious; no forced "best" decision.
- [ ] **UX-102 — Shop-focused recommendation.** When shop state is verified, show the next *feasible* item, affordable component path and one meaningful alternative; expandable detail explains enemy counters and chosen-augment synergy.
- [ ] **UX-103 — Optional scoreboard summary.** Only after validating a permissible scoreboard signal or an explicit manual toggle, show a compact, useful opponent/team summary; otherwise keep it collapsed and never assert that the scoreboard is open.
- [ ] **UX-104 — Remove redundant HUD and debug noise.** Avoid repeating game clock, level, gold, all enemies and technical status continuously. Reserve raw data and diagnostics for Settings or expandable debug views; retain only decision-relevant labels.
- [ ] **UX-105 — Progressive disclosure.** Default to one decision and one short rationale; details, item comparison, counter analysis and source confidence expand only on deliberate user action (or outside the match).
- [ ] **UX-106 — Contextual overlay priority and layout.** Augment > shop > optional scoreboard, single small surface at a time; prevent simultaneous panels, flicker, overlaps with Riot HUD and repetitive toast interruptions.
- [ ] **UX-107 — Pre-game Settings Windows walkthrough.** Open via Qt tray **Open Settings**, change build style before League, refresh/restart the app, ensure the value persists in `~/.aram-oracle/preferences.json`, and confirm the in-game indicator uses it.
- [ ] **UX-108 — Live preference sync in a real match.** Change build style in Settings while Qt overlay stays open, see recomputed build suggestions without restart; verify Alt+H, Alt+O and click-through still behave correctly.
- [ ] **UX-109 — Feedback Windows walkthrough.** Submit a report from Settings, inspect the actual local JSON description, verify helpful errors for cooldown or disk failure and preserve unsent text. No typing required during gameplay.
- [ ] **UX-110 — Transparent overlay in League borderless mode.** Verify the already-confirmed Qt desktop transparency also works on top of the game; check window location, mouse pass-through and recovery after Alt+Tab.
- [ ] **UX-111 — Champion Select minimal view.** Validate bench/own champion detection, clear heuristic confidence and at least two contextual alternatives without cluttering selection or falsely presenting Mayhem win rates.
- [ ] **UX-112 — Manual interaction as fallback, not default.** If OCR fails, manual choices should be usable without trapping focus; outside an offer the click-through overlay should not expose editing fields or dropdowns.
- [ ] **UX-113 — Clear UI state messaging.** Distinguish offline/disconnected, waiting for match, OCR not installed, scan in progress, uncertain detection and incomplete catalog; never display "success" for an unsuccessful operation.

## P2 — Stability, accessibility, polish and validation

- [ ] **UX-201 — Real screen matrix.** Test 1920×1080 and 2560×1440, Windows scaling (100%/125%/150% where available), borderless windowed LoL, screenshot capture coordinates and screen-edge anchoring.
- [ ] **UX-202 — Lifecycle matrix.** Test death/respawn, rerolls, Alt+Tab, shop opening/closing, match end, reconnect, overlay hide/restore and two consecutive games; record screen evidence and exact failures.
- [ ] **UX-203 — Low-attention presentation.** Check readability at game distance, contrast, font size, optional opacity/scale, keyboard accessibility and reduced-motion preference without blocking gameplay.
- [ ] **UX-204 — Performance under a full match.** Measure CPU, memory, OCR polling cost, WS reconnection and update latency; avoid unnecessary recalculation of unchanged score/build inputs.
- [ ] **UX-205 — Test fixtures per patch and UI state.** Store sanitized fixture captures for 3-card OCR/reroll, old/new item catalogs, full inventory, unknown enemies and disconnected state. Keep real participant identifiers out.
- [ ] **UX-206 — Feedback privacy and consent.** Review local log/state payload for sensitive identifiers; make optional upload to GitHub visibly opt-in before transmission and surface upload failures accurately.
- [ ] **UX-207 — Layout refinement only after stable detection.** Improve spacing, card hierarchy, animation and adaptive positioning after real OCR + state-driven modes pass; do not spend the P0 budget on cosmetic polish.
- [ ] **UX-208 — Scenario-based acceptance recording.** Record for each P0/P1 behavior: screenshot/fixture, expected overlay state, observed state, pass/fail, tested revision and Windows resolution; link evidence to the task ID.


## Desktop app and installer roadmap — OP.GG-inspired usability, original implementation

> Added after reviewing the user-provided OP.GG Settings and overlay screenshots (2026-11-18). This is a **proposed product direction**, not a claim that the desktop app or installer already exists. Use familiar Windows UX patterns; do not copy OP.GG assets, protected artwork, code, or distinctive UI.

- [ ] **UX-D01 — Native desktop control center (P1).** Open a normal, resizable Qt desktop window from the tray/Start menu, reusing the existing local Settings page. Keep the transparent overlay as a separate, lightweight Qt window backed by the same local engine; avoid introducing a second backend.
- [x] **UX-D02 — Clear Settings navigation (P1).** Organize General, Overlay, Build Preferences, Augment Detection/OCR, Diagnostics, Feedback, and About into a consistent desktop navigation. Persist settings with validation, helpful errors, and clear 'Saved' states; no in-game forms.
- [ ] **UX-D03 — Overlay customization with preview (P1).** Configure anchor/corner, offsets, opacity, scale, compact vs expanded mode, visibility and safe click-through from the desktop app, with a simulated preview. Never use fake game-state detection in a real match.
- [x] **UX-D04 — One-engine lifecycle and tray behavior (P1).** Enforce single instance, no duplicate port 8765 servers, reliable Open Settings/Show Overlay/Quit actions, explicit background-vs-exit behavior, no elevation needed for ordinary use. Preserve Alt+O and Alt+H.
- [ ] **UX-D05 — Windows installer and uninstaller (P1 after core validation).** Produce a reproducible installer (evaluate PyInstaller onedir + Inno Setup first) with Start menu/desktop shortcuts, sensible install path, clean uninstall and optional user-data retention. User should never need Python, pip or PowerShell.
- [ ] **UX-D06 — First-run onboarding / OCR readiness (P1).** Detect Tesseract and required executables, explain installation or legally compatible bundling with notices, let the user test OCR, and provide manual fallback. Do not silently download or install third-party packages.
- [ ] **UX-D07 — Distribution safeguards (P2).** Validate clean Windows install/uninstall/upgrade, antivirus false positives, packaging of local frontend/static assets, process shutdown, minimum permissions, and code signing/SmartScreen strategy before public distribution.
- [ ] **UX-D08 — Updates and rollback (P2).** Design a versioned, opt-in update path with integrity verification, visible release notes, no disruptive update mid-match and rollback/recovery. Do not introduce auto-updates before a reliable package exists.
- [ ] **UX-D09 — Desktop/overlay smoke matrix (P1).** Test app launch, minimize to tray, Settings persistence, reopening an overlay, switching modes, exit and restart on real Windows at 1080p/1440p, including League borderless and Alt+Tab. Attach evidence to each item.
- [ ] **UX-D10 — Branding and licensing (P2).** Build original ARAM Oracle icon, typography, layout and visual hierarchy; use OP.GG only as an interaction reference, check Riot requirements and every bundled dependency's license/attribution.
- [ ] **UX-D11 — Claude UX/UI audit after desktop interface completion (P1).** After D3, D4a/D4b and D5a/D5b, commission/document an actual Claude review of the real Windows Settings, onboarding, preview and feedback flows. Triage concrete accessibility, consistency and usability findings and implement bounded P0/P1 design fixes before D6. Keep future D7/D8 live gameplay panels separately validated; no pretend audit or copied OP.GG designs.

**Delivery order (desktop roadmap):** D1–D2 lifecycle, D3 navigation, D4a preferences, D4b preview, **A-FUNC Claude functionality/code audit and P0 defect triage (next, before new interface work)**, D5a OCR readiness, D5b diagnostics, **D5c Claude UI/UX audit + bounded design closure**, then D6–D8 contextual in-game engine/panels, then D9–D11 packaging/release when core behavior is dependable. Historical PR #12 follow-ups remain independently tracked. Do not treat a pretty installer as evidence that live recommendations work. Do not treat a pretty installer as evidence that live recommendations work.

## Small desktop development phases — implementation checklist

> Authoritative phase scope and gates: [`docs/IMPLEMENTATION_PHASES.md`](IMPLEMENTATION_PHASES.md). Architectural contract: [`docs/DESKTOP_ARCHITECTURE.md`](DESKTOP_ARCHITECTURE.md). These checkboxes represent **new development work**, not completed work.

### G0 — Baseline (verification only)

- [x] **PH-G0.1:** Reconfirm current draft PR #12 head, its PR #11 base, unchanged main, and the latest Windows Actions results immediately before starting development.
- [x] **PH-G0.2:** Inspect the actual launcher/Qt/API source and record any blockers for a separate normal desktop window; preserve the tested Qt renderer as the baseline.

### D1 — First implementation phase: native Settings shell

- [x] **PH-D1.1:** Add `backend/desktop` normal Qt window hosting the existing `/settings` page (no transparency, topmost or click-through).
- [x] **PH-D1.2:** Add `python -m backend.desktop` dev entrypoint and clear error handling for missing Qt, unavailable API or unexpected port conflict; use **one** local backend.
- [x] **PH-D1.3:** Add automated tests for launch/URL/readiness and legacy `python -m backend.overlay --renderer qt` compatibility; keep Alt+O / Alt+H unchanged.
- [x] **PH-D1.4:** Create a draft PR stacked on `feat/pregame-settings-feedback`, verify its Windows CI at final code head and update TODO/state/log.
- [x] **PH-D1.5 (Windows):** Confirm actual standard Qt Settings window (focus, resize, preferences, feedback) and old transparent overlay behavior. **Never check from CI alone.**

**D1 code/CI evidence (2026-11-18):** [draft PR #13](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/13), [Windows run 44336280007](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44336280007) at code head `d5aff632`: **234 Python passed, 1 warning; 4 Node tests passed and both JS syntax checks passed**. The 19 new tests cover API fingerprint, reuse, occupied port, failure, host URL and legacy overlay contract. **PH-D1.5 remains unverified on a real Windows GUI.** UX-D01 and UX-D04 are broader than this shell and remain unchecked. See [external reuse candidates](REUSE_CANDIDATES.md) for separately licensed opportunities; none imported in D1.

**Windows evidence, 2026-11-18 (partial D1.5 only):** User screenshots confirm `python -m backend.desktop` opened and loaded the normal PyQt6 Settings window, with the saved `Balanced` style displayed. User explicitly confirmed that `python -m backend.overlay --renderer qt` remains transparent and that both **Alt+O** interaction and **Alt+H** hide/restore work; terminal shows both shortcut transitions. User installed the separately required UB-Mannheim Tesseract executable after the previous `OCR unavailable` warning, and explicitly confirmed the OCR status indicator turned green. **Do not mark PH-D1.5 complete:** resizing/focus, saving and persisting a changed build style across restart, and local feedback submission have not been explicitly verified. **Green OCR is only dependency readiness, not proof of three-card recognition or reroll accuracy in a Mayhem match.** No normal-match abandonment is required for a smoke test; keep in-game OCR validation open and use a permitted custom/test session if supported or observe a naturally completed match.

### D2 — Stable single instance and tray lifecycle

- [x] **PH-D2.1:** Reuse one ASGI server and one tray owner; prevent duplicate instances and conflicting port starts.
- [x] **PH-D2.2:** Implement reliable Open Settings, Show/Hide Overlay, Close/Minimize and Quit behavior without orphaned processes; test failures and recovery.
- [x] **PH-D2.3 (Windows):** Validate startup, repeat launch, taskbar/tray, close/reopen and keyboard shortcuts.

**D2 automated implementation evidence (2026-11-18):** [draft PR #14](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/14), [Windows CI 44345555542](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44345555542) at D2 code head `0b4a563b`: **253 Python passed, 1 warning; 4 Node tests passed; JavaScript syntax checks passed**. New headless tests cover OS-held lock, local activation, duplicates, error/stop paths and Qt launcher contract; they do **not** prove real tray, focus, close/hide or no orphan processes on the user's Windows machine. At this historical automated-test checkpoint the Windows validation was pending; later user-device evidence below confirms **PH-D2.3 and UX-D04**. **UX-D09 and PH-D1.5 remain unchecked**. The explicit legacy `--renderer webview` fallback is not part of the unified Qt tray lifecycle.

**D2 on-device tray acceptance, 2026-11-18 (completed for lifecycle/tray):** The user launched the D2 branch on Windows. The first process logged `Settings hidden to notification area`, and the user confirmed the tray icon remains in the Windows `^` notification area rather than in the taskbar. They confirmed all three right-click actions: **Open Settings**, **Show/Hide Overlay**, and **Quit** (full app exit). A second `python -m backend.desktop` logged `Activated existing ARAM Oracle settings window`; a deliberate foreign `python -m http.server 8765 --bind 127.0.0.1` listener was correctly rejected as incompatible when the overlay launcher was attempted. An earlier `KeyboardInterrupt` reflects manually interrupting the Python process, not proof of a tray regression. **Follow-up Windows screenshot and logs:** the D2 Qt launcher logged `Qt overlay hidden (Alt+H or tray to restore)`, `Qt click-through OFF` and `Qt overlay shown`, confirming Alt+H hide/restore and Alt+O interaction switching. After the user exited with Quit, `Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue` produced no listener rows. This validates the expected lifecycle and release of the managed API port; it does not prove every process/thread is absent. **PH-D2.3 and UX-D04 accepted.** Keep `UX-D09` (broader Windows/display matrix), `PH-D1.5` (focus/resize, preference save/restart and feedback), real borderless League transparency, OCR three-card/reroll accuracy and shop detection open.

### D3 — Desktop Settings information architecture

- [x] **PH-D3.1:** Group General, Overlay, Build Preferences, OCR, Diagnostics, Feedback and About as focused navigable areas using current Settings implementation.
- [x] **PH-D3.2:** Add keyboard/ARIA navigation and clear loading/save/error feedback; do not expose inaccessible features as functional.
- [x] **PH-D3.3:** Run UI interaction tests and validate real Windows navigation/resize.

**D3 code/test evidence (2026-11-18):** [draft PR #15](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/15), [Windows CI run 44352298709](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44352298709) at code head `346998a8`: **255 Python passed, 1 warning; 8 Node passed; both JS syntax checks passed**. Seven Settings sections, accessible keyboard tabs, existing API save/error/retry states and truthful OCR status are implemented. **PH-D3.3 remains unchecked** until real Windows GUI/navigation/resize and save/feedback acceptance; `PH-D1.5`, broad `UX-D02` and `UX-D09` are also open.

**D3 real Windows acceptance (user confirmation, 2026-11-18):** User reported testing the D3 checklist with everything functioning except actual in-game OCR validation; screenshot of the D3 OCR page shows the seven-section navigation, **Local API reachable**, and **Tesseract detected** after Recheck. The report covers the requested non-OCR Settings walkthrough (keyboard/mouse navigation, focus/resize, build preference save/restart, feedback and preserved D2 lifecycle). Accept `PH-D3.3`, `PH-D1.5`, and `UX-D02` on the user's explicit overall confirmation; this does **not** constitute independently captured screenshots or measured results for every subtest. If a specific subtest was not in fact performed, reopen its checkbox. Keep `UX-D09` (1080p/1440p, League borderless, Alt+Tab game smoke) and real **three-card/reroll OCR** detection, shop-state/score validation unchecked. The Recheck button only tests Tesseract availability, not in-game recognition. [D3 final Windows Actions run 44353064467](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44353064467) passed at documentation head `1748d6e4` (255 Python + 8 JS on preceding D3 code run).

### D4 — Overlay customization, split into two PRs

- [x] **PH-D4a.1:** Add validated, versioned local preferences/API for anchor, offsets, opacity and scale with safe defaults.
- [x] **PH-D4a.2:** Test invalid settings and migration/restart persistence without changing Qt renderer semantics.

**D4a code/test evidence (2026-11-18):** [draft PR #16](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/16) introduces schema v1 overlay preferences, a strict FastAPI write route, legacy migration and restart persistence. Windows CI [44355601388](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44355601388) on D4a code head passed regression steps (**292 Python, 1 warning; 13 Node**); check the final docs-head run separately. The frontend helper is data-only; no preview or Qt application. D3 user-reported Windows acceptance is tracked separately and real in-game OCR remains open.

- [x] **PH-D4b.1:** Add safe preview in desktop Settings and controlled application of user preferences to Qt overlay. Implemented and regression-tested in draft PR #17; manual Windows validation remains separately open.
- [ ] **PH-D4b.2 (Windows):** Confirm 1080p/1440p scaling, positioning, click-through and no white background.

**D4b Windows Settings acceptance (user report, 2026-11-18; 6/6):** User explicitly confirmed the Overlay section and all appearance controls, all four anchors, opacity at 60% and 100%, scale at 75%, 100% and 150%, a responsive clearly **SIMULATED** preview, and preferences retained after closing/reopening the desktop app. These are Settings/form/preview/persistence observations, **not** evidence that the actual transparent Qt overlay adopted every saved value or behaved correctly during League gameplay. Leave `PH-D4b.2` and `UX-D09` unchecked until actual Qt transparency, live placement, Alt+O/Alt+H, Alt+Tab, borderless League and applicable resolution/DPI/monitor matrix are tested.

**D4b implementation status (2026-11-18):** [draft PR #17](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/17), stacked on PR #16, adds the appearance form, explicit sample-only preview, Qt display-aware placement/zoom/opacity and Python/JS regressions. Initial Actions [run 44360223711](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44360223711) exposed a tiny-screen geometry regression, and later JavaScript test-fixture failures were corrected. **Verified successful** Windows Actions [44361461870](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44361461870) at `9520057c`: **303 Python passed (1 warning), 18 Node passed (0 failed)**, syntax checks passed. `PH-D4b.1` code/test gate is complete. User-device `PH-D4b.2` and `UX-D09` remain unchecked pending actual Windows/League tests.

### D5 — OCR diagnostics and onboarding

- [ ] **PH-D5a.1:** Detect Tesseract availability/path and show helpful first-run status; no silent installation.
- [ ] **PH-D5b.1:** Add a user-triggered OCR diagnostic/preview with confidence and safe manual fallback.
- [ ] **PH-D5b.2 (Windows):** Confirm three real Mayhem cards and rerolls at the actual user's HUD scaling.

### D5c — Claude UX/UI audit and design closure (after D3 + D4a/b + D5a/b)

- [ ] **PH-D5c.1:** Obtain and record the actual Claude audit of implemented Windows Settings/OCR/preview flows, with screenshots or reproducible evidence, severity (P0/P1/P2), accessibility/visual hierarchy/usability checks and privacy-safe inputs; do not mark complete without the review artifact.
- [ ] **PH-D5c.2:** Triage the audit; fix and regression-test bounded P0/P1 desktop navigation, layout, states and feedback issues while preserving existing backend, Qt lifecycle, transparency, hotkeys and preferences. Defer larger suggestions with tracked IDs and reasons.
- [ ] **PH-D5c.3 (Windows):** Confirm the resulting desktop design at real display scaling with keyboard navigation, resize, saved/error/OCR states and preview; log pass/fail evidence. This gate closes **desktop** UI structure/design only; live overlay augment/shop cards await D7/D8.

### D6–D8 — Contextual overlay engine (separate small PRs)

- [ ] **PH-D6.1:** Build tested deterministic/permission-aware overlay context controller, debouncing and stale-state handling; unknown shop must not be inferred from death/gold.
- [ ] **PH-D6.2:** Default to hidden during combat/loading and ensure augment > verified shop > optional scoreboard priority.
- [ ] **PH-D7.1:** Show concise score/reason for each of three **confirmed** augment cards, including rerolls; hide when selection vanishes.
- [ ] **PH-D7.2 (Windows):** Validate alignment, calibration and failure fallback in an actual match.
- [ ] **PH-D8.1:** Verify legitimate shop-open signal and Mayhem purchasability before presenting one next item/alternative.
- [ ] **PH-D8.2 (Windows):** Confirm recommendations appear only with shop open and do not suggest impossible/duplicate items.

### D9–D11 — Packaging and release (not in first PR)

- [ ] **PH-D9.1:** Produce local onedir executable, package Qt WebEngine/frontend/data and verify clean Windows launch without Python.
- [ ] **PH-D10.1:** Create installer/uninstaller with Start menu shortcut, optional desktop shortcut, error/rollback and user-data retention choice.
- [ ] **PH-D11.1:** Audit privacy, optional bug-report upload consent, third-party license notices, Riot compliance and release readiness.
- [ ] **PH-D11.2:** Investigate signing/SmartScreen and opt-in safe updates only after a tested installer.

## Completed implementation milestones (Windows in-game validation may still be open above)

- [x] ~~**UX-C01 — Baseline transparent Qt renderer.**~~ User confirmed the white desktop rectangle disappeared with `--renderer qt`; PR #9 Windows CI passed. **Real LoL overlay still open:** UX-110.
- [x] ~~**UX-C02 — Window controls and keyboard/tray hooks.**~~ Qt Alt+H/Alt+O, hide/quit actions and tray menu implemented; PR #10 CI passed. **Real interactions still open:** UX-108/UX-202.
- [x] ~~**UX-C03 — Existing context-aware scoring/build pipeline.**~~ Original 0–10 augment model, enemy/team signals, four build styles and optional boot swap implemented/tested across PRs #4–#8. **End-to-end accuracy open:** UX-008/UX-009.
- [x] ~~**UX-C04 — Initial real game-state integration.**~~ Champion, level, gold and five enemies were recognized in the first live screenshot. **Completeness open:** UX-010/UX-111.
- [x] ~~**UX-C05 — Non-equipment trinkets and duplicate build names filtered in code.**~~ PR #11: Poro-Snax excluded from main item slots; same-name Phantom Dancer variants deduplicated; Windows CI **200 passed**. **Actual shop test open:** UX-009.
- [x] ~~**UX-C06 — Level-triggered scan and manual augment fallback implemented.**~~ PR #11: initial eligible levels, manual search and match reset; **200 Python tests** passed. **Real three-card detection open:** UX-002/UX-003/UX-007.
- [x] ~~**UX-C07 — Separate pre-game Settings page and local style persistence implemented.**~~ PR #12 `/settings`, `GET/PUT /api/preferences`, WebSocket updates, disk persistence and Qt tray link; Windows Actions **215 Python + 4 Node tests passed**. **Real Windows verification open:** UX-107/UX-108.
- [x] ~~**UX-C08 — Remove in-game build dropdown and feedback entry.**~~ PR #12 leaves a read-only style label and post-game Settings guidance; JavaScript handlers cleaned up and checked by CI. **Manual augment input remains temporary fallback.**
- [x] ~~**UX-C09 — Local feedback description and failures handled in code.**~~ PR #12 saves user text into local JSON, reports HTTP 429/500 and preserves draft text on error; Windows CI passed. **User device test open:** UX-109.
- [x] ~~**UX-C10 — GitHub Windows automated regression gate.**~~ Workflow runs Python suite, syntax checks for both JS entrypoints and 4 DOM-stub Settings interaction tests; last verified [Actions run 44331470781](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44331470781) passed at `7912f471`. Later documentation-only commits require their own check.

## Immediate next execution order

1. **UX-107/108/109/110**: quick real Windows smoke test of PR #12 Settings/Qt transparency and feedback.
2. **UX-002/003/007/004**: capture and validate 3 augment options and rerolls; preserve a safe OCR fallback.
3. **UX-001/005/006/012**: implement trustworthy contextual state controller and quiet in-game presentation.
4. **UX-008/009/010**: guarantee useful ratings/builds with transparent confidence and verified item feasibility.
5. **UX-101–106**, then **UX-201–208**: compact decision UI and broad validation/polish.

Do not mark implementation or in-game validation as done solely because a draft PR exists, a historical CI run passed or a mocked UI test succeeds.
