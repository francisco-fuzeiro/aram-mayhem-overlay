# Overlay LoL — Project State / Chat Handoff

> **Canonical handoff for future ChatGPT project conversations.**
> Update this document after meaningful development steps, test runs, architectural decisions, and before switching chats.
> Log each dated change separately in `docs/DEVELOPMENT_LOG.md`.

Last authored: **2026-11-18**, Europe/Lisbon. Code and product UI must remain **English**; user conversation is **European Portuguese**.

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

**Continue on `feat/dynamic-team-threats`**, unless its PR is merged and a new branch is appropriate. Follow the dependency order; never assume all stacked drafts have been merged.

## Current work: PR #6 — team and enemy observation coverage

- Branch `feat/team-threat-coverage`, stacked on PR #5 `feat/dynamic-team-threats`; `main` is unchanged.
- The current champion now counts in allied role coverage (exactly once), so allied deficits include the player's own capabilities.
- Enemy inventories are examined even when an enemy champion is not present in the catalog. `visible_items` now means the observed item count; `unknown_items` indicates IDs lacking our item metadata.
- High threat confidence requires all visible enemy champions to be recognized and every observed item to resolve, as well as minimum roster/item coverage.
- New deterministic tests cover partial catalog coverage, item observation without a known champion, and including the player in allied roles.
- Validation: **not run** for this branch's new commits until the draft PR's Windows CI completes. Windows in-game sample remains outstanding.
- Remaining risks: DataDragon tags may not correspond to verified item stats; role vectors approximate threat types; actual LCDA roster must be checked on Windows.

## Automated verification (as last observed)

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

## Highest-priority remaining work

1. Re-check PR #5 latest CI and fix failures, especially after `tests/test_dynamic_team_pipeline.py`.
2. Review and test enemy/ally parsing against actual LCDA samples on Windows; no unsupported invisible opponent detection.
3. Validate Mayhem item availability, inventory limits, components, multi-boot/exclusive rules, quest rewards, and shop buyability. Current item matching is **heuristic**, not purchase-path validated.
4. Improve threat accuracy: champion damage-source metadata vs generic AP/AD vector; enemy resistance items must be recognized from verified item properties, not merely unverified tags. Expose low-confidence cases.
5. Improve synergy model for augment-specific effects, quests, abilities, duplicate/redundant interactions and chosen augment history; calibrate against real matches.
6. Make the three item paths actually selectable and persist player preferences; currently they are displayed as alternatives, not a committed style selector.
7. Patch/version-aware data ingestion and confidence; ensure only ARAM Mayhem games are counted (verify actual queue/mode identifiers).
8. Test champion select, augment OCR, build updates, click-through and resize live on user's Windows; keep interface polishing last.

## How to work in a new chat

1. Read **this file** and `docs/DEVELOPMENT_LOG.md` from the connected private GitHub repository.
2. Check PR #5 head + GitHub Actions live; inspect code before assuming log is perfectly current.
3. Continue through GitHub connector on a separate feature branch / draft PR; do not directly edit the user's Windows `D:` path unless confirmed access exists.
4. Write English code, English UI and English documentation; answer the user in PT-PT.
5. After a completed task, update this current-state snapshot and append a dated, verifiable entry to the development log. Record tests as `passed`, `failed`, or `not run`, never inferred.
6. Request Windows in-game testing only when needed; provide exact PowerShell commands to fetch/checkout the branch and run tests/overlay.
