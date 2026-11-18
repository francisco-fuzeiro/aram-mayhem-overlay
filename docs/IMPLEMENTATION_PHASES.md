# ARAM Oracle — Small, Gated Implementation Phases

Status: **planned**. Each phase should be a small, focused **stacked draft PR** with test evidence and a minimal diff. Check the corresponding tasks in [TODO.md](TODO.md), not just the phase title, after the relevant acceptance criteria are met. The original PRs #1–#12 remain drafts. Never merge to `main` without the user's approval.

Read [DESKTOP_ARCHITECTURE.md](DESKTOP_ARCHITECTURE.md) and the original UX backlog first.

## Delivery order

| Phase | Size / purpose | Dependencies | Gate |
| --- | --- | --- | --- |
| G0 — Baseline snapshot | Review only; verify state and CI, identify risks | PR #12 | Correct branch, approved baseline, previous launch remains documented |
| **D1 — Desktop Settings shell (first development phase)** | Small: native normal Qt window hosting `/settings` | G0 | Standalone Settings window with reliable startup/error state and tests |
| D2 — Single-instance and lifecycle | Small: reuse existing server, Quit/close behavior | D1 | One API server and one tray owner, graceful exit/reopen |
| D3 — Desktop navigation | Small: General + Build + Feedback/Diagnostics sections | D2 | No duplicate settings backend and accessible navigation |
| D4 — Overlay controls and preview | Small: persisted scale/anchor/opacity + non-game preview | D3 | Changes validated and reflected safely in Qt, without transparency regression |
| D5 — OCR first-run diagnostics | Small: detection/setup/test capture UI | D3 | Missing OCR readable; reliable manual route, no false auto-detection |
| D6 — Game context state machine | Small: pure deterministic state reducer + transitions | P0 OCR readiness | Minimal overlay in combat, explicit unknown states, regression tests |
| D7 — Augment micro-advice | Small: align 3 scores to 3 **verified** offers | D6 + live OCR fixtures | Hide when cards vanish; rerolls and uncertain detection handled |
| D8 — Shop-context micro-advice | Small: shop detector + feasible next item | D6 + verified shop source and item catalog | No shop = no shop advice; real purchase eligibility validated |
| D9 — App package smoke | Small: unsigned local onedir Windows package | D2–D5 + core P0 readiness | Starts on clean Windows without Python; assets bundled |
| D10 — Installer and uninstall | Small: Inno Setup or evaluated equivalent | D9 | Installs, launches, repairs/uninstalls, preserves data only by choice |
| D11 — Release quality | Separate later PRs: privacy, license, updater, signing | D10 | Explicit release gates; no misleading trust/compliance claims |

D6–D8 are **product core work**, not prerequisites for prototyping the Settings shell. They **are prerequisites for marketing or releasing a reliable in-game assistant**. Keep installer work behind verified lifecycle and P0 game-data tests.

## G0 — Baseline and handoff (no new feature)

- Confirm `feat/pregame-settings-feedback` and PR #12 draft base `fix/live-augment-detection-item-duplicates`; read `AGENTS.md`, `PROJECT_STATE.md`, `DEVELOPMENT_LOG.md`, `TODO.md`, this phase plan and architecture.
- Confirm the latest actual Windows Actions run at current head. Separate automated tests from real Windows tests.
- Inspect `backend/overlay/__main__.py`, `backend/overlay/window.py`, `backend/api/server.py`, `frontend/settings.html`, and the existing `GET/PUT /api/preferences` contract.
- Do not require the user to repeat project decisions. If Windows observations are needed, record as separate unchecked follow-ups.

## D1 — First development PR: desktop Settings shell

**Goal:** open existing Settings in a regular, focusable Qt window independently of the transparent game overlay.

