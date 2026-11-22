# F0.1 — Functional data lineage and failure boundaries

**Date:** 2026-11-22  
**Baseline:** draft #76, `d806a9791b18fab07e52a70a78b56f52144f5b8d`  
**Status:** SOURCE REVIEW COMPLETE; native cause NOT PROVEN  
**Scope:** read-only mapping. No runtime behavior, OCR engine, thresholds, item scores, capture policy, or HUD changes.

## Evidence boundaries and incident

On the user's first real N1 ARAM match the desktop launched, bench champions appeared, own champion was incorrect, augment titles were intermittent/apparently unrelated, and build advice appeared arbitrary/unhelpful. These are **user-observed FAIL**, not replayed or measured failures. No match screenshots or instrumented traces exist. The prior Windows #76 baseline CI proves unit/JS regression pass, not device correctness.

The evidence flow is: **external data → collector (proof and freshness) → canonical state → decision → API serialization → frontend visibility**. A valid item/champion/augment name in one stage does not prove its identity at another stage.

## Champion Select chain (F0.1 / FR-F0.1)

| Stage and source anchor | Source / output | Existing check or abstention | Open failure mode / needed trace |
| --- | --- | --- | --- |
| LCU access, `backend/collectors/lcu.py:9-86,132-149` | Local lockfile-authenticated `/lol-champ-select/v1/session`; returns draft or `None` | Read-only HTTPS; non-200/connection failure → `None`; credentials remain backend-only | Distinguish no LCU, phase absent, malformed draft, changed draft; never persist lockfile |
| Local identity, `backend/engine/champion_select.py:49-78` | `localPlayerCellId`, `myTeam[].cellId/championId` → `local_id` | Equal cell comparison, champion ID 0 excluded | Missing/duplicate cell, changing/swap, type mismatch, late update, missing local champion need separate enum outcomes; no authoritative self identity if the cell is absent |
| Bench / allies, `backend/collectors/lcu.py:87-103`, `backend/engine/champion_select.py:65-92` | `benchChampions` plus local ID become candidate set; other team roles contribute context | Bench IDs de-duplicated, zero excluded; teammate roles resolved when available | Bench being correct says nothing about self identity; missing self currently does not block bench scoring |
| Numeric ID → alias, `backend/collectors/lcu.py:104-130` | `/lol-game-data/assets/v1/champion-summary.json` maps numeric string to lowercase alias | Non-200/invalid response → empty map; requires positive numeric ID and alias | Mapping unavailable, renamed alias or missing static champion silently skips candidate, not a proven wrong champion |
| Candidate/scoring, `backend/engine/champion_select.py:91-143` | `get_champion(alias)`, kit/team/personal evidence → sorted `candidates[]` with `current` | Missing mapping → `skipped_ids`; `current` only `numeric_id == local_id` | Current identity provenance/unknown reason absent from payload; confidence applies to heuristic *score*, not correctness of local identity |
| API + WebSocket, `backend/api/server.py:511-521,539-542,1847-1880` | `_read_champ_select_payload` → `champ_select` / `champ_select_unavailable` or a minimal fallback message | LCU read in worker during poll; no raw player info sent | A changed/missing local cell has no stable source freshness tag; no per-candidate self/bench provenance |
| UI, `frontend/app.js:311-326,525-567` | Sorted cards; suffix `(current)` derived from backend boolean | Clears match display on champ-select payload; no local-champion lookup in JS | Missing current is indistinguishable from unverified; stale API payload vs incorrect server identity requires an offline UI assertion |

**Suggested F1 RED fixtures:** local ID different from bench and highest score; changed local cell across two LCU drafts; absent and type-inconsistent local cell; alias omitted; stale update. Assert local selection separately from bench listing, never equate score rank with current champion.

## Augment chain (F0.1 / FR-F0.2)

