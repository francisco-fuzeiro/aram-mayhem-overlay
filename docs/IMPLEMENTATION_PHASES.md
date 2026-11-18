# ARAM Oracle — Small, Gated Implementation Phases

> **2026-11-18 supersession note:** This file preserves the historical D-series UI/desktop sequencing. The subsequently approved **Functional Fix Implementation Plan (M1–M8, P0.1–V1, G1–G6)** is the implementation authority until P0 gameplay correctness is stable. M1 P0.1–P0.3 have stacked draft PRs [#20](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/20), [#21](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/21) and [#22](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/22). Prior A-FUNC and A-FIX identifiers are historical traceability, including the separate preserved [docs-only PR #18](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/18); do not treat D5a as the immediate next implementation. The full new plan and source audit are available on the **independent docs-only draft PR #19** (`docs/a-func-audit-report`: `docs/FIX_IMPLEMENTATION_PLAN_2026-11-18.md` and `docs/FUNCTIONAL_AUDIT_REPORT_2026-11-18.md`), not in the M1 implementation branch; do not confuse this with A-FIX draft PR #18. **M2/A1** now has a tests-first implementation on [draft PR #23](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/23). Continue with **M2/A2** only after A1 final-head CI, not UI/installer work.

Status: **in progress** (D2 lifecycle and D3 Settings accepted by user on Windows; D4a final CI passed; D4b draft PR #17 under automated validation, real monitor/League matrix pending). Each phase should be a small, focused **stacked draft PR** with test evidence and a minimal diff. Check the corresponding tasks in [TODO.md](TODO.md), not just the phase title, after the relevant acceptance criteria are met. The original PRs #1–#12 remain drafts. Never merge to `main` without the user's approval.

Read [DESKTOP_ARCHITECTURE.md](DESKTOP_ARCHITECTURE.md) and the original UX backlog first.

## Delivery order

| Phase | Size / purpose | Dependencies | Gate |
| --- | --- | --- | --- |
| G0 — Baseline snapshot | Review only; verify state and CI, identify risks | PR #12 | Correct branch, approved baseline, previous launch remains documented |
| **D1 — Desktop Settings shell (first development phase)** | Small: native normal Qt window hosting `/settings` | G0 | Standalone Settings window with reliable startup/error state and tests |
| D2 — Single-instance and lifecycle | Small: reuse existing server, Quit/close behavior | D1 | One API server and one tray owner, graceful exit/reopen |
| D3 — Desktop navigation | Small: General + Build + Feedback/Diagnostics sections | D2 | No duplicate settings backend and accessible navigation |
| D4a — Overlay preferences | Small: validated scale/anchor/offset/opacity model and persistence | D3 | Migration, error handling and safe defaults tested |
| D4b — Overlay preview and apply | Small: Settings preview and safe Qt position/scale/opacity apply | D4a | No transparency, hotkey or click-through regressions |
| **A-FUNC — Claude gameplay/functionality audit (next)** | **Review current code, OCR and playtest evidence; prioritize P0 bugs, no unreviewed implementation** | **D4b code/Settings complete, gameplay failures logged** | **Actual Claude output saved; each fault has source evidence, tests and small repair phases before new interface work** |
| D5a — OCR readiness | Small: Tesseract detection and setup guidance | A-FUNC intake/roadmap + D3 | Missing OCR clearly reported, no silent install |
| D5b — OCR test and diagnostics | Small: manual capture/recognition test with confidence and privacy-safe report | D5a | Failure and manual fallback tested; real screen calibration pending until observed |
| **D5c — Claude UX/UI audit and desktop design closure** | **Small, evidence-based audit of completed desktop Settings/preview/OCR workflows, then prioritized design fixes** | **D3 + D4a + D4b + D5a + D5b** | **Claude audit findings recorded, P0/P1 UX defects resolved or explicitly tracked, desktop Windows recheck before D6** |
| D6 — Game context state machine | Small: pure deterministic state reducer + transitions | D5c + P0 OCR readiness | Minimal overlay in combat, explicit unknown states, regression tests |
| D7 — Augment micro-advice | Small: align 3 scores to 3 **verified** offers | D6 + live OCR fixtures | Hide when cards vanish; rerolls and uncertain detection handled |
| D8 — Shop-context micro-advice | Small: shop detector + feasible next item | D6 + verified shop source and item catalog | No shop = no shop advice; real purchase eligibility validated |
| D9 — App package smoke | Small: unsigned local onedir Windows package | D2–D5c + core P0 readiness | Starts on clean Windows without Python; assets bundled |
| D10 — Installer and uninstall | Small: Inno Setup or evaluated equivalent | D9 | Installs, launches, repairs/uninstalls, preserves data only by choice |
| D11 — Release quality | Separate later PRs: privacy, license, updater, signing | D10 | Explicit release gates; no misleading trust/compliance claims |

The new **A-FUNC audit** precedes the next interface implementation. It investigates real functional defects, does **not** itself fix OCR/ratings and must not be confused with the later D5c **desktop design/UX audit**. See [the functional audit intake](FUNCTIONAL_AUDIT_HANDOFF_2026-11-18.md).

D5c closes the **desktop Settings interface design pass** before core gameplay panels begin. It does not certify the later D7/D8 in-game augment/shop micro-panels; those need their own contextual Windows/League validation when implemented.

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

**D3 implementation:** [draft PR #15](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/15) and [Windows Actions run 44352298709](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44352298709) cover the seven sections, ARIA/keyboard navigation and truthful API state handling. Actual Qt Windows Settings acceptance remains a distinct gate.

## D4 — Overlay configuration (split if needed)

- **D4a:** validated settings model/API for anchor/offset/scale/opacity plus safe defaults and migration.
- **D4b:** [draft PR #17](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/17) provides an explicitly simulated Settings preview and form backed by D4a schema/API. The existing transparent Qt window polls the atomic saved file and clamps logical coordinates to the current display's available geometry while applying opacity and zoom. Manual Windows resolution/DPI/hotplug/League validation remains a separate gate.
- Tests: invalid input, persistence across restart, 1080p/1440p scaling, multiple monitors when available.

## A-FUNC — Functional/code audit checkpoint after D4b

**Status: requested, not performed.** D4b implementation and user Windows Settings smoke passed; the playtest showed P0 gameplay defects. Ask Claude to inspect the actual connected private code and [audit handoff](FUNCTIONAL_AUDIT_HANDOFF_2026-11-18.md), including custom-game transition, **wrong three augments**, per-card reroll, uniform **2.1/10** on unknown data, stale Neeko/time/gold after game exit and bad-offer lifecycle. Record source/line evidence, confirmed versus suspected root causes, fixture/test needs and a ranked ordered repair plan. **Do not start new visual/in-game card-aligned UI until foundational identity and score confidence are verified.**

- **Audit gate:** Claude's actual report exists; triage `A-FUNC.1` and `A-FUNC.2` with user approval of bounded fixes. Functional Windows acceptance `A-FUNC.3` and visual integration `A-FUNC.4` remain separately open.
- D4b code/CI and 6/6 Settings are **development complete**, while `PH-D4b.2` and `UX-D09` remain unchecked; no fabricated full-screen/DPI/League test.
- Do **not** accept the unverified `fix/postgame-stale-match-state` WIP branch as a completed fix. `main` unchanged.

## D5 — First-run OCR and diagnostics

- **D5a:** local Tesseract executable detection; explicit status and guided install path, no hidden installation.
- **D5b:** manual capture/test recognition with confidence and safe fallback; save sanitized diagnostics only.
- Tests: installed/missing OCR, failed extraction and privacy/errors; user Windows screenshot calibration required.

## D5c — Claude-led UX/UI audit and desktop design closure (new phase)

**Goal:** once D3 navigation, D4a/D4b settings and preview, and D5a/D5b OCR/onboarding are implemented, review the **complete desktop interface** with Claude, then close its highest-priority design and usability findings before D6. This is a **planned external audit**, not a completed Claude review or an instruction to access a Claude account automatically.

**Audit inputs:** current runnable Windows desktop app, screenshots of General/Overlay/Build/OCR/Diagnostics/Feedback/About, interactive states (first run, loading, saved, invalid input, missing Tesseract, preview, errors), implementation/docs, and 1080p/1440p or relevant DPI captures where available. Avoid private League data or credentials in shared screenshots/reports.

**Audit rubric:** navigation/information architecture, clarity of action hierarchy, visual consistency (typography/spacing/contrast), error/preference feedback, accessibility/keyboard, focus/resizing and system-tray expectations, onboarding, performance/perceived latency, and legibility of the non-game overlay preview. Respect the event-driven overlay design and Riot/privacy constraints.

**Deliverables and acceptance:**

1. Obtain an actual Claude audit (user-provided or performed with an explicitly available authorized Claude workflow), stored as a review artifact with annotated evidence; rank issues P0/P1/P2 with reproduction, impact and suggested change. **Never claim Claude reviewed the app without its real output.**
2. Implement and test **bounded P0/P1 desktop UX/design corrections** from the review, preserving existing APIs, semantics, Qt transparency, click-through, Alt+H/Alt+O and single-instance ownership. Record anything larger as separate TODO work, not an open-ended redesign.
3. Run automated frontend/desktop tests and recheck actual Windows Settings navigation, resize, focus, save/error states, OCR failure/manual path and overlay preview. Document accepted findings, deferred polish and evidence; no fabricated Windows or game tests.

**Not in scope:** rewriting the engine, changing recommendation scores/OCR recognition algorithms, copying OP.GG visuals/assets, claiming League in-game panels are complete, installer/release packaging. D7/D8 contextual panels receive their own in-game UX checks later. Start D6 only after D5c's desktop review gate is resolved or explicitly carried forward with rationale.

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
