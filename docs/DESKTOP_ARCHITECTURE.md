# ARAM Oracle — Desktop and Contextual Overlay Architecture

Status: **approved architecture; D1 Settings host draft PR #13, D2 single-instance/tray draft PR #14 (Windows lifecycle accepted), D3 Settings navigation draft PR #15 (manual Windows acceptance pending)**. Baseline: 2026-11-18. All PRs remain stacked drafts; `main` unchanged.

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

D1 introduced the Settings Qt shell without duplicating the API. D2 now uses one per-user OS lock and authenticated loopback activation to arbitrate both Qt launch commands, one Qt application/tray owner and one managed ASGI server thread (or a reused compatible external API). One process owns both Settings and overlay Qt windows; no new scoring/preference engine was introduced. Explicit non-Qt webview remains a legacy developer fallback outside this managed Qt lifecycle. The user confirmed Settings close-to-tray, tray actions, Alt+H/Alt+O and an empty 8765 listener check after Quit; broader Windows/League validation remains open. Treat `localhost` web routes as local UI, but keep authorization, validation and privacy boundaries explicit before public distribution.

## Components and ownership

| Component | Existing implementation | Target responsibility |
| --- | --- | --- |
| `backend.api.server` | FastAPI, preferences, WebSocket and bug reports | Exactly one local server, API validation and state synchronization |
| `backend.preferences` | Atomic `~/.aram-oracle/preferences.json` build style | Versioned validated preferences as UI configuration grows; no secrets |
| `backend.overlay.window` | Transparent PyQt6 overlay and hotkeys | In managed mode, no separate tray; preserve click-through, transparency, Alt+O and Alt+H. Legacy standalone Qt helpers retain fallback |
| `backend.overlay.__main__` | Dev launcher and original loopback ASGI startup | Delegate Qt launches to the managed desktop owner; preserve the explicit Qt entrypoint and non-Qt fallback |
| `backend.desktop` (D1 + D2) | Normal Settings QMainWindow, one QSystemTrayIcon, transparent overlay Qt surface and local activation | Single owner of Qt UI and explicit Quit; separate native window behaviors |
| `backend.desktop.instance` + `backend.desktop.service` | OS-held per-user lock, local authenticated activation, managed FastAPI ASGI shutdown | Avoid duplicate process owners; never kill pre-existing compatible API; fail safely on port conflict |
| `frontend/settings.*` | D3 seven-section accessible Settings navigation using the existing preferences/OCR/feedback APIs | D4 will add validated overlay positioning preferences; D5 will add OCR testing; no duplicated JS framework |
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
- **Single instance** is implemented for managed Qt entrypoints through an OS-held lock. Repeated launches forward Settings or overlay requests through a per-user authenticated loopback channel. The managed app owns one tray icon, and only stops an ASGI server that it started. Unrelated occupants of port 8765 are rejected. Legacy explicit non-Qt webview is not managed by this gate.
- D2 code closes Settings to tray when tray is present; without a tray, closing Settings quits rather than stranding a process. The tray's Quit stops polling, exits the Qt event loop and requests the owned uvicorn server to stop. User-device validation confirms the expected controls and no port 8765 listener after Quit; this is not a full process audit.
- Use the existing browser `/settings` fallback until the native desktop shell is verified on the user's Windows machine.

## Desktop UI design-closure gate (D5c, before D6)

The desktop interface is built progressively in D3 (navigation), D4a/D4b (validated overlay preferences and safe preview) and D5a/D5b (OCR readiness, test and diagnostics). **D5c is a new planned Claude-led UX/UI audit and bounded design refinement phase** after these capabilities exist, before D6 gameplay context logic.

- Review the actual runnable desktop Settings experience across General, Overlay, Build Preferences, OCR, Diagnostics, Feedback and About, including loading, missing-data, save/error and keyboard states. Use real screenshots and safe mock data, not invented success screens or private League data.
- Save the actual Claude audit/report with ranked P0/P1/P2 issues and reproducible evidence. Claude analysis is **not yet performed**; no audit is implied merely by this plan.
- Fix bounded P0/P1 usability/visual/accessibility issues; keep UX hierarchy, consistent forms and truthful system states. Preserve single-instance/tray, existing APIs, click-through, transparency and Alt+H/Alt+O. Separate deferred design wishes into TODO.
- Gate the design pass on automated interaction tests and observed Windows navigation/scaling/recovery. **This closes the desktop design system only**, not the future D7 augment panel or D8 shop panel, which need contextual in-game audit at implementation time.

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

## D1 evidence and remaining on-device gate

- [Draft PR #13](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/13) implements the normal Settings Qt shell and API reuse checks while leaving transparent overlay files unchanged.
- [Windows Actions run 44336280007](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44336280007) passed at D1 code head `d5aff632`: 234 Python tests, 1 warning; 4 Node Settings tests and JS syntax checks passed.
- Real Windows Settings resize/focus, preference saving, feedback, overlays and Alt+O/Alt+H are not yet observed for this branch; do not infer them from CI.
- [External reuse candidates](REUSE_CANDIDATES.md) are scoped to later phases, with verification of licenses, notices and permitted data sources before code import.

## Non-goals for the first desktop phase

No installer; no global app startup integration; no full Settings redesign; no new scoring algorithm; no shop detector; no forced migration from the existing Qt overlay; no auto-updater; no use of OP.GG assets/code.
