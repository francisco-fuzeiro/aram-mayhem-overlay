---
name: continue-aram-oracle
description: Resume ARAM Oracle development safely across ChatGPT project conversations using GitHub state, stacked draft PRs and evidence-based TODO tracking.
---

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
