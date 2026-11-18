# Continue ARAM Oracle in a New Chat

The repository-local continuity skill is [`.agents/skills/continue-aram-oracle/SKILL.md`](../.agents/skills/continue-aram-oracle/SKILL.md). This is **not** automatically installed into ChatGPT; include its path in a new chat and ask the assistant to read it from the GitHub-connected repository.

## Next phase

The first new development slice is **D1 — Desktop Settings shell**, after verifying the baseline. Read [IMPLEMENTATION_PHASES.md](IMPLEMENTATION_PHASES.md) before touching code. Preserve the current draft PR chain and leave `main` untouched.

## Copy-paste prompt (English reference)

Continue development of private GitHub repository `francisco-fuzeiro/aram-mayhem-overlay` via the connected GitHub integration. Read `AGENTS.md`, `.agents/skills/continue-aram-oracle/SKILL.md`, `docs/PROJECT_STATE.md`, `docs/TODO.md`, `docs/IMPLEMENTATION_PHASES.md`, `docs/DESKTOP_ARCHITECTURE.md` and `docs/DEVELOPMENT_LOG.md` before changing code. Also read the ChatGPT project file `funcionalidades.md` if available. Inspect the actual head and Windows Actions status of draft PR #12 (`feat/pregame-settings-feedback`, based on PR #11). Implement only phase **D1 — native Qt desktop Settings shell**, in a new branch `feat/desktop-settings-shell` based on PR #12, without merging to `main`. Reuse the existing FastAPI server and `/settings` page; provide `python -m backend.desktop`; do not launch a duplicate server, do not change the transparent overlay, Alt+O or Alt+H, and do not build the installer yet. Add regression tests and JavaScript checks as relevant, create a new **draft** stacked PR, check actual Windows Actions and fix failures, update TODO/PROJECT_STATE/DEVELOPMENT_LOG with evidence, distinguish CI from real Windows tests. All code and docs must be English; respond to me in European Portuguese. Work autonomously and only ask for actual Windows testing or essential decisions.
