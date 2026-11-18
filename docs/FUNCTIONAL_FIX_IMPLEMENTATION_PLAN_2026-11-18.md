# ARAM Oracle — Functional Fix Implementation Plan (2026-11-18)

**Status:** User-provided implementation proposal, registered in Git. Its **execution rules are project policy**; individual fixes are not yet implemented, and the proposed sequencing has unresolved review gates noted at the end. This plan translates the FX-0…FX-8 outline in `7 of `FUNCTIONAL_AUDIT_REPORT_2026-11-18.md` into small phases and is intended to cover AUD-01…AUD-19. The full audit report has not been independently verified in this documentation session. Visual work (F-AUD-07 card badges, D5c) stays blocked until M7 passes.

## Rules for every phase

- **One phase = one branch = one small draft PR**, stacked on the previous phase branch (the first implementation phase stacks on D4b PR #17). Never merge to `main` without explicit approval.
- **Size target:** S ≈ ≤ 150 changed lines, M ≈ ≤ 400, excluding fixtures and tests. If a phase grows past M, split it before coding.
- **Rollback:** reverting the PR restores the previous behaviour. No data migrations; config keys are additive with safe defaults.
- **Definition of done:** new regression tests before each fix (they fail on the previous head), then the fix; full Python + JS suite green on Windows Actions; TODO/PROJECT_STATE/DEVELOPMENT_LOG updated. A phase with a **Windows gate** is "code done" after CI, and "accepted" only after the user reports the device check.
- **No new UI design.** Text and status changes only where a phase needs them to tell the truth.

## Milestones and order

| Milestone | Phases | What the user gets |
| --- | --- | --- |
| **M1 Foundations** | P0.1–P0.3 | Tests and logs that can reproduce the bugs. No behaviour change. |
| **M2 Stop false outputs** | A1–A3, E1–E3 | No phantom picks, no fake 2.1/10, no false reroll advice. |
| **M3 Match lifecycle** | F1–F5 | Clear states for loading, live data unavailable, in game, game end and next game. No stale Neeko. |
| **M4 Read the right screen** | B1–B3 | OCR only runs on the League window; no private screenshots. |
| **M5 Read the right cards** | P0.4, C1–C4 | Three cards identified by position, or marked unknown; rerolls detected per card. |
| **M6 One source of truth** | D1–D3 | Scores always follow the current offer, in card order. |
| **M7 Acceptance** | V1 | A-FUNC.3 full Windows custom-match acceptance. Unblocks D5a and later F-AUD-07. |
| **M8 Quality and hardening (P1/P2)** | G1–G6 | Catalog accuracy, score calibration, local API security, clean-ups. |

M2 and M3 do not depend on each other. M5 needs M4. M6 needs M5.

## M1 — Foundations

### P0.1 — Poll-loop test harness · S · no behaviour change
- **Change:** extract the body of `_poll_game_loop` into `async def poll_tick(state, deps, now)` with injectable LCDA, LCU, OCR and clock. Behaviour identical.
- **Tests:** harness smoke test; audit reproductions as `xfail(strict=True)`: level-up during an offer creates a pick (AUD-03a), first LCDA miss broadcasts `game_ended` (AUD-07), damage closes the scan window (AUD-03d).

### P0.2 — `app.js` message test harness · S · no behaviour change
- **Change:** expose `handleMessage` and render functions to a DOM-stub test, like `tests/js/settings.test.cjs`.
- **Tests:** current behaviour snapshots; failing assertions for AUD-05 (header kept after `game_ended`/`no_game`).

### P0.3 — Structured diagnostic log · S
- **Change:** one JSON line per state transition: LCDA result class (`ok`, `http_404`, `timeout`, `refused`, `bad_json`), scan window open/close with reason, OCR per-slot text/match/confidence, pick inference. Rotating file in user-data dir. No screenshots, no player names beyond the local champion.
- **Tests:** entries on transitions; size cap honoured.
- **Windows gate:** user plays one custom match and sends the log (evidence missing for AUD-01).

## M2 — Stop false outputs

### A1 — No pick from stat changes · S · AUD-03a
- **Change:** delete the passive path in `server.py:762-776`. A stat change alone never sets `awaiting_stat_delta`.
- **Tests:** level-up, purchase, death/respawn during an open offer: no pick, offer kept.

### A2 — Scan window ignores health · S · AUD-03d
- **Change:** remove the `health_pct < 0.98` close rule (`server.py:778-791`). Window closes only when the offer disappears, a pick is confirmed, or the match ends.
- **Tests:** level 7 at 60% HP keeps scanning until cards are gone.

### A3 — Confirm picks instead of guessing · S · AUD-03a
- **Change:** when the offer disappears, ask the user which card was picked. Stat deltas may only highlight a "likely" option, only if level and inventory didn't change. Remove auto-confirm at confidence ≥ 0.3 (`server.py:927-952`).
- **Tests:** disappearance + level-up → prompt, no highlight; clean delta → prompt with highlight; never automatic.
- **Windows gate (A1–A3):** hold an offer in fountain across two level-ups and one purchase; stays 0/4. Pick a card; prompt shows it; becomes 1/4.

### E1 — Fix catalog parsing errors · S · AUD-04b/04c
- **Change:** keyword matching on word boundaries (`loader.py:457-466`) so "Upgrade" no longer contains "AD". Correct Donation name hint. Bump cache schema version.
- **Tests:** "Upgrade Stormsurge" has no AD; Donation has no HP; old-schema cache ignored.

### E2 — Coverage flag and provenance · S · AUD-04a/04e
- **Change:** each augment gets `modelled: bool` and `provenance` (`override`, `name_hint`, `description_keywords`, `none`). All-zero vector ⇒ `modelled = False`.
- **Tests:** coverage helper; Impassable, Tooth Fairy, Shark Bait, Get Jinxed are `modelled = False`.

### E3 — "Not rated" instead of 2.1 · M · AUD-04, F-AUD-04
- **Change:** `rate_augment` returns `score = None` for unmodelled augments. Keep negative raw fit distinct from "no data". `should_reroll` only advises when all three cards are identified and modelled, and names the reason. UI shows "Not rated — insufficient data" and no reroll banner.
- **Tests:** playtest offers give `None/None/None` and no reroll; fully modelled weak offer still gives reroll hint; `null` score renders without `NaN`.
- **Windows gate (E1–E3):** unknown cards show "Not rated", no reroll advice.

## M3 — Match lifecycle

### F1 — LCDA off the event loop, classified · S · AUD-01
- **Change:** `get_raw_game_data` runs in `asyncio.to_thread`, returns `(status, payload)`. Logged via P0.3.
- **Tests:** status classes map correctly; slow LCDA doesn't block WebSocket.

### F2 — Explicit status machine · M · AUD-01
- **Change:** read LCU gameflow phase (read-only). Broadcast `status`: `client_idle`, `champ_select`, `loading`, `live_data_unavailable`, `in_game`, `champion_unresolved`, `post_game`. When `Pipeline.run` returns `None`, send `champion_unresolved`. Match active player by `riotId`, then `summonerName`.
- **Tests:** champ select → loading → LCDA 404 ×3 → ok; unresolved champion; riotId mismatch.

### F3 — Debounced game end and match identity · M · AUD-06, AUD-07
- **Change:** game ends only after ≥ 3 consecutive LCDA misses and ≥ 6 s, or when gameflow says so. Match id from LCU gameflow session, fallback (riotId, champion) + `gameTime` regression check. New match id resets state immediately. Replaces the 300 s post-game timer. Reuse the useful part of the WIP branch, with its test fixed.
- **Tests:** one miss mid-game keeps picks; real end resets; new game within 5 min without champ select starts clean.

### F4 — Client clears or marks stale · S · AUD-05
- **Change:** `clearMatchDisplayState()` (from WIP branch) on `game_ended`, `no_game`, `champ_select` and new match id. On WebSocket close, dim panels with "Reconnecting…". Show F2 status texts.
- **Tests:** no champion/time/gold after `game_ended`; reconnect shows stale then fresh.

### F5 — Broadcast outside the lock · S · AUD-12
- **Change:** collect messages under `game_state.lock`, send after release.
- **Tests:** slow fake client doesn't delay next tick.
- **Windows gate (F1–F5):** custom Mayhem start leaves "Waiting" within two ticks; alt-tab or brief freeze keeps picks; game end clears header; second game with another champion has no carry-over.

## M4 — Read the right screen

### B1 — League window locator · S · AUD-02a
- **Change:** pure module finding the League game window, returning client rect in screen coords and foreground flag. Read-only Win32 via `ctypes`; `None` off Windows.
- **Tests:** fake Win32: windowed with title bar, borderless, second monitor with negative origin, minimised, not found.

### B2 — Capture only the focused League window · S · AUD-02a
- **Change:** OCR uses B1's client rect. Not foreground ⇒ no OCR, status `not_focused`, previous slots kept but marked stale.
- **Tests:** OCR never called when not focused; region follows client rect.

### B3 — Screenshot policy · S · AUD-09
- **Change:** `ocr_debug_screenshots = false` by default; when on, card crops only, only when League focused, saved in user-data dir, retention cap. Remove full-screen save on manual scan.
- **Tests:** default saves nothing; debug never saves full screen.
- **Windows gate (B1–B3):** with open offer, alt-tab to browser: overlay says not in focus, nothing saved. Windowed and borderless at 1440p, plus 1080p if available.

## M5 — Read the right cards

### P0.4 — Redacted OCR fixtures · S
- **Change:** script that saves only the three title bands from a debug crop plus truth file `{left, centre, right: augment_id | null}` under `tests/fixtures/ocr/`.
- **Windows gate:** one session with debug crops: full offer, each card rerolled once, one card twice, one dialog over a card. 1440p, and 1080p if possible.

### C1 — Card title geometry · S · AUD-02b
- **Change:** pure function client rect → three title-band rects, calibrated on P0.4. 16:9 first; 16:10 and 21:9 unsupported until fixtures exist.
- **Tests:** rects at 1080p/1440p and windowed offset contain fixture titles.

### C2 — Strict per-card OCR · M · AUD-02b
- **Change:** OCR each band alone (`--psm 7`). Match only against catalog: normalized exact or ≥ 90 with ≥ 8 margin over runner-up, else `unknown`. Never read descriptions.
- **Tests:** all fixture slots correct or `unknown`; descriptions/dialogs never produce a name; "Get Excited!" case gives `unknown`.

### C3 — Per-card change detection · M · AUD-03b/03c
- **Change:** replace `ScreenWatcher` with one hash per band. Changed band re-read alone. Slot identified after two consistent reads; failed reads retry with backoff, old id cleared.
- **Tests:** measured fixture pair gives 0/65/0 and only middle re-read; unreadable reroll leaves `unknown`.

### C4 — Offer present / gone · S · AUD-03a
- **Change:** offer "gone" after N consecutive focused frames with no title text in any band. Only pick trigger, feeding A3.
- **Tests:** dialog over cards isn't "gone"; real disappearance after pick is.
- **Windows gate (C1–C4):** 10 offers (30 cards) correct or `unknown`; every position rerolled once, one card twice in a row, without Alt+O.

## M6 — One source of truth

### D1 — Offer model and serial OCR · M · AUD-06
- **Change:** `GameState.offer = {match_id, generation, slots[3]}`; every change increments `generation`. All OCR incl. manual through one serial executor.
- **Tests:** concurrent scans serialized; generation monotonic.

### D2 — Protocol v2 · M · AUD-06
- **Change:** `offer` message carries `match_id`, `generation`, three slots. Recommendations per slot, card order. Client ignores older generations; "Detected augments" list derived from the offer.
- **Tests:** out-of-order dropped; slot order kept; never two offers shown.

### D3 — Input validation · S · AUD-11, AUD-16
- **Change:** WebSocket ids checked against catalog, max 4 picks, booleans coerced; REST `/api/ocr/scan` via D1; no private watcher fields.
- **Tests:** invalid ids rejected; fifth pick rejected.
- **Windows gate (D1–D3):** reroll twice fast; scores match visible cards, no stale list.

## M7 — Acceptance

### V1 — A-FUNC.3 Windows acceptance · no code
- One custom Mayhem match, log and debug crops on, written script with periodic movement (AFK kick, AUD-19): start, first offer, each reroll type, a pick, level-up with offer open, alt-tab, brief live-data loss, game end, second game.
- **Pass:** no wrong card names, unknown stays unknown, no phantom pick, no stale score, no carry-over.
- **Unblocks:** D5a, then F-AUD-07 badges (on D2 slot data).

## M8 — Quality and hardening (P1/P2)

| Phase | Size | Scope | Audit IDs |
| --- | --- | --- | --- |
| G1 | S | Spike: authoritative Mayhem augment source and id range; real LCDA `gameMode` sample. Research only. | AUD-04d, AUD-14 |
| G2 | M | Mayhem-only deduplicated catalog, no placeholders; never cache empty/failed fetch; cache keyed by patch + content hash. | AUD-04d, AUD-10 |
| G3 | S | Game-mode gate for OCR and scoring, using G1 value. | AUD-14 |
| G4 | M | Local API hardening: `Origin`/`Host` allow-list, per-launch token for state-changing calls and WebSocket. | AUD-08 |
| G5a/b/c | M each | Score calibration: curated tags for common Mayhem augments, provenance line per score, review of saturation, context range, overlap penalty. | AUD-13 |
| G6 | S | Clean-ups: `ImageStat` pixel mean, `time.monotonic()`, cached LCU lockfile path. | AUD-15, 17, 18 |

## Coverage check

| Observed defect | Fixed by |
| --- | --- |
| F-AUD-01 Waiting for game | P0.3, F1, F2 |
| F-AUD-02 wrong three cards | B1, B2, C1, C2 |
| F-AUD-03 single-card reroll | A1, A2, C3, C4 |
| F-AUD-04 uniform 2.1 / reroll advice | E1, E2, E3 (then G2, G5) |
| F-AUD-05 stale Neeko/time/gold | F3, F4 |
| F-AUD-06 stale/out-of-order offers | F3, D1, D2 |
| F-AUD-07 badges over cards | after V1, on D2 slot data |

## Cross-cutting decisions to settle before code

1. **The implementation phase identifiers above are canonical.** The prior A-FIX.0–A-FIX.6 documents were coarse planning placeholders; keep them as references for traceability only. Preserve the existing A-FUNC.3 Windows acceptance and A-FUNC.4 UI gate.
2. **Release security:** G4 is located in M8 in the submitted plan, but AUD-08 is a release-blocking security issue. It **must be complete before any public build**, and should be brought forward if test tooling, exposure or API changes make early hardening necessary.
3. **Data confidence:** G1/G2 and sufficient G5 calibration may be necessary **before trusting actual numerical ratings or declaring M7 fully reliable**. M7 may validate *safe unknown behaviour* without claiming substantive rating accuracy; do not present “unknown” as a verified best augment. Investigate Mayhem-only data early.
4. **No mandatory in-combat confirmation:** The proposed A3 explicit prompt must be designed to be non-intrusive. Do not require interaction while fighting. Until a reliable passive signal or appropriate out-of-game confirmation exists, retain unknown chosen augment status.
5. **No accidental green tests:** With `xfail(strict=True)`, unexpected passes fail the suite as XPASS. Keep the original defect reproductions linked to narrow test IDs, and convert expected failures to passing assertions when each repair lands.
6. **Evidence privacy:** Sanitized title bands and redacted IDs only. No commit or external upload of full-screen desktop images. Confirm diagnostic opt-in at time of capture.
7. **No fabricated acceptance:** This document registers a **proposal** and its **working rules**. No phase is implemented or Windows-accepted by registration alone; the full separate audit report should be preserved and checked if supplied.
