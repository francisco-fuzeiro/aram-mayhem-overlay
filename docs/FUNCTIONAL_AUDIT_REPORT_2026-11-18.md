# ARAM Oracle — A-FUNC Functional Code Audit Report (2026-11-18)

**Scope:** `A-FUNC.1` (defect ledger) and `A-FUNC.2` (proposed fix plan). Audit only: **no application code was changed, nothing was merged, `main` is untouched.**
**Audited head:** `feat/desktop-overlay-preview-apply-d4b` @ `9832fb0` (draft PR #17). The user's local Windows folder (`D:\Overlay ARAM\aram-oracle`) was compared file-by-file with this head: `backend/` and `frontend/` sources are identical apart from CRLF line endings, so the playtest artefacts below were produced by this code.
**Reviewed but not trusted as a fix:** `fix/postgame-stale-match-state` @ `cc4aee7` (see §6).

## 1. What was actually executed vs. what still needs Windows

| Check | Result | Where |
| --- | --- | --- |
| Python suite on audited head (Linux, Python 3.13) | **303 passed** | `python -m pytest -q` |
| JavaScript Settings tests + `node --check` of the three entry points | **18 passed, 0 failed**; syntax OK | `node --test tests/js/settings.test.cjs` |
| WIP branch `fix/postgame-stale-match-state` suite | **1 failed, 303 passed** (`test_game_end_state.py`) | §6 |
| Scoring reproduction with the user's real `augments_16.23.1.json` cache | Real offers reproduce **2.1 / 2.1 / 2.1 + reroll advice** | §3, AUD-04 |
| Stat-delta reproduction (simulated Neeko level-up) | Level-up auto-"chooses" **Donation at 0.998 confidence** | AUD-03a |
| Hash-distance measurement on the user's 18 saved playtest frames | Single-card rerolls = **3–6 bits** vs threshold **30**; dialogs = 57 bits | AUD-03b |
| OCR (Tesseract) execution | **Not run** (no Tesseract/League in the audit container). OCR conclusions come from the annotated frames the app itself saved during the playtest. | — |
| Live League / LCDA / LCU / Qt / DPI / multi-monitor | **Not run.** Everything marked *Windows evidence* below remains open. | — |

Unit tests passing does **not** approve any live feature: there are **no tests at all** for `ScreenWatcher`, `_poll_game_loop`, the stat-delta selection path, or `frontend/app.js` message handling (§5).

### Evidence used

The app's own debug output from the playtest (`data/screenshots/`, 2026-11-18 18:01–18:09 Europe/Lisbon, 2560×1440, League **windowed** with a title bar). These frames contain unrelated desktop content (a ChatGPT conversation, League client friends list) and **must not be committed**; §5 specifies redacted, crop-only fixtures instead.

| Frame | Shows |
| --- | --- |
| `ocr_1795024908` | Crop of a **ChatGPT window**, not League. Annotated matches: **Restart 80%, escAPADe 77%, Mercy 75%** — the exact wrong offer reported in F-AUD-02. |
| `ocr_1795024923/38` | Real offer Impassable / Upgrade Stormsurge / Tooth Fairy, correctly matched (100/100/100 and 100/100/91). |
| `ocr_1795025002` | AFK-warning dialog over the cards; matched a catalog placeholder **"Augment 405" (77%)**. |
| `ocr_1795025207` | League **client home page** (user alt-tabbed mid-game); matched **BEES! / Bouncing Bees / BONK!**. |
| `full_1795025135` + `region_1795025142` | Screen shows **Impassable / Shark Bait / Donation**; overlay panel still lists **Donation / Impassable / Upgrade Stormsurge**, progress **1/4**, and "No augment choices to evaluate" although the player has **not picked** (card-1 reroll still available, offer still open). |
| `ocr_1795025367` | Network/AFK disconnect dialog; third slot filled by fuzzy junk **"Get Excited!" (84%)**. |

## 2. Defect ledger

Confidence marks: **[Confirmed]** = reproduced or directly visible in code + artefact; **[Likely]** = strong inference, not reproduced live; **[Hypothesis]** = needs Windows evidence.

### P0 — recommendations wrong or unreliable

#### AUD-02a — Capture is not bound to the League window (F-AUD-02) — [Confirmed]
- **Files:** `backend/collectors/screen_ocr.py:333-369` (`capture_augment_region` grabs a fixed fraction of `mss` monitor 1), `:83-101` (fractions of the *monitor*, not of the game client rect).
- **Cause:** No foreground-window check and no League-window geometry. When League is not focused, windowed, or on another monitor, whatever is on screen is OCR'd. `ocr_1795024908` proves the escAPAde/Restart/Mercy offer came from ChatGPT text.
- **User impact:** Confident scores for augments that were never offered; screenshots of private desktop content saved to disk.
- **Fix:** Before any capture, resolve the League game window (read-only Win32: `FindWindow`/`GetForegroundWindow`/`GetClientRect`/`ClientToScreen` via `ctypes`). If it is not the foreground window, return `not_focused` and do not OCR. Compute card regions from the **client rect**, not the monitor.
- **Tests:** pure geometry tests (client rect at 1080p/1440p, windowed offset, second monitor with negative origin); watcher returns `not_focused` and never calls OCR when a fake foreground check is false.
- **Windows evidence:** League windowed + borderless at 1080p and 1440p; alt-tab to another app while an offer is open → overlay shows "League not in focus", no new matches, no non-League screenshots saved.

#### AUD-02b — Matcher accepts arbitrary words and loses card positions (F-AUD-02, F-AUD-07) — [Confirmed]
- **Files:** `screen_ocr.py:440-463` (one `--psm 6` pass over the whole three-card crop), `:471-549` (`match_augments`: every 1–5-word fragment of every line, `token_sort_ratio`, threshold **65**, results sorted by score then name, truncated to 3).
- **Cause:** Description text, dialogs and other apps produce fragments that fuzzy-match short catalog names (31 names ≤ 6 chars, e.g. Mercy, POWER, RISE, DOOM, Deft). With fewer than three strong hits, weak matches fill the remaining slots (`ocr_1795025367`: "Get Excited!" 84%). The result order is score order, so **left/centre/right is unknowable** — badges above cards cannot be built on this output.
- **Fix:** Slot-based recognition: crop the three **title bands** individually, OCR each with `--psm 7` (single line), match only against the Mayhem catalog, accept only near-exact matches (e.g. ≥ 90 with a uniqueness margin over the runner-up), otherwise mark the slot `unknown`. Never fill a slot from another slot's text.
- **Tests:** fixture crops for every slot of the observed offers; description-only text never matches; a dialog-covered slot yields `unknown`, not a neighbour's name; output always has exactly three ordered slots.
- **Windows evidence:** 10 consecutive offers with per-slot screenshots in a debug folder; 30/30 slots correct or explicitly `unknown`, zero wrong names.

#### AUD-03a — Level-ups are mistaken for augment picks (F-AUD-03, F-AUD-06) — [Confirmed in code + reproduction; live sequence Likely]
- **Files:** `backend/api/server.py:762-776` (passive path: any stat change while the scan window is open sets `awaiting_stat_delta`), `:755-760` → `:894-952` (`_try_stat_delta_match` auto-confirms at confidence ≥ 0.3, clears `augment_choices`, closes the scan window, resets the watcher); `backend/engine/augment_detector.py:89-93` (`has_stats_changed`: ‖Δ‖ ≥ 2.0), `:143-175` (cosine match).
- **Cause:** ARAM gives passive XP. A level-up raises maxHealth/AD/armor/MR far beyond the 2.0 threshold, so it counts as "augment chosen". Reproduction: a Neeko-like level-up with Impassable/Upgrade Stormsurge/Donation offered auto-confirms **Donation at 0.998** (Donation is wrongly tagged `hp: 0.3`, AUD-04c). Item purchases trigger the same path. With no matching candidate, the player is instead asked "Which augment did you pick?" while still choosing.
- **Matches the artefact:** progress shows **1/4** although no pick was made; `augment_choices` is empty ("No augment choices to evaluate") while the separate "Detected augments" list is stale. After the false confirm the scan window stays closed until the next threshold level or respawn, so the Upgrade Stormsurge → Shark Bait reroll was never scanned.
- **User impact:** Phantom picks, missed rerolls, overlap penalties computed from augments the player does not own, wrong build input.
- **Fix:** A pick may only be inferred from **offer disappearance** (the card UI is gone for N stable frames) — never from stat change alone. If stats are used, compare only ticks at the same level with no inventory change, and never auto-confirm above a "suggest" level; ask the user once the offer is gone.
- **Tests:** level-up during an open offer → no pick, offer kept; item purchase → no pick; offer disappears with no level change → confirmation prompt; offer disappears plus Donation-like zero-stat → no auto-confirm.
- **Windows evidence:** Hold an offer in fountain across two level-ups and one purchase; progress stays 0/4 and the offer stays scored.

#### AUD-03b — Full-crop average hash cannot see a single-card reroll (F-AUD-03) — [Confirmed by measurement]
- **Files:** `screen_ocr.py:72-77` (16×16 average hash, threshold 30), `:162-210` (`ScreenWatcher.check`).
- **Measured on the user's frames** (annotation area masked): Tooth Fairy→Donation **5**, Upgrade Stormsurge→Shark Bait **3**, Impassable→Get Jinxed **6** bits; AFK dialog appearing **57**. Real rerolls sit far below the threshold; dialogs, alt-tab and thumbnails sit far above it. The "reroll_detected" frames in the playtest were all triggered by dialogs or screen switches, not by rerolls. **Per-card title-band hashes** of the missed reroll give **left 0 / middle 65 / right 0**.
- **Fix:** One hash per title band; a band whose hash changes is re-OCR'd alone; unchanged slots keep their id and score.
- **Tests:** fixture pairs above as regression data (band distance > threshold only for the changed slot; whole-crop noise does not trigger).
- **Windows evidence:** Reroll each slot once, then the same slot twice in a row; each change reflected within ≤ 2 poll ticks without Alt+O.

#### AUD-03c — Reroll path never retries after a failed OCR — [Confirmed in code]
- **Files:** `screen_ocr.py:207-210` sets `_frozen_hash = current_hash` *before* OCR; `:257-267` returns `unchanged` when text has no match ("retrying next tick" is not true: the next tick's hash equals the frozen one). Same for `no_text`: `:226-236` only counts towards "disappeared" when OCR runs, so disappearance needs two separate hash changes.
- **Impact:** Old choices survive indefinitely after an unreadable reroll (F-AUD-03 "inconsistent/old offer").
- **Fix:** Only freeze a slot hash after a stable successful read (2 consistent reads); otherwise keep the slot `pending` and retry with bounded backoff; on failure, clear that slot's score instead of keeping the old one.
- **Tests:** unmatched text after reroll → slot becomes `unknown`, old id removed; retry happens next tick.

#### AUD-03d — Scan window closes on any damage — [Confirmed in code; impact Likely]
- **Files:** `server.py:778-791` closes the window when `health_pct < 0.98`, evaluated on the same tick it opens (`:730-749`).
- **Impact:** Thresholds 7/11/15 are often reached in combat: the window opens and closes in one tick, so no automatic OCR happens for that offer. Mayhem offers persist until picked (the playtest offer stayed open for 6+ minutes), so health is not a valid "offer gone" signal.
- **Fix:** Window lifetime is driven by offer visibility (AUD-02b/03b), not health.
- **Tests:** level 7 reached at 60% HP → OCR still runs until the cards disappear.

#### AUD-04 — Uniform 2.1/10 and false reroll advice (F-AUD-04) — [Confirmed, reproduced]
- **Files:** `backend/engine/augment_rating.py:227` (`synergy = 10·(1−e^(−max(0,raw)/1.2))`), `:228-231` (context 5.0 when no enemy data); `backend/engine/composite_score.py:330-336` (`(0.35·0 + 0.25·5)/0.60 = 2.083 → 2.1`); `backend/engine/ranker.py:104,149-165` (reroll if best < 4.0).
- **Reproduction (user's cache, Neeko, no visible enemies):** Impassable 2.1 / Tooth Fairy 2.1 / Upgrade Stormsurge 2.1 → `suggest_reroll=True`; Donation 2.2 / Impassable 2.1 / Shark Bait 2.1 → reroll. Across the catalog for Neeko **334/600 (56%) score exactly 2.1** and 504/600 (84%) score below the reroll threshold; Jinx 363/600; Sona 334/600. Negative raw scores are clamped to the same 0 synergy, so "bad fit" and "no data" are indistinguishable.
- **Causes (data):**
  - **AUD-04a [Confirmed]:** 276/600 catalog entries have an all-zero contribution vector and 260 have no description. Descriptions are borrowed from the **Arena** `en_us.json` by name (`backend/static_data/loader.py:385-397,417`), so Mayhem-only augments (Shark Bait, Tooth Fairy, Get Jinxed…) get none.
  - **AUD-04b [Confirmed]:** substring keyword matching (`loader.py:457-466`) gives "Upgr**ad**e Stormsurge" an `ad` contribution because `"AD"` is found inside "Upgrade".
  - **AUD-04c [Confirmed]:** curated name hint gives Donation (`Get 1750 Gold`) `hp: 0.3`.
  - **AUD-04d [Confirmed]:** the catalog is the Arena `cherry-augments.json` (600 entries, **121 duplicate names**, one placeholder "Augment 405"); it is not filtered to Mayhem, which also widens the OCR false-match space.
  - **AUD-04e [Confirmed]:** `confidence` is always 0.0 and `sample_size` 0 while empirical evidence is disabled, yet the UI shows a precise `x.x/10` with no "unrated" state (`frontend/app.js:466`).
- **Fix:** Add per-augment coverage (`modelled: bool`, provenance) to the catalog. Unmodelled → `score: null`, label "Not rated — insufficient data". Reroll advice only when all three slots are identified **and** modelled, with an explicit reason. Fix word-boundary keyword parsing; Mayhem-only, deduplicated catalog; reject placeholder names. Calibrating the score model is P1 and is a separate phase.
- **Tests:** zero-contribution augment → `null` score, never 2.1; an offer with ≥ 1 unrated slot never suggests reroll; "Upgrade Stormsurge" parses no AD; catalog has no duplicate normalized names and no `Augment \d+` names.
- **Windows evidence:** The same three real offers display "Not rated" for unmodelled cards and no reroll banner.

#### AUD-05 — Stale champion/time/gold after the match (F-AUD-05) — [Confirmed in code]
- **Files:** `frontend/app.js:167-229` (`no_game`, `game_ended`, `champ_select` never clear the header), `:324-359` (header is written only from `update`), `:593-620` (the "Detected augments" list is only replaced by the next `ocr_result`); `server.py:849-868` (backend keeps match state for up to 300 s in post-game).
- **Fix:** One `clearMatchDisplayState()` (the WIP version is a reasonable start, §6) on `game_ended`, `no_game`, `champ_select`, new match identity; on WebSocket close, mark panels **stale** rather than silently keeping them.
- **Tests:** DOM-stub tests for `app.js` (none exist today): after `game_ended` the header shows placeholders; after reconnect no previous champion is shown until a fresh `update`.
- **Windows evidence:** Finish a custom game, return to client, start a second game with a different champion: no Neeko/time/gold carry-over at any point.

#### AUD-06 — No offer identity, generation or match identity (F-AUD-06) — [Confirmed in code]
- **Files:** `server.py:36-102` (`GameState` has no offer object, no generation counter), `:585-600` (manual `scan_augments` runs OCR in a thread concurrently with the watcher at `:801-826`; last finisher wins), `:806-817` vs `:829-838` (two independent sources — `ocr_result` and `update` — feed two different UI lists), `:1024-1039` (recommendations sorted by score, no slot), `backend/collectors/lcda.py:80` (`gameData.gameId` is used as match id; LCDA's `gameData` is not known to contain it, so it is **[Likely]** always `"unknown"`), `server.py:541-553` (`set_augment_choices` accepts unvalidated ids).
- **Impact:** Out-of-order results, reordering, the "Detected" list disagreeing with scores (seen in `full_1795025135`), and possible cross-match leakage when a new game starts within the 300 s post-game window without a readable Champion Select.
- **Fix:** A single `Offer {match_id, generation, slots[3]: {augment_id|null, confidence, band_hash, state}}` owned by `GameState`; every mutation increments `generation`; one serial OCR executor (manual scan goes through the same queue); every outbound message carries `match_id` + `generation`; the client drops older generations; recommendations are emitted **per slot, in slot order**. Match id from LCU `/lol-gameflow/v1/session` (read-only), fallback to a hash of (riotId, champion) plus a `gameTime` regression check.
- **Tests:** two OCR results delivered out of order → only the newer generation is applied; new match id → offer and picks reset; manual scan during auto scan → serialized.

#### AUD-01 — Custom match stays on "Waiting for game..." (F-AUD-01) — [Hypothesis; partly Confirmed]
- **Confirmed contributors:**
  - `server.py:833-838`: when `Pipeline.run` returns `None` (`backend/workflow/pipeline.py:15-17`, champion not resolved) **nothing is broadcast**, so the client stays on whatever it last showed, typically "Waiting for game..." (`frontend/index.html:34`).
  - `lcda.py:42-48`: any non-200, timeout (1 s) or JSON error is collapsed to `None`; the poll loop cannot distinguish "no game", "loading" and "LCDA slow" and logs nothing.
  - `server.py:704`: `get_raw_game_data()` is a **blocking** HTTP call on the asyncio event loop.
- **Hypotheses to verify:** (H1) LCDA returns 404/timeout during the first seconds while the first Mayhem offer is already visible; (H2) `activePlayer.summonerName` vs `allPlayers[].summonerName` mismatch after Riot ID changes leaves `champion_id` empty (`lcda.py:69-72`) — match by `riotId` first; (H3) event-loop stalls delay ticks. Custom games are **not** excluded anywhere in code.
- **Fix:** Explicit status machine broadcast to the client (`client_idle`, `champ_select`, `loading`, `live_data_unavailable(retrying)`, `in_game`, `post_game`), driven by LCU `gameflow-phase` + LCDA; log status code/exception class on every transition; run LCDA off the loop; broadcast `champion_unresolved` instead of silence.
- **Windows evidence:** Log excerpt from a custom Mayhem start showing the per-tick LCDA status from loading screen to first offer; overlay leaves "Waiting" within ≤ 2 ticks of LCDA 200.

### P1

| ID | Finding | Files | Status | Fix |
| --- | --- | --- | --- | --- |
| AUD-07 | A single LCDA miss marks the game ended (`had_game_last_tick` → `game_ended` on the first `None`). Today state survives because reset waits 300 s; the WIP branch would wipe picks on one timeout (§6). | `server.py:850-857` | Confirmed | Debounce: ≥ 3 consecutive misses / ≥ 6 s, or LCU gameflow says the game is over. |
| AUD-08 | **Cross-origin access:** no `Origin`/`Host` check on `/ws/game` or REST. Any web page the user visits can open `ws://127.0.0.1:8765/ws/game`, read live state and send commands, or fire a body-less `POST /api/bug-report` (posts a GitHub issue if a token is configured) and `/api/history/import`. Loopback binding does not prevent this. | `server.py:497-511, 433-491, 315-322` | Confirmed in code | Allow-list `Origin` (overlay/settings pages, Qt), validate `Host` (DNS rebinding), per-launch token for state-changing calls. |
| AUD-09 | **Privacy:** every OCR pass saves annotated PNGs, and manual scans save the **full screen**, including non-League windows (the playtest saved a ChatGPT conversation and a friends list). `/api/ocr/screenshots` serves them. Under PyInstaller they land in the temp `_MEIPASS` tree. | `screen_ocr.py:52, 202-203, 244-245, 566-569`; `server.py:367-386` | Confirmed | Off by default (debug toggle), crop-only, only when League is focused, user-data directory, retention limit. |
| AUD-10 | Catalog cache poisoning: if DDragon or CDragon fails, an **empty** `augments_<version>.json` (or `augments_unknown.json`) is written and reloaded forever. Cache key is the DDragon version while the source is CDragon `latest`. | `loader.py:362-441` | Confirmed in code | Never cache empty/failed fetches; key by content hash + patch; validate counts. |
| AUD-11 | Unvalidated WS inputs: `set_augment_choices` (any strings), `choose_augment` (no cap of 4, ids not checked), `toggle_ocr` (non-bool). REST `/api/ocr/scan` mutates state outside the lock. | `server.py:541-627, 341-364` | Confirmed | Validate ids against catalog, cap counts, bool coercion, lock. |
| AUD-12 | Broadcasts are awaited while holding `game_state.lock`; a slow client stalls the poll loop. | `server.py:805-817, 946-952` | Confirmed in code | Collect messages under the lock, send after release. |
| AUD-13 | Score model quality beyond coverage: synergy saturates (max ≈ 7.9 without context), context only moves ±4 via `tanh`, overlap penalty is tiny, role weights are hand-set, no Mayhem-specific mechanics. Not calibrated on any outcome data. | `augment_rating.py`, `scoring.py`, `role_weights.py` | Confirmed (design) | Separate calibration phase after P0; publish provenance per score. |
| AUD-14 | The app runs in every queue: no game-mode check before OCR/scoring. | `server.py:704-838` | Confirmed | Gate on mode reported by LCU/LCDA (exact Mayhem mode string to be captured from a real LCDA sample, not guessed). |

### P2

| ID | Finding | Files |
| --- | --- | --- |
| AUD-15 | `preprocess_for_ocr` builds a Python list of every pixel (~720k at 1440p) per pass; use `ImageStat`. | `screen_ocr.py:432-435` |
| AUD-16 | Manual scan pokes the private `screen_watcher._frozen_hash`. | `server.py:594` |
| AUD-17 | `asyncio.get_event_loop()` inside a coroutine (deprecated); use `time.monotonic()`. | `server.py:855, 860` |
| AUD-18 | LCU discovery may spawn PowerShell (3 s timeout) on every no-game tick when the lockfile is not in a default path. Cache the discovered path. | `lcu.py:155-195` |
| AUD-19 | The playtest itself hit the AFK kick (6+ minutes in fountain). Future acceptance scripts must include periodic movement. | test procedure |

## 3. Riot policy and licensing notes

- Read-only LCU/LCDA usage, no input automation, no auto-pick/buy: consistent with `AGENTS.md`. **[Confirmed in code]**
- Screen OCR of the player's own screen is not something this audit can declare Riot-approved. **[Assumption]** Keep it read-only, local, focused-window-only (AUD-02a) and do not persist screenshots by default (AUD-09).
- `experimental_augment_evidence` is disabled by default (`backend/config.py:54`); keep it so. A 0–10 number without evidence must not look like a statistical rating (AUD-04e).
- Third-party reuse notices in `screen_ocr.py:478-481` and `lcu.py:157-159` point to `THIRD_PARTY_NOTICES.md`; the code reviewed does not copy Mayhem Advisor. **[Likely]**

## 4. Root-cause chain of the playtest (combined reading)

1. Auto-scan started while a ChatGPT window covered the screen → **escAPAde / Restart / Mercy** (AUD-02a/02b). **[Confirmed]**
2. When League was in front, the first offer was read correctly; the scores were **2.1 ×3 + reroll** because those augments are unmodelled (AUD-04). **[Confirmed]**
3. Passive XP level-ups were treated as a pick: **Donation auto-confirmed**, choices cleared, scan window closed (AUD-03a). **[Likely]** (reproduced offline; consistent with 1/4 and the empty recommendation list in `full_1795025135`).
4. With the window closed and a whole-crop hash that cannot see one-card changes, the Upgrade Stormsurge → Shark Bait reroll was missed; only Alt+O → Scan found it (AUD-03b/03d). **[Confirmed]** (measured 3 bits).
5. After the AFK disconnect, the client never cleared the header (AUD-05). **[Confirmed]**

## 5. Missing fixtures and test harness

- **Redacted offer fixtures:** crop only the three title bands (no HUD, chat, names or desktop) from real 1080p and 1440p frames: one full offer, each single-slot reroll, two consecutive rerolls of the same slot, dialog-occluded slot, non-League foreground. Store under `tests/fixtures/ocr/` with a JSON truth file `{slot: augment_id|null}`.
- **Poll-loop harness:** inject sequences of fake LCDA payloads/`None`, LCU phase and OCR results, then drive ticks with a fake clock; assert broadcast sequence and state (`_poll_game_loop` currently has zero tests; it also only polls when a WS client is registered, which the WIP test missed).
- **`app.js` DOM-stub tests** like the existing `settings.test.cjs`, for `handleMessage` transitions.
- **Catalog contract tests:** Mayhem-only, no duplicate normalized names, no placeholders, coverage report (share of modelled augments) printed in CI.
- **Structured logs:** per tick LCDA status, gameflow phase, offer generation, per-slot OCR text/match/confidence. Needed for every Windows acceptance below.

## 6. WIP branch `fix/postgame-stale-match-state` — review, not a fix

- **CI-equivalent run:** `tests/test_game_end_state.py` **fails** (`messages == []`): `_poll_game_loop` skips the tick because the test registers no WebSocket client (`server.py:702-703`).
- **Regression risk:** it calls `game_state.reset()` on the **first** LCDA `None` (`server.py:853` on the branch). One 1-second timeout mid-match would wipe all picked augments and the offer. Must be combined with AUD-07 debounce and match identity (AUD-06).
- **Frontend:** `clearMatchDisplayState()` is a reasonable basis for AUD-05, but clearing everything on `ws.onclose` hides state during a two-second reconnect instead of marking it stale; no automated test exercises it.
- **Verdict:** reusable as input for FX-6; do not merge as is.

## 7. Proposed fix plan — for approval (A-FUNC.2)

Small draft PRs stacked on #17, each independently revertible (revert the PR; no data migrations). Order = severity × dependency. **Nothing below is approved yet.**

| Phase | Severity | Depends on | Scope (only) | Automated gate | Windows gate |
| --- | --- | --- | --- | --- | --- |
| **FX-0 Harness + logs** | enabler | — | Poll-loop harness, `app.js` DOM-stub harness, redacted fixture format, structured logs. No behaviour change. | New harness tests green; full suite unchanged. | One logged custom-match session. |
| **FX-1 Stop phantom picks** | P0 | FX-0 | Remove stat-change-as-pick and the health close rule (AUD-03a/03d). | Level-up/purchase/damage regression tests. | Hold offer across 2 level-ups + 1 purchase: 0/4, offer kept. |
| **FX-2 League-window capture gate** | P0 | FX-0 | Foreground + client-rect capture; no OCR/screenshot when not focused; screenshots off by default (AUD-02a, AUD-09). | Geometry + gating tests. | Alt-tab with open offer; windowed/borderless 1080p/1440p. |
| **FX-3 Slot-based recognition** | P0 | FX-2 | Three title bands, `psm 7`, strict per-slot match, per-band hash, retry until stable (AUD-02b, 03b, 03c). | Fixture suite: 100% slots correct or `unknown`; band-hash pairs. | 10 offers / 30 slots, each slot rerolled, double reroll. |
| **FX-4 Offer generation** | P0 | FX-3 | `Offer` model, generation + match id in messages, serial OCR, per-slot recommendations, single UI source (AUD-06, AUD-11). | Out-of-order, concurrency, reset tests. | No stale "Detected" list; scores follow rerolls. |
| **FX-5 Honest scores + catalog** | P0 | FX-0 | `modelled` flag, `null` score/"Not rated", reroll gating, keyword word boundaries, Mayhem-only dedup catalog, no empty-cache poisoning (AUD-04, AUD-10). | Catalog contract + scoring tests. | Same offers show "Not rated"; no false reroll banner. |
| **FX-6 Match lifecycle** | P0 | FX-0 | LCU gameflow + LCDA status machine, debounce, match identity, client clear/stale states, LCDA off the event loop, `champion_unresolved` (AUD-01, 05, 07, 12). Reuses WIP ideas. | Harness: transient miss, real end, new game, reconnect. | Custom start → no long "Waiting"; end → clean; second game clean. |
| **FX-7 Local API hardening** | P1 | — | Origin/Host allow-list, token for state-changing calls, input validation (AUD-08, AUD-11). | Rejected foreign origin tests. | Overlay + Settings still work in Qt. |
| **FX-8 Score calibration** | P1 | FX-5 | Curated Mayhem augment tags, provenance, model review (AUD-13). | Differentiated scores for fixture offers. | User judgement on 3 real offers. |

FX-1, FX-2, FX-5 and FX-6 are independent of each other after FX-0; FX-3 needs FX-2, FX-4 needs FX-3. Then **A-FUNC.3** (full Windows acceptance), then the previously planned **D5a**. **F-AUD-07** card-aligned badges stay blocked until FX-3 + FX-4 pass on Windows (A-FUNC.4).

### Suggested approval question

Approve FX-0 → FX-1 as the first two PRs? FX-1 is small, low-risk, and removes the cascade that produced the phantom pick and the missed reroll.
