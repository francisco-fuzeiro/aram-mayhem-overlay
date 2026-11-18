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

- **Draft PR #14:** [D2 single-instance and tray lifecycle](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/14), branch `feat/desktop-single-instance-tray`, targeting `feat/desktop-settings-shell` (draft PR #13), itself stacked on draft PR #12. `main` remains unchanged.
- D2 adds one per-user OS process lock, authenticated loopback launch forwarding, one owned FastAPI uvicorn thread (or safe reuse of a compatible existing API), one Qt app/tray managing both normal Settings and transparent overlay surfaces, hide/restore/quit actions and a clean server stop. Duplicate desktop or Qt overlay launches activate the existing window rather than opening a second owner.
- `python -m backend.desktop` opens Settings; `python -m backend.overlay --renderer qt` opens/restores the overlay. The explicit legacy `--renderer webview` path is outside the managed Qt lifecycle. No installer, UI redesign, updater or scoring/OCR change was made.
- **Verified code-head CI:** [Windows Actions run 44345555542](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44345555542) at `0b4a563b` succeeded: **253 Python passed, 1 warning; 4 Node Settings tests passed; both JavaScript syntax checks passed**. Confirm latest PR #14 head CI separately after documentation commits.
- **Not yet verified on the user's Windows:** repeated launch to one tray/one API, native Settings close-to-tray/restore and focus/resize, overlay transparency/Alt+H/Alt+O, Quit releasing the process/port, foreign port 8765 rejection, recovery after abnormal stop. `PH-D2.3` and `UX-D04` remain open. `PH-D1.5` also remains open for changed preference save/restart and feedback report creation.
- The user already confirmed that D1 Settings loaded, Qt transparency/shortcuts worked and OCR installation is ready (green). **The real three-card augment names, rerolls and dynamic in-game behavior remain unverified**; do not treat the green Tesseract status as proof. Do not ask the user to abandon matchmaking.
- No new external companion source was imported. See `docs/REUSE_CANDIDATES.md` for candidate MIT projects and unlicensed/proprietary restrictions.

## Next phase

**D3 — Desktop Settings information architecture**, only after D2 Windows acceptance or with its manual gate explicitly carried forward. Create `feat/desktop-settings-navigation` based on `feat/desktop-single-instance-tray`, open a new **draft PR targeting the PR #14 branch**, and keep all older PRs and `main` untouched. Add navigable General, Overlay, Build Preferences, OCR, Diagnostics, Feedback and About sections by reusing the existing frontend/API, keyboard/ARIA support and truthful save/error states. No installer, OCR overhaul, recommendation changes or overlay layout redesign in D3.

## Copy-paste prompt for the next ChatGPT project conversation

ARAM Oracle: continuar. Resume connected GitHub repository `francisco-fuzeiro/aram-mayhem-overlay` and read `AGENTS.md`, `.agents/skills/continue-aram-oracle/SKILL.md`, `docs/PROJECT_STATE.md`, `docs/TODO.md`, `docs/IMPLEMENTATION_PHASES.md`, `docs/DESKTOP_ARCHITECTURE.md`, `docs/DEVELOPMENT_LOG.md`, `docs/REUSE_CANDIDATES.md` and `docs/CONTINUE_PROJECT.md` at the live head. Check draft PR #14 on `feat/desktop-single-instance-tray`, based on PR #13, and latest Windows GitHub Actions. D2 implementation has one OS-held process lock, launch forwarding, one FastAPI owner, one Qt tray controlling Settings/overlay and clean Quit; do not redo D2. Carry forward D2 Windows checks (duplicate launch, tray, Close/Restore, Alt+O/H, Quit/no orphan/port conflict) until I confirm them; retain D1 preference persistence/feedback checks and unverified real three-card/reroll OCR, despite green Tesseract readiness. After D2 verification, implement only D3 desktop navigation (General, Overlay, Build Preferences, OCR, Diagnostics, Feedback, About; keyboard/ARIA; truthful save/error states), creating `feat/desktop-settings-navigation` from PR #14 with a new draft PR targeting its branch. Do not merge `main`, introduce installers or change scoring/game detection. Add tests, verify actual Actions at final head, update TODO/state/log/continuity skill. Code/docs/UI English; talk to the user in European Portuguese.
