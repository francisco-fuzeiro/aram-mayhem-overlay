# Continue ARAM Oracle in a New Chat

The repository-local continuity skill is [`.agents/skills/continue-aram-oracle/SKILL.md`](../.agents/skills/continue-aram-oracle/SKILL.md). It is not automatically installed into ChatGPT; each new session should fetch it from the connected private repository.

## Current handoff — 2026-11-18

- **Draft PR #13:** [D1 desktop Settings shell](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/13), head `feat/desktop-settings-shell`, **base** `feat/pregame-settings-feedback` (draft PR #12), itself stacked on PR #11. Do not merge or modify `main` without explicit approval.
- D1 added `python -m backend.desktop`, a normal resizable PyQt6 WebEngine Settings window, a compatible API readiness/reuse check, missing-Qt and port-conflict handling, and headless regressions. It reuses `/settings`, existing preferences, feedback and FastAPI server.
- The latest verified D1 code+README Windows Actions run at `d5aff632` was [44336280007](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44336280007): **234 Python passed, 1 warning; 4 JavaScript tests passed; both JS syntax checks passed**. Check newer Actions for subsequent documentation commits instead of assuming this remains the latest run.
- **Manual D1 acceptance remains open**: Windows native window focus/resize/preference save and restart/feedback, old `python -m backend.overlay --renderer qt` transparency, click-through, Alt+O/Alt+H and actual League behavior. Do not mark `PH-D1.5` done without observed evidence.
- Reusable components from other LoL overlays are being evaluated in [`REUSE_CANDIDATES.md`](REUSE_CANDIDATES.md). Reuse only explicitly licensed, attributable code. D1 copied no third-party app code.

## Next development phase

**D2 — Stable single instance and tray lifecycle**, after verifying the latest D1 head and taking account of Windows observations. Follow the bounded scope in [`IMPLEMENTATION_PHASES.md`](IMPLEMENTATION_PHASES.md): one API owner, one tray owner, reliable settings/overlay open/hide/quit, no orphan services. Avoid installer or Settings redesign in D2.

## Copy-paste prompt (English reference)

Continue the ARAM Oracle project at private GitHub repository `francisco-fuzeiro/aram-mayhem-overlay` using the GitHub connector. Read `AGENTS.md`, `.agents/skills/continue-aram-oracle/SKILL.md`, `docs/PROJECT_STATE.md`, `docs/TODO.md`, `docs/IMPLEMENTATION_PHASES.md`, `docs/DESKTOP_ARCHITECTURE.md`, `docs/DEVELOPMENT_LOG.md`, `docs/REUSE_CANDIDATES.md` and `docs/CONTINUE_PROJECT.md`. Also consult the project `funcionalidades.md` and UX audit when accessible. Verify draft PR #13 (branch `feat/desktop-settings-shell`, based on PR #12) and its latest live Windows Actions. Do not repeat completed D1 work. Keep pending manual Windows checks distinct from automated tests. Continue with narrowly scoped D2 (unified single-instance/tray/server lifecycle), in a new stacked draft PR targeting PR #13, without touching `main`. Retain old `python -m backend.overlay --renderer qt`, transparent click-through, Alt+O/Alt+H, settings persistence, feedback and existing scoring engine. Consider explicitly licensed third-party code only if it genuinely helps, verifying exact file licenses and attribution; never copy proprietary source. Run relevant Python and JS tests, check the actual final CI, update TODO/state/log and give only necessary Windows checks. Keep source, UI and docs English; communicate in PT-PT.
