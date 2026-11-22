# F5 / #86 — Verified live picked augment: source evaluation and contract

**Date:** 2026-11-22  
**Status:** provider-neutral synthetic contract implemented in draft PR #87, **NOT connected to a live producer**, **NOT native accepted**. This is the first bounded subphase of automatic picked-augment support.

## Product requirement (user-approved)

After the user clicks an augment **normally in League**, ARAM Oracle should identify the **actual chosen augment**, add exactly one confirmed catalog ID for that match/offer, automatically close the obsolete choice and adapt subsequent augment synergies + item build, with **no Alt+3 or additional interaction** in normal use. The overlay must never automatically click or select any League option.

Source identity, selection outcome and choice disappearance are **distinct** facts: reading a card title cannot prove it was chosen; a card panel disappearing cannot prove which card was chosen; a late reroll cannot be reattached to another level-due offer.

## External source feasibility (verified official documentation)

| Candidate | What is actually documented | Deployment / live acceptance |
| --- | --- | --- |
| Overwolf GEP / League `augments` | Available augments in ARAM Mayhem; supported since GEP **299.0** | Requires a legitimately approved Overwolf app and real on-device event validation |
| Overwolf GEP / League `picked_augment` | Last selected augment in ARAM Mayhem; supported since GEP **299.0** | Best **prospective** authoritative event, **not** available to the standalone Python LCDA by documentation |
| Riot Game Client `https://127.0.0.1:2999/liveclientdata/*` | Official active-player stats, items, scores, game events; no documented `picked_augment` endpoint in the public Live Client Data docs | Existing standalone Oracle can read supported user-visible fields, **not** an assumed automatic augment choice |
| Riot local League Client API / LCU | Unsupported third-party client service; match results can contain selected augments **after** the match | Not proof of live picked-augment identity and not a source for immediate build refresh |
| Independent client-visible selected-card visual UI | Potential locally observed selected marker / persistent chosen-augment UI | No calibrated source yet. Requires local private real scenes across reroll/selection/4-card/occluded/focus; never guess from click position or blank OCR |

Primary documentation:
- https://dev.overwolf.com/ow-electron/live-game-data-gep/supported-games/league-of-legends/
- https://dev.overwolf.com/ow-native/live-game-data-gep/supported-games/league-of-legends/
- https://dev.overwolf.com/ow-electron/getting-started/project-roadmap/
- https://dev.overwolf.com/ow-native/getting-started/guidelines-and-requirements/
- https://dev.overwolf.com/ow-electron/guides/game-compliance/per-game-requirements/
- https://developer.riotgames.com/docs/lol

**Critical integration constraint:** Overwolf does **not** approve private/faceless bridge apps or apps that merely forward Overwolf API data into another standalone app. Riot apps also need Riot approval for the relevant Overwolf distribution. Do not build an unapproved WebSocket, filesystem, HTTP, or DLL relay from Overwolf to the current PyQt Oracle. A compliant **full Overwolf Electron edition** must be considered and approved as an actual app if this provider is chosen.

**Unknowns:** Overwolf's public Electron and Native documentation examples show **different payload shapes** (a single display title versus a JSON object with slot names). Neither example proves a reliable match ID, offer/epoch, event ID, precise source event timestamp, source security attestation, or Riot-catalog mapping. An implementation must obtain a **legitimately authorized, real source event** and independently validate each part. A screenshot of docs is not proof of live compatibility. No user action on Overwolf approval is assumed or claimed completed.

## Implemented in draft #87 — provider-neutral in-process contract only

1. `backend/workflow/picked_augment.py` provides immutable `PickedAugmentEvidence`: `match_id, offer_id, epoch, catalog_id, source, source_event_id, observed_at, verified`. It is a **typed container, not an attestation**. Only a real approved adapter could supply trustworthy fields.
2. `OfferLedger.confirm_verified_external` requires an explicit **approved source allowlist**, disabled by default, exact current match, existing offer ID/epoch, canonical ID in a verified catalog, valid bounded opaque event ID, `verified=True`, and a conservative fresh event time. Duplicate same-event same-offer is idempotent; conflicting replay is rejected without mutation; manual/postgame confirmations cannot be overridden. An authenticated event may name a legitimate picked ID even when OCR titles were unreadable.
3. `backend/api/server.py:_apply_approved_pick_evidence` is **an internal helper only**; no REST/WS ingest, no Overwolf bridge, no environment-variable bypass. Only an approved in-process provider may call it under the existing `GameState.lock`. Confirmed IDs enter the existing build/synergy input on the next normal poll, and the latest confirmed offer closes the obsolete choice. A late older offer confirmation must not change the newest offer.
4. Synthetic test fixtures cover source approval, freshness, wrong match/epoch, catalog membership, duplicates, event conflicts, manual-source conflicts, late older offers, and confirmed build inputs. **Check actual code and final SHA Actions results** before marking this stage CODE GREEN.
5. There is deliberately **no actual runtime provider**, so **no automatic picks currently occur on the user's Windows game**. Original manual fallback remains, but is not the accepted normal end state.

