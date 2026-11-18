# Overlay LoL — Project State / Chat Handoff

> **Canonical handoff for future ChatGPT project conversations.**
> Update this document after meaningful development steps, test runs, architectural decisions, and before switching chats.
> Log each dated change separately in `docs/DEVELOPMENT_LOG.md`.

Last authored: **2026-11-18**, Europe/Lisbon. Code and product UI must remain **English**; user conversation is **European Portuguese**.


## 2026-11-18 — M2/A1 stop passive stat-change picks (draft PR #23)

- The **complete Functional Fix Implementation Plan** (M1–M8, 31 slices, gates G1–G6) and source audit report were located on the **independent docs-only draft PR #19**, branch `docs/a-func-audit-report`, paths `docs/FIX_IMPLEMENTATION_PLAN_2026-11-18.md` and `docs/FUNCTIONAL_AUDIT_REPORT_2026-11-18.md`. The originally proposed plan was subsequently approved by the user; do not treat PR #19 as merged into the M1 chain. The historical A-FIX docs-only draft PR #18 stays independent.
- M1 documentation head `c2c639a93b874ed59c3a4b3f7de02278359e7878` is verified by successful [headless Windows Actions 44398642390](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44398642390). Baseline: 317 Python passed, 3 xfailed, 24 JavaScript passed, 4 TODO; real Windows/League gameplay not tested.
- **Current implementation:** [draft PR #23](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/23) on `fix/m2-a1-no-stat-change-picks`, stacked on M1/P0.3 PR #22. Tests-first commit `31dca394` makes AUD-03a a normal test and adds item stat-change, death/respawn and OCR-disappearance regression coverage. Fix commit `c8a41921` removes only the passive stat-change-to-pick inference path; OCR disappearance still triggers existing matching pending M2/A3. **Final branch documentation-head CI must be verified separately**; A1 is not accepted on real Windows/League.
- **Next only after successful A1 final-head CI:** M2/A2 (damage must not close scan eligibility), on its own new stacked branch/draft PR. Then A3, E1, E2, E3 in that order. AUD-03d and AUD-07 xfails remain strict; four Node TODO tests still await M3/M6. Do not implement UI/installer or merge to `main`.
- Open constraints: G4 local API Host/Origin/per-launch token before public build; G1/G2 authoritative patch-specific Mayhem catalog source/coverage before accepting M7 scoring; A3 confirmation must remain non-intrusive and must never manufacture an augment pick. Preserve bounded structured logs and disabled automatic screenshots.

## 2026-11-18 — Approved M1 Functional Fix implementation checkpoint

- New approved M1–M8 Functional Fix Implementation Plan drives implementation; existing A-FUNC/A-FIX labels are kept for defect traceability. The full newer plan and full audit report have **not** been located at the baseline ref. Historical A-FIX planning lives untouched on separate docs-only draft PR #18.
- **M1 / P0.1**: [draft PR #20](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/20), branch `test/m1-p01-poll-tick-harness`, starts at approved `9832fb0`. Replaced the body of `_poll_game_loop` with injectable `poll_tick(state, deps, now)` and retained existing behavior/defects. Three strict expected-failure regressions cover AUD-03a, AUD-07 and AUD-03d.
- Verified P0.1 code SHA `646161378`: [Windows headless Actions 44394538148](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44394538148), **306 Python passed, 3 xfailed, 1 warning, 18 Node passed**. An earlier extraction CI run 44393987021 failed syntax and was corrected. No genuine League/Windows gameplay test performed. The P0.1 documentation-head CI is separately checked after writing this checkpoint.
- **Next sequential gates:** P0.2 frontend DOM/message harness on a branch based on P0.1, then P0.3 bounded structured diagnostics on P0.2. One branch and draft PR per phase, no merge.
- Record without implementing: G4 local API origin/auth security must precede public distribution; G1/G2 patch-specific Mayhem augment data coverage before M7 scoring; A3 no intrusive manual confirmation in combat (never invent picks).


## 2026-11-18 — M1/P0.2 frontend message harness

- [Draft PR #21](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/21), branch `test/m1-p02-frontend-message-harness`, stacked on P0.1 draft PR #20. `frontend/app.js` exports existing handlers/renderers only under CommonJS test mode, leaving browser/Qt boot unchanged. Added `tests/js/overlay-messages.test.cjs` with DOM/WebSocket mocks, and extended the workflow to run both JS files.
- The test suite covers `game_ended`, `no_game`, WebSocket disconnected, stale data and game with a different champion. Current known violations are executed as Node TODO cases (AUD-05/06); frontend functional fixes F1–F5 are **not implemented**.
- Verified at P0.2 code/workflow head `f736e14be7b6b53cb4fc59619c3408535b78af42`: [Windows headless Actions 44395754449](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44395754449) succeeded: **306 Python passed, 3 xfailed, 1 warning; 24 Node passed, 4 TODO, 0 failed**. Documentation-head CI to be checked separately. Real native Windows/League test not performed.
- Next gated work: P0.3 safe structured transition diagnostics; branch and draft PR stacked on P0.2 only after final-head CI.


## 2026-11-18 — M1/P0.3 structured diagnostics; M1 code gates closed

- [Draft PR #22](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/22) `feat/m1-p03-structured-diagnostics` is stacked on PR #21 (P0.2), which is stacked on PR #20 (P0.1). All three remain **draft and unmerged**; `main` was not changed. Historical docs-only draft PR #18 was preserved separately.
- P0.3 introduced `backend/diagnostic_events.py` with a bounded in-memory queue (256), daemon disk writer, structured JSONL allowlist and rotation (256 KiB per file and 3 backups, approx. 1 MiB total), under `%LOCALAPPDATA%/ARAMOracle/logs` on Windows or the platform's per-user state directory. No names, match IDs, accounts, free-form OCR/LCDA data or screenshots are serialized.
- Hooked sanitized **LCDA available/error-class transitions**, **OCR scan-window open/close**, **recognition outcomes and confidence**, **augment inference/confirmation**, and **match phase transitions** without waiting on disk I/O in the poll loop. Automatic/manual OCR screenshot saving is now disabled; `ScreenWatcher.check` and `detect_augments` default `save=False`, with opt-in debug path retained but not invoked by runtime flows.
- P0.3 tested at code SHA `be77b6c3db9e85adb6c1c764319584123181d4e6` with [Windows headless Actions 44398134318](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44398134318): **317 Python passed, 3 xfailed (1 warning); 24 JavaScript passed, 4 TODO, 0 failed**. New tests verify serialization privacy, rotation, queue saturation, LCDA timeout classification, OCR screenshot defaults and actual polling/automatic-confirmation event emission. Earlier run 44397259218 failed two tests because pytest's `tmp_path` directory already exists; the expectations were corrected.
- **M1 foundations code complete, but not real-game accepted.** AUD-03a/07/03d remain strict xfails, AUD-05/06 remain Node TODO; all need functional correction in M2+. Actual Windows desktop/League capture and behavior must be validated later. Before distribution, resolve G4 local API authorization/Origin/Host security; before M7 scoring acceptance, validate G1/G2 Mayhem catalog patch/source/coverage; A3 fallback must avoid in-combat interaction and never fabricate selections.
- **Next: M2 — Stop false outputs**, starting from P0.3 branch head only after documentation-head CI, with new branch/draft PR and tests before fixes. No interface redesign, installer or merge.

## Current goal

Build a Windows companion overlay for **League of Legends — ARAM Mayhem** that responds to the actual match state instead of displaying static tier lists. Show alternative options rather than forcing decisions. The same augment can score differently depending on champion, already-picked augments, items, allies, opponents and game phase.

The user supplied `funcionalidades.md` in the ChatGPT Overlay LoL project on 2026-11-18 as the requirements specification. It lists P0: game-state collection; threat and ally analysis; dynamic 0.0–10.0 augment ratings (40% performance / 35% synergy / 25% context, adjusted for evidence confidence); adaptive builds; explicit synergy/counter rules; contextual champion select; score provenance. P1: reroll improvements, alternative build paths, post-game, patch-awareness, UI polish. The score must **not simply conceal a win-rate percentage**.

## Access and repository

- GitHub private repository: `francisco-fuzeiro/aram-mayhem-overlay` (connected GitHub connector; edit through its API).
- User's Windows clone: `D:\Overlay ARAM\aram-oracle` (not directly accessible from this ChatGPT session; changes appear locally after `git fetch`/checkout).
- Original base: `fabs133/league-aram-builder` (ARAM Oracle, MIT).
- Windows: Python 3.11, PowerShell, pywebview. User successfully launched overlay with `python -m backend.overlay` and ran tests in previous conversations.
- Keep `main` unchanged until reviewed, validated and consciously merged.

## Open stacked draft PRs (2026-11-18)

| PR | Feature branch | Based on | What it implements |
| --- | --- | --- | --- |
| [#1](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/1) | `fix/overlay-backend-stability` | `main` | Avoid nested WebSocket lock, loopback-only overlay server, database initialization/tests |
| [#2](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/2) | `feat/champion-select-companion` | PR #1 branch | Read-only LCU champion select, bench/current champ, initial contextual options |
| [#3](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/3) | `feat/reuse-mayhem-core` | PR #2 branch | Adapt permissively licensed OCR and client discovery, opt-in own-match history, proprietary composite champion score and CI |
| [#4](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/4) | `feat/augment-composite-rating` | PR #3 branch | Absolute experimental augment score 0.0–10.0, confidence and source, optional empirical signal **disabled by default** |
| [#5](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/5) | `feat/dynamic-team-threats` | PR #4 branch | LCDA visible enemy/ally state, original threat profiles, shared augment/build context, Balanced + Damage/Survival/Utility build paths and tests |
| [#6](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/6) | `feat/team-threat-coverage` | PR #5 branch | Player-inclusive ally roles, catalog coverage safeguards and visible enemy inventory fallback |
| [#7](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/7) | `feat/selectable-build-paths` | PR #6 branch | Selectable build style, saved UI preference, inventory-safe next item, WebSocket contract |
| [#8](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/8) | `feat/late-game-boots-replacement` | PR #7 branch | Optional full-inventory boots-to-mobility item swap with conservative stat comparison |
| [#9](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/9) | `fix/windows-overlay-transparency-fallback` | PR #8 branch | Explicit Qt fallback for Windows transparency; pywebview HWND fix |
| [#10](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/10) | `feat/qt-overlay-window-controls` | PR #9 branch | Hide/show/quit buttons, Alt+H restore, Qt system tray menu |
| [#11](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/11) | `fix/live-augment-detection-item-duplicates` | PR #10 branch | Fix early level scan, manual augment fallback, duplicate-name builds and non-equipment trinkets |
| [#12](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/12) | `feat/pregame-settings-feedback` | PR #11 branch | Out-of-game Settings, persistent live build preferences, Qt tray access and local feedback |
| [#13](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/13) | `feat/desktop-settings-shell` | PR #12 branch | D1 native normal PyQt6 Settings host, shared API readiness/conflict handling and headless regressions |
| [#14](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/14) | `feat/desktop-single-instance-tray` | PR #13 branch | D2 exclusive process lock, repeat-launch IPC, single Qt tray owner and managed API shutdown (Windows acceptance pending) |
| [#15](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/15) | `feat/desktop-settings-navigation` | PR #14 branch | D3 accessible seven-section Settings; reported Windows navigation acceptance recorded 2026-11-18; real in-game OCR remains pending |
| [#16](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/16) | `feat/desktop-overlay-preferences-d4a` | PR #15 branch | D4a versioned anchor/offset/opacity/scale preferences with validation, v0 migration and FastAPI persistence |
| [#17](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/17) | `feat/desktop-overlay-preview-apply-d4b` | PR #16 branch | D4b Settings appearance controls, labelled simulated preview, Qt geometry/opacity/zoom apply and headless tests; Windows GUI acceptance pending |

**Active working head: `feat/desktop-overlay-preview-apply-d4b` (draft PR #17)**, based on D4a draft PR #16 (`feat/desktop-overlay-preferences-d4a`). Earlier drafts remain stacked; no merge into `main`.

## New functional audit gate — user playtest (2026-11-18)

- **User decision:** D4b **implementation** and the 6/6 Settings acceptance are sufficient to stop this development phase. Before further interface work, request an actual **Claude review of source code and gameplay functionality**, not just aesthetics. Keep D4b's full Windows QA matrix and P0 gameplay defect tasks unchecked; passing Settings is not gameplay acceptance.
- Playtest screenshots captured real regressions: **F-AUD-01** intermittent custom-match `Waiting for game`; **F-AUD-02** wrong augment triple (Impassable / Upgrade Stormsurge / Tooth Fairy on screen versus escAPAde / Restart / Mercy in overlay); **F-AUD-03** one-card reroll needing Alt+O + Scan Screen; **F-AUD-04** repeated 2.1/10 and misleading reroll; **F-AUD-05** Neeko/time/gold persist after match exit; **F-AUD-06** stale/out-of-order offer risks. **F-AUD-07** requests future score badges on the actual game cards, **only after OCR/score mapping passes**.
- Canonical audit handoff: [`docs/FUNCTIONAL_AUDIT_HANDOFF_2026-11-18.md`](FUNCTIONAL_AUDIT_HANDOFF_2026-11-18.md), with P0/P1 table, source review, tests needed, acceptance gates and copy/paste Claude prompt. The screenshots exist in ChatGPT Overlay LoL; Claude needs user-provided copies, never claim they were copied into the repository.
- Source review indicates a global OCR fuzzy matcher that lacks card-position alignment, full-crop threshold-based reroll polling, a zero-contribution heuristic that yields 2.1 and a frontend postgame path that retains HUD values. These are **investigation leads**, not user-verified fixes. No Claude audit has occurred.
- An **unverified preliminary** `fix/postgame-stale-match-state` branch was created off D4b with frontend/backend edits and one test; it is **not merged, CI-verified or user-accepted**. Canonical development/audit branch remains `feat/desktop-overlay-preview-apply-d4b`; `main` unchanged. **Do not resume that partial fix without a deliberate post-audit decision.**
- **Next action: A-FUNC Claude functional/code audit and triage.** D5a is the next bounded implementation phase **after audit intake/roadmap**, not started. Planned D5c **design-only UX audit** remains a separate gate after D5a/b.

## Approved interface-design checkpoint — D5c (planned, 2026-11-18)

- The user requested a **Claude-led UX/UI audit after D3 Settings navigation, D4a/D4b overlay preferences/preview, and D5a/D5b OCR/onboarding**, before starting D6. This adds **D5c — Claude UX/UI audit and desktop design closure**; it does not replace existing D6–D11 phases.
- **D5c scope:** audit the real Windows desktop Settings interface, navigation, hierarchy, consistency, accessibility, saved/error/loading states, preview and OCR setup. Persist an actual evidence-backed Claude report with P0/P1/P2 findings, apply bounded priority design fixes, add UI regressions and verify on Windows. A report has **not** been produced and none of D5c's new tasks are completed.
- **Out of scope:** claiming real augment or shop in-game panels are validated (D7/D8), rewriting OCR/scoring, duplicating the engine, or using protected competitor UI/assets. Maintain Riot/privacy safeguards. See `PH-D5c.1`–`PH-D5c.3` and `UX-D11` in `docs/TODO.md`, and gates in `docs/IMPLEMENTATION_PHASES.md`.
- Existing order continues: **D3 -> D4a -> D4b -> D5a -> D5b -> D5c -> D6 context -> D7 augment -> D8 shop -> D9 Windows package -> D10 installer -> D11 release quality**. Each phase remains a small stacked draft PR when executed; `main` stays untouched.

## Current work: PR #17 — D4b desktop preview and Qt apply (2026-11-18)

- [Draft PR #17](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/17) targets `feat/desktop-overlay-preferences-d4a` (draft PR #16), not `main`. D4a final [Windows Actions 44356926105](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44356926105) passed at `0bc9535a`: 292 Python and 13 JavaScript tests, with syntax checks.
- The desktop Overlay section now offers four anchors, signed integer offsets, opacity and scale. It consumes the existing D4a `frontend/overlay-preferences.js` validation/migration helper, GET/PUT v1 preferences routes and persisted JSON; the preview is explicitly simulated and updates from unsaved drafts, while the real Qt window changes only after saving.
- `backend.overlay.layout.calculate_overlay_geometry` is pure/testable, clamps size/coordinates to the selected monitor's available logical Qt geometry, including negative desktop origins. The existing transparent Qt window loads saved values, checks the atomic preferences file every 800 ms, applies Qt WebEngine zoom and window opacity, and reacts to display geometry, DPI, screen changes and resizing. Existing Win32 click-through/Alt+O and Alt+H paths remain; no OCR/scoring, packaging or API service work.
- Headless Python geometry/Qt contract tests and JavaScript form, validation, save/retry and simulated-preview tests added. **D4b verified code-head Windows Actions [44361461870](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44361461870) at `9520057c`: 303 Python passed (1 warning), 18 Node passed; JavaScript syntax checks succeeded.** Earlier failures for tiny-screen height and JS test regular expressions were corrected. Recheck any newer documentation-head CI. Real 1080p/1440p/100%/125%/150%, multi-monitor, no-white-background, Alt+Tab and League borderless tests have **not** been observed; keep `PH-D4b.2` and `UX-D09` open.
- **D4b Windows Settings partial acceptance (2026-11-18, user-reported 6/6):** User confirmed the Overlay Settings controls, all four anchor positions, opacity 60%/100%, scale 75%/100%/150%, explicitly simulated preview responsiveness and persistence across app restart. This validates Settings/preview only. The actual Qt overlay applying those values, transparency/click-through, Alt+O/Alt+H, Alt+Tab, League borderless and DPI/monitor matrix were **not** reported in this test. Retain `PH-D4b.2` and `UX-D09` as open.
- Next phase after CI and on-device review: **D5a OCR executable/path readiness guidance**, not live three-card recognition (D5b) or D6 context management. D5c Claude UI audit remains after D5b, before D6.

## Previous work: PR #16 — D4a overlay preferences model/API (2026-11-18)

- [Draft PR #16](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/16) targets `feat/desktop-settings-navigation` (draft PR #15). D3 Windows Settings acceptance was later **reported by the user** and recorded on the D3 base; D4a preserves that newer documentation. `main` is unchanged.
- Existing `backend.preferences` now persists **schema v1** (`schema_version`, `build_style`, `overlay`), with anchor `top_left/top_right/bottom_left/bottom_right`, integer offsets from -500 to 500, opacity 0.40–1.0, scale 0.75–1.50, default top-right/24px/24px/0.92/1.0. Invalid disk values fall back independently; legacy `{ "build_style": "..." }` files migrate on the next write; future unknown versions are not overwritten. Writes remain atomic. No match state is stored.
- The **same FastAPI server** exposes these settings in `GET /api/preferences` and provides strict full-object `PUT /api/preferences/overlay`, with 422 for unsafe writes, 409 for unknown persisted schema and 500 for disk failures. Existing build-style-only `PUT /api/preferences` and WebSocket updates remain compatible; independent style writes retain saved overlay choices. The server loads both settings at startup; game resets do not clear appearance.
- `frontend/overlay-preferences.js` provides data-only client validation/migration for D4b; it is not wired to an in-game panel. D4a deliberately **does not** create a Settings preview, alter Qt geometry/opacity/scale, transparency, click-through, Alt+O/Alt+H, tray or single-instance behavior, change OCR/scoring, or add a service.
- **Verified Windows code-head Actions:** [run 44355601388](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44355601388) at `8ef17b81`: **292 Python passed, 1 warning; 13 Node tests passed**; original JS syntax checks passed. A follow-up commit also checks the new JavaScript helper's syntax; verify final docs/merge head CI independently.
- D3 accepted tasks `PH-D3.3`, `PH-D1.5` and `UX-D02` are based on user confirmation, not independent per-step logs. `UX-D09` multi-resolution/borderless League, three-card augment OCR and reroll detection remain pending. **D4b work now follows separately in draft PR #17**, with distinct real Windows validation remaining.

## Previous work: PR #15 — D3 desktop Settings navigation (2026-11-18)

- Draft [PR #15](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/15) targets `feat/desktop-single-instance-tray` (draft PR #14), preserving the latest D2 documentation commits. `main` is untouched.
- `frontend/settings.html`, `settings.js` and `settings.css` now organize General, Overlay, Build Preferences, OCR, Diagnostics, Feedback and About. Keyboard/ARIA tabs use roving focus with arrows/Home/End; preference read/write and feedback have clear loading/saving/error states and explicit retry when the initial preference load fails.
- Reuses exactly the existing `GET/PUT /api/preferences`, `GET /api/ocr/status` and `POST /api/bug-report` contracts. Diagnostics reflect actual endpoint responses; future appearance controls, diagnostic export and OCR capture/testing are labelled unavailable. Tesseract detection is **not** real three-card or reroll recognition.
- D3 changes no FastAPI, Qt, transparent overlay, tray, single-instance owner, Alt+H/Alt+O, game detection or scoring code. Added Python and JavaScript regression tests.
- **Verified Windows Actions at D3 code head `346998a8`:** [run 44352298709](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44352298709) succeeded — **255 Python passed, 1 warning; 8 Node passed, 0 failed; both JavaScript syntax checks passed.** [Final documentation-head Windows Actions run 44353064467](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44353064467) succeeded at `1748d6e4`; this later acceptance-only documentation commit requires an independent CI check.
- **D3 Windows acceptance reported by user, 2026-11-18:** In the D3 Settings screenshot, the OCR page shows seven-section navigation, a reachable local API and Tesseract detected on Recheck. The user said they had tested everything else in the D3 walkthrough; this is accepted as user-reported keyboard/navigation, focus/resize, preference save/restart, feedback and D2 regression confirmation. `PH-D3.3`, `PH-D1.5`, `UX-D02` are checked based on that report (not independent per-step screenshots). If any individual check was not actually performed, reopen it. **Still pending:** `UX-D09` complete device/game matrix, real League borderless, three visible Mayhem augment names/rerolls and verified shop context. Green Tesseract is dependency availability only.
- **D4a handoff caution:** User reports D4a is underway in another conversation; at this checkpoint no D4a branch or PR is visible on GitHub. That absence does not mean the work is not happening. Do not create a duplicate D4a branch without checking live state first.

## Previous work: PR #14 — D2 single instance and tray lifecycle (2026-11-18)

- Branch `feat/desktop-single-instance-tray`, [draft PR #14](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/14), targeting `feat/desktop-settings-shell` (draft PR #13). The earlier drafts and `main` are not merged.
- New `backend/desktop/instance.py` holds a per-user OS process lock through application lifetime and publishes an authenticated loopback activation channel. Second desktop launches request Settings activation; repeated Qt overlay launches request overlay restoration, without starting a second managed backend or tray. A crashed owner releases the OS lock; stale metadata is replaced on restart. An unresponsive owner is reported, not stolen.
- New `backend/desktop/service.py` owns the existing FastAPI ASGI application in a stoppable uvicorn thread, or reuses a compatible already-running API without terminating that external owner; unknown port 8765 services are rejected.
- `backend/desktop/window.py` hosts a single QApplication, one system tray, independent normal Settings and transparent overlay Qt surfaces, explicit hide/restore and Quit. The original Qt overlay keeps the same Win32 transparency/hotkeys; its optional internal tray is disabled in managed mode. `python -m backend.overlay --renderer qt` and auto mode with Qt available delegate to the unified lifecycle. The explicit non-Qt webview renderer remains a legacy developer fallback outside this single-tray Qt path.
- Headless regressions added in `tests/test_desktop_lifecycle.py`; legacy launcher assertions updated. JavaScript and preference/feedback implementations are unchanged. D2 does not claim real OCR 3-card/reroll detection, verified shop state, or compliance clearance.
- **Verified Windows GitHub Actions:** [run 44345555542](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44345555542) at reviewed merge head `0b4a563b`: **253 Python tests passed, 1 warning; 4 Node Settings tests passed; both JavaScript syntax checks passed**. Windows native GUI acceptance for the D2 lifecycle is now **confirmed** by the user (see observations below). `PH-D2.3` and `UX-D04` are checked; `PH-D1.5`, `UX-D09` and actual in-game/OCR behavior remain unverified. The previous documentation-only commit `be878f1d` passed Windows GitHub Actions [run 44349582275](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44349582275); check any newer documentation-head run separately.
- **Windows D2 user observation (accepted for lifecycle/tray, 2026-11-18):** User checked out `feat/desktop-single-instance-tray` and confirmed native Settings launches, closing it hides to the Windows notification area (`^` menu), and right-click tray actions Open Settings, Show/Hide Overlay and Quit all work. Separate commands showed repeat `python -m backend.desktop` activated the existing instance and a foreign local `http.server` on port 8765 was safely rejected when attempting `python -m backend.overlay --renderer qt`. Follow-up screenshot from D2 showed `Qt overlay hidden (Alt+H or tray to restore)`, `Qt click-through OFF` after Alt+O, and `Qt overlay shown`; user exited the application via Quit and `Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue` returned no listeners. These observations support **PH-D2.3 and UX-D04 passing**; no listening server does not independently prove every child process/thread is absent. The initial `KeyboardInterrupt` reflected manually stopping a process, not a tray regression. **Still open:** `PH-D1.5` focus/resize, saved preferences across restart and feedback, `UX-D09` multi-resolution/match smoke tests, real LoL transparency and 3-card/reroll OCR.
- **Next independent phase: D3 Settings navigation**, on a new branch and draft PR stacked on [PR #14](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/14), no merges to `main`.
- No third-party external companion source was imported. `docs/REUSE_CANDIDATES.md` remains the license register. Next phase after this D2 gate is **D3 Settings navigation**, not installation or in-game OCR feature development.

## Current work: PR #13 — D1 native desktop Settings shell (2026-11-18)

- Branch `feat/desktop-settings-shell`, draft [PR #13](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/13), based on `feat/pregame-settings-feedback` (draft PR #12); `main` unchanged.
- New `backend/desktop/{__main__,runtime,window}.py` opens a **standard, resizable, focusable** `QMainWindow` / `QWebEngineView` hosting the unchanged `http://127.0.0.1:8765/settings` page. No overlay transparency/topmost/click-through flags are applied.
- `python -m backend.desktop` checks for Qt before starting a server, recognizes a compatible running local ARAM Oracle API, otherwise starts the **same** FastAPI startup path as the overlay, and refuses unexpected services already bound to 127.0.0.1:8765. Readiness, missing PyQt6, startup errors, and page load failure are surfaced. This does not yet provide unified process/tray ownership (D2).
- The existing `frontend/settings.{html,js,css}`, `GET/PUT /api/preferences`, feedback endpoint, disk persistence and WebSocket synchronization are reused without new business logic.
- The existing `backend/overlay` files remain unchanged, including explicit `--renderer qt`, transparency, Alt+O/Alt+H, click-through, and legacy tray/browser Settings fallback.
- **Verified Windows Actions:** [run 44336280007](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44336280007) at D1 code+README head `d5aff632`: **234 Python passed, 1 warning**, 4 Node Settings tests passed, both JS syntax checks passed. Nineteen new Python tests cover startup/readiness, conflict and native host/overlay contracts. Subsequent documentation-only commits require checking the latest Actions result separately.
- **Windows manual acceptance remains open:** native window focus/resize, style preference save/restart, feedback report and pre-existing transparent in-game overlay/keyboard shortcuts. D2 will unify single-instance and tray ownership; an installer/redesign/update service is not in D1.
- External-source register: [`docs/REUSE_CANDIDATES.md`](REUSE_CANDIDATES.md). Permissively licensed companion projects are candidates for targeted future adaptation with exact license/attribution verification; D1 imports **no** external overlay code.

## Latest Windows evidence and next-chat decisions (2026-11-18)

- User's PowerShell confirms checkout `feat/desktop-settings-shell` in `D:\\Overlay ARAM\\aram-oracle`, and successful `python -m backend.desktop`: the existing FastAPI server started, native Settings window opened at `http://127.0.0.1:8765/settings`, and the page loaded. Screenshot shows the normal Windows title bar, Settings sections and current `Balanced` preference loaded.
- The user confirmed **transparent Qt overlay, Alt+O click-through toggling and Alt+H hide/restore** on their Windows machine; the terminal output includes repeated toggle/hide/show logs. The final `KeyboardInterrupt` came from stopping the Python process, not a proven application crash. The Qt DPI-awareness warning was nonfatal in the observed session.
- **Tesseract readiness fixed on-device:** Initially the Settings page showed `OCR unavailable` and `Test-Path "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"` was `False`. The user installed `UB-Mannheim.TesseractOCR` via winget and then explicitly reported the OCR status became green. This confirms the Settings availability check is now positive, **not** that three ARAM Mayhem cards or rerolls were detected in-game. Keep OCR capture/region, name matching and reroll tests open.
- **D1 Windows acceptance is partial:** user has not explicitly verified native window resize/focus, a changed build-style save persisting after restart, or feedback report creation. Keep `PH-D1.5` unchecked and request only these checks if still relevant. In-game OCR validation should be done without abandoning a matchmaking game; if available, use a permitted custom/test mode, otherwise capture naturally during a normally completed game. Never assume bot custom games support this mode.
- **Cross-chat workflow decision:** one development phase per ChatGPT conversation, one stacked draft branch and one PR; GitHub documents are the canonical shared project state. Open a new chat for **D2 single-instance/API/tray lifecycle** based on draft PR #13, after reading `.agents/skills/continue-aram-oracle/SKILL.md` and the current docs. Reuse permitted external code only with verified licensing and attribution; see `docs/REUSE_CANDIDATES.md`.
- **Last verified CI at the previous documentation head:** [Windows Actions run 44337928614](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44337928614) succeeded on `52a96563`: **234 Python passed, 1 warning; 4 Node tests passed** and JS checks passed. New documentation commits in this handoff require their own CI check; don't claim newer green results without checking.

## Current work: PR #6 — team and enemy observation coverage

- Branch `feat/team-threat-coverage`, stacked on PR #5 `feat/dynamic-team-threats`; `main` is unchanged.
- The current champion now counts in allied role coverage (exactly once), so allied deficits include the player's own capabilities.
- Enemy inventories are examined even when an enemy champion is not present in the catalog. `visible_items` now means the observed item count; `unknown_items` indicates IDs lacking our item metadata.
- High threat confidence requires all visible enemy champions to be recognized and every observed item to resolve, as well as minimum roster/item coverage.
- New deterministic tests cover partial catalog coverage, item observation without a known champion, and including the player in allied roles.
- Validation: CI regression run `44314745431` failed (154 passed/1 failed); fixed in `9954041`. Latest PR #6 Windows run `44315513781` **passed: 155 tests, 1 warning, JavaScript syntax check passed**. Real in-game sample still outstanding.
- Remaining risks: DataDragon tags may not correspond to verified item stats; role vectors approximate threat types; actual LCDA roster must be checked on Windows.

## Current work: PR #7 — selectable build paths

- Branch `feat/selectable-build-paths` stacked on PR #6. The previous PRs remain drafts; `main` is untouched.
- The player can select Balanced, Damage, Survival or Utility using the overlay. The selected style is sent over the local WebSocket, applies to later live pipeline snapshots, and is saved in frontend local storage across restarts.
- The selected path now drives `full_build` and its affordable `next_item_id`, while all paths remain visible for comparison. A full inventory does not produce a seventh item suggestion. Unknown style values fall back to Balanced.
- Item catalog restrictions, actual purchase path/component costs, mode-specific inventory rules and real in-game persistence still need verification. This does **not** auto-buy items.
- Tests: Windows run `44315895591` on PR #7 **passed: 163 tests, 1 warning, JS syntax passed**. Includes the passing PR #6 fix. Real Windows in-game testing is still pending.
- Next P0: strengthen verified item availability, enemy item-stat provenance and patch-aware metadata; validate Windows LCDA and OCR.

## Current work: PR #8 — late-game boot replacement

- Branch `feat/late-game-boots-replacement` (stacked on PR #7). A full 6-slot build can now show an **optional boot replacement**, as an explicit sell-then-buy alternative; ordinary `next_item_id` still remains empty to avoid recommending an impossible seventh item.
- The candidate must be a non-boots catalog item with **listed unconditional movement speed** and a meaningful contextual-stat improvement after a mobility trade-off penalty. Rank by selected build style, champion, active augments and visible team threats; deterministic tie-breaking.
- DataDragon item loader now collects structured flat/percent movement speed and unconditional movement stats from the `<stats>` description section, never conditional passive text. Cache schema v2 prevents silently treating stale items as fully known; legacy cached items can still support regular builds offline with boot swaps disabled.
- The recommendation appears in the English build panel with item names, purchase cost (excluding uncertain sell value), approximate listed movement-speed change and a shop-availability disclaimer. No buying or selling is automated.
- Missing/conditional movement effects, mode shop eligibility, unique passives, full actual movespeed/soft cap and item buy path **remain unverified**. The comparison is **heuristic** and needs real Windows/Mayhem validation.
- Tests: [Windows GitHub Actions run 44318127647](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44318127647) **passed: 171 tests, 1 warning**, plus successful `node --check frontend/app.js`. Real Mayhem shop/Windows in-game verification remains pending.

## Current work: PR #9 — Windows overlay transparency diagnosis/fallback

- User screenshot (2026-11-18) shows `163 passed, 2 warnings` on Windows, normal `Waiting for game...` when no match, but a large unwanted white area. Log also reports `Could not find overlay HWND — click-through not set`; these are two distinct desktop-window concerns.
- Current on-device checkout appears to be PR #7 (`163` tests), not the latest PR #8 (`171` tests on GitHub Actions). Screenshots are **not** in-game tests.
- pywebview/Edge WebView2 transparency on Windows is known to be inconsistent. `backend/overlay/__main__.py` now accepts `--renderer qt` and `--renderer webview`; default remains pywebview for compatibility. Qt is an **opt-in fallback**, not a proven fix on the user's machine.
- `backend/overlay/webview_window.py` now prefers `_window.native.Handle` for the Win32 HWND and retries when the window has just opened; exact-title `FindWindowW` is fallback only.
- `backend/overlay/window.py` now supports an Alt+O click-through toggle using a Qt timer that observes the global key chord, maintaining access to build style and other UI controls when Qt is used.
- Added `tests/test_overlay_renderer.py` and a Windows troubleshooting section in README. [Windows CI 44319789943](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44319789943) **passed: 178 tests, 1 warning; JavaScript syntax passed**. On-device Qt/WebView2 comparison **not yet run**.
- **User Windows desktop validation confirmed on 2026-11-18:** the user ran `python -m backend.overlay --renderer qt`; the screenshot shows fully transparent unused window regions with legible panels, and terminal logs `Using PyQt6 transparent overlay`, `Overlay window started` and `Click-through enabled (HWND=...)`. Their local pytest run reported **178 passed, 2 warnings**. This resolves the reported white-background symptom **on that desktop**. The actual in-game render, Alt+O interactivity and LCDA/OCR remain unverified. The default `auto` renderer still chooses pywebview; Qt must be requested explicitly.

## Current work: PR #10 — Qt overlay window visibility controls

- User identified the next UI blocker: the frameless Qt overlay had **no built-in button to hide or quit**, and no direct recovery route after hiding. The existing Alt+O shortcut only toggled click-through.
- Branch `feat/qt-overlay-window-controls`, stacked on the tested transparency PR #9; `main` remains untouched.
- The Qt-only header now has small **− Hide** and **× Quit** buttons (requires Alt+O to make the overlay clickable). These buttons issue local same-page URL-fragment actions, interpreted only by the Qt window on `localhost:8765/overlay?mode=overlay`; remote origins and malformed actions do not control the native window.
- **Alt+H** globally toggles visibility even while hidden. A Windows notification-area tray icon provides Show/Hide, Toggle interaction, and Quit; a double-click also toggles visibility. When the tray is unavailable, Alt+H still works. Hiding preserves the Python process; quitting exits the app.
- Added local-action parser tests, native UI presence guards and explicit README instructions.
- **Validated CI:** [Windows Actions run 44322346286](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44322346286) at feature commit `5c0d82ed`: **191 passed, 1 warning; JavaScript syntax check passed**. Real Windows Qt button/hotkey/tray behavior still requires user validation.
- Next user verification: `python -m backend.overlay --renderer qt`, Alt+O then click − and restore with Alt+H, finally test × and tray restore.

## Current work: PR #11 — first in-game Mayhem findings

- User's first live in-game screenshot on Windows shows a level-4 Jinx with **Blunt Force, Erosion and Homeguard** on screen, while the overlay shows **NO OCR** and no offers scored. Champion, gold and all five opponents are recognized; build incorrectly lists **Poro-Snax as one of six owned items** and **Phantom Dancer twice**. Enemy threat panel reports seven items missing from the scored catalog. This screenshot is evidence of these visible symptoms, not of actual OCR output.
- **Root causes in source:** Tesseract unavailable to the Python process; overlay mode permanently hid manual input; UI used `phase.startsWith("aug_pick")` despite live messages being `in_game`; backend opened OCR scan only on respawn, missing newly eligible level snapshots; inventory parser counted trinket slot 6 as a build item; planner deduplicated catalog item IDs, not equivalent names.
- Branch `fix/live-augment-detection-item-duplicates` stacked on PR #10. No merge to `main`.
- `backend/collectors/lcda.py` now counts only main item slots 0–5, excluding Poro-Snax 2052 as a fallback even if slot missing. The same rule removes non-equipment trinkets from observed enemy inventory counts, reducing noisy "unknown items" without fabricating stats.
- `backend/engine/build_suggester.py` deduplicates candidate names (casefold + whitespace normalization) across items already owned, planned paths and proposed boot swaps. This avoids listing two different mode-specific catalog IDs with the same name as separate items.
- `backend/api/server.py` starts OCR scans when an augment becomes due at a newly observed 3/7/11/15 level, including the first in-game snapshot, or on respawn with outstanding offers; avoids repeatedly reopening the same-level scan. Reset clears manual augment state without requiring previous OCR detection.
- `frontend/app.js` leaves **DETECT AUGMENTS** accessible in overlay mode, opens manual input when a pick is due and OCR is unavailable, does not falsely report SCANNING without OCR. `frontend/index.html` shows install/manual instructions; README provides the Tesseract command and fallback steps.
- `tests/test_live_mayhem_regressions.py` covers duplicate names, owned aliases, active and enemy trinket filtering, scan triggers, hidden fallback and per-game reset. **Verified Windows Actions run `44325282457`: 200 passed, 1 warning; JavaScript syntax check passed**, at feature+documentation head `df2cf1ba`. Actual in-game OCR recognition and shop eligibility still require user verification.
- **Immediate user dependency:** install Windows Tesseract OCR (Python `pytesseract` alone is insufficient), restart Qt overlay, and test. Manual three-choice search works without Tesseract. Avoid inferring augment effectiveness from the screenshot alone.

## Current work: PR #12 — out-of-game Settings (in progress)

- Branch `feat/pregame-settings-feedback` is stacked directly on `fix/live-augment-detection-item-duplicates` (PR #11). Neither branch nor any earlier draft PR has been merged to `main`.
- Local `/settings` serves a full-page Preferences and Feedback & diagnostics UI. The chosen Balanced/Damage/Survival/Utility style is stored atomically under `~/.aram-oracle/preferences.json` and loaded on API startup. `GET/PUT /api/preferences` validate it, broadcast `preferences_updated`, and the game poll applies it to the next build pipeline snapshot. The in-game panel remains a read-only style label.
- The Qt system tray now includes **Open Settings**, launching `http://127.0.0.1:8765/settings` in the default browser; `Alt+O`, `Alt+H`, Qt window transparency, and click-through implementation were not changed. The local page can also be opened directly before a match while the server is running.
- Removed obsolete in-game feedback submission handlers/button. The post-game overlay is now guidance to Settings; manual augment fallback is unaffected.
- Fixed a real persistence defect: the user's feedback description was included in optional GitHub issue text but not the locally saved JSON. The report now includes `user_description`. Submission returns explicit HTTP 429 cooldown / 500 local-write errors, and failed writes do not consume the cooldown. Settings keeps entered feedback on error.
- Added Python tests covering disk roundtrips, safe defaults, REST preference updates, live poll selection, feedback JSON/error handling and Qt/tray markup. Added Node DOM-stub interaction tests, `node --check frontend/settings.js`, and Node tests to Windows Actions. README updated.
- **Verified PR #12 Windows Actions run [44331056654](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44331056654)** at feature head `d8dd7c5`: **215 passed, 1 warning**, `node --check frontend/app.js` and `node --check frontend/settings.js` passed, and **4 Node Settings UI tests passed**. Earlier run `44330933993` failed one newly introduced test due to an incomplete mock snapshot; fixed before the successful run. The later documentation-only head requires separate Actions verification. Actual browser/tray use, persistence after restart, live build recalculation and OCR still require Windows on-device validation.

## Automated verification (as last observed)

- PR #12 Windows CI run [44331056654](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44331056654) on feature head `d8dd7c5`: **215 passed, 1 warning**; `node --check` passed for both frontend JS entrypoints; **4 Node Settings interaction tests passed**. Subsequent documentation-only head not yet rechecked.

- PR #11 Windows CI `44325282457` on commit `df2cf1ba`: **200 passed, 1 warning**, `node --check frontend/app.js` passed. Later documentation commits require separate CI validation.

- PR #10 Windows CI `44322346286` on feature commit `5c0d82ed`: **191 passed, 1 warning**, JavaScript syntax check passed. Later documentation-only commits need separate CI confirmation.

- PR #9 latest completed Windows GitHub Actions run `44320104470` on documentation-only head `388fe862`: **success**. The user also ran **178 passed, 2 warnings** locally with the Qt renderer. The warning count differs between environments.

- PR #9 Windows CI `44319789943` at `e93aad6b`: **178 passed, 1 warning**, JavaScript syntax check passed. On-device Qt render remains unconfirmed; later documentation commits need own CI recheck.

- PR #8 Windows CI `44318127647` on feature commit `280e7659`: **171 passed, 1 warning**, JavaScript syntax check passed. Newer documentation commits require separate CI recheck.

- PR #6 latest Windows CI `44315513781`: **155 passed, 1 warning**; JS syntax passed.
- PR #7 Windows CI `44315895591` on feature commit `c4f8ba25`: **163 passed, 1 warning**; JS syntax passed. Documentation-only commits may be newer; verify head.

- Previous user-run suite on the Champion Select branch: **114 passed**.
- PR #3: **138 passed** on GitHub Actions Windows (one earlier transient failure was a badly specified assertion, fixed).
- PR #4: **145 passed**, 1 warning, on GitHub Actions Windows.
- PR #5: Windows Actions run **44312454589 passed** for commit `dc96f3647cbd85e471ef4dd1090a788f415c84cf` (before adding `tests/test_dynamic_team_pipeline.py`).
- **Verified:** PR #5 commit `8c8109838c9de03076078a90a480462427accbce` passed GitHub Actions Windows run **44312737054** with **153 passed, 1 warning**, including `node --check frontend/app.js`.
- Workflow `.github/workflows/python-tests.yml`: Windows `pytest -q` and `node --check frontend/app.js`.
- Documentation-only commits subsequently created `docs/PROJECT_STATE.md`, `docs/DEVELOPMENT_LOG.md` and root `AGENTS.md`; their own later CI runs may still be running when this snapshot is read. Check the newest branch head before claiming its CI status.
- No real-match end-to-end validation of PR #5 has been observed. Only previous screenshots showed the desktop overlay opening; aesthetics remain secondary.

## Architecture and key files

- `backend/collectors/lcu.py`: local LCU read-only champion select, custom-install lockfile discovery.
- `backend/collectors/lcda.py`: active-player/allPlayers snapshot via local LCDA, including *visible* enemy items and scores.
- `backend/collectors/screen_ocr.py`: Tesseract-based augment detection with wrapped-name matching.
- `backend/models.py`: champion/augment/item/game data models, `EnemyState`, `BuildState`, `PipelineResult`.
- `backend/engine/composite_score.py`: confidence-shrunk composition of empirical success evidence, kit synergy and context; provenance.
- `backend/engine/champion_select.py`: preliminary 0–10 champion composite model and allied role fit.
- `backend/engine/augment_rating.py`, `backend/engine/ranker.py`: bounded augment ratings, prior picks, enemies; experimental personal history component disabled by default.
- `backend/engine/team_context.py`: new *original* ally/enemy threat profile derived from observable data; estimates are **not measured damage percentages**.
- `backend/engine/build_suggester.py`: baseline item ratings and alternative paths based on active augments, enemy threats and owned items.
- `backend/workflow/pipeline.py`: single orchestration path for augments and builds using shared profiles.
- `backend/storage/db.py`, `backend/storage/history_import.py`: local SQLite and explicit opt-in import of up to 40 own recent Mayhem games.
- `backend/api/server.py`: FastAPI/WebSocket serialization, local status and history endpoints.
- `frontend/index.html`, `frontend/app.js`: minimal English overlay, contextual enemies, build paths, scores.
- `tests/`: mock/simulation regressions; add targeted tests for every new rule.
- `AGENTS.md`, `docs/PROJECT_STATE.md`, `docs/DEVELOPMENT_LOG.md`: mandatory future-session read/update protocol and persistent handoff.

## Source licensing / Riot safety

- ARAM Oracle original MIT licensing applies to its licensed code.
- `zp96-cmd/mayhem-overlay` declares MIT in `package.json`; **adapted** client-lockfile discovery and multiline OCR concepts. Preserve attribution in `THIRD_PARTY_NOTICES.md`; verify exact terms before expanding reuse.
- `ItzStorDz/mayhem-advisor` is **ALL RIGHTS RESERVED**, not open-source under a reuse license. No copying/translating its code, UI, assets or implementation without prior written permission. Its *publicly described capabilities* can inform independent implementation. If actual reuse is desired, obtain explicit written permission.
- `valkia/aramgg_client`: no overall reuse license confirmed. Reference only.
- Third-party datasets (e.g. AramHex CC BY-NC 4.0) have **separate licenses**; do not import without validating provenance and permitted use.
- User reports separately researching Riot's third-party policy. Avoid definitive claims that converting augment win rates into a 0–10 number makes live recommendations permissible. **Do not expose raw augment win rates**; keep empirically derived augment scoring behind `experimental_augment_evidence=False` until resolved. Use player-visible permitted interfaces; no hidden information, memory injection, or automatic augment/item selection.

## Approved desktop application architecture and delivery phases

- **Approved architectural direction:** Python/FastAPI remains the sole engine, with a normal PyQt6 desktop Settings window and a separate transparent, click-through Qt game overlay; both communicate through the existing local HTTP/WebSocket API.
- Full component boundaries, state-driven presentation, lifecycle, preference/diagnostics handling and future packaging decisions: [`docs/DESKTOP_ARCHITECTURE.md`](DESKTOP_ARCHITECTURE.md).
- Small, gated implementation plan and acceptance tests: [`docs/IMPLEMENTATION_PHASES.md`](IMPLEMENTATION_PHASES.md); task checkboxes `PH-G0.*` and `PH-D1.*` through `PH-D11.*` in [`docs/TODO.md`](TODO.md).
- Implemented code/CI phase: **D1 — native desktop Settings shell** (`backend/desktop`, `python -m backend.desktop`, existing `/settings` UI, tests; **no installer yet**). Implemented in draft PR #13 based on PR #12; no merge to main.
- Next planned development slice: **D2 — single-instance and tray lifecycle**, after Windows D1 smoke tests.
- Chat-to-chat reusable repository workflow: [`.agents/skills/continue-aram-oracle/SKILL.md`](../.agents/skills/continue-aram-oracle/SKILL.md) and [`docs/CONTINUE_PROJECT.md`](CONTINUE_PROJECT.md). The repository skill is not automatically installed in ChatGPT; future chats must fetch it via GitHub.
- **Overlay implementation remains unchanged:** D1 adds a separate native Settings host while preserving the existing Qt overlay renderer, Alt+H/Alt+O and legacy browser Settings fallback.

## Desktop packaging direction (planned, not implemented)

- The user wants an intuitive Windows installer, a full desktop Settings/control app and a contextual in-game overlay similar in usability (not appearance/assets) to OP.GG.
- Proposed architecture: reuse the existing Python/FastAPI engine and PyQt6 renderer, add a separate conventional Qt desktop window for Settings and diagnostics, and retain the verified transparent click-through Qt overlay. Do not duplicate the backend.
- First validate PR #12 Settings and the P0 OCR/gameplay behavior. Then build the native desktop experience; package a Windows installer only after reliable lifecycle and on-device checks.
- Tracked as **UX-D01–UX-D10** in [`docs/TODO.md`](TODO.md). These items are proposals, all open, and not proof of an existing installer.

## Canonical product / UX backlog

- [`docs/TODO.md`](TODO.md) contains the persistent, prioritized checklist derived from the **Auditoria UX — ARAM Oracle** discussion plus the current product specification, real match findings and code audit.
- **Decision:** the target is an event-driven, unobtrusive companion, not a permanent dashboard. Primary states: augment offer (highest priority), verified shop, optional scoreboard; stay quiet in combat. Never claim unknown shop/scoreboard state is observable.
- Completed **implementation** tasks are explicitly separated from pending **real Windows/League validation**. Each future meaningful feature must update the checklist and include evidence before checking a task off.
- UX audit created in the existing draft PR #12 branch; no merge to `main`.

## Highest-priority remaining work

1. **PR #13 D1 automated code validation passed (234 Python + 4 Node at `d5aff632`).** Verify latest docs-head Actions and test the new native Settings window, preference persistence and local feedback on Windows; then revalidate PR #11 OCR/build regressions in a match. Install/locate Tesseract and recheck offered augments including manual fallback, Poro-Snax and duplicate-name item behavior.
2. Review and test enemy/ally parsing against actual LCDA samples on Windows; no unsupported invisible opponent detection.
3. Validate Mayhem item availability, inventory limits, components, multi-boot/exclusive rules, quest rewards, and shop buyability. Current item matching is **heuristic**, not purchase-path validated.
4. Improve threat accuracy: champion damage-source metadata vs generic AP/AD vector; enemy resistance items must be recognized from verified item properties, not merely unverified tags. Expose low-confidence cases.
5. Improve synergy model for augment-specific effects, quests, abilities, duplicate/redundant interactions and chosen augment history; calibrate against real matches.
6. Validate the new selectable build-style preference in the actual Windows overlay and confirm the selected path updates after purchases and augment picks.
7. Patch/version-aware data ingestion and confidence; ensure only ARAM Mayhem games are counted (verify actual queue/mode identifiers).
8. Test champion select, augment OCR, build updates, click-through and resize live on user's Windows; keep interface polishing last.

## Cross-chat session triggers (documented, not native commands)

- `ARAM Oracle: preparar passagem` — in the current conversation, update
  and verify GitHub state/TODO/log, CI and unresolved acceptance checks, then
  return the exact prompt for a new chat. An unfinished phase rotates on its
  existing branch and PR.
- `ARAM Oracle: continuar` — in a freshly opened ChatGPT Overlay LoL project
  conversation, load `.agents/skills/continue-aram-oracle/SKILL.md` and
  `docs/CONTINUE_PROJECT.md` from GitHub, verify live branch and CI, and
  resume the in-progress/next phase.
- The phrases are a documented convention, **not** registered ChatGPT
  commands or automatic creation of new chats. The user opens the next chat.
  One new stacked branch and draft PR per new phase; no merge to `main`
  without explicit approval.

## How to work in a new chat

1. Read **this file** and `docs/DEVELOPMENT_LOG.md` from the connected private GitHub repository.
2. Check PR #13 head, its PR #12 / #11 stacked dependencies and GitHub Actions live; inspect source code before assuming this snapshot is perfectly current.
3. Continue from PR #13 through the GitHub connector in a new stacked feature branch / draft PR for D2 after Windows smoke tests; do not directly edit the user's Windows `D:` path unless confirmed access exists.
4. Write English code, English UI and English documentation; answer the user in PT-PT.
5. After a completed task, update this current-state snapshot and append a dated, verifiable entry to the development log. Record tests as `passed`, `failed`, or `not run`, never inferred.
6. Request Windows in-game testing only when needed; provide exact PowerShell commands to fetch/checkout the branch and run tests/overlay.
