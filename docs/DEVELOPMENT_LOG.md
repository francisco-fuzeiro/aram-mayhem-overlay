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