| Stage and source anchor | Source / output | Existing check or abstention | Open failure mode / needed trace |
| --- | --- | --- | --- |
| Eligibility / due, `backend/api/server.py:317-338,1537-1619` | LCDA level, death/respawn; due ledger and `scan_window_open` | Level gate enables *attempt*, not proof of visible cards | An open scan window can exist with no visible cards. No live approved independent present/absent event |
| Window and frame, `backend/collectors/league_window.py`, `window_capture.py:1-120`, `screen_ocr.py:264-305,614-658` | League HWND/client rect → WGC frame with `CaptureProof`; separately gated z-order screen-copy fallback | Reject invalid, old, wrong-window/occluded frames; focus recorded as `league/self/other`, not unconditional focus prohibition | Need source/backend, frame-proof and rejection reason per attempt; WGC under user's actual game unverified |
| Physical L/C/R geometry, `backend/collectors/card_title_geometry.py:1-67`, `slot_title_ocr.py:81-106` | Client-relative calibrated 2544×1353 title bands scaled to supported aspect/size; ordered `left/centre/right` crops | Reject unsupported ratio, undersized window and ROI mismatch | 1080p geometry is extrapolated, not native-calibrated; DPI, HUD scale, dialog, Maestro four-card layout require ground truth; never infer card order from OCR confidence |
| Title recognition, `backend/collectors/slot_title_ocr.py:31-79,108-151`, `screen_ocr.py:730-777` | Tesseract `eng` PSM7 then PSM6 per physical crop → normalized title → Mayhem catalog candidate | Exact strict `MATCH_THRESHOLD=90` and `MIN_MARGIN=8`; short/ambiguous/duplicate identity rejected; no raw OCR persisted | Cannot distinguish OCR misread from geometry failure or a wrong catalog title using existing bounded logs alone. Historical OCR benchmark does not prove live Windows |
| Temporal and reroll, `backend/collectors/slot_temporal.py:34-188`, `screen_ocr.py:305-484` | Per-slot image hash + repeated identity; independently newer second proven frame when pending | Two consistent reads; changed/unknown slots withheld; stale after capture interruption; pending across old/new epoch cannot be treated as current | Which physical slot changed, what was rejected (unknown/duplicate/transition), when freshness reset must be traced with coded outcomes |
| Lifecycle / epochs, `backend/collectors/offer_visibility.py:34-98`, `backend/workflow/offer_ledger.py:46-240`, `backend/api/server.py:1660-1811` | Shadow `offer_cue`, `OfferLedger`, `offer_epoch`, match identity; OCR `detected` updates verified slots | C1 cue shadow-only, negative calibration not approved; ledger rejects stale epoch and conflicts; disappearance does not confirm a pick | `due` and `visible` differ; a verified closure is unavailable in production absent an approved cue; need explicit epoch invalidation and rejection codes, not arbitrary identity guesses |
| Rank + WS/UI, `backend/workflow/pipeline.py:15-125`, `backend/api/server.py:1813-1839,2164-2245`, `frontend/app.js:705-745,880-958` | Strict offered IDs → ranking; only ledger **confirmed** augment IDs feed builds; WS `ocr_slots`, `offers`, `ocr_phase`, `offer_epoch` | JS drops older epoch and gates ratings on visible/verified/current; reroll requires 3 modelled ratings | UI rating may be absent because of lifecycle/phase/epoch even when OCR was read; need same-frame source→WS→UI stage correlation, without storing raw strings |

**Suggested F2 RED fixtures:** no offer/dialog with due level; physical L/C/R (including one unknown); single-slot reroll with old epoch response racing new result; unresolved duplicate title; capture interruption and stale state; four-card unsupported frame. Preserve 90/8, two-read, WGC policy and Tesseract.

## Build chain (F0.1 / FR-F0.3)

| Stage and source anchor | Source / output | Existing check or abstention | Open failure mode / needed trace |
| --- | --- | --- | --- |
| In-game self identity and inventory, `backend/collectors/lcda.py:20-33,130-210` | LCDA `activePlayer` matched to `allPlayers` using Riot ID first, legacy name fallback; champion alias, visible items in slots 0–5, gold, level/death, enemies | Excludes Poro-Snax / slot 6; missing active player can yield empty champion/unknown team; internal identity is not logged | A fall-back matching ambiguity, delayed inventory or unknown item mapping can poison context; no source freshness age or identity-method indicator to result |
| Confirmed augments, `backend/api/server.py:740-766,1813-1827`, `backend/workflow/offer_ledger.py:176-216` | `active_augment_ids()` → `snapshot.chosen_augments` | Pick requires explicit user confirmation tied to offer and epoch; candidate identities never imply owned augments | Legitimately chosen but not confirmed augments are absent from build context; distinguish `none_confirmed` from a full observed list |
| Item catalog and eligibility, `backend/static_data/loader.py:259-336,891-1035`, `item_policy.py:38-177` | Versioned DD/CDragon two-source patch proof, special recipes, item class, exclusivity and verified candidate pool | `recommendable_items()` empty unless `verified_two_source`; unknown/quest/conditional entries filtered; unverified meta disables next purchase | A patch-proof item candidate is not independent evidence the shop is open or that all current mode-specific entitlements are known; trace pool version/availability/class |
| Item/remaining cost, `backend/engine/inventory.py:17-85`, `build_suggester.py:130-330,331-443` | Six slots, owned finals/components, recursive recipes, exclusive groups, optional boots→MS swap | Unknown inventory/recipe can suppress next item; duplicate final/name, boots and exclusive items filtered; cost and slot block distinguished | Need explicit candidate exclusion reasons, actual slot facts and remaining-gold proof; optional boot swap uses estimated listed MS, not observed in-game active/passive effects |
| Composition/heuristics, `backend/engine/team_context.py`, `scoring.py`, `build_suggester.py:21-128` | Visible enemy/ally kits and items → threat profile; score_item and small reaction bonuses by chosen style | Context bonuses bounded, ranked by score then item ID | Score breakdown/top discarded candidates not sent to UI; the current generic explanation does not prove why one item outranked another |
| Pipeline, `backend/workflow/pipeline.py:15-125` | Confirmed champion, chosen augments, inventory, threat profile, item pool → `suggest_build` | Unknown champion returns `None`; unavailable pool clears next item | Partial context is still accepted for scoring: need explicit completeness/status and source cause before judging recommendations |
| Serialization/UI, `backend/api/server.py:2164-2260`, `frontend/app.js:570-575,960-1035` | `next_item_id/name`, gold needed, reasons, full build, selected style, data version → `Next: …` | Escapes names in expanded rows, hides missing next item | **Source-code PROVEN:** `renderUpdate` calls `renderBuild` on every update; no verified shop-open event gating this render. Existing UI reasons are broad, not an auditable winner-versus-excluded factor list |

