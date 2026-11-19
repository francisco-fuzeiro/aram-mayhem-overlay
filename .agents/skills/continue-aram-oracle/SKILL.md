---
name: continue-aram-oracle
description: Resume ARAM Oracle development safely across ChatGPT project conversations using GitHub state, stacked draft PRs and evidence-based TODO tracking.
---


## 2026-11-19 active handoff — M5/C2 implemented, C3/C4 and native gates OPEN

- [Draft PR #42](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/42) on `feat/m5-c2-slot-locked-ocr` stacked on C1 draft PR #41. User's current League example: left En Passant, centre Ravenous Bind, right It's Killing Time; old overlay showed left/right/centre because OCR sorted confidence/name and recommendation engine sorted score. C2 adds title-only strict per-slot OCR and explicit `left/centre/right` in server/REST/WS/UI, with unknown/duplicate fail-closed. PSM7 first, guarded PSM6 for wrapped titles, >=90 full title + >=8 runner-up. Frontend physically locates cards instead of relying on ranking order; no gameplay input changed.
- Tests-first [RED 44446773105](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44446773105); [GREEN code CI 44447689233](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44447689233) at `b31da976` **474 Python passed (17 warnings), 41 JS passed**. Follow-up test+REST `62d50fc1`: final code/doc SHA and CI must be checked live. No user Windows run of C2 has occurred. The original 15 B3 debug PNGs were invalid; C1 diagnostic crops were calibrated using real 2544x1353 client but still require native acceptance; do not use images containing HUD as fixtures.
- **Next C3:** per-slot hash, two consistent scans, single-card reroll, unknown on changed/unreadable title without stale values, Alt+Tab and refocus guards. Keep C4 presence/gone separate and pending. Do not ask the user to open League until offline acceptance of required steps; user explicitly asked not to repeat unproductive in-game tests. Preserve all M4/M5 1080p, DPI, negative monitor and 10 offers/30 cards gates, G1/G2/G4, A-FUNC.3/V1, Riot/licensing, no merge/main, no installer/UI redesign.

## 2026-11-19 historical handoff — M5/C1 geometry code implemented, device validation pending

- Current draft [PR #41](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/41) on `docs/m5-c1-evidence-gate`, stacked on PR #40. User supplied real League 2544x1353 client at desktop origin (8,31) and offer/reroll screenshots. The invalid 15 B3 diagnostic images contain icons/HUD instead of title text. After user flagged tight crops, three padded title rectangles were visually verified in two captures: client-relative `left=(643,490,340,90)`, `centre=(1100,490,340,90)`, `right=(1567,490,340,90)`. Full/window images and player data must not be committed. The source images are chat evidence, not repository PNG fixtures; visible titles are not independently catalog-ID verified.
- C1 tests-first [RED 44443785774](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44443785774) `e96d0c59` failed as expected on missing geometry; code [GREEN 44443941406](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44443941406) `6ed8d3d5` passed **464 Python (1 warning), 38 JS (0 failures/TODO)**. Pure `card_title_geometry.py` and bounded `screen_ocr.save_screenshot` now emit title-only candidate bands in slot order when focused and debug opt-in. 1080p values are *extrapolated*, not Windows verified; other aspect families are rejected. Existing whole-strip OCR still sorts by fuzzy-match confidence, not slot, so C2 is not implemented.
- Next gate: verify this documentation-head Actions, then ask user to pull/restart and inspect three corrected debug PNGs during a Mayhem offer/reroll. Collect privacy-safe actual 1080p / catalog ID/null truth, dialogue/absent, signed display origin and DPI. M4 broader native acceptance, M5 10 offers /30 cards, G1/G2/G4, A-FUNC.3/V1 and Riot/licensing remain open. **No new C2 branch, installer, redesign, or merging main until gated.**

## 2026-11-19 historical handoff — M5/C1 pre-evidence gate (SUPERSEDED)

- **2026-11-19 M5/C1 evidence gate — BLOCKED (documentation only).** Verified PRs #37–#40 remain open, draft and stacked, with their exact final-head Windows Actions successful (#40 `e4179044`, run `44432793973`); `main` remains `ebc24c25`. The PR #40 tree has only `tests/fixtures/ocr/README.md`, no real redacted PNG triplets, verified augment-ID truth, or client-relative title measurements. Historical full/window screenshots noted in the independent audit PR #19 include unrelated private content and must not be committed. B3 band coordinates are provisional, not calibration. **No C1 geometry, test-first RED/GREEN, OCR accuracy or native Windows acceptance is claimed.** Capture reviewed, title-only real offers at 1440p and 1080p if possible, rerolls, dialogue, absent state, with measured title rectangles relative to the League client rect, window offsets/mode and ground truth. Do not advance C2–C4/M6, UI or installer; G1/G2, G4, A-FUNC.3/V1 and Riot/licensing remain OPEN. Resume C1 on this same evidence-gated draft branch after the evidence is reviewed, then run true tests-first RED, implementation GREEN and final documentation-head CI before C2.
- Current one-branch checkpoint: `docs/m5-c1-evidence-gate` stacked on PR #40 branch `feat/m5-p04-redacted-ocr-fixture-prep`. This is **docs only**; preserve this same branch/draft PR for C1 after real reviewed sample evidence arrives instead of opening another phase PR. Refer to `tests/fixtures/ocr/README.md` for required extra client-relative measurements. The fixture preparer does not preserve source crop positions. No evidence means no RED tests or C1 implementation, and no C2 prompt treated as executable. Do not merge or modify `main`.

## 2026-11-19 active handoff — M5/P0.4 offline fixture tool to C1 (BLOCKED on real samples)

- **2026-11-19 M5/P0.4 — offline OCR fixture preparation:** [draft PR #40](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/40), branch `feat/m5-p04-redacted-ocr-fixture-prep`, stacked on B3 [PR #39](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/39) final `054fbc00` ([Windows CI 44429624951](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44429624951) passed). Tests-first `470fe7bc` produced [RED CI 44432045580](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44432045580) (missing module). Offline script `scripts/prepare_ocr_fixtures.py` and `tests/fixtures/ocr/README.md` through `37531ad2` passed [code CI 44432340456](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44432340456): **451 Python passing, one warning; 38 JavaScript passing, zero failures/TODO/xfail**. It accepts exactly three existing B3 title-band PNGs and explicit ID/null truth; rejects full screen/augment-strip sizes, path-traversal IDs/labels, bad PNGs, duplicates and overwrites, reencodes pixels without image metadata, and emits only three sanitized bands plus `{left, centre, right}` JSON. No screen capture/OCR or behavioral changes. **No real League 1080p/1440p samples were provided or calibrated; P0.4 on-device collection remains OPEN and C1–C4 remain BLOCKED by verified fixture geometry and truth.** This document commit requires its own final-head Windows CI. No merges/main edits; G1/G2, G4, A-FUNC.3/V1 and Riot/licensing remain open.
- Read actual `tests/fixtures/ocr/README.md` and script, verify PR #40 latest head, CI and draft stack. **Do not create C1 geometry or report OCR accuracy before receiving real reviewed League card title bands with ground truth.** On-device M4 validation and fixture capture remain a user-device gate. If evidence is available, start C1-only tests-first stacked draft, otherwise record the blocker and ask for the minimal triplets. No M6, installer or redesign.


## 2026-11-19 active handoff — M4 B1–B3 drafts complete

- **M4/B3 completed in code, pending real Windows/League acceptance (2026-11-19):** [draft PR #39](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/39), branch `fix/m4-b3-screenshot-card-privacy` stacked on B2 PR #38 @ `b6a2ab19` ([final B2 CI 44428061714](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44428061714) green). B3 tests-first `24063cd5` reproduced ten screenshot privacy defects in [RED CI 44428396349](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44428396349). Final code head `aaddfba5`, [GREEN Windows CI 44429328760](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44429328760): **424 Python passed (one warning), 38 JavaScript passed, zero failures/TODO/xfail**. Diagnostic screenshots are strictly opt-in via `ocr_debug_screenshots=false` default; save at most three narrow card title-band crops from a focused League augment region, never full game/desktop; reject untrusted sizes and invalid/out-of-client OCR overrides; retain at most 15 PNG files and at most 72 hours under per-user data. Manual REST/WS and auto scans use the same gate; screenshot HTTP access requires opt-in and only lists card crops from that directory. The three title-band positions are provisional, not real League validated. Documentation-head CI must still be checked. No merges or main edits; G1/G2, G4, A-FUNC.3/V1 and Riot/licensing remain open.
- Before resuming: verify B3's final docs-head Actions, inspect all three draft stacked PRs (#37/#38/#39), and do not merge automatically. Native League Windows/Qt/Alt+Tab and privacy acceptance is still necessary. G1/G2/G4/A-FUNC.3/V1 and Riot/licensing remain open. No M5, installer or redesign without new authorization.


## 2026-11-19 active handoff — M4/B2 to B3

- **2026-11-19 M4/B2:** [draft PR #38](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/38), branch `fix/m4-b2-focused-league-capture`, stacked on final-green B1 [PR #37](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/37) @ `6746705d` ([CI 44426460134](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44426460134) success). B2 tests-first SHA `33524345` [RED CI 44426849243](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44426849243), 7 expected Python failures. B2 `screen_ocr`, state, diagnostics and frontend changes through `2ea0c63c` passed [code CI 44427808226](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44427808226) with **412 Python passing (one warning), 38 JavaScript passing, zero failures/TODO/xfail**. OCR now crops only the focused League client rectangle, not the selected display; `not_focused` preserves old slots as explicitly stale until fresh detection on refocus; auto/manual OCR fail closed on lost focus; frontend shows the stale indicator. Final documentation-head CI must pass before B3. No real League/Windows acceptance; G1/G2/G4, A-FUNC.3/V1 and Riot/licensing remain open.
- Resume by checking final B2 documentation-head Actions and opening a new stacked B3-only draft branch/PR after success. B3 removes full-screen screenshots, introduces an explicit disabled-by-default config for focused League card-crop diagnostics with bounded user-data retention, and tests default/privacy/manual scan. Do not start M5 or claim Windows game acceptance.


## 2026-11-19 active handoff — M4/B1 to B2

- **2026-11-19 M4/B1 — [draft PR #37](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/37)** on `fix/m4-b1-league-window-locator` stacked on F5 PR #34 (`0ba8d161`). Tests-first `7f759279` reproduced a missing module in [RED Windows CI 44425838372](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44425838372). Read-only Win32 process-identity/client-rect/focus selector `1799def5` passed [code CI 44426045251](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44426045251): **405 Python passed (one warning), 37 JS passed, zero failures/TODO/xfail**. Final documentation-head CI must be checked before B2. No native League/Windows capture acceptance yet; B2 focused capture and B3 privacy are not implemented. G1/G2, G4, A-FUNC.3/V1 and Riot/licensing remain open.
- On resume: inspect live PR #37 and its final docs-head Actions. Do not start B2 until this CI succeeds. B2 must be tests-first, use B1's real League client rectangle (never whole monitor), skip capture/OCR and emit `not_focused` on Alt+Tab, preserve old slots as explicitly stale. B3 remains separate. No on-device Mayhem acceptance.

# Continue ARAM Oracle

Use this repository-local skill when the user asks to continue work on the private League of Legends ARAM Mayhem companion from another ChatGPT conversation. **This file is a reusable repository instruction, not an automatically installed ChatGPT plugin/skill.** The next chat must explicitly fetch/read it from GitHub, along with the current repository files.

## Trigger phrases and cross-chat rotation

The following are **user-facing phrases**, not registered slash commands or
automatically executed GitHub hooks. They provide a reliable convention for a
ChatGPT conversation with the GitHub connector available:

- **`ARAM Oracle: preparar passagem`** — In the **current** conversation,
  finish/record the current small work unit, verify the actual draft PR/head
  and latest available CI, update `docs/PROJECT_STATE.md`, `docs/TODO.md`,
  `docs/DEVELOPMENT_LOG.md` and `docs/CONTINUE_PROJECT.md`. Refresh this
  skill's handoff anchor only when the phase/PR has really changed. Separate
  verified Windows observations from untested behaviors. Provide a compact
  next-chat prompt naming the current PR, base branch, pending Windows checks
  and next bounded phase. If CI is pending, state that fact rather than
  claiming success; do not start a new phase in the old chat.
- **`ARAM Oracle: continuar`** — In a **new conversation in the Overlay LoL
  ChatGPT project**, first read this repository skill through GitHub, then
  `AGENTS.md`, `docs/PROJECT_STATE.md`, `docs/TODO.md`,
  `docs/IMPLEMENTATION_PHASES.md`, `docs/DESKTOP_ARCHITECTURE.md`,
  `docs/DEVELOPMENT_LOG.md`, `docs/REUSE_CANDIDATES.md` and
  `docs/CONTINUE_PROJECT.md` at the **current head**, plus the project
  specification/UX audit when available. Check live PRs and Actions and
  continue the next uncompleted phase described in the handoff, rather
  than relying on chat memory or a hard-coded PR number.

**One phase = one chat = one new stacked branch = one draft PR.** A rotation
may also happen mid-phase when context becomes long: record a checkpoint on
the *same* branch/PR and resume that unfinished phase in the next chat,
**without creating a new phase branch prematurely**. Never mark a phase
complete merely to rotate chats.

**Limitations:** A repository-local skill is documentation, not an installed
ChatGPT invocation, scheduled job, or new-chat creator. The user opens the new
chat and sends the phrase; the assistant explicitly fetches this skill from
the connected private GitHub repository. If the connector is unavailable,
request connection rather than inventing state. Always protect `main`.

## Startup — mandatory, in order

1. Locate the GitHub-connected repo `francisco-fuzeiro/aram-mayhem-overlay`; read `AGENTS.md`.
2. Fetch `docs/PROJECT_STATE.md`, `docs/TODO.md`, `docs/IMPLEMENTATION_PHASES.md`, `docs/DESKTOP_ARCHITECTURE.md`, `docs/DEVELOPMENT_LOG.md`, `docs/REUSE_CANDIDATES.md` and `docs/CONTINUE_PROJECT.md` from the latest working branch and consult `funcionalidades.md` from this ChatGPT project when accessible.
3. Inspect the **live** latest head, PR number, base branch, draft status, dependencies and GitHub Actions. Repository files may trail behind the latest commits; source code and actual CI outrank historical descriptions.
4. Check task IDs and acceptance criteria. Avoid repeating already-settled research; choose one **small, not-yet-complete** phase. Never assume a prior chat or a local Windows directory is directly accessible.
5. State exactly what is confirmed by code/CI and what still needs Windows/League testing. Do not mark uncertain tasks complete.

## Execution

- Work through the **connected GitHub**, using a new branch stacked on the previous draft PR branch. Do not merge or modify `main` without explicit approval.
- Code, tests, app UI, commit messages and docs **English**; user-facing communications **European Portuguese**.
- Keep changes focused. Reuse Python/FastAPI/Qt and existing interfaces; no duplicated engine or silent third-party integration.
- Keep Qt transparency, Alt+O and Alt+H functional. Do not regress source-confidence logic; no guessing shop events or hidden opponent information.
- Add tests. Run what is actually available, read the final Windows Actions outcome and fix failures. Never report green CI merely because it started.
- Preserve Riot/licensing limits: no automated player choices, no uncited third-party source reuse, no experimental augment evidence until reviewed.

## Closure of a phase

1. Update `docs/TODO.md` checkboxes only with verifiable code/tests; keep separate **on-device** acceptance tasks unchecked until the user confirms them.
2. Update `docs/PROJECT_STATE.md` with active branch/PR, architecture and pending work.
3. Append a dated, factual entry to `docs/DEVELOPMENT_LOG.md` with test counts, exact CI run link/head SHA or explicit `not run`, and real Windows blockers.
4. Keep the PR draft, targeting its predecessor; leave `main` untouched.
5. Conclude in PT-PT with accomplished changes, automated results, unresolved Windows validation and a ready-to-paste prompt for the next phase/chat.

## Active handoff (2026-11-18) — F5 code green, M4 after final-head verification

- **2026-11-18 F5 code gate (CI validated):** Existing [draft PR #34](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/34), branch `fix/m3-f5-lockfree-ordered-websocket` stacked on F4 [PR #32](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/32) (final F4 [CI 44418948857](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44418948857) passed). F5 tests-first `b362e112` [red CI 44419363819](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44419363819): four failures. Final F5 code head `fff4ee7f` [Windows Actions 44423518242](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44423518242) succeeded: **395 Python passed, 37 JavaScript passed, zero xfail/TODO, one nonblocking warning**. OCR/confirmation payloads are serialized before broadcasts outside `GameState.lock`; polling serialized; bounded, ordered, asynchronous per-client WS queues handle slow/disconnected clients and direct ACKs; queue tasks terminate after draining. **Verify Actions on the new documentation head before commencing M4.** Native Windows/League game verification, G1/G2, G4 and Riot/licensing remain open.
- Full M4/B1–B3 prompt in `docs/CONTINUE_PROJECT.md`; no M4 implementation or user-device acceptance recorded. Check live GitHub PRs before creating branches.

## Active handoff (2026-11-18) — M3/F5 → M4 after final green CI

- F4 [PR #32](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/32) final SHA `b6d1f32b` passed [CI 44418948857](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44418948857). F5 [draft PR #34](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/34), branch `fix/m3-f5-lockfree-ordered-websocket` stacked on F4, reuses an existing parallel branch. Its tests-first commit `b362e112` [failed as expected](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44419363819) with four F5 regressions and 387 Python passing. Implementation through `ac9a22a0`: OCR and stat-confirmation messages prepared without awaiting WebSockets inside `GameState.lock`, serialized polling, bounded ordered per-client WS sender queues including direct ACKs, and slow-client regressions. **F5 final code/docs CI unverified at this checkpoint; do not mark complete or start M4 until final-head CI is green.** Actual League/Windows behavior, G1/G2, G4 and Riot/licensing remain open.
- Next M4/B1→B2→B3 requires separate stacked draft PRs and red→green tests at each gate. The full prompt is in `docs/CONTINUE_PROJECT.md`. No M4 code has been written. Never substitute headless CI for real Windows/League acceptance.

## Active handoff (2026-11-18) — M3/F4 → F5

- F4 [draft PR #32](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/32), branch `fix/m3-f4-frontend-match-stale-clear` stacked on verified F3 PR #31. Red [44418231275](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44418231275) (9 Node failures), green code [44418575069](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44418575069): 385 Python, 37 JS, 0 xfail/TODO. Code `3d2c4608`.
- **Check F4 final docs-head CI before F5**. F5 only broadcast outside lock, bounded non-blocking ordered per-client messaging and regression tests; separate stacked draft, no merge or native League/Riot validation claims.

## Active handoff (2026-11-18) — M3/F3 → F4

- F3 [draft PR #31](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/31) `fix/m3-f3-match-identity-debounced-end` stacked on F2 final green [44416684750](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44416684750). F3 red [44417070655](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44417070655) and green code [44417583673](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44417583673): 385 Python passed, 0 xfail, 28 JS passed, 4 TODO. Code `90f30018`.
- **Verify F3 docs-head CI success before opening F4**. F4 only frontend clear/stale reconnect and JS TODO activation. F5 lock-safe broadcast later; no merges, OCR changes, real Windows/League or Riot acceptance claims.

## Active handoff (2026-11-18) — M3/F2 → F3

- F2 [draft PR #30](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/30) `fix/m3-f2-explicit-gameflow-status` stacked on verified F1 PR #29. F2 red CI `44415699928`, green code [44416355903](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44416355903): 374 Python, 1 AUD-07 xfailed; 28 JS, 4 TODO. Code SHA `0493fad2`.
- **Verify final F2 docs-head CI before F3**. Next F3: debounced game end >=3 misses over >=6 seconds or authoritative LCU end, identity and reset without 300-second hold, AUD-07 promotion; no F4/F5 work in F3. No merges or Windows acceptance assertions.

## Latest active handoff (2026-11-18) — M3/F1 → F2

- F1 [draft PR #29](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/29) `fix/m3-f1-classified-lcda-nonblocking` stacks on E3 [PR #28](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/28); E3 final [CI 44412288780](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44412288780) green. F1 red [44414416010](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44414416010), F1 green code [44415046195](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44415046195): 367 Python, 1 AUD-07 xfailed, 28 JS, 4 TODO.
- Verify **F1 final documentation-head CI** before F2. F1 provides typed status/payload and worker-thread LCDA, not debounced end; AUD-07 and F4 JS TODOs remain. F2 is read-only Gameflow/status machine; one new stacked draft PR and tests-first gate. Do not start F3 until F2's final-head green CI. No merges, M4 or Windows-game acceptance inferred.

## Latest authoritative handoff (2026-11-18) — M2/E3 → M3

- M2 automated code: E1 [PR #26](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/26) `cc34107b`, final [CI 44409175703](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44409175703); E2 [PR #27](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/27) `a4432f69`, final [CI 44410150004](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44410150004); E3 [PR #28](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/28) `fix/m2-e3-unrated-safe-rerolls`, code `5efa3628`, [CI 44411567599](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44411567599) green (354 Python passing, 1 AUD-07 xfailed, 28 JS passing, 4 TODO). **Verify E3 docs-head CI at current PR head before M3.** All stacked draft PRs unmerged; main untouched.
- E1: whole-term keyword matches, Donation hint corrected, augment cache invalidation. E2: actual modelled/provenance/coverage. E3: honest null/unrated and complete-offer-only reroll.
- Next approved M3 (F1–F5) as separate stacked tests-first CI-gated draft PRs. Implement: F1 LCDA off loop/classified, F2 LCU gameflow statuses, F3 match identity and debounced end, F4 stale frontend clear/reconnect, F5 no broadcasts under lock. Exact next-chat contract in `docs/CONTINUE_PROJECT.md`; full approved plan independent PR #19. Do not repeat old audit or start M4, redesign, installer.
- Open gates: AUD-07 transient LCDA failure, four JS TODO cases, G1/G2 authoritative Mayhem source & patch, G4 Host/Origin/auth, A-FUNC.3/V1 native Windows/League and Riot/licensing. Preserve privacy-capped logs, screenshots off and experimental_augment_evidence off. Never mistake CI for native acceptance.

## Current handoff anchor (verify live GitHub and CI)

- **Latest 2026-11-18: M2/A3** is [draft PR #25](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/25), branch `fix/m2-a3-confirm-not-infer-augment-picks`, stacked directly on A2 draft PR #24; A2 final head `ebaac767` verified successful [Actions 44404260509](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44404260509). No merges or `main` changes.
- A3 removed auto-picked augments/stat anvils, guarded “likely” with unchanged level + inventory and OCR-observed cards, and made confirmation deferred without forced overlay expansion. Tests-first red [Actions 44405833311](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44405833311), green backend [44406157335](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44406157335) (334 Python, 1 xfailed; 24 JS, 4 TODO), green UI [44406383857](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44406383857) (334 Python, 1 xfailed; 26 JS, 4 TODO). **Verify newest/final head CI** and the added manual confirmation test before proceeding. No real-game acceptance.
- **Next M2/E1 only** (word-boundary parsing, Donation name hint, augment cache schema), in a NEW stacked branch/draft PR after a green A3 gate. Full implementation plan on independent docs-only PR #19; historical PR #18 separate. G4 local API Host/Origin/token and G1/G2 Mayhem catalog still open. Prompt in `docs/CONTINUE_PROJECT.md`; E2, E3 and M3 later.
- Older A2, A1 and D4b entries below are historical continuation anchors.


- **Latest 2026-11-18 checkpoint: M2/A2** is [draft PR #24](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/24), branch `fix/m2-a2-health-independent-ocr-window`, stacked on A1 draft PR #23, which had final green [Actions 44402650250](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44402650250). `main` untouched and no merges.
- A2 tests-first commits `d88f472c`, `b1b60e91` reproduced AUD-03d; fix `c42625c9` removed only the health-triggered OCR window closure and inadvertent confirmation/log event. Green code [Windows headless Actions 44403646160](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44403646160): **325 Python passed, 1 strict xfailed (AUD-07), 24 JS passed, 4 TODO**. Verify **final documentation-head CI** before any next phase; no native League/Windows game acceptance.
- **Next: M2/A3 only**, one new stacked branch/draft PR, following exact contract in full plan on separate docs-only draft PR #19 and next prompt in `docs/CONTINUE_PROJECT.md`. Preserve historical A-FIX PR #18; G4 security, G1/G2 Mayhem data and A3 non-intrusive fallback still open. E1/E2/E3, M3 and UI are not A2 work.
- Older A1 and D4b entries below are historical handoff anchors.


- **Newer 2026-11-18 checkpoint:** M2/A1 is the active [draft PR #23](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/23), branch `fix/m2-a1-no-stat-change-picks`, stacked on M1/P0.3 draft PR #22; `main` stays untouched. M1 final `c2c639a` passed [Actions 44398642390](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44398642390).
- Full M1–M8 approved implementation order exists on **independent docs draft PR #19** at `docs/FIX_IMPLEMENTATION_PLAN_2026-11-18.md`. Do not confuse this with the historical A-FIX plan on PR #18. M2 order: A1 then A2, A3, E1, E2, E3; each new phase gets its own stacked draft branch and CI gate.
- A1 tests-first commit `31dca394` recorded failures from passive stat changes. Fix commit `c8a41921` removes this path; [Actions 44401726776](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44401726776) passed (321 Python, 2 xfailed; 24 JavaScript, 4 TODO). **Check final documentation-head CI before A2.** Native League/Windows acceptance remains open.
- **Next phase:** A2 only, after final A1 CI; remove the health-triggered scan closure and satisfy AUD-03d regression. Follow the complete next-chat prompt in `docs/CONTINUE_PROJECT.md`. Keep G4 local API hardening, G1/G2 catalog coverage and A3 non-intrusive fallback open.
- The older D4b/A-FUNC entries below describe **historical context only**, not the current execution head.


- As of 2026-11-18, D4b [draft PR #17](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/17), branch `feat/desktop-overlay-preview-apply-d4b`, is stacked on D4a [draft PR #16](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/16) (`feat/desktop-overlay-preferences-d4a`), based on D3 PR #15. No `main` merge. Always verify live status on resume.
- D4a final [Windows Actions 44356926105](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44356926105) at `0bc9535a` succeeded: 292 Python and 13 Node tests, JavaScript syntax checks. D4b code-head [Windows Actions 44361461870](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44361461870) passed at `9520057c`: **303 Python (1 warning), 18 JavaScript (0 failures)** and syntax checks. Earlier tiny-screen/JS test-fixture regressions were corrected. Recheck any later documentation-head CI.
- D4b uses D4a v1 preferences/API/pure JavaScript helper to expose Overlay anchor/offset/opacity/scale Settings with validation, persistence and a visibly labelled simulated preview. The existing transparent Qt window reloads the atomically saved file, applies DPI-aware available-screen bounds/zoom/opacity and monitors geometry/DPI/hotplug/resize. No OCR, recommendation, D6 context, installer or updater changes.
- D2 tray/lifecycle and Alt+O/Alt+H and D3 Settings navigation/persistence/feedback were previously user-confirmed on Windows. **D4b Settings device validation was reported 6/6 PASS; the full native Qt/League matrix is still incomplete**: `PH-D4b.2` and `UX-D09` remain unchecked, including 1080p/1440p, 100/125/150% DPI, multiple displays, all corners, transparency, click-through, Alt+Tab, League borderless. Real three Mayhem augment cards/rerolls remain unverified and are not a D4b success condition.
- **New user decision, 2026-11-18:** D4b **development is complete**, but real game correctness is not. The next immediate work is **A-FUNC Claude functional/code audit** before *any* new interface implementation. Read `docs/FUNCTIONAL_AUDIT_HANDOFF_2026-11-18.md` and the new `F-AUD-01`–`07` and `A-FUNC.1`–`4` items in `docs/TODO.md`. Actual Claude report is still pending. The user playtest exposed initial custom-game waiting, wrong 3 augments, single-card reroll requiring Alt+O + Scan Screen, uniform 2.1/10/unsound reroll, stale Neeko/time/gold after match, and requests for future card-aligned micro-score badges. **Do not declare these fixed**, and no new card-anchored UI until identity, ratings and lifecycle are validated.
- An **unverified WIP** `fix/postgame-stale-match-state` branch exists with preliminary game-end code/test edits, **not merged/CI-tested/accepted**. Remain on D4b for audit; preserve `main`. Do not confuse this WIP with a delivered fix.
- The next planned **development** phase *after the A-FUNC audit/triage* is **D5a Tesseract readiness/path detection and first-run guidance only**, in a new stacked draft PR based on #17; no silent installation or D5b recognition testing. D5c external Claude UX/UI **design** audit remains separate after D5b before D6. Copy the immediate **A-FUNC prompt** from `docs/CONTINUE_PROJECT.md` for the next session.
