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
2. Fetch `docs/PROJECT_STATE.md`, `docs/TODO.md`, `docs/IMPLEMENTATION_PHASES.md`, `docs/DESKTOP_ARCHITECTURE.md`, `docs/DEVELOPMENT_LOG.md` from the latest working branch and consult `funcionalidades.md` from this ChatGPT project when accessible.
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

## Current handoff anchor (verify the live PR and CI)

- On 2026-11-18, D2 is implemented on `feat/desktop-single-instance-tray`, [draft PR #14](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/14) targeting `feat/desktop-settings-shell` (draft PR #13), stacked on draft PR #12 and preceding branches. `main` has not been modified.
- D2's Python process lock, authenticated local activation, stoppable ASGI owner and unified Qt tray/Settings/overlay are implemented. Both `python -m backend.desktop` and `python -m backend.overlay --renderer qt` enter the same owner. [Windows CI 44345555542](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44345555542) passed at D2 code head `0b4a563b`: **253 Python passed, 1 warning, 4 Node tests passed** and JS syntax checks passed. Recheck at the latest documentation head, not just this known run.
- The explicit non-Qt `--renderer webview` fallback is a separate developer path. No installer, auto-update, recommendation changes or third-party code import was made in D2.
- **Windows acceptance is outstanding:** one tray and no duplicate API after repeat launches, Settings close-to-tray/reopen and focus/resize, overlay Show/Hide, Alt+O and Alt+H with click-through/transparency, clear stop/restart and no orphan port listener, compatible API reuse and conflicting port. Keep `PH-D2.3` and broad `UX-D04` unchecked until observed.
- D1 Settings preference save/restart and feedback report creation remain unconfirmed (`PH-D1.5`). Green Tesseract readiness does not establish real three-card Mayhem OCR/reroll detection; these remain independent P0 tests.
- After D2 Windows acceptance, start **D3 — Settings information architecture/navigation** in a new branch stacked on PR #14 and a new draft PR. Do not create D3 while fixing unfinished D2. See `docs/CONTINUE_PROJECT.md` for the next chat prompt.
