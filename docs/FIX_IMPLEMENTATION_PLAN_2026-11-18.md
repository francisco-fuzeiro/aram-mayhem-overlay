# ARAM Oracle — Functional Fix Implementation Plan (proposed 2026-11-18)

**Status: proposal, not approved, nothing implemented.** This plan splits the FX-0…FX-8 outline of [FUNCTIONAL_AUDIT_REPORT_2026-11-18.md](FUNCTIONAL_AUDIT_REPORT_2026-11-18.md) §7 into small phases. It covers every functional defect in that report (AUD-01…AUD-19). Visual work (F-AUD-07 card badges, D5c) stays blocked until milestone M7 passes.

## Rules for every phase

- **One phase = one branch = one small draft PR**, stacked on the previous phase branch (the first one stacks on D4b PR #17). Never merge to `main` without explicit approval.
- **Size target:** S ≈ ≤ 150 changed lines, M ≈ ≤ 400, excluding fixtures and tests. If a phase grows past M, split it before coding.
- **Rollback:** reverting the PR restores the previous behaviour. No data migrations; config keys are additive with safe defaults.
- **Definition of done:** new tests first (they fail on the previous head), then the fix; full Python + JS suite green on Windows Actions; TODO/PROJECT_STATE/DEVELOPMENT_LOG updated. A phase with a **Windows gate** is "code done" after CI, and "accepted" only after the user reports the device check.
- **No new UI design.** Text and status changes only where a phase needs them to tell the truth.

## Milestones and order

| Milestone | Phases | What the user gets |
| --- | --- | --- |
| **M1 Foundations** | P0.1–P0.3 | Tests and logs that can reproduce the bugs. No behaviour change. |
| **M2 Stop false outputs** | A1–A3, E1–E3 | No phantom picks, no fake 2.1/10, no false reroll advice. Quickest real improvement. |
| **M3 Match lifecycle** | F1–F5 | Clear states for loading, live data unavailable, in game, game end and next game. No stale Neeko. |
| **M4 Read the right screen** | B1–B3 | OCR only runs on the League window; no private screenshots. |
| **M5 Read the right cards** | P0.4, C1–C4 | Three cards identified by position, or marked unknown; rerolls detected per card. |
| **M6 One source of truth** | D1–D3 | Scores always follow the current offer, in card order. |
| **M7 Acceptance** | V1 | A-FUNC.3 full Windows custom-match acceptance. Unblocks D5a and later F-AUD-07. |
| **M8 Quality and hardening (P1/P2)** | G1–G6 | Catalog accuracy, score calibration, local API security, clean-ups. |

M2 and M3 do not depend on each other and can run in either order. M5 needs M4. M6 needs M5.

---

## M1 — Foundations

### P0.1 — Poll-loop test harness · S · no behaviour change
- **Change:** extract the body of `_poll_game_loop` into `async def poll_tick(state, deps, now)` with injectable LCDA, LCU, OCR and clock. The loop calls it. Behaviour identical.
- **Tests:** harness smoke test; mark the audit reproductions as `xfail(strict=True)`: level-up during an offer creates a pick (AUD-03a), first LCDA miss broadcasts `game_ended` (AUD-07), damage closes the scan window (AUD-03d).
- **Fixes:** none (enabler for A, F, D).

### P0.2 — `app.js` message test harness · S · no behaviour change
- **Change:** expose `handleMessage` and the render functions to a DOM-stub test, like `tests/js/settings.test.cjs`.
- **Tests:** current behaviour snapshots; `xfail`-style failing assertions for AUD-05 (header kept after `game_ended`/`no_game`).

### P0.3 — Structured diagnostic log · S
- **Change:** one JSON line per state transition (not per tick): LCDA result class (`ok`, `http_404`, `timeout`, `refused`, `bad_json`), scan window open/close with reason, OCR per-slot text/match/confidence, pick inference. Rotating file in the user-data directory. No screenshots, no player names beyond the local champion.
- **Tests:** log entries emitted on transitions; size cap honoured.
- **Windows gate:** user plays one custom match and sends the log. This is the evidence still missing for AUD-01.

## M2 — Stop false outputs

### A1 — No pick from stat changes · S · AUD-03a
- **Change:** delete the passive path in `server.py:762-776`. A stat change alone never sets `awaiting_stat_delta`.
- **Tests:** level-up, item purchase and death/respawn during an open offer: no pick, offer kept.

### A2 — Scan window ignores health · S · AUD-03d
- **Change:** remove the `health_pct < 0.98` close rule (`server.py:778-791`). The window closes only when the offer disappears, a pick is confirmed, or the match ends.
- **Tests:** reaching level 7 at 60% HP keeps scanning until the cards are gone.

### A3 — Confirm picks instead of guessing · S · AUD-03a
- **Change:** when the offer disappears, ask the user which card was picked. Stat deltas may only highlight a "likely" option, and only if the level and inventory did not change between the two snapshots. Remove the auto-confirm at confidence ≥ 0.3 (`server.py:927-952`).
- **Tests:** disappearance + level-up → prompt with no highlight; disappearance + clean delta → prompt with highlight; never an automatic pick.
- **Windows gate (A1–A3):** hold an offer in fountain across two level-ups and one purchase; progress stays 0/4. Pick a card; the prompt shows it; progress becomes 1/4.

### E1 — Fix catalog parsing errors · S · AUD-04b/04c
- **Change:** keyword matching on word boundaries (`loader.py:457-466`), so "Upgrade" no longer contains "AD". Correct the Donation name hint. Cache schema version bump so old caches are rebuilt.
- **Tests:** "Upgrade Stormsurge" has no AD; Donation has no HP; a cache from the old schema is ignored.

### E2 — Coverage flag and provenance · S · AUD-04a/04e
- **Change:** each augment gets `modelled: bool` and `provenance` (`override`, `name_hint`, `description_keywords`, `none`). An all-zero vector means `modelled = False`.
- **Tests:** coverage report helper; the zero-vector augments from the playtest (Impassable, Tooth Fairy, Shark Bait, Get Jinxed) are `modelled = False`.

### E3 — "Not rated" instead of 2.1 · M · AUD-04, F-AUD-04
- **Change:** `rate_augment` returns `score = None` for unmodelled augments. Keep a negative raw fit distinguishable from "no data" (no clamp to the same value). `should_reroll` only advises when all three cards are identified and modelled, and names the reason. The UI shows "Not rated — insufficient data" and no reroll banner in that case.
- **Tests:** the real offers from the playtest give `None/None/None` and no reroll; a fully modelled weak offer still gives a reroll hint; a payload with a `null` score renders without `NaN`.
- **Windows gate (E1–E3):** the same kind of offer shows "Not rated" for unknown cards and no reroll advice.

## M3 — Match lifecycle

### F1 — LCDA off the event loop, classified · S · AUD-01
- **Change:** `get_raw_game_data` runs in `asyncio.to_thread` and returns `(status, payload)` instead of `dict | None`. Logged through P0.3.
- **Tests:** each status class maps correctly; a slow LCDA no longer blocks WebSocket handling.

### F2 — Explicit status machine · M · AUD-01
- **Change:** read the LCU gameflow phase (read-only). Broadcast a `status` message: `client_idle`, `champ_select`, `loading`, `live_data_unavailable`, `in_game`, `champion_unresolved`, `post_game`. When `Pipeline.run` returns `None`, send `champion_unresolved` instead of nothing. Match the active player by `riotId` first, then `summonerName`.
- **Tests:** harness sequences: champ select → loading → LCDA 404 ×3 → LCDA ok; unresolved champion; riotId mismatch case.

### F3 — Debounced game end and match identity · M · AUD-06, AUD-07
- **Change:** a game ends only after ≥ 3 consecutive LCDA misses and ≥ 6 s, or when the gameflow phase says so. Match id comes from the LCU gameflow session, with a fallback on (riotId, champion) and a `gameTime` regression check. A new match id resets match state immediately. This replaces the 300 s post-game timer. Reuses the useful part of the WIP branch, with its test fixed.
- **Tests:** one miss mid-game keeps picks; real end resets; a new game inside 5 minutes without champ select starts clean.

### F4 — Client clears or marks stale · S · AUD-05
- **Change:** `clearMatchDisplayState()` (from the WIP branch) on `game_ended`, `no_game`, `champ_select` and a new match id. On WebSocket close, dim the panels with a "Reconnecting…" label instead of wiping them. Show the F2 status texts.
- **Tests:** P0.2 harness: no champion/time/gold after `game_ended`; reconnect shows stale, then fresh data.

### F5 — Broadcast outside the lock · S · AUD-12
- **Change:** collect messages while holding `game_state.lock` and send them after release.
- **Tests:** a slow fake client does not delay the next tick.
- **Windows gate (F1–F5):** custom Mayhem start leaves "Waiting" within two ticks of live data; alt-tab or a brief freeze keeps picks; game end clears the header; a second game with another champion shows no carry-over.

## M4 — Read the right screen

### B1 — League window locator · S · AUD-02a
- **Change:** new pure module that finds the League game window and returns its client rect in screen coordinates and whether it is foreground. Read-only Win32 calls through `ctypes`; returns `None` off Windows.
- **Tests:** fake Win32 layer: windowed with title bar, borderless, second monitor with negative origin, minimised, not found.

### B2 — Capture only the focused League window · S · AUD-02a
- **Change:** OCR capture uses the client rect from B1. If League is not foreground: no OCR, status `not_focused`, previous slots kept but marked stale.
- **Tests:** OCR is never called when not focused; the region follows the client rect.

### B3 — Screenshot policy · S · AUD-09
- **Change:** debug screenshots off by default (`ocr_debug_screenshots = false`); when on, card crops only, only when League is focused, saved in the user-data directory, with a retention cap. Remove the full-screen save on manual scan.
- **Tests:** default config saves nothing; the debug mode never saves a full screen.
- **Windows gate (B1–B3):** with an open offer, alt-tab to a browser: the overlay says League is not in focus and nothing is saved. Test windowed and borderless at the user's 1440p, plus 1080p if available.

## M5 — Read the right cards

### P0.4 — Redacted OCR fixtures · S
- **Change:** a script that, from a debug crop, saves only the three title bands plus a truth file `{left, centre, right: augment_id | null}`. Store under `tests/fixtures/ocr/`.
- **Windows gate:** the user collects one session with debug crops on: a full offer, each card rerolled once, one card rerolled twice, one dialog over a card. At 1440p, and 1080p if possible.

### C1 — Card title geometry · S · AUD-02b
- **Change:** pure function from client rect to three title-band rectangles, calibrated on the P0.4 fixtures. 16:9 first; 16:10 and 21:9 marked unsupported until fixtures exist.
- **Tests:** band rectangles at 1080p/1440p and with a windowed offset contain the fixture titles.

### C2 — Strict per-card OCR · M · AUD-02b
- **Change:** OCR each band on its own (`--psm 7`). Match only against the catalog: normalized exact or near-exact (≥ 90) with a margin of ≥ 8 over the runner-up, else `unknown`. Descriptions are never read.
- **Tests:** all fixture slots correct or `unknown`; description text and dialogs never produce a name; the "Get Excited!" fill-in case gives `unknown`.

### C3 — Per-card change detection · M · AUD-03b/03c
- **Change:** replace `ScreenWatcher` with one hash per band. A changed band is re-read alone. A slot is identified after two consistent reads; failed reads retry with backoff, and the old id is cleared rather than kept.
- **Tests:** the measured fixture pair gives 0/65/0 and only the middle card is re-read; an unreadable reroll leaves `unknown`, not the old card.

### C4 — Offer present / gone · S · AUD-03a
- **Change:** the offer is "gone" after N consecutive focused frames with no title text in any band. This is the only pick trigger, feeding A3.
- **Tests:** a dialog over the cards is not "gone"; real disappearance after a pick is.
- **Windows gate (C1–C4):** 10 offers (30 cards) all correct or `unknown`; every position rerolled once, one card rerolled twice in a row, all without Alt+O.

## M6 — One source of truth

### D1 — Offer model and serial OCR · M · AUD-06
- **Change:** `GameState.offer = {match_id, generation, slots[3]}`. Every change increments `generation`. All OCR, including manual scan, goes through one serial executor.
- **Tests:** concurrent manual and automatic scans are serialized; generation is monotonic.

### D2 — Protocol v2 · M · AUD-06
- **Change:** an `offer` message carries `match_id`, `generation` and the three slots. Recommendations are sent per slot, in card order. The client ignores older generations, and the separate "Detected augments" list is derived from the offer, not kept apart.
- **Tests:** out-of-order messages are dropped; slot order is preserved; the UI never shows two different offers.

### D3 — Input validation · S · AUD-11, AUD-16
- **Change:** WebSocket ids checked against the catalog, at most 4 picks, booleans coerced; REST `/api/ocr/scan` goes through D1; no access to private watcher fields.
- **Tests:** invalid ids rejected; fifth pick rejected.
- **Windows gate (D1–D3):** reroll rapidly twice; the scores always match the visible cards, and no stale list appears.

## M7 — Acceptance

### V1 — A-FUNC.3 Windows acceptance · no code
- One permitted custom Mayhem match, with the log and debug crops on, following a written script that includes periodic movement (to avoid the AFK kick, AUD-19): start, first offer, each reroll type, a pick, a level-up with an offer open, alt-tab, a brief live-data loss, game end, a second game.
- **Pass criteria:** no wrong card names, unknown stays unknown, no phantom pick, no stale score, no carry-over between games.
- **Unblocks:** D5a, then F-AUD-07 card badges (built on D2 slot data).

## M8 — Quality and hardening (P1/P2)

| Phase | Size | Scope | Audit IDs |
| --- | --- | --- | --- |
| **G1** | S | Spike: identify the authoritative Mayhem augment source and its id range; capture a real LCDA `gameMode` sample. Research only, written up in the docs. | AUD-04d, AUD-14 |
| **G2** | M | Mayhem-only, deduplicated catalog without placeholders; never cache an empty or failed fetch; cache keyed by patch + content hash. | AUD-04d, AUD-10 |
| **G3** | S | Game-mode gate for OCR and scoring, using the value captured in G1. | AUD-14 |
| **G4** | M | Local API hardening: `Origin`/`Host` allow-list, a per-launch token for state-changing calls and the WebSocket. | AUD-08 |
| **G5a/b/c** | M each | Score calibration in slices: curated tags for the most common Mayhem augments, a provenance line per score, a model review of saturation, context range and overlap penalty. | AUD-13 |
| **G6** | S | Clean-ups: pixel mean via `ImageStat`, `time.monotonic()`, cached LCU lockfile path. | AUD-15, 17, 18 |

## Coverage check

| Observed defect | Fixed by |
| --- | --- |
| F-AUD-01 Waiting for game | P0.3, F1, F2 (evidence first) |
| F-AUD-02 wrong three cards | B1, B2, C1, C2 |
| F-AUD-03 single-card reroll | A1, A2, C3, C4 |
| F-AUD-04 uniform 2.1 / reroll advice | E1, E2, E3 (then G2, G5) |
| F-AUD-05 stale Neeko/time/gold | F3, F4 |
| F-AUD-06 stale/out-of-order offers | F3, D1, D2 |
| F-AUD-07 badges over cards | after V1, on D2 slot data |