## Future, independently gated phases (do not bundle)

**F5.2 — Provider legitimacy and payload contract:** decide whether a fully integrated Overwolf Electron edition can be submitted/approved and instrumented legally, or find a stand-alone authorized observable selected marker. Validate one real match-bound event stream, source event ID/ordering, TTL, copy/replay behavior, multi-event pick progression, 3/4 cards, stat anvils, and patch-specific catalog mapping without leaking private frames. Never invent proof fields.

**F5.3 — Authorized runtime adapter:** add exactly one approved runtime source and integrate under `GameState.lock`, with post-confirm latest-offer closure, explicit update revision, immediate downstream rebuild and no duplicated selection. Keep service disabled if source approval is absent, if payload is ambiguous, or if the app isn't a legitimately approved Overwolf app.

**F5.4 — Windows native holdout / release gate:** verified supported custom Mayhem; no `Alt+3` in the normal path; accurate first/second/third/fourth pick, individual rerolls, absent/out-of-order/replayed events, app restart and match change, no false positive, no stale recommendations, updated valid build. Riot score and item shop gates #84/#49 still independent. A successful synthetic test is **not** evidence of this native feature working.

**Safety:** preserve draft-only PR stack, public-repo privacy, PP-OCRv4 experimental, capture/OCR provenance, match/epoch fences and Riot policy. No private game captures or raw player data in GitHub; no hidden game APIs, memory inspection, injection, automatic gameplay input or third-party data scraping.

## 2026-11-22 F5.2 standalone decision update

- **Official new constraint:** Overwolf Developer Terms effective **2026-11-01** allow distribution only for applications monetized using Overwolf ads and/or subscriptions, on top of Riot/Overwolf approval and prohibition on faceless bridges: https://legal.overwolf.com/docs/overwolf/developers/developer-terms/. Therefore a default forced Overwolf migration is **not approved** for ARAM Oracle. The user wants an intuitive independent Windows desktop application; no decision to introduce ads/subscriptions has been made.
- **Source feasibility result:** independent on-screen evidence is possible in principle, but our existing calibrated image rectangles are *OCR title-only*, not full clickable cards. The existing `VerifiedAbsenceGate` has **no calibrated independent visual observer enabled** in production. The open-source MIT `zp96-cmd/mayhem-overlay` uses a hover-then-two-OCR-misses heuristic; reviewed as an external feature reference, no code copied, and rejected as insufficient for unambiguous picked IDs.
- **First F5.2 implementation:** [draft PR #88](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/88) stacked on draft #87 contains `backend/collectors/standalone_pick_candidate.py`: pure, disabled-by-default, match/epoch/window-fenced, separately calibrated three-card click rectangles; only a proven left-button down edge in League foreground; three independently calibrated negative visual observations; replay/ambiguity/focus/timeout guards. It emits **`StandalonePickCandidate(verified=False)` only**. The #87 ledger explicitly rejects it as `bad_evidence`; no build changes result. Runtime has no mouse observer or calibrated marker wired.
- **Remaining mandatory source:** a distinct *positive acquired-augment ID* signal (e.g. a locally visible owned-augment indicator, independently shown to be newly acquired) is required before any candidate can promote to `PickedAugmentEvidence`. Native calibration and consented local-only tests remain BLOCKED/NOT RUN; see [F5.2 full calibration protocol](F5_STANDALONE_PICK_CALIBRATION_2026-11-22.md). A 4-card layout is deliberately unsupported pending #85.
- **Code evidence:** tests-only RED `fde947887b2109e461e73e09d95ddf572003079f`, Windows #45077582489 FAILED on expected missing module; source implementation `8b7457ad4e0f0a4c71ca4537ea951682249a6541` plus click-ID pattern correction `97ef0da81f2e369ffacc76f9b679a2a8d18aa95c`; [Windows code GREEN #45077810931](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45077810931) **1,996 Python PASS / 27 SKIP, 79 JS PASS, real PP-OCRv4 PASS**, full final code+docs SHA requires separate verification.
- **F5.2 not native acceptance:** no automatic selected augment ever recorded in a real match from this branch. The no-Alt+3 feature still requires an approved and correctly verified production source and a user-controlled holdout. All PRs draft, main unchanged.
