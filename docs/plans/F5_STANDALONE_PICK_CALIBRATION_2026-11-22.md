# F5.2 — Standalone Mayhem picked-augment feasibility and calibration

**Date:** 2026-11-22  
**Status:** private Windows source/geometry calibration **BLOCKED / NOT PERFORMED**; purely synthetic SHADOW candidate is under review in [draft PR #88](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/88).  
**Parent:** draft #87 (provider-neutral verified event contract) → #83 → #80 → #78 → #76. All unmerged; `main` untouched.

## Decision: preserve the independent desktop application

Official Overwolf GEP League documentation describes ARAM Mayhem `augments` and `picked_augment` info updates from GEP 299.0, but this does not authorize the events on a standalone Python/Qt application or document stable match+offer+epoch/event ID fields. Overwolf and Riot app approvals are required, and OW terms **effective November 1, 2026** require Overwolf-distributed apps to monetize using Overwolf subscriptions and/or ads. An unapproved relay between Overwolf and the standalone Oracle is not an acceptable workaround.

**Decision for this subphase:** prefer a strictly user-visible, independently calibrated Windows-side source, preserving the user's current app architecture. Overwolf remains a **separate possible full-app edition only after legitimate approvals and a monetization decision**; it is not integrated or assumed accessible in the current build.

Primary sources:
- https://dev.overwolf.com/ow-electron/live-game-data-gep/supported-games/league-of-legends/
- https://dev.overwolf.com/ow-electron/guides/game-compliance/riot-games/
- https://dev.overwolf.com/ow-electron/getting-started/guidelines-and-requirements/
- https://legal.overwolf.com/docs/overwolf/developers/developer-terms/
- https://developer.riotgames.com/docs/lol

### External example studied — NOT copied

The open-source `zp96-cmd/mayhem-overlay` repository identifies itself as MIT in `package.json`. Its public README describes inferred picks from cursor visiting a card and subsequent disappearance of the panel; code uses a recent hover and two OCR-based no-match scans. This **does not meet our no-false-picked-ID requirement**: hovering is not clicking; OCR misses are not calibrated visual absence; losing focus/occlusion/reroll/queue transitions can misattribute a pick. No source/assets were copied from that repository in this PR. See https://github.com/zp96-cmd/mayhem-overlay.

## Proposed evidence chain

1. **Previously present, verified offer:** the current OCR watcher must provide C3-verified physical card identities (three distinct canonical catalog IDs) in the actual League window, bound to exact match/offer/epoch and a validated window key. The already calibrated `card_title_geometry.py` boxes are **title crops only**, not proven click zones.
2. **Independent clickable-card layout:** a reviewed, calibrated client-relative rectangle per card, same League window key and fixed geometry revision. Must be non-overlapping and fully inside the client, with separate support for 3-card and 4-card variants. Unsupported geometry abstains.
3. **Real passive click edge:** a future explicitly enabled and reviewed Windows local-only reader must capture a genuine left-button **down transition**, not cursor hover/dwell, within exactly one card, while League is verified foreground. No game input injection, synthetic click, global recording, or collecting events outside relevant in-game offer. Only match+epoch-bound minimal metadata can enter the local state machine; never publish input metadata.
4. **Independent offer disappearance:** `VerifiedAbsenceGate` requires exactly matched calibration + window and at least three separate verified negative observations. Blank/failed OCR and teal fraction of the same title crops do **not** count. Focus loss/occlusion/dialogue and uncertain or repeated frames reset/suspend proof. The existing production `ScreenWatcher` has **no approved observer or calibration**, so this gate is disabled.
5. **Only an unverified candidate is emitted:** `backend/collectors/standalone_pick_candidate.py` (shadow-only) requires the four prerequisites and emits `StandalonePickCandidate(verified=False)` for the single identified slot. It **cannot** be accepted by `OfferLedger.confirm_verified_external`: this is an intention/closure inference, **not** independent proof that the game awarded the augment.
6. **Independent positive acquisition proof remains necessary:** identify a permitted, user-visible **owned-augment / acquired-effect UI indicator** whose identity can be independently matched to a catalog ID and to this choice, including repeated/stacking augments and stat anvils. Calibrate its geometry/timing separately and verify an actual newly acquired change (not merely the presence of an earlier augment). Without a distinct validated source, do not automatically confirm, close as selected or update build inputs.
7. **Only after the full native source is proven and compliance reviewed**, wrap it into `PickedAugmentEvidence` and call the #87 in-process gate with a deliberately approved source, under `GameState.lock`, exactly once. No HTTP/WS relay or public endpoint.

## Synthetic acceptance and counterexamples

- [ ] **RED→GREEN:** no calibration or click source => no candidate; proved three distinct OCR card identities; one bounded real left-down edge in exactly one reviewed card rect; three independent absent reads => *candidate only*, not an accepted pick
- [ ] Hover without down edge, clicking outside, reroll button, overlapping card bounds, duplicate slot IDs, unreadable slot, unverified capture, wrong window or focus => no candidate
- [ ] Clicks on two different cards, repeated identical event/frame, timestamp rollback, expired click, occluded/dialogue/unknown or changed window, new match/offer/epoch => never confirm
- [ ] Four-card mode => must stay unsupported until separate 4-slot calibrated geometry and capture coverage (#85); do not silently map fourth to L/C/R
- [ ] Synthetic candidate passed to `OfferLedger.confirm_verified_external` => `bad_evidence`, zero mutations; no build/synergy changes from candidates
- [ ] Exact final Windows Actions SHA full Python/JS/real-model GREEN; passing CI is **NOT** native auto-pick acceptance

## Mandatory future local-only calibration

The original private screenshots and holdout data **must remain on the user's Windows machine**, never committed to the intentionally PUBLIC repository. The user need not play another normal match now. When calibration is ready, use a controlled custom Mayhem environment with user-operated input only, optional temporary local opt-in instrument that **never stores screenshots, cursor trails or raw OCR** and reports only aggregate correctness/abstention. Test varied supported resolution/DPI/ratio, focus/alt-tab, overlay covered/hidden, first/second/queued picks, single-card rerolls, selection animation, 4-card Maestro, stat anvils, repeated augments, interrupted choices, restart and reconnect, positive acquired marker and zero wrong selected IDs.

**Status labels:** F5.2 deterministic shadow gate may become CODE GREEN; actual automatic selected augment and no-Alt+3 goal remain **BLOCKED / NOT TESTED** without real independent acquisition evidence. Existing #82 false OCR native acceptance, #84 `Not Rated` and unreliable scores, #49 boots `Unavailable`, #85 four cards are independent open gates. No default PP-OCRv4 promotion, game input automation, Overwolf bridge, unstated Riot approval or merges.
