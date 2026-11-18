# ARAM Oracle — Desktop and Contextual Overlay Architecture

Status: **approved direction, not yet implemented**. Baseline: 2026-11-18, draft PR #12 stacked on draft PR #11. This document records the architecture decision and implementation boundaries; see [IMPLEMENTATION_PHASES.md](IMPLEMENTATION_PHASES.md) for small delivery slices and [TODO.md](TODO.md) for live task status.

## Design principles

1. **One local Python engine, two independent UI surfaces.** Keep the existing FastAPI/Live Client Data API/OCR/scoring backend; do not fork or rewrite the recommendation engine.
2. **Desktop Settings is a normal interactive Windows window**, accessible from Start menu/tray even before League starts. It hosts the existing local `/settings` HTML/CSS/JavaScript in PyQt6 WebEngine, preserving the current `GET/PUT /api/preferences` and feedback API contracts.
3. **In-game overlay is a distinct transparent, topmost, normally click-through Qt window.** Preserve the already visually validated Qt desktop transparency and Alt+O / Alt+H behavior. Desktop Settings must not inherit click-through or topmost flags.
4. **The user sees decisions, not a dashboard.** The default overlay is hidden in combat/loading; during a verified augment offer it displays short, correctly mapped card ratings; during a *verified* open shop it shows the next feasible purchase; optional scoreboard details are explicitly invoked or backed by a reliable, permitted signal. Priority: augment > shop > optional scoreboard.
5. **Never infer unknown events as facts.** Gold/death alone do not prove the shop is open. Level thresholds alone do not prove a currently visible augment offer. Unreliable OCR must show a safe fallback without potentially misaligned ratings.
6. **Game-safe UX and policy.** No automatic augment/champion/item actions, no secret game state, no unsupported win-rate displays or third-party code reuse. All recommendations remain suggestions subject to Riot review.
7. **Incremental and reversible.** Each small PR compiles independently, has deterministic tests, and keeps the previous `python -m backend.overlay --renderer qt` launch path working.

## Proposed runtime topology

```text
Windows Start menu / ARAM Oracle.exe (future)
                  |
          Desktop host / Qt application
                  |
     +------------+-------------+
     |                          |
Desktop Settings window   Transparent game overlay
(normal, focusable)       (topmost, click-through)
QWebEngineView /settings   QWebEngineView /overlay
     |                          |
     +------------+-------------+
                  |
       HTTP + WebSocket on 127.0.0.1:8765
                  |
        One FastAPI process/engine
    +-------------+------------------+
    |             |                  |
preferences   collectors/OCR     scoring/pipeline
disk + API    (permitted input)   + diagnostics
```

The first development slice introduces the Settings Qt shell **without** launching a second overlay or introducing a new backend. Later slices unify lifecycle and tray ownership. Treat `localhost` web routes as local UI, but keep authorization, validation and privacy boundaries explicit before public distribution.

## Components and ownership

| Component | Existing implementation | Target responsibility |
| --- | --- | --- |
| `backend.api.server` | FastAPI, preferences, WebSocket and bug reports | Exactly one local server, API validation and state synchronization |
| `backend.preferences` | Atomic `~/.aram-oracle/preferences.json` build style | Versioned validated preferences as UI configuration grows; no secrets |
| `backend.overlay.window` | Transparent PyQt6 overlay, hotkeys and tray | Only the in-game decision surface; do not change transparency while building desktop shell |
| `backend.overlay.__main__` | Dev launcher and loopback ASGI thread | Keep backward-compatible developer entrypoint |
| `backend.desktop` (planned) | Not present | Normal, resizable Settings window; separate launcher/host and later one-app lifecycle |
| `frontend/settings.*` | Existing browser Settings for build style and feedback | Reuse as desktop control center; add modules incrementally, no second JS framework initially |
| `frontend/index.html` + `app.js` | Current multipanel overlay | Future event-driven contextual surfaces with strict data confidence |
| `backend.collectors.*` | LCDA and Tesseract watcher | Explicit observable offer/shop state only after tested capture/data-source validation |
| `backend.workflow.pipeline` | Dynamic scoring/build recommendations | No duplicated scoring in UI; consume stable state, preserve rule explanations |

## Configuration boundaries

- **User-editable:** build style, overlay positioning/scale/opacity, visibility and keyboard controls, OCR readiness/manual fallback, diagnostics/reporting preferences.
- **Display-only diagnostics:** engine/WS/OCR status, data-source and patch confidence, read-only logs and export.
- **Separate sensitive configuration:** GitHub token and credentials must not enter the browser UI, report JSON, or git. Any diagnostic upload requires clear opt-in and disclosure.
- Desktop preference writes use the existing local HTTP API (not direct unsynchronized JSON writes); overlay receives changes from WebSocket and applies them at the next relevant pipeline update.
- Support failing dependencies gracefully. Missing Tesseract should not prevent opening Settings; unavailable Qt should report an actionable install error in developer mode.

## Window lifecycle contract

- Desktop Settings: regular taskbar window, keyboard/mouse interaction, resizable, no transparent fullscreen region.
- In-game overlay: separate window with transparent idle space, click-through by default, Alt+O interaction toggle, Alt+H show/hide and tray recovery preserved.
- **Single instance** and single bound loopback server; distinguish a healthy current instance from a different process occupying port 8765 before reuse. Avoid duplicate tray icons and orphan background servers.
- Close/minimize semantics configurable only when tested. The application must expose a reliable Quit that cleans up the overlay, ASGI server, hotkeys and tray.
- Use the existing browser `/settings` fallback until the native desktop shell is verified on the user's Windows machine.

## Distribution architecture (later phases only)

- Initial hypothesis: PyInstaller **onedir** executable bundle + Inno Setup installer; verify exact bundle inputs (PyQt6 WebEngine plugins, `frontend/`, static data, SQLite migrations), license notices and reproducibility.
- Installer provides Start menu entry, optional desktop shortcut, clean uninstall and optional user-data retention. Do not require users to install Python or use PowerShell.
- Tesseract: detect existing install first. Bundle or guide installation only after verifying packaging license, provenance, version and expected executable path. Never silently install third-party software.
- Signed releases and Windows SmartScreen trust are distribution requirements, not automatically solved by creating an EXE.
- Updates and rollback are **later**, after a tested installer. Never restart/update during a match without an explicit action.

## Required acceptance evidence

- Automated Windows Actions `pytest` + JavaScript checks for each PR, actual run URL and head SHA.
- An on-device Windows test must confirm that the desktop Qt window opens Settings independently, does not affect the transparent in-game overlay, and survives hide/restore/restart.
- At 1080p and 1440p, confirm focus, scaling, click-through and borderless League behavior before marking UX acceptance complete.
- OCR/shop contextual detection and Riot policy remain distinct release gates; passing a desktop or packaging CI run **does not** validate gameplay accuracy.

## Non-goals for the first desktop phase

No installer; no global app startup integration; no full Settings redesign; no new scoring algorithm; no shop detector; no forced migration from the existing Qt overlay; no auto-updater; no use of OP.GG assets/code.