**Suggested F3 RED fixtures:** verified vs unverified patch/item source, unknown owned item, components and full six-slot boots, conditional/quest reward, unavailable item, insufficient gold, missing confirmed augment, enemy armor/healing and stale/partial opponent context. Assert reason and eligibility separately from item's numeric score.

## Instrumentation gap matrix and non-invasive requirements

| Feature | Existing safe evidence | Missing trace for exact cause | Next diagnostic contract |
| --- | --- | --- | --- |
| Champion select | `champ_select` payload, `skipped_ids`, `/api/champ-select/status` | LCU cell outcome vs alias outcome vs UI badge, swap epoch | Enumerated stages `lcu/local_cell/alias/api/ui`; bounded `found/missing/ambiguous/unmapped/stale` with zero personal identifiers |
| Augments | `ocr_scan_stage`, `ocr_recognition`, `offer_cue` and payload phase/epoch | Slot-specific reason, proof freshness, strict match rejection class, reroll invalidation chain | Stage and reason enums, physical slot only, epoch local bounded, no text, pixels, HWND or screen coordinates |
| Builds | `item_data_source`, `item_outside_pool`, build_state reasons/version | Input completeness, pool candidate exclusions, score factor contributions | Typed `input/eligible/excluded/ranked/presented` codes; never arbitrary names, raw inventory, private IDs or free-form score inputs |
| Cross-boundary | Existing nonblocking bounded JSONL, `backend/diagnostic_events.py:1-258` | Optional event-level trace and opt-in for additional F0 diagnostics | Reuse journal, opt-in F0 events, no competing logger. Redact by allow-list and test hostile strings |

The existing `StructuredEventLogger` starts with the FastAPI lifespan and stores only schema-whitelisted fields in local rotating JSONL (256 KiB + 3 backups, bounded queue); it is **not** itself a default-off F0 tracing facility. F0 additions must be opt-in and must never save screenshots, OCR strings, player names, Riot IDs, auth, filesystem paths, raw LCDA, or unvalidated free-form explanations. Existing manually enabled screenshot diagnostics are out of scope: F0 does not turn them on.

## Fault tree / evidence status

1. **Observed FAIL / cause BLOCKED:** wrong self champion; LCU local-cell mismatch, source timing, ID/alias lookup and UI badge remain **SUSPECTED alternatives**, not root-cause verdicts.
2. **Observed FAIL / cause BLOCKED:** unreliable augment identities; capture, physical crops, OCR raw, catalog matching, temporal transitions and UI gating remain **SUSPECTED alternatives**. Shadow cue is not an approved present/absent proof (**PROVEN by code**).
3. **Observed FAIL / cause BLOCKED:** arbitrary item advice; corrupted/partial champion, unconfirmed augments, incomplete inventory, item eligibility, context scoring and broad UI explanation remain **SUSPECTED alternatives**. Lack of shop-open gating in `renderUpdate` is **PROVEN by source**, but not proven as the cause of the user's disliked item.
4. **NOT TESTED:** diagnostic opt-in effectiveness, synthetic end-to-end replay, real Windows frame and native custom-game acceptance on this F0 branch.

### Exit conditions before correction work

F0.2: whitelist-only opt-in event contract, deterministic negative tests, no private data exfiltration and no screenshot creation. F0.3: offline replay artifacts and explicit source-vs-UI differentiation, triage backed by reproducible tests; every F1/F2/F3 correction has its own future RED and Windows/custom acceptance gate. No F1–F4 production changes in F0.
