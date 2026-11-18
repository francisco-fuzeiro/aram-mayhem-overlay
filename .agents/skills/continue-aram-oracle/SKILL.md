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

## Current handoff anchor (verify live GitHub and CI)

- On 2026-11-18 D4a `feat/desktop-overlay-preferences-d4a` opened in [draft PR #16](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/16), targeting D3 `feat/desktop-settings-navigation` ([draft PR #15](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/15)). No `main` merge or modification. Verify the live head/PR chain before proceeding.
- D4a data/API implementation: `backend.preferences` schema v1 stores `build_style` plus overlay `anchor`, bounded signed offsets, opacity and scale in the **existing** local JSON file. Legacy v0 migrates on save; invalid saved fields use safe defaults; future schemas are not overwritten; atomic writes preserve the other setting family. Existing FastAPI exposes `GET /api/preferences` and new `PUT /api/preferences/overlay`; legacy style-only PUT remains compatible.
- D4a has **no Qt overlay geometry/scale/opacity change and no Settings preview**. The new JavaScript helper is pure validation/migration data for D4b. No extra backend service, new OCR engine, game-state logic or scoring.
- Code-head Windows [Actions run 44355601388](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44355601388) at `8ef17b81`: **292 Python passed (1 warning), 13 Node passed**, legacy Settings/overlay JS syntax passed. Later workflow adds a syntax check for the helper. **Recheck Actions on the final D4a documentation/merge head** before treating the complete PR as validated.
- D2 user-confirmed Windows tray, single instance, Alt+H/Alt+O and 8765 release remain accepted. D3 Windows Settings navigation, focus/resize, style save/restart and feedback were subsequently user-reported as tested and recorded on D3 base; `PH-D3.3`, `PH-D1.5` and `UX-D02` are checked on that evidence (no individual logs for all substeps).
- **Still open:** `UX-D09` full Windows display/League borderless/Alt+Tab matrix and real OCR detection of three augments and rerolls. Green Tesseract indicates dependency readiness only; do not claim recognition. No D4b manual Windows validation has happened.
- **Next D4b:** build accessible desktop controls, simulated preview and safe Qt application/reload using D4a values, with dedicated Windows tests. Create a new branch and draft PR *after* confirming D4a final CI. Keep D5c Claude UX/UI audit after D5a/b and before D6. Use `docs/CONTINUE_PROJECT.md` for the complete ready-to-paste prompt.
