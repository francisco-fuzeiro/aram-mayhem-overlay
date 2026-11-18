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

## Current handoff anchor (verify live GitHub and CI)

- On 2026-11-18 D3 UI navigation landed on `feat/desktop-settings-navigation` in [draft PR #15](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/15) targeting `feat/desktop-single-instance-tray` ([draft PR #14](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/14)). D2 user Windows acceptance is complete (tray, duplicate launch, Alt+H/Alt+O, port release); `main` remains untouched.
- D3 offers seven Settings sections, ARIA/keyboard tablist, real load/save/error/retry states and OCR dependency-only readiness using the existing API. No new settings backend, Qt changes or game detection/scoring. **Verified Windows Actions [44352298709](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44352298709)** at code head `346998a8`: **255 Python passed, 1 warning; 8 Node passed; both JS syntax checks passed**. Final previous documentation-head CI [44353064467](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44353064467) succeeded at `1748d6e4`; verify new commits separately.
- **D3 user-reported Windows acceptance:** user stated all manual D3 checklist steps other than real OCR were tested; screenshot shows local API reachable and Tesseract detected after Recheck. `PH-D3.3`, `PH-D1.5` and `UX-D02` were checked based on that report. Individual test logs/screenshots were not provided. `UX-D09` and real three-card/reroll recognition remain open. Green Tesseract is dependency readiness only.
- **D4a user reports already in progress in another conversation.** Check live GitHub branches and PRs first; no D4a branch/PR was visible at this snapshot and do not duplicate ongoing work. D4a is validated overlay preferences data model/API stacked on PR #15, with D4b Qt preview/apply separate. See `docs/CONTINUE_PROJECT.md` for scope.
