# Continue ARAM Oracle in a New Chat

The repository-local continuity skill is [`.agents/skills/continue-aram-oracle/SKILL.md`](../.agents/skills/continue-aram-oracle/SKILL.md). It is a **GitHub repository skill**, not an automatically installed ChatGPT plugin. A new project conversation must explicitly fetch it through the connected GitHub app.

## Trigger phrases (in the ChatGPT project)

Use one phrase per action. These are **conventions interpreted by the
assistant**, not real slash commands or an automatic new-chat mechanism.

- **`ARAM Oracle: preparar passagem`** in the current chat: persist
  verified facts, pending tests, branch/PR and actual CI to the GitHub
  state/log/TODO files; refresh this handoff and give the exact next prompt.
  A partial/incomplete phase is handed off **on the same branch**, not falsely
  marked complete.
- **`ARAM Oracle: continuar`** in a **new chat**: open this private GitHub
  repository, read `.agents/skills/continue-aram-oracle/SKILL.md` and all
  mandatory state files, verify the current PR/CI, then follow the
  `Next phase` instructions below. For an explicit first message use:
  `ARAM Oracle: continuar. Lê a skill .agents/skills/continue-aram-oracle/SKILL.md diretamente do GitHub francisco-fuzeiro/aram-mayhem-overlay e segue docs/CONTINUE_PROJECT.md.`

The user must manually start the next ChatGPT conversation. When GitHub is
not connected, ask to reconnect rather than guessing previous work. All
changes remain stacked drafts unless the user explicitly approves merging.

## Confirmed handoff — 2026-11-18, Europe/Lisbon

- **Draft PR #13**: [D1 native Settings shell](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/13), branch `feat/desktop-settings-shell`, targeting draft PR #12 branch `feat/pregame-settings-feedback` (itself stacked on PR #11). Do **not** merge or edit `main`.
- D1 introduces `python -m backend.desktop`, a normal PyQt6 WebEngine Settings window, same existing `/settings` HTML/CSS/JS, compatible local FastAPI instance reuse, missing-Qt/port/startup handling and headless regression tests. No installer or updater.
- **Verified Windows on the user's computer**: developer desktop Settings launcher opened successfully, the Settings page loaded and displayed `Balanced`; the existing transparent Qt overlay worked, including **Alt+O** toggle and **Alt+H** hide/restore. Do not imply window resize/focus, preference save after restart or local feedback submission were already confirmed.
- **OCR readiness repaired on Windows**: `Tesseract-OCR` executable was initially absent, user ran `winget install --id UB-Mannheim.TesseractOCR --exact`, and then reported Settings OCR status **green**. This is a **dependency check only**; detection of the real three offered augments, screen region, rerolls and in-match scoring remain unverified. A full normal matchmaking game must not be abandoned just to test OCR. Use a permitted custom/test mode when supported or observe during a naturally completed game.
- **Latest verified CI before this documentation update**: [Windows Actions 44337928614](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44337928614) at `52a96563`: 234 Python passed, 1 warning; 4 JS passed, both JS syntax checks passed. Always verify Actions at the **latest live head** again after documentation changes.
- **Pending D1.5**: actual Settings resize/focus, change/save/restart persistence and feedback file creation. Leave `PH-D1.5` unchecked until all verified.
- **Source reuse**: [`docs/REUSE_CANDIDATES.md`](REUSE_CANDIDATES.md) catalogs permissive candidate implementations and proprietary examples. Reuse only components with verified applicable file-level licenses, transitive notices, attribution and legitimate data sources. Never copy Mayhem Advisor proprietary code.
- **Chat workflow decision**: use **one phase = one conversation = one new stacked branch = one draft PR**. The repository state files, not previous conversations, are the durable handoff; keep each chat focused and record verified vs unverified outcomes.

## Next phase

**D2 — Single Instance & Tray Lifecycle.** Create `feat/desktop-single-instance-tray` from `feat/desktop-settings-shell` and a new draft PR based on PR #13. Implement exactly one backend lifecycle owner and tray owner, open/close/reopen Settings, show/hide the overlay, safe repeated launch and clean exit. Preserve Qt transparency, click-through, Alt+O/Alt+H, OCR readiness and existing engine/API. Do not bundle the installer, updater or Settings redesign in D2.

## Copy-paste prompt for the next ChatGPT project conversation

Continue ARAM Oracle development using connected GitHub repository `francisco-fuzeiro/aram-mayhem-overlay`. Read `AGENTS.md`, `.agents/skills/continue-aram-oracle/SKILL.md`, `docs/PROJECT_STATE.md`, `docs/TODO.md`, `docs/IMPLEMENTATION_PHASES.md`, `docs/DESKTOP_ARCHITECTURE.md`, `docs/DEVELOPMENT_LOG.md`, `docs/REUSE_CANDIDATES.md`, and `docs/CONTINUE_PROJECT.md`. Consult the project `funcionalidades.md` and UX audit if accessible. Inspect draft PR #13 live on branch `feat/desktop-settings-shell`, stacked on PR #12, and its latest Windows Actions. Do not redo D1. User confirmed native Qt Settings launch/page load, transparent overlay, Alt+O and Alt+H on Windows, and green Tesseract OCR readiness after installing the external executable. This does not establish Settings resize, saved preferences after restart, feedback creation, or actual three-card/reroll OCR detection; retain these checks and do not ask user to abandon a matchmaking game. Develop only D2 — one instance/backend/tray lifecycle, safe window show/hide/reopen, repeated launch and graceful quit — in `feat/desktop-single-instance-tray`, new draft PR stacked on PR #13; protect `main`. Prefer reuse of correctly licensed overlay components where genuinely helpful, verify exact notices/attribution, do not copy Mayhem Advisor. Add tests, verify actual GitHub Actions at final head, update TODO/PROJECT_STATE/DEVELOPMENT_LOG and refresh this handoff. All code/docs/UI English; communicate in European Portuguese. Provide only essential Windows acceptance checks and the next-phase prompt.
