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

**One phase = one new stacked branch = one draft PR.** One chat may implement several consecutive phases only after each previous phase passes its independent gates. A rotation
may also happen mid-phase when context becomes long: record a checkpoint on
the *same* branch/PR and resume that unfinished phase in the next chat,
**without creating a new phase branch prematurely**. Never mark a phase
complete merely to rotate chats.

**Limitations:** A repository-local skill is documentation, not an installed
ChatGPT invocation, scheduled job, or new-chat creator. The user opens the new
chat and sends the phrase; the assistant explicitly fetches this skill from
the connected private GitHub repository. If the connector is unavailable,
request connection rather than inventing state. Always protect `main`.

## Functional fix plan precedence (2026-11-18)

The current functional repair sequence is the [full M1–M8 implementation plan](../../../docs/FUNCTIONAL_FIX_IMPLEMENTATION_PLAN_2026-11-18.md), with *per-phase* P0.1–G6 checkboxes in [TODO](../../../docs/TODO.md). Read it at every new development session and prefer the last unchecked phase backed by real GitHub evidence over this skill's older D5a handoff anchor. See `AGENTS.md` for mandatory tests-first, ≤150/400 changed-line targets, stacked draft PRs, Windows gates, safety, data accuracy and localhost API release rules. **One phase = one branch = one draft PR; one chat may complete multiple sequential phases with separate review evidence.** Mid-phase chat rotation continues the same branch/PR. The old A-FIX numbering is historical planning, not an alternative schedule. PR #18 contains documentation only, not fixes.

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

## Current handoff anchor (verify live GitHub and CI)
**Important 2026-11-18 update:** The historical handoff bullets below describe the state *before* the Claude functional audit proposal was supplied. The full user-supplied M1–M8 plan is now in `docs/FUNCTIONAL_FIX_IMPLEMENTATION_PLAN_2026-11-18.md`; the active next phase is **M1 P0.1**. See `docs/CONTINUE_PROJECT.md` for the current prompt. The audit-next and D5a-next statements below are **superseded**; do not treat them as current instructions.



- As of 2026-11-18, D4b [draft PR #17](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/17), branch `feat/desktop-overlay-preview-apply-d4b`, is stacked on D4a [draft PR #16](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/16) (`feat/desktop-overlay-preferences-d4a`), based on D3 PR #15. No `main` merge. Always verify live status on resume.
- D4a final [Windows Actions 44356926105](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44356926105) at `0bc9535a` succeeded: 292 Python and 13 Node tests, JavaScript syntax checks. D4b code-head [Windows Actions 44361461870](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44361461870) passed at `9520057c`: **303 Python (1 warning), 18 JavaScript (0 failures)** and syntax checks. Earlier tiny-screen/JS test-fixture regressions were corrected. Recheck any later documentation-head CI.
- D4b uses D4a v1 preferences/API/pure JavaScript helper to expose Overlay anchor/offset/opacity/scale Settings with validation, persistence and a visibly labelled simulated preview. The existing transparent Qt window reloads the atomically saved file, applies DPI-aware available-screen bounds/zoom/opacity and monitors geometry/DPI/hotplug/resize. No OCR, recommendation, D6 context, installer or updater changes.
- D2 tray/lifecycle and Alt+O/Alt+H and D3 Settings navigation/persistence/feedback were previously user-confirmed on Windows. **D4b Settings device validation was reported 6/6 PASS; the full native Qt/League matrix is still incomplete**: `PH-D4b.2` and `UX-D09` remain unchecked, including 1080p/1440p, 100/125/150% DPI, multiple displays, all corners, transparency, click-through, Alt+Tab, League borderless. Real three Mayhem augment cards/rerolls remain unverified and are not a D4b success condition.
- **New user decision, 2026-11-18:** D4b **development is complete**, but real game correctness is not. The next immediate work is **A-FUNC Claude functional/code audit** before *any* new interface implementation. Read `docs/FUNCTIONAL_AUDIT_HANDOFF_2026-11-18.md` and the new `F-AUD-01`–`07` and `A-FUNC.1`–`4` items in `docs/TODO.md`. Actual Claude report is still pending. The user playtest exposed initial custom-game waiting, wrong 3 augments, single-card reroll requiring Alt+O + Scan Screen, uniform 2.1/10/unsound reroll, stale Neeko/time/gold after match, and requests for future card-aligned micro-score badges. **Do not declare these fixed**, and no new card-anchored UI until identity, ratings and lifecycle are validated.
- An **unverified WIP** `fix/postgame-stale-match-state` branch exists with preliminary game-end code/test edits, **not merged/CI-tested/accepted**. Remain on D4b for audit; preserve `main`. Do not confuse this WIP with a delivered fix.
- The next planned **development** phase *after the A-FUNC audit/triage* is **D5a Tesseract readiness/path detection and first-run guidance only**, in a new stacked draft PR based on #17; no silent installation or D5b recognition testing. D5c external Claude UX/UI **design** audit remains separate after D5b before D6. Copy the immediate **A-FUNC prompt** from `docs/CONTINUE_PROJECT.md` for the next session.
