# ARAM Oracle V1.2c — verified boundary between augment offers

**Date:** 2026-11-22  
**Status:** synthetic safety gates CODE GREEN; automatic offer boundary/pick identity **NOT IMPLEMENTED**; native acceptance **OPEN / STOP**  
**Branch / review:** `feat/ocr-v12-ppocrv4-optin-20261122`, draft PR #83 stacked on #80 → #78 → #76. Never merge or promote OCR default based only on CI.

## User-observed failure and independently proven code defects

In a controlled Windows Mayhem session, the second Gold offer briefly displayed three wrong augment identities that subsequently corrected; later individual rerolls worked. Prismatic recognition exceeded the six-second target and most cards showed `Not Rated`. The player's selected augment was not automatically registered and the advice persisted until the manual shortcut. These are **native observations**; root cause is not uniquely proven by tests.

Source work in #83 isolated three distinct race/boundary defects:

1. An `ocr_result` containing fresh physical slots can precede the authoritative ledger/update, causing stale previous identities to render. The frontend consistency guard has a synthetic RED→GREEN test.
2. A new level-due offer could inherit previously verified candidates and slot temporal baselines when the earlier unconfirmed scanner remained open. A later-offer reset plus candidate invalidation has a synthetic RED→GREEN test.
3. A fresh scan after that reset can still recognize the earlier card triple (including permutations); `_prior_due_triple` rejects this with a synthetic RED→GREEN test.
4. **This subphase:** a *different*, C3-verified triple could still be a **late reroll belonging to the earlier, unresolved offer**. Prior code treated it as the next offer purely from title difference + level threshold. Added deterministic [tests-only RED #45073811287](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45073811287) at `ad50e6c83b78418b852f185afeb865e89da17061`: exactly one new Python assertion failed (`present` versus required `pending`), 1,980 previous Python PASSED / 27 SKIPPED. The narrow backend guard `636fbbd70df2a581875fb3b89980e62dd2c586fb` plus regression update `39cc1edd7ccfc42cc9042639b7d04ac11ec5c02d` passed [Windows code GREEN #45074067687](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45074067687): **1,981 Python PASSED / 27 SKIPPED, 79 JavaScript PASSED / 0 FAILED, three syntax checks and the separate real pinned PP-OCRv4 model job PASSED**. Final documentation-head CI must be independently verified.

## What the current backend can and cannot prove

- An observed level threshold (`3/7/11/15`) creates an **eligible** new ledger offer; it does not prove the previous offer UI disappeared.
- `backend/collectors/slot_temporal.py` validates *what physical titles currently read*, not *which offer generation those titles belong to*. Even two fresh strict OCR reads can confirm a late previous-offer reroll.
- `backend/collectors/offer_visibility.py` has a deliberately disabled `VerifiedAbsenceGate` in production. `card_background_cue` is **shadow-only, derived from the title crops**, and MUST NOT be treated as independent calibrated proof of an offer ending. Blank text, elapsed time, level changes, lost focus or damage are not substitute signals.
- `OfferLedger` distinguishes verified card identities from confirmed player picks. No authorized live automatic picked-augment event is currently integrated. `picked_augment` is documented for Overwolf GEP League, **not** proved available on the standalone Python LCDA/LCU runtime. An Overwolf adapter requires legitimate full-app integration and compliance approval, not a bridge.
- As an interim **fail-closed** rule, `GameState.accept_new_due_slot_identity` now refuses a later offer's OCR candidate **if any earlier OfferLedger offer is still `due`, `visible` or `awaiting_confirm`**. This applies to both automatic and manual OCR paths and even a new complete triple. The guard allows later verified titles after *all earlier offers* reach `confirmed` or `reconciled`, and retains the previous triple-replay fence. It never fabricates a picked ID. This is a deliberate, possibly intrusive UX tradeoff: **without automatic selection confirmation, the second/later offer may remain unrated/hidden indefinitely**, which is safer than a wrong accepted identity but **not product-complete**.
- A manually confirmed prior offer may unblock later scanning; manual is exceptional recovery, **not** the target experience. Future independent visual offer disappearance can close/hide advice, but disappearance alone cannot prove which card was picked. Do not treat a synthetic success as a native pass.

## Next engineering decisions and gates

1. **Boundary source:** validate an independent, calibrated, read-only client-visible **offer present/gone** visual marker using LOCAL-only varied positive/negative/occluded/animation samples; require a separate client-window proof and at least three independent negative reads, no title-crop-derived evidence. Only then may it authorize close/hide; identify chosen card separately.
2. **Automatic picked augment P0 (#86):** prioritize a permitted source that gives the exact picked ID, bound to match+offer+epoch with replay protection, catalog mapping and idempotence. Audit Overwolf full-app compliance/approval and alternative standalone native detection before selecting architecture. Do not imply Overwolf GEP is exposed on 127.0.0.1:2999, use memory reads, inject code or automatically click in-game.
3. **Once a confirmed pick event exists:** persist the actual chosen augment once per offer, recalculate synergy and legal item build, and release the next offer boundary without Alt+3; preserve ability to distinguish 3- and 4-card layouts. Explicitly test mismatched, duplicate, late/out-of-order and restarted-match events.
4. **Native V1.2c (#82):** one user-controlled supported custom Mayhem test after offline readiness, observing physical first/second offers, three positions, per-slot rerolls and zero wrong identities, including focus/occlusion and latency. Neither current safe abstention nor code CI is native PASS.
5. **Independent non-OCR issues:** #84 `Not Rated`/score calibration, #49 Berserker's Greaves → `Unavailable` and #85 four-card layout. Avoid changing their implementation in the OCR boundary subphase.

## Safety / acceptance

- Keep PP-OCRv4 user-selected experimental opt-in, Tesseract fallback, 90/8 strict title match, two-read temporal verification, match/epoch fencing and capture proof.
- Only read permitted, user-visible local data. No player actions, hidden information, unapproved data transfer, or inferred selected augment.
- Repository is intentionally PUBLIC; never commit a personal game screenshot, player identity, raw OCR text, logs, credentials, Windows paths, model blobs or restricted third-party code.
- All PRs draft, protect `main`, preserve stack. Update state/TODO/log and verify **exact final SHA** Windows Actions before claiming code green.
