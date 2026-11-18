# Overlay LoL — Development Log

Append-only timeline. Entries are factual snapshots, not future promises. For the latest task plan, read [`PROJECT_STATE.md`](PROJECT_STATE.md).

## 2026-11-18 — Project setup and original overlay

- Project goal: League of Legends ARAM Mayhem companion with in-game augment recommendations, Champion Select ranking, prior augment synergies, build adaptation and enemy team context; custom 0.0–10.0 scores, not win-rate display.
- Local Windows clone identified as `D:\Overlay ARAM\aram-oracle`. GitHub private repo created: `francisco-fuzeiro/aram-mayhem-overlay`. This chat connects through GitHub API and cannot directly write to Windows D drive.
- User installed Python dependencies and ran tests on their local machine; earlier iterations showed 108 and then 114 passing tests.
- The desktop overlay launches on Windows. Earlier screenshot showed a rudimentary interface (`Waiting for game...` when no match); the user wants functionality before appearance.

## 2026-11-18 — PR #1: base safety and stability

- Branch `fix/overlay-backend-stability`, based on `main`.
- Avoided a nested asyncio lock during WebSocket broadcasts; bound desktop server to loopback; ensured SQLite database is initialized through application startup.
- Added regression tests and created draft PR #1. Local user test passed; do not assume this is merged.

## 2026-11-18 — PR #2: Champion Select

- Branch `feat/champion-select-companion`, based on PR #1 branch.
- Added read-only League Client API champion-select snapshot, numeric champion ID mapping, own champion/bench options and initial role-fit heuristic panel.
- Created local diagnostic endpoint `/api/champ-select/status`; added tests. User ran 114 tests successfully and launched the app. Actual champion selection behavior still requires observed in-game validation.

## 2026-11-18 — PR #3: permitted reuse and own-match evidence

- Branch `feat/reuse-mayhem-core`, based on PR #2 branch.
- Adapted portions of MIT-declared Mayhem Overlay (lockfile discovery, multiline OCR matching); documented attribution in `THIRD_PARTY_NOTICES.md`.
- Implemented composite champion rating 0.0–10.0: kit synergy and team context with sample-confident optional personal performance, using local history records.
- Added optional local ARAM Mayhem match-history importer, user-triggered sync button, idempotent game recording, tests and a Windows CI workflow.
- Initial CI failed 1 assertion because composite score happened to equal a transformed win rate; changed the test to verify that context changes the output when empirical evidence is constant.
- **Verified latest PR #3 CI: 138 passed** on Windows GitHub Actions.

## 2026-11-18 — PR #4: augment score normalization

- Branch `feat/augment-composite-rating`, based on PR #3 branch.
- Added absolute augment scoring on 0.0–10.0, with chosen-augment and enemy context, confidence and optional empirical history; no automatic best-of-three 10.0 normalization.
- Kept `experimental_augment_evidence` disabled by default while Riot compliance is separately evaluated. Added tests and provisional reroll threshold.
- **Verified latest PR #4 CI: 145 passed, 1 warning** on Windows GitHub Actions.

## 2026-11-18 — PR #5: dynamic team threats and build choices

