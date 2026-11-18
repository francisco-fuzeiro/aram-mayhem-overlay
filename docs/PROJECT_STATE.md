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
| [#6](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/6) | `feat/team-threat-coverage` | PR #5 branch | Player-inclusive ally roles, catalog coverage safeguards and visible enemy inventory fallback |
| [#7](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/7) | `feat/selectable-build-paths` | PR #6 branch | Selectable build style, saved UI preference, inventory-safe next item, WebSocket contract |
| [#8](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/8) | `feat/late-game-boots-replacement` | PR #7 branch | Optional full-inventory boots-to-mobility item swap with conservative stat comparison |
| [#9](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/9) | `fix/windows-overlay-transparency-fallback` | PR #8 branch | Explicit Qt fallback for Windows transparency; pywebview HWND fix |
| [#10](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/10) | `feat/qt-overlay-window-controls` | PR #9 branch | Hide/show/quit buttons, Alt+H restore, Qt system tray menu |

**Active working head: `feat/qt-overlay-window-controls` (draft PR #10)**, stacked on PR #9 -> PR #8 -> PR #7 -> PR #6 -> PR #5 -> PR #4 -> PR #3 -> PR #2 -> PR #1. Follow the dependency order; none of these draft changes should be assumed merged into `main`.

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
- **Validation pending**: Windows Actions `pytest -q` and JS check, and real Windows Qt button/hotkey/tray behavior. The previously observed 178 Windows tests belong to PR #9, not this branch.
- Next user verification: `python -m backend.overlay --renderer qt`, Alt+O then click − and restore with Alt+H, finally test × and tray restore.

## Automated verification (as last observed)

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

## Highest-priority remaining work

1. **Qt desktop transparency is validated.** Verify PR #10 native hide/show/quit, Alt+H recovery and tray on Windows; then verify over League in borderless mode, champion select, LCDA, OCR and build updates.
2. Review and test enemy/ally parsing against actual LCDA samples on Windows; no unsupported invisible opponent detection.
3. Validate Mayhem item availability, inventory limits, components, multi-boot/exclusive rules, quest rewards, and shop buyability. Current item matching is **heuristic**, not purchase-path validated.
4. Improve threat accuracy: champion damage-source metadata vs generic AP/AD vector; enemy resistance items must be recognized from verified item properties, not merely unverified tags. Expose low-confidence cases.
5. Improve synergy model for augment-specific effects, quests, abilities, duplicate/redundant interactions and chosen augment history; calibrate against real matches.
6. Validate the new selectable build-style preference in the actual Windows overlay and confirm the selected path updates after purchases and augment picks.
7. Patch/version-aware data ingestion and confidence; ensure only ARAM Mayhem games are counted (verify actual queue/mode identifiers).
8. Test champion select, augment OCR, build updates, click-through and resize live on user's Windows; keep interface polishing last.

## How to work in a new chat

1. Read **this file** and `docs/DEVELOPMENT_LOG.md` from the connected private GitHub repository.
2. Check PR #10 head, its stacked dependencies and GitHub Actions live; inspect code before assuming this snapshot is perfectly current.
3. Continue from PR #10 through the GitHub connector in a new stacked feature branch / draft PR; do not directly edit the user's Windows `D:` path unless confirmed access exists.
4. Write English code, English UI and English documentation; answer the user in PT-PT.
5. After a completed task, update this current-state snapshot and append a dated, verifiable entry to the development log. Record tests as `passed`, `failed`, or `not run`, never inferred.
6. Request Windows in-game testing only when needed; provide exact PowerShell commands to fetch/checkout the branch and run tests/overlay.