**Suggested branch:** `feat/desktop-settings-shell`, branched from `feat/pregame-settings-feedback` (expected next draft PR #13; **use the number assigned by GitHub**).

**Scope (small and testable):**

1. Introduce a minimal `backend/desktop/` package and a normal `QMainWindow` + `QWebEngineView` host for `http://127.0.0.1:8765/settings`. Use Qt availability guards so automated Python tests run without a display or Qt installed.
2. Provide developer entrypoint `python -m backend.desktop`. Reuse the existing **one** FastAPI server/startup path or detect an already healthy local ARAM Oracle instance; do not start two conflicting servers. Report port conflict or server readiness failure clearly; do not open an empty white browser view.
3. Keep `python -m backend.overlay --renderer qt`, `Alt+H`, `Alt+O`, click-through and the Qt system tray fully backward-compatible; do not switch the default renderer yet.
4. Add targeted Python tests for launcher/state, host URL and unavailable dependencies plus a safe UI contract test. Tests must not require an actual League client or a graphical CI session.
5. Record test counts and Windows Actions URL; create one draft PR based on PR #12 branch, update task IDs and continuity docs. **Do not implement an installer in D1.**

**Acceptance criteria:** one clean Settings window opens before a match; it loads existing Preferences and Feedback without HTML duplication; the app handles server-unavailable and duplicate-server conditions; existing overlay is unchanged; tests and latest CI pass. Actual native Windows focus, resize, tray and persistence tests are **pending** until user-observed.

**Non-goals:** multiple tabs redesign, preferences schema expansion, auto-launch on boot, OCR installation, custom icons, updater, packaging, shop detection.

## D2 — Instance/lifecycle (next small PR)

- Create one lifecycle owner for FastAPI and Qt windows; distinguish a second launch from an unrelated process on port 8765.
- Make Open Settings/Show Overlay/Quit work consistently with one tray icon.
- Tests: repeated launch, server already running, close vs hide, clean shutdown, loss/reconnect. Validate actual Windows hotkeys.

## D3 — Settings navigation (separate UI-only PR)

- Reorganize current page into focused General, Overlay, Build Preferences, OCR, Diagnostics, Feedback and About tabs/sections. Keep labels English and preserve existing API calls.
- Tests: keyboard navigation, form save/error states and loading with no League client. No fabricated hardware status.

## D4 — Overlay configuration (split if needed)

- **D4a:** validated settings model/API for anchor/offset/scale/opacity plus safe defaults and migration.
- **D4b:** preview/position in desktop window and Qt apply/reload without disrupting click-through.
- Tests: invalid input, persistence across restart, 1080p/1440p scaling, multiple monitors when available.

## D5 — First-run OCR and diagnostics

- **D5a:** local Tesseract executable detection; explicit status and guided install path, no hidden installation.
- **D5b:** manual capture/test recognition with confidence and safe fallback; save sanitized diagnostics only.
- Tests: installed/missing OCR, failed extraction and privacy/errors; user Windows screenshot calibration required.

## D6 — Context controller (separate from new UI look)

- Build a **pure, testable** decision-state controller: unknown/idle, champion select, verified augment offer, verified shop, optional scoreboard, post-game. Handle stale evidence and priority/debouncing.
- For unknown shop/scoreboard state, emit nothing by default. Keep combat hidden; never equate 'dead' to 'shop open'.
- Tests: transitions, rerolls, source timeouts, disconnect/reconnect and priority collisions.

## D7 — Augment advice delivery

- Prove capture of the 3 current cards and rerolls at real HUD scales; show small aligned ratings only for reliably mapped choices.
- Never cover reroll controls, fake a 0–10 rating or show stale cards; preserve explicit manual fallback.
- Tests: fixtures from screenshots and full state transitions; real in-game observation required.

## D8 — Shop advice delivery

- Research, then verify a permitted shop-open signal (visual confirmation or explicit player command); do **not** guess from gold/death.
- Render one feasible next purchase plus alternative and expandable explanation. Honor owned components, gold, slots, availability and boots replacement.
- Tests: opened/closed shop, six slots, mode restrictions and disabled detection; real Mayhem validation required.

## D9–D11 — Packaging and release

- **D9:** prototype onedir PyInstaller build in an isolated PR; verify bundled Qt WebEngine and frontend data on clean Windows. This is not a release installer.
- **D10:** separate Inno Setup installer/uninstaller PR with shortcuts and uninstall data choices. Never silently install Tesseract.
- **D11a:** privacy review, explicit diagnostic upload consent and error handling.
- **D11b:** licensing, Riot review, version/patch policy, logo/icon and accessibility.
- **D11c:** optional signed/verified updates with opt-in, idle-safe timing and rollback. No auto-update during gameplay.

## Completion protocol per phase

1. Check actual branch/head, stacked PR chain and unchanged `main`.
2. Implement only the current phase; avoid opportunistic design/polish work.
3. Add targeted tests, `python -m pytest -q`, and relevant `node --check` / `node --test`; check **real** Windows Actions on final code head.
4. Open a **draft** PR targeting the previous feature branch (never `main`).
5. Mark only genuinely implemented/verified checkbox items in `docs/TODO.md`; leave on-device validation unchecked until observed.
6. Update `docs/PROJECT_STATE.md`, append `docs/DEVELOPMENT_LOG.md` with branch/PR, CI link and explicit missing Windows evidence.
7. Provide a concise user-facing PT-PT summary and minimal next Windows verification commands only if needed.
