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