- Branch `feat/dynamic-team-threats`, based on PR #4 branch.
- Added `EnemyState` to the game snapshot and read-only extraction of visible enemy champions, item IDs, kills and deaths, plus known allied champions.
- Introduced an original `backend/engine/team_context.py`: ally role coverage and enemy threat indicators for tanks, CC, burst, sustain, defensive item stacking and high-kill enemies. Signals are heuristic, not actual observed damage shares.
- Integrated these profiles into both augment context and the build planner so a visible change in the opposing team can affect both.
- Expanded build planning to Balanced, Damage, Survival and Utility paths; respects owned items and limits duplicate boots. Paths are currently display-only, without user style selection.
- Added simple English presentation of enemy pressure and alternate builds; added Windows CI JavaScript syntax check.
- Added focused tests `tests/test_team_context.py` and `tests/test_dynamic_team_pipeline.py`.
- Opened [draft PR #5](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/5).
- **Verified CI** for commit `dc96f3647cbd85e471ef4dd1090a788f415c84cf` succeeded. A subsequent commit `8c8109838c9de03076078a90a480462427accbce` added an end-to-end pipeline test; its run 44312737054 was pending at the time this log entry was composed. Re-check latest CI.

## 2026-11-18 — Cross-chat continuity requested

- The user explicitly requested a durable work log and a copy/paste handoff prompt, because this long conversation will be replaced by another chat inside the same project.
- Created `docs/PROJECT_STATE.md` (current state, responsibilities, safety/licensing decisions, PR dependency graph, remaining work, future-chat checklist).
- Created this `docs/DEVELOPMENT_LOG.md` as an append-only record. **Update both after meaningful future changes**.
- User's `funcionalidades.md` is the feature specification, supplied as a ChatGPT project upload. Future sessions should use it alongside these two GitHub documents.

## 2026-11-18 — Verification and continuity completion

- **Verified** PR #5 functional test commit `8c8109838c9de03076078a90a480462427accbce`: Windows GitHub Actions run **44312737054 succeeded**, **153 passed, 1 warning**; `node --check frontend/app.js` also succeeded.
- Created durable `docs/PROJECT_STATE.md` (current snapshot) and this append-only `docs/DEVELOPMENT_LOG.md`.
- Added root `AGENTS.md` instructing coding agents to read handoff documents, honor license and game-policy constraints, and keep logs updated after future work.
- Subsequent documentation-only commits do not themselves prove end-to-end Windows in-game behavior; recheck GitHub Actions on the latest head.
## Rule for every future entry

Use a date/time in Europe/Lisbon, branch/PR, files changed, why, test command and result (or `not run`), outstanding risks, and next step. Do not silently claim tests passed or functionality is integrated into main until verified.

## 2026-11-18 13:27 Europe/Lisbon — Enemy/ally catalog coverage (PR #6)

- Branch `feat/team-threat-coverage`, based on `feat/dynamic-team-threats` (draft PR #5). Changes remain isolated from `main`.
- Changed `backend/engine/team_context.py` to count visible enemy items even when champion metadata is missing, surface unresolved item IDs, and avoid high confidence for incomplete catalog coverage.
- Changed `backend/workflow/pipeline.py` to include the current champion once in allied role analysis.
- Added regressions in `tests/test_team_context.py` and `tests/test_dynamic_team_pipeline.py`.
- Tests: `python -m pytest -q` and `node --check frontend/app.js` **not run** at the time of this entry; Windows GitHub Actions is required.
- Next: verify CI, then tackle item feasibility and purchase recommendations separately. Real LCDA samples and Riot policy review remain open.


## 2026-11-18 — PR #6 CI regression and fix

- Windows GitHub Actions run [44314745431](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44314745431) **failed**: 154 passed, 1 failed, 1 warning. The failure proved that observed armor metadata was discarded when no enemy champion was recognized.
- Fixed `backend/engine/team_context.py` zero-champion return to preserve recognized armor and magic-resist item counts in commit `9954041`.
- Full suite for this follow-up commit: **not run** at time of entry; awaiting new Windows Actions result.
- No actual Windows in-game LCDA evidence yet.


## 2026-11-18 — PR #6 final automated validation

- Windows GitHub Actions run [44315513781](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44315513781) completed successfully at head `1c7da85`.
- `python -m pytest -q`: **155 passed, 1 warning**.
- `node --check frontend/app.js`: **passed**.
- In-game LCDA capture, actual enemy items and Riot policy: **not run / not resolved**. Keep the PR draft.

## 2026-11-18 — Selectable build paths (PR #7)

- Branch `feat/selectable-build-paths` stacked on `feat/team-threat-coverage` (draft PR #6).
- Changed `backend/engine/build_suggester.py`, `backend/models.py`, `backend/workflow/pipeline.py`: four selected build styles are recomputed from chosen augments, visible teams and owned items; next affordable item is constrained to the selected path and an inventory of six items does not suggest a seventh.
- Changed `backend/api/server.py`: validated local WebSocket build-style selection, live snapshot propagation and serialization; no purchase automation.
- Changed `frontend/index.html` and `frontend/app.js`: lightweight style selector with local browser preference persistence and path alternatives. This is functional UI, not a cosmetic overhaul.
- Added style, inventory, next-item and protocol tests in `tests/test_build_suggester.py` and `tests/test_build_style_contract.py`.
- Includes the PR #6 zero-champion observed resistance fix in the stacked branch.
- Validation: `python -m pytest -q` and `node --check frontend/app.js` **not run** at time of entry; CI must verify. Local Windows in-game choice synchronization and item purchase availability remain untested.
- Decision: style selection changes recommendations only; it never buys/equips items. Player preferences can influence ordering but must not replace the contextual rules.


## 2026-11-18 — PR #7 automated validation

- Windows GitHub Actions run [44315895591](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44315895591) **succeeded** on feature merge commit `c4f8ba25`.
- `python -m pytest -q`: **163 passed, 1 warning**; `node --check frontend/app.js`: **passed**.
- The branch was reconciled with PR #6's fix without modifying `main`; the development log remains append-only.
- Outstanding: Mayhem shop eligibility, purchased-component paths, item exclusivity and real in-game player preference check on Windows.


## 2026-11-18 — PR #8 optional late-game boot replacement

- Branch `feat/late-game-boots-replacement`, stacked on PR #7. All PRs remain draft and `main` is untouched.
- Updated `backend/models.py` with optional item movement speed metadata and a separate boot replacement advice model.
- Updated `backend/static_data/loader.py` to extract unconditional movement speed from structured item stats and the DataDragon `<stats>` description; conditional passives are intentionally ignored. Movement-aware cache v2 requires refreshed item data; legacy cache fallback retains regular offline builds.
- Updated `backend/engine/build_suggester.py` to identify a positive-value, non-boot replacement when six slots are occupied and boots are recognized. Item value responds to selected style, champion, augments and the observed team context. It factors in an estimated lost-mobility penalty.
- Updated `backend/api/server.py` and `frontend/app.js` to show a dedicated **optional swap** with a caution about approximate movement and unverified Mayhem shop availability; not a seventh purchase or automated action.
- Added deterministic tests in `tests/test_boot_replacement.py` for a full inventory, style, catalog confidence, fallback safety, move-speed extraction, repeatability and API serialization.
- Validation at entry: `python -m pytest -q` **not run**; `node --check frontend/app.js` **not run**; Windows Actions pending PR creation.
- Pending: sample actual item records and Mayhem shop eligibility, special augments that modify boots, active movement effects, purchases/components and Windows in-game checks.


## 2026-11-18 — PR #8 Windows CI verification

- Verified [GitHub Actions run 44318127647](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44318127647) at head `280e7659`: **success**.
- `python -m pytest -q`: **171 passed, 1 warning**.
- `node --check frontend/app.js`: **passed**.
- No actual Windows in-game item swap test has been observed. Keep PR #8 in draft until Mayhem item availability and purchase behavior are checked.
- The original six-slot restriction is preserved: swap advice is separate from `next_item_id` and no item is sold/purchased by the app.

## 2026-11-18 — PR #9: Windows white overlay background and HWND investigation

- User provided an actual Windows desktop screenshot: `pytest` **163 passed, 2 warnings** at 13:55; process launched `python -m backend.overlay` with pywebview, rendered a persistent white region under the "Waiting for game..." panel, and logged `Could not find overlay HWND — click-through not set`.
- The `163` local tests identify an older PR #7 checkout versus PR #8's `171` CI tests. No match was running or verified, so "Waiting for game..." alone is not a game-state bug.
- WebView2/pywebview Windows transparency has independently reported rendering issues; changing CSS only is not a reliable native fix.
- Branch `fix/windows-overlay-transparency-fallback`, stacked on PR #8; `main` unchanged.
- Implemented explicit `python -m backend.overlay --renderer qt` alternate backend, preserving pywebview default/override; missing optional Qt dependencies report exact install command.
- Fixed pywebview native HWND discovery to prefer the actual window handle and retry before relying on the potentially changed window title.
- Added Qt Alt+O interaction toggle for mouse-transparent controls, targeted launcher/HWND regressions and README troubleshooting instructions.
- Verification: full Windows CI **not run yet** at this entry; user's **163 passed** are for earlier code, not proof of this fix. On-device Qt transparency **not yet tested**.
- Next: verify CI then request Windows screenshot of `--renderer qt`; if necessary inspect pywebview runtime version and GPU rendering issues.

## 2026-11-18 — PR #9 automated validation

- [Windows Actions run 44319789943](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44319789943) completed successfully at code/docs head `e93aad6b`.
- `python -m pytest -q`: **178 passed, 1 warning**. Includes 7 focused native handle and renderer tests.
- `node --check frontend/app.js`: **passed**.
- Transparency over Windows desktop/League and the Qt global Alt+O hotkey are **not yet verified in-game**. Only user-on-device visual feedback can confirm the compositor workaround.
- Recommended user command after fetching PR #9 branch: `python -m pip install -e ".[overlay]"` then `python -m backend.overlay --renderer qt` (stop the old overlay first). Do not merge draft PRs into `main` yet.

## 2026-11-18 — Windows desktop confirms Qt transparency fix

- User executed `python -m backend.overlay --renderer qt` on Windows, from `D:\Overlay ARAM\aram-oracle`.
- User screenshot confirms the previous large white rectangle is gone: unused Qt overlay area is transparent over the desktop; the "Waiting for game..." and header panels display legibly.
- Startup logs confirm `Using PyQt6 transparent overlay (explicit renderer)`, `Overlay window started` and `Click-through enabled (HWND=...)`.
- User's local test run: `pytest` **178 passed, 2 warnings**, confirming the current PR #9 test count. The warnings concern dependency deprecations, not test failures.
- The Qt DPI-awareness warning appeared in the terminal, but the desktop renderer started and displayed as expected.
- Verified scope: **Windows desktop transparency and startup click-through only**. Not yet confirmed: Qt overlay over League, actual key-toggle behavior, champion select / LCDA / OCR signals, builds and boot replacement in a match.
- The CLI default `--renderer auto` still prefers pywebview. Run `--renderer qt` explicitly for the confirmed working desktop renderer; do not claim default changed.
- Latest CI at the preceding documentation-only head `388fe862`: [Windows run 44320104470](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44320104470) **success**. Neither draft PR #9 nor prior PRs were merged to `main`.

## 2026-11-18 — PR #10: controllable Qt overlay window

- The user reported the frameless Qt overlay lacked buttons to open or close. Before changes, users could stop the process via terminal or toggle click-through with Alt+O; neither provided direct hide/show.
- New branch `feat/qt-overlay-window-controls`, stacked on PR #9. `main` unchanged.
- Added Qt-only header buttons: **− Hide** and **× Quit**. Commands are only accepted from the trusted local overlay origin and are not exposed as network endpoints. A fragment is cleared after Qt dispatch so the user can repeat the action.
- Added global **Alt+H** show/hide, persisted timer while window is hidden, and Qt system tray Show/Hide, Toggle interaction and Quit actions (double-click toggles).
- Preserved Alt+O for toggling click-through; must enable interaction to click controls. Browser-only UI hides native buttons.
- Added `tests/test_overlay_window_controls.py`, with valid/invalid local action URIs and UI contract tests. Updated README with how to hide, restore, and fully close.
- At writing: Windows Actions full suite and JS syntax check **not yet run**; actual Windows click-through and tray tests **pending**. No claim of real-game validation.

## 2026-11-18 — PR #10 Windows CI verification

- [Windows GitHub Actions run 44322346286](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44322346286) succeeded at PR #10 feature commit `5c0d82ed`.
- `python -m pytest -q`: **191 passed, 1 warning**; `node --check frontend/app.js`: **passed**.
- Added tests cover local control fragment origin, markup/JS hooks and Qt hotkey/tray lifecycle as code-level contracts. Actual Windows GUI clicks, Alt+H restore and tray actions are **not yet tested on user machine**.
- PR #10 remains draft, stacked on PR #9; `main` unchanged.

## 2026-11-18 — PR #11: first real ARAM Mayhem screenshot regressions

- The user shared a level-4 in-game Jinx screenshot showing three offered augments, `NO OCR`, an unscored AUGMENT PICK panel, an incorrectly owned Poro-Snax, a twice-recommended Phantom Dancer, and unscored visible enemy items. The champion/roster/gold read path is at least partially functional.
- The client Live Client Data API represents equipped items with a `slot`; slot 6 is for trinkets such as Poro-Snax (item ID 2052). `backend/collectors/lcda.py` now ignores those items in both own equipment planning and enemy equipment coverage; this does not assert unseen item data.
- `backend/engine/build_suggester.py` now excludes duplicate catalog names even when IDs differ (same item/mode variants) and does not suggest a same-named already-owned item as a late-game boot swap.
- `backend/api/server.py` now also starts scan windows on newly observed eligible levels, not exclusively on respawn. A separate pure decision helper prevents repeated same-level reopening. Per-game reset clears manually entered augments even with OCR missing.
- `frontend/app.js` no longer permanently hides manual augment entry in overlay mode. During eligible picks it opens the augment/manual panel and does not show "SCANNING" when OCR is unavailable; `frontend/index.html` has clear manual fallback text.
- Added regression suite `tests/test_live_mayhem_regressions.py` and install/troubleshooting instructions to README. Prior PR #10 tests were **191 passed** on Windows; this PR's modified tests have **not run yet**.
- Remaining: install/locate Tesseract on the actual user PC, confirm 3-card OCR results and positional cropping with another live image; validate Mayhem item metadata and real shop buyability, since current builds remain heuristic.

## 2026-11-18 — PR #11 Windows CI verification

- Verified [Windows Actions run 44325282457](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44325282457) **success**, at feature head `df2cf1ba`.
- `python -m pytest -q`: **200 passed, 1 warning**, zero failed; `node --check frontend/app.js`: **passed**.
- Includes nine new focused regression tests from the first actual Mayhem screenshot, plus the pre-existing 191. This is CI evidence, **not proof** of automatic three-card OCR, real shop item availability or live equip behavior.
- Required Windows follow-up: verify `Test-Path 'C:\Program Files\Tesseract-OCR\tesseract.exe'`, install via `winget install --id UB-Mannheim.TesseractOCR --exact` if needed, fetch PR #11 branch, restart `python -m backend.overlay --renderer qt`, inspect AUGMENT PICK and DETECT AUGMENTS in a match, confirm Poro-Snax does not occupy a build slot and Phantom Dancer is not repeated.
- Remaining Mayhem-specific considerations: actual augment name variants, OC R region calibration, eligible levels, item patch/mode availability and enemy catalog provenance.



## 2026-11-18 Europe/Lisbon — PR #12: pre-game Settings and local feedback (implementation)

- Branch `feat/pregame-settings-feedback` based on `fix/live-augment-detection-item-duplicates` (PR #11); earlier draft PRs and `main` remain untouched.
- Audited the seven partial commits already present: local preference persistence, API `/settings`, `GET/PUT /api/preferences`, Settings HTML/CSS/JS and display-only in-game build style.
- Added Qt **Open Settings** tray action via default browser, without altering Qt transparency, Alt+O, Alt+H or click-through flags.
- Removed dead frontend feedback button/handlers; retained a post-game explanation pointing to Settings. Manual augment search remains available during eligible picks.
- Fixed diagnostics so user text is actually stored in the local JSON report. Server now emits HTTP 429 for cooldown and 500 for an unsuccessful local save; cooldown is only consumed after a successful file write. Settings displays these errors and preserves unsent text.
- Added `tests/test_pregame_settings.py`, `tests/js/settings.test.cjs`, and Windows Actions checks for `frontend/settings.js` syntax and browserless Settings interactions. Updated README.
- Validation: `python -m pytest -q`, `node --check frontend/app.js`, `node --check frontend/settings.js`, `node --test tests/js/settings.test.cjs` **not run at entry**; new PR/CI to be checked. No Windows on-device Settings/feedback/OCR test yet.
- Pending: create draft PR #12 targeting PR #11 branch, verify Actions and fix failures; afterwards request only necessary real Windows tests.


## 2026-11-18 15:04 Europe/Lisbon — PR #12 Windows CI validation

- Opened [draft PR #12](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/12) with head `feat/pregame-settings-feedback`, targeting PR #11 branch `fix/live-augment-detection-item-duplicates`. No merge to `main`.
- First Windows Actions run [44330933993](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44330933993) **failed**: **214 passed, 1 failed, 1 warning**. The sole failure was in the newly created `test_runtime_pipeline_uses_updated_style_on_next_poll`: its mocked `GameSnapshot` omitted six mandatory constructor fields. Fixed the test fixture at commit `d8dd7c5`; application code was not implicated by this failure.
- Second Windows Actions run [44331056654](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44331056654) **succeeded** on feature commit `d8dd7c5`. Results: **215 Python tests passed, 1 warning**, `node --check frontend/app.js` **passed**, `node --check frontend/settings.js` **passed**, and `node --test tests/js/settings.test.cjs` **4 passed, 0 failed**.
- These are automated Windows-runner results, not evidence of actual Qt tray/browsers, saved preferences after a user's reboot, live in-match build changes, local Tesseract/OCR or Mayhem shop eligibility.
- Next: recheck Actions at this later documentation-only head, keep PR #12 draft, then ask the user only for necessary on-device checks.


## 2026-11-18 Europe/Lisbon — UX audit backlog recovered and persisted

- User requested importing conclusions from the separate **Auditoria UX — ARAM Oracle** project conversation into a permanent checklist and crossing off completed items. The recovered conversation summary describes a contextual/event-driven companion (augment offers > verified shop > optional scoreboard), quiet combat UI, compact choices and validation at 1080p/1440p.
- Created `docs/TODO.md` with stable UX task IDs, P0/P1/P2 priorities, explicit criteria, known UI-state proposals, existing completed **code-level** milestones, and a separate Windows/live-validation backlog. This is a synthesis of the conversation summary, not a verbatim transcript.
- Cross-checked historical completion claims against PRs #9–#12 and [Windows Actions run 44331470781](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44331470781) (**215 Python passed, 1 warning; 4 Node tests passed; both JS syntax checks passed**). None of this proves live UX outside the already confirmed Qt desktop transparency and visible LCDA screenshot fields.
- Updated `AGENTS.md` session startup and end-of-work instructions and `docs/PROJECT_STATE.md` to make this backlog mandatory for future development continuity.
- This commit changes **documentation only**; no Python or JavaScript tests were run locally for these edits. Check the latest Windows CI triggered by the updated PR #12 head. The branch and PR remain draft; `main` is untouched.

## 2026-11-18 Europe/Lisbon — Desktop app and intuitive installer roadmap

- User shared OP.GG Settings and overlay screenshots as a usability reference and proposed a proper Windows installer plus desktop application for ARAM Oracle.
- Added proposed tasks `UX-D01` through `UX-D10` to `docs/TODO.md`: native Qt Settings window, navigation, overlay preview/configuration, single engine/tray lifecycle, Windows packaging/uninstall, OCR onboarding, distribution safeguards, updates, real Windows acceptance matrix and original branding/licensing.
- Architecture direction: keep the existing Python/FastAPI engine and two purposeful Qt surfaces (standard desktop window + transparent click-through overlay). Preserve Riot/licensing guardrails; no OP.GG source/assets are reused.
- Documentation-only change; installer and desktop shell **not implemented**. Do not mark these tasks complete. Source code tests for this change **not run locally**; verify Actions at the updated branch head.
- PR #12 remains draft targeting PR #11; `main` unchanged.

## 2026-11-18 Europe/Lisbon — Approved desktop architecture, granular phases and continuity skill

- The user approved an intuitive Windows installer, a dedicated desktop Settings/control app and a separate contextual Qt game overlay inspired by the usability of OP.GG (not its source/assets).
- Added `docs/DESKTOP_ARCHITECTURE.md`: single existing FastAPI/scoring/OCR engine, normal focusable Qt Settings window and separate transparent click-through Qt overlay, configuration/data ownership and safeguards, pending installer/lifecycle gates.
- Added `docs/IMPLEMENTATION_PHASES.md`: baseline G0, first small implementation D1 desktop Settings shell, separate D2 lifecycle, D3 navigation, D4 preferences/preview, D5 OCR, D6–D8 contextual overlay, and D9–D11 packaging/release. Each phase has a narrow scope, acceptance gates and dependencies.
- Added `PH-G0.*` and `PH-D1.*` through `PH-D11.*` unchecked task items to `docs/TODO.md`, preserving existing UX-D tasks and completed milestones.
- Added repository-local skill `.agents/skills/continue-aram-oracle/SKILL.md` and `docs/CONTINUE_PROJECT.md` prompt to restart development from GitHub in another ChatGPT project conversation; documented that repository skill is not an automatically installed ChatGPT skill.
- Updated `AGENTS.md` and `docs/PROJECT_STATE.md` to require reading these plans in future sessions.
- This is a **documentation/plan-only** change: no application code implemented, no Windows device tests performed, and no local Python/JS suite run. The prior PR #12 head `b09f736b` passed Windows CI run `44333213842`; verify Actions at the **new documentation head** separately.
- Remain on draft PR #12 (`feat/pregame-settings-feedback` targeting PR #11), never merge to `main` without user approval. Next development action is **D1** in a new stacked draft feature branch.

## 2026-11-18 Europe/Lisbon — PR #13 D1 native desktop Settings shell

- Confirmed live PR #12 `feat/pregame-settings-feedback` is draft against PR #11 `fix/live-augment-detection-item-duplicates` at head `590e2348`. Its Windows run `44334884227` succeeded. Created `feat/desktop-settings-shell` from that branch, then opened [draft PR #13](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/13) **targeting PR #12 branch**. `main` remains untouched.
- Implemented `backend/desktop/__main__.py`, `backend/desktop/runtime.py`, and `backend/desktop/window.py`. The entrypoint `python -m backend.desktop` checks for PyQt6 WebEngine, then reuses an already compatible loopback FastAPI instance or starts the **existing** FastAPI launcher on 127.0.0.1:8765. Unexpected port occupants, server startup failures/timeouts and Settings page load failures produce actionable diagnostics. Qt hosts the already-existing `/settings` page in a normal, resizable `QMainWindow` / `QWebEngineView`.
- Left `frontend/settings.html`, `frontend/settings.js`, `frontend/settings.css`, all preference/bug-report APIs and the complete `backend/overlay` renderer code untouched. In particular the explicit `python -m backend.overlay --renderer qt`, Qt transparency, click-through, Alt+O/Alt+H and tray/browser behavior are unchanged. The native Settings shell and legacy overlay can connect to the same compatible API. Unified instance/tray ownership is **D2, not D1**.
- Added `tests/test_desktop_shell.py` (19 new headless Python tests) for API signature/URL, healthy server reuse, unrelated port listener, startup and missing Qt failure, and Qt-vs-overlay source contracts. Updated README with independent Windows dev launch and D1 boundaries.
- **Verified GitHub Actions:** [run 44336280007](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44336280007) at code+README head `d5aff632`: **234 Python tests passed, 1 warning**, `node --check frontend/app.js` passed, `node --check frontend/settings.js` passed, `node --test tests/js/settings.test.cjs`: **4 passed, 0 failed**. No local Windows Qt GUI smoke test was performed. A subsequent docs-only HEAD may trigger another Actions run.
- As requested, recorded future source-reuse research in `docs/REUSE_CANDIDATES.md`: `smiteless` and `ez-lol-spell-tracker` appear MIT-licensed, while `mayhem-advisor` is not generally licensed for copying; other candidate licenses need exact verification. **No third-party app source was imported in this phase.** Only code with a verified applicable license, attribution, tests and appropriate permitted data sources may be reused in future phases.
- Updated `docs/TODO.md`: G0 and D1 code/CI gate items marked complete; **PH-D1.5 and broad UX-D01/UX-D04 remain unchecked**. `docs/PROJECT_STATE.md` reflects current PR #13. User-device Windows Qt focus/resize, preference persistence/feedback and legacy in-game overlay tests remain outstanding. No installer, updater or Settings redesign attempted.

## 2026-11-18 Europe/Lisbon — D1 Windows observations, OCR dependency ready and chat handoff

- User checked out `feat/desktop-settings-shell` on `D:\\Overlay ARAM\\aram-oracle` and started `python -m backend.desktop`. Screenshot shows a normally framed Settings window with the existing Preferences and Feedback navigation and loaded `Balanced` style. Terminal shows API started, Settings window opened and Settings loaded. This does **not** prove modified preference persistence, feedback submission, or actual resizability/focus interaction.
- User separately confirmed the **Qt overlay transparency, Alt+O interaction toggling and Alt+H show/hide** on the Windows desktop; log confirms toggling. `KeyboardInterrupt` was observed after stopping the process; the earlier Qt DPI warning did not prevent the window opening.
- The Settings page initially showed `OCR unavailable`; user verified the default Tesseract executable path was absent. They invoked `winget install --id UB-Mannheim.TesseractOCR --exact` and subsequently reported the OCR readiness indicator is now **green**. This confirms the external OCR dependency can be found according to the Settings status, **not** that OCR recognizes actual Mayhem augment cards or rerolls. Next in-game OCR fixture/calibration checks remain separate and must not involve abandoning a matchmaking game.
- User approved **one phase per conversation, branch and draft PR**, with a repository skill + handoff prompt: D2 is the next chat on a fresh stacked draft branch, targeting PR #13. Future sessions must reread live GitHub state and license-reuse register; no repeated settled investigations.
- `PH-D1.5` remains open for native resize/focus, saved style across restart and local feedback testing; `PH-D2.*`, live OCR and reroll accuracy also remain open. No application code changed in this documentation update. Automated regression tests **not run locally** for this record; previously verified Windows Actions [44337928614](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44337928614) succeeded at `52a96563` (234 Python, 1 warning; 4 JS). Reconfirm any CI triggered by new doc commits.

## 2026-11-18 Europe/Lisbon — Explicit chat rotation and resume triggers

- Confirmed the repository-local continuity skill `.agents/skills/continue-aram-oracle/SKILL.md` existed and the D1 -> D2 handoff had already been recorded in `docs/CONTINUE_PROJECT.md`.
- Added two documented user phrase conventions: `ARAM Oracle: preparar passagem` closes/checkpoints the current unit with verified live GitHub PR/CI, TODO, state, log, and a next-chat prompt; `ARAM Oracle: continuar` starts the next manually opened ChatGPT project conversation by fetching the skill and current state from the connected private GitHub repository.
- Documented the same conventions in `AGENTS.md` and `docs/CONTINUE_PROJECT.md`, including that they are **not registered slash commands, background jobs or an automatic chat creator**.
- If context rotation occurs while a phase is unfinished, stay on its current branch/PR and preserve the unchecked acceptance gates. One new branch/PR is created only on beginning the **next phase**.
- This entry is documentation-only; no source code or tests were changed for the trigger convention. Verify CI separately on the latest PR #13 head.

## 2026-11-18 Europe/Lisbon — PR #14 D2 unified process, API and tray lifecycle

- Created `feat/desktop-single-instance-tray` from the originally inspected D1 code head; opened [draft PR #14](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/14) targeting `feat/desktop-settings-shell` (draft PR #13). The D1 base subsequently received five documentation-only commits, which are reflected in the updated D2 handoff documents; do not modify `main`.
- Added an OS-held per-user lock, authenticated loopback activation queue and stale-descriptor recovery in `backend/desktop/instance.py`; duplicate Qt launches activate the existing owner and do not start a second tray or API.
- Added `backend/desktop/service.py` to manage the existing FastAPI/uvicorn server with explicit `should_exit` and bounded join at Quit, without killing compatible external server processes. Unknown port 8765 listeners are refused.
- Unified Settings and transparent overlay surfaces under one Qt event loop and one tray in `backend/desktop/window.py`; the Qt overlay's tray is disabled only in managed mode while its original Windows transparent/click-through flags and Alt+O/Alt+H polling are retained. Both `python -m backend.desktop` and `python -m backend.overlay --renderer qt` activate the managed owner. The explicit legacy `--renderer webview` remains outside the unified Qt tray path.
- Added 17 headless process/activation/cleanup/launcher tests in `tests/test_desktop_lifecycle.py` and adjusted D1 launcher mocks. Tests are structural and headless; they do not prove Windows tray focus or in-game OCR.
- **At this checkpoint:** local Python/Node tests not run in the GitHub connector. GitHub Actions final head status must be checked and recorded in a follow-up log entry. No user Windows acceptance test for D2 has been performed.
- `PH-D1.5`, `PH-D2.3`, `UX-D04` and in-game three-card/reroll OCR remain open until their separate evidence gates. No third-party source was copied (reviewed `docs/REUSE_CANDIDATES.md`); D3 navigation remains the next bounded phase.

## 2026-11-18 Europe/Lisbon — PR #14 D2 verified Windows CI

- Confirmed [Windows Actions run 44345555542](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44345555542) succeeded on stacked D2 merge head `0b4a563b861dac7f44bd50f057e53f085c86e52a` (including the latest PR #13 documentation). `python -m pytest -q`: **253 passed, 1 warning**; `node --check frontend/app.js` and `node --check frontend/settings.js`: **passed**; `node --test tests/js/settings.test.cjs`: **4 passed, 0 failed**.
- The new D2 tests cover exclusive lock, authenticated duplicate activation, stale startup recovery, safe failure on conflicting services, managed uvicorn stop and port-bind failure, Qt entrypoint continuity and headless source contracts.
- No native Qt GUI, in-game overlay, OCR card/reroll detection, preference persistence or feedback submission was actually performed on the user's Windows device as part of D2. Keep `PH-D2.3`, `PH-D1.5`, `UX-D04` and other game-context gates unchecked. Draft PR #14 remains stacked on draft PR #13; `main` remains unchanged.
- These are verified tests at the stated head; subsequent documentation-only handoff commits should be checked independently and not portrayed as a separate live Windows acceptance.

## 2026-11-18 Europe/Lisbon — D2 real Windows tray and single-instance observations

- User checked out D2 `feat/desktop-single-instance-tray` on Windows and started `python -m backend.desktop`; terminal logged `Managed ARAM Oracle Qt application opened`, `Desktop Settings loaded`, and after pressing the Settings X `Settings hidden to notification area`.
- The user confirmed that after the X the application **remains in the Windows notification area under `^`**, rather than displaying a persistent taskbar icon. They then explicitly confirmed right-click tray actions **Open Settings**, **Show/Hide Overlay** and **Quit** successfully perform their advertised actions.
- Screenshot of a second invocation `python -m backend.desktop` logged `Activated existing ARAM Oracle settings window`, demonstrating the visible activation pathway rather than opening another normal Settings window. This alone does not measure process counts or prove the absence of duplicate servers.
- In a deliberate port-conflict scenario, user started `python -m http.server 8765 --bind 127.0.0.1`; the Qt overlay invocation logged `Port 8765 is occupied by an incompatible service`, as intended. The HTTP server returning 404 for `/health` is consistent with the test. A separate earlier terminal showed `KeyboardInterrupt` after the owner process had logged Settings hide; it should not be mistaken for a crash caused by closing Settings.
- **Acceptance status: partial.** Still unverified specifically on the D2 unified launcher: Alt+O interaction toggle, Alt+H overlay restoration, post-Quit owned API port 8765 release and orphan-process check, Settings focus/resize, saved preference after restart, feedback report, in-game transparency, and real three-card/reroll OCR. Keep `PH-D2.3`, `PH-D1.5`, `UX-D04` and `UX-D09` open until their remaining criteria have evidence. Earlier D1 Qt shortcut tests are historical evidence, not D2 validation.
- Documentation-only update in [draft PR #14](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/14); no application code changed and Python/Node suites were not run for this entry. Last known code CI: [Windows run 44346046844](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44346046844), reportedly successful at pre-update head `3070b32e`; verify the latest run if triggered by docs changes. No merges to `main`.

## 2026-11-18 Europe/Lisbon — D2 on-device shortcut and Quit acceptance completed

- Follow-up screenshot of the D2 Windows desktop runtime logs `Qt overlay shown`, `Click-through enabled`, `Qt overlay hidden (Alt+H or tray to restore)`, `Qt click-through OFF`, and `Qt overlay shown`. These corroborate hide/restore and interaction toggling through Alt+H/Alt+O in the unified D2 Qt launcher.
- After using Quit (confirmed in the prior user report), user ran `Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue` and received **no output**. The port was no longer listening and available for reuse; this command alone does not prove all OS processes/threads are gone.
- With previous on-device Settings X -> notification area, right-click tray Open Settings/Show-Hide Overlay/Quit, duplicate activation, and incompatible foreign 8765 port handling, this satisfies the **D2 lifecycle/tray acceptance** for `PH-D2.3` and `UX-D04`. Marked both checkboxes in `docs/TODO.md` and updated `docs/PROJECT_STATE.md`.
- **Not validated:** D1 Settings focus/resize, preference save across restart and local feedback; in-game League borderless behavior and OCR three-card/reroll recognition; broader `UX-D09` smoke matrix. Do not mark them done. Proceed to separate **D3 Settings navigation** phase through a new branch/draft PR stacked on PR #14; `main` unchanged.
- Documentation-only commits; no Python/JavaScript source edits or new local test runs. The preceding [Windows GitHub Actions run 44349582275](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44349582275) completed with **success** at prior documentation head `be878f1d`; the final documentation-head run needs separate verification.

## 2026-11-18 Europe/Lisbon — Scheduled Claude UI audit after D5

- User approved a **new design-closure milestone after all desktop interface phases D3, D4a/D4b, D5a/D5b**, before D6. Added **D5c — Claude-led UX/UI audit and bounded desktop design improvements** to `docs/IMPLEMENTATION_PHASES.md`, `docs/TODO.md`, `docs/DESKTOP_ARCHITECTURE.md` and `docs/PROJECT_STATE.md`.
- D5c requires an **actual Claude audit** of real Windows Settings/preview/OCR flows and screenshots, a P0/P1/P2 defect log, bounded fixes with regression tests and a Windows verification gate. Claude has **not** reviewed the UI yet; review and implementation tasks are unchecked.
- Future D7/D8 in-game contextual panels still need separate real League UX validation. The existing D6–D11 work is retained: context reducer, augment/shop panels, Windows package, installer and release/privacy/licensing/update gates. No proprietary competitor assets or third-party source imported.
- **Documentation-only scope:** no Python, JavaScript or Qt behavior changed; no local tests run. Working draft PR #14 `feat/desktop-single-instance-tray` is not merged and `main` remains untouched. Recheck GitHub Actions at the latest documentation head.

 
## 2026-11-18 Europe/Lisbon — D3 draft PR #15 and Windows CI validation

- Read repository agent/continuity skill, all mandated state/TODO/phases/architecture/log/reuse/handoff files and project UX audit; verified D2 [draft PR #14](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/14) and D2 on-device lifecycle/tray evidence. The D3 branch was started from the current D2 feature branch and updated to retain concurrent D2 documentation changes.
- Created `feat/desktop-settings-navigation`, opened [draft PR #15](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/15) **targeting D2 branch** (not `main`), implemented General, Overlay, Build Preferences, OCR, Diagnostics, Feedback and About in the existing frontend. Added roving ARIA keyboard tabs, loading/save/error/retry states, diagnostics using current endpoint results, and clear labels for planned but unavailable features. No API/backend/Qt/overlay/game algorithm/hotkey/tray change.
- Added `tests/test_desktop_settings_navigation.py` (2 structural tests) and expanded `tests/js/settings.test.cjs` from 4 to 8 tests. **Verified [Windows Actions run 44352298709](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44352298709) at D3 code head `346998a843b8690255f8acacd0b958b2cfb67532`: 255 Python passed, 1 warning; 8 Node tests passed, no failures; `node --check` for overlay and Settings JavaScript passed.** No local Windows Qt GUI or League test performed in this session.
- `PH-D3.1`/`PH-D3.2` code/test completed; `PH-D3.3`, `PH-D1.5`, `UX-D02`, `UX-D09` remain pending real Windows navigation, resize/focus, persistence and feedback. Tesseract green remains dependency-readiness only, not three-card/reroll OCR proof. Next bounded phase after D3 user acceptance is D4a validated overlay preferences/model (D4b Qt apply/preview separately). Documentation-head CI to be checked separately.

 
## 2026-11-18 Europe/Lisbon — D3 Windows user acceptance recorded; D4a development independent

- Rechecked live GitHub draft PR #15 `feat/desktop-settings-navigation` targeting the D2 PR #14 branch. PR #15 code and seven Settings sections, test files, architectural documents and continuity skill are present. Verified its **final documentation-head Windows Actions [run 44353064467](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44353064467) completed successfully** at `1748d6e4`. The preceding D3 code run `44352298709` passed **255 Python (1 warning), 8 Node and both JavaScript syntax checks**.
- User subsequently posted a Windows screenshot of the D3 OCR section showing **Local API reachable** and **Tesseract detected** after pressing Recheck. They explicitly reported having tested everything else from the manual D3 checklist. Record this as **user-reported overall Windows acceptance** of Settings navigation, keyboard/focus/resize, changed build preference persistence and feedback, plus previously verified D2 tray/hotkeys. No independent per-step screenshots or console logs were supplied for all tests. Mark `PH-D3.3`, `PH-D1.5` and `UX-D02` accepted from user confirmation; reopen a checkbox if the user clarifies a subtest was not performed.
- Recheck confirms **OCR dependency readiness only**. Real automatic detection of the three Mayhem augment cards, rerolls, confidence and in-game UI mapping was **not** tested and remains an explicit P0/D5b/D7 validation gate. Keep `UX-D09` League borderless and 1080p/1440p/Alt+Tab matrix open.
- User reports D4a implementation is underway in a separate chat. No D4a branch/PR was yet visible in the connected GitHub snapshot; do not claim it is absent locally or start duplicate work. This log entry is **documentation only**, no Python/frontend/Qt changes and no fresh manual tests by this assistant; recheck Actions at this documentation commit's head.

## 2026-11-18 Europe/Lisbon — D4a PR #16: persisted versioned overlay preferences

- Re-read the repository-local continuation skill, agent instructions, state/TODO/phases/architecture/reuse/handoff documents and checked the live D3 draft PR #15. Its final earlier documentation-head Windows Actions [44353064467](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44353064467) passed at `1748d6e4`. The D3 base subsequently received a user-acceptance documentation commit: reported navigation, focus/resize, preference save/restart and feedback were checked by the user; individual subtest logs were not all provided. Retained that evidence rather than reverting it.
- Created `feat/desktop-overlay-preferences-d4a` and [draft PR #16](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/16) targeting `feat/desktop-settings-navigation` (PR #15), not `main`. No merge to `main`.
- Added schema v1 (`schema_version`, `build_style`, `overlay`), four named corners, bounded integer offsets, finite opacity/scale, safe defaults, per-field saved-value sanitization, legacy v0 migration on successful write, atomic file replace and refusal to overwrite unknown future versions. Both build-style and overlay writes preserve the other preference family across restarts.
- Reused `backend.api.server` / FastAPI and the existing preferences file. `GET /api/preferences` now includes schema and overlay; `PUT /api/preferences/overlay` validates strict full objects and returns appropriate 422/409/500 errors; legacy `PUT /api/preferences` remains compatible. Startup loads both settings. Added a pure, currently unmounted frontend JavaScript model to prepare future D4b UI integration; no preview and no Qt geometry/opacity changes.
- Added `tests/test_overlay_preferences_d4a.py` with invalid-value, migration, atomic failure, persistence and server lifespan restart cases; updated legacy Python assertion and expanded the existing JS Settings suite with migration, boundary, round-trip and D3 compatibility checks. Windows Actions [44355601388](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44355601388) at D4a code head `8ef17b81`: **292 Python passed, 1 warning; 13 Node tests passed**, existing JS syntax checks passed. Added an extra syntax check for `frontend/overlay-preferences.js` in CI after that code-head run. Recheck final code/docs/ancestry-head CI before claiming complete branch validation.
- Marked `PH-D4a.1` and `PH-D4a.2` code/test gates complete. Separate D3 user-reported acceptance is retained; `UX-D09`, actual League borderless at varied resolutions and three-card/reroll OCR remain unverified. D4b will own appearance controls, preview and safe Qt apply; never infer they work from this data-only phase.



## 2026-11-18 Europe/Lisbon — D4b stacked draft PR #17, code/checkpoint

- Verified D4a [final Windows Actions 44356926105](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44356926105) completed successfully at `0bc9535a7ba58858ccbc4352d318bd5c3b971cc1`: **292 Python passed (1 warning), 13 JavaScript passed**; syntax checks passed. D4a draft PR #16 remains based on #15, no merge to `main`.
- Created `feat/desktop-overlay-preview-apply-d4b` and [draft PR #17](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/17), targeting the D4a branch, not `main`. Implemented Overlay-section anchor, signed offset, opacity and scale inputs; an explicitly simulated/static preview with form validation, API save and retry; no live game data. D4a schema v1, API and JS helper are reused.
- Added pure, bounds-clamped Qt logical-coordinate geometry calculator for four anchors, negative screen origins, scaling, taskbar-available regions and small screens. Existing Qt transparent window reloads sanitized persisted preferences every 800 ms, adjusts WebEngine zoom and window opacity and watches monitor geometry, DPI, hotplug and resizing. Win32 click-through state and Alt+O/Alt+H/tray ownership are preserved in source; they are **not** yet verified again on the user's Windows device.
- Added `tests/test_overlay_layout_d4b.py` and five JavaScript Settings tests for form, sample preview, invalid values, retry and persisted API payload. No actual Qt/League instance was launched in this connected GitHub session. Initial Actions [44360223711](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44360223711) was **in progress** when this entry was written; a final-head check is required and will be recorded separately.
- On-device acceptance remains open: `PH-D4b.2`, `UX-D09` (1080p/1440p, DPI 100/125/150%, multi-monitor, click-through/transparency, Alt+Tab and League borderless). Real augment detection/rerolls remain D5b/D7; OCR and scoring were not modified. Next phase D5a is dependency-readiness guidance only.


## 2026-11-18 Europe/Lisbon — D4b automated Windows CI succeeded

- Repaired the initial tiny-screen geometry test failure by ensuring a usable minimum content-height target before clamping the overlay to the available display; corrected a malformed JavaScript regression-test regex and retained API-save error messages in the form. The final code/test-head [Windows Actions run 44361461870](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44361461870) **succeeded** at `9520057c6da6228c4ff7772ec43310060e736d37`: **303 Python passed, 1 warning; 18 JavaScript passed, 0 failed; syntax checks passed**.
- `PH-D4b.1` completed based on implemented controls/preview/Qt apply and successful headless regression tests. **No native Windows Qt, game, display-DPI or Alt+Tab validation performed here**. Leave `PH-D4b.2` and `UX-D09` unchecked, plus separate OCR three-card/reroll and shop detection requirements. PR #17 remains draft, based on #16, with `main` untouched.
- This entry is documentation-only; after this commit, check latest CI again to validate the final documentation head. Next scoped work is D5a OCR executable/path readiness and first-run guidance (a different draft PR).

## 2026-11-18 Europe/Lisbon — D4b Settings real Windows partial acceptance (user report)

- On the active stacked [draft PR #17](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/17), user reported **6/6 PASS** for the native Windows Settings checklist: Overlay section and appearance controls; all four anchor options (top/bottom, left/right); opacity 60% and 100%; scale 75%, 100%, 150%; simulated preview responds and retains clear `SIMULATED` label; saved preferences persist after closing/reopening the desktop app. Treat these as **user-reported device observations**, not independent screenshots/diagnostic logs.
- This validates the D4b Settings form, preview and persistence subset. It **does not** confirm that the live transparent Qt overlay actually repositions/scales/changes opacity after save or that transparency, Alt+O/Alt+H, mouse click-through, Alt+Tab, League borderless, 1080p/1440p, DPI variations and multi-monitor/hotplug behave correctly. `PH-D4b.2` and `UX-D09` remain **unchecked** until their broader acceptance matrix has evidence.
- Documentation-only checkpoint on `feat/desktop-overlay-preview-apply-d4b`; no app code/test changes or new local test run. Prior confirmed final-head Windows Actions [44362005497](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44362005497) at `4eb821f` succeeded (303 Python, 1 warning; 18 JavaScript). A documentation commit may trigger a new workflow, whose result must be verified separately. PR #17 stays draft, based on #16; `main` unchanged.

## 2026-11-18 Europe/Lisbon — User Windows Mayhem functional regressions; Claude code audit checkpoint

- User explicitly declared D4b **development/Settings phase finished** after 6/6 on-device Settings acceptance; they want **a Claude source-code and functionality audit before further interface development**. This does **not** mean D4b full Windows display matrix or gameplay correctness was accepted. `PH-D4b.2`, `UX-D09` and P0 in-game tasks remain unchecked.
- Screenshots from a permitted custom Mayhem session: Champion Select recognized, initial in-game state `Waiting for game` despite visible augment cards, followed by correct active-game Neeko context; actual **Impassable / Upgrade Stormsurge / Tooth Fairy** differed from overlay **escAPAde / Restart / Mercy**. One-card reroll required **Alt+O → Scan Screen** instead of automatic re-identification. Many offered augments displayed **2.1/10** with reroll advice. After leaving game, overlay retained **Neeko, prior time and gold**. User also requested eventual **small scores above each League augment card**, not a large right-side permanent panel.
- Registered `F-AUD-01`–`F-AUD-07` and `A-FUNC.1`–`A-FUNC.4` with severity, code-inspection leads and pass/fail evidence in `docs/TODO.md`, `docs/PROJECT_STATE.md`, `docs/IMPLEMENTATION_PHASES.md`, `docs/DESKTOP_ARCHITECTURE.md` and new `docs/FUNCTIONAL_AUDIT_HANDOFF_2026-11-18.md`. Updated `docs/CONTINUE_PROJECT.md` and continuation skill with Claude audit prompt. Real screenshots remain in ChatGPT and have not been attached to GitHub, nor reviewed by Claude.
- Code review only: OCR fuzzy matcher lacks left/center/right card mapping; full-crop hash threshold and `unchanged` fallback may miss one-card rerolls; **(0.35 * 0 + 0.25 * 5) / 0.60 = 2.1** for zero-contribution augments is not an evidence-based low rating; frontend game-end/no-game events do not clear champion/time/gold. Root cause of intermittent custom-match waiting is not established; the game did subsequently connect.
- **Important unverified WIP:** before user requested audit-only, a separate branch `fix/postgame-stale-match-state` was created with preliminary frontend/backend code edits and `tests/test_game_end_state.py`. No pull request, CI or device validation for that branch; it is excluded from canonical D4b PR #17. Do not mark stale-state regression fixed or merge WIP automatically.
- **This checkpoint changes documentation only on the canonical D4b branch**; no new code changes, local test execution or external Claude audit. Before audit, latest confirmed D4b code regression was 303 Python and 18 Node tests in [Windows Actions 44362005497](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44362005497); latest pre-audit documentation checkpoint [44364164792](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44364164792) passed. Recheck new workflow at audit documentation head rather than claiming success early.
- Next: Claude A-FUNC audit and prioritized P0 correction plan, then small follow-up repair PRs/Windows evidence. **D5a** remains the next previously planned implementation after the audit intake/triage; **D5c** later desktop visual UX audit remains distinct. `main` untouched; PR #17 remains draft stacked on #16.


## 2026-11-18 Europe/Lisbon — M1/P0.1 poll-loop regression harness (draft PR #20)

- Branch `test/m1-p01-poll-tick-harness` was created from the approved D4b baseline `9832fb0`, targeting `feat/desktop-overlay-preview-apply-d4b`; draft [PR #20](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/20). The separate documentation-only draft PR #18 stays intact; main was not touched.
- `backend/api/server.py`: extracted a single `poll_tick(state, deps, now)`, injecting LCDA/LCU, OCR watcher, broadcast, serializer and monotonic clock while preserving existing polling behavior. `tests/test_poll_tick_m1.py`: 3 ordinary deterministic tests plus `xfail(strict=True)` for AUD-03a (level-up falsely treated as augment pick), AUD-07 (one transient LCDA miss ends game), AUD-03d (damage closes OCR window). These xfails are observed defects, NOT fixes.
- First headless Windows Actions run [44393987021](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44393987021) failed during collection due a malformed nested OCR `except` in the initial refactor; repaired extraction and expanded the level-up fixture to include the complete inference tick sequence.
- Verified corrected code/test SHA `646161378a1b742074fbe947ba8fb510f13b95ca`: [Windows Actions 44394538148](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44394538148) succeeded: `python -m pytest -q` **306 passed, 3 xfailed, 1 warning**; Node **18 passed, 0 failed**, all configured syntax checks passed. Documentation-head CI follows separately.
- Real League session, screen OCR, native Qt and device matrix: **not executed**. Next: P0.2 only after P0.1 documentation-head gate; never confuse CI Windows runner with actual gameplay evidence.


## 2026-11-18 Europe/Lisbon — M1/P0.2 frontend DOM/WebSocket regression harness (draft PR #21)

- Branch `test/m1-p02-frontend-message-harness`, stacked on P0.1 PR #20; draft [PR #21](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/21). `frontend/app.js` now exposes its existing message and renderer callbacks only for CommonJS testing, avoiding a production boot during VM tests. Added `tests/js/overlay-messages.test.cjs` (DOM and WebSocket mocks) and the CI command to run it.
- Targeted checks verify message paths for game end, no game, disconnect/reconnect, fresh champion updates and OCR rendering without a browser. Four executed `TODO` tests demonstrate desired future behavior still missing: clearing header and old snapshot on game end/no game, disconnect stale-state invalidation and clearing old augment confirmation on champion change (AUD-05, AUD-06). No F1–F5 application fixes.
- [Actions 44395754449](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44395754449) on `f736e14be7b6b53cb4fc59619c3408535b78af42`: **306 Python passed + 3 strict xfailed (1 warning); 24 JS passed, 4 TODO, 0 failed**; syntax checks passed. CI headless Windows runner, not real League Windows playtest. Verify final documentation commit separately. No merge.
