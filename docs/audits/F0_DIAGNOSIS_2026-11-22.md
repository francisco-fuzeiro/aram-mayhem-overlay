# F0.3 — Functional fault triage, reproducibility and correction queue

**Date:** 2026-11-22  
**Branch / draft:** `audit/f0-functional-lineage-20261122` / [#78](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/78), stacked directly on [#76](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/76).  
**Inputs:** [source lineage](F0_FUNCTIONAL_LINEAGE_2026-11-22.md), user-reported N1 game result, current offline source/tests.  
**Meaning of status:** `PROVEN` is a behavior directly established by code or a passing targeted deterministic test; `SUSPECTED` is a plausible explanation without reproducing the user's failure; `BLOCKED` needs an unavailable independent reference/trace; `NOT TESTED` is an unexecuted device or acceptance step. `FAIL (user-observed)` remains a distinct incident classification. No synthetic case is represented as replay of the unrecorded match.

## Results by fault boundary

| Reported problem / stage | Classification | Evidence actually available | Implication, not a speculative fix |
| --- | --- | --- | --- |
| Wrong **own** champion, bench recognized | **FAIL (user-observed); root cause BLOCKED** | No recorded LCU draft, UI frame or version-specific state from the match | Do not attribute to any one source; distinguish local cell and candidate list in a controlled session |
| LCU local-cell / alias / update ordering | **SUSPECTED** | `lcu.py` reads numeric ID summary; `champion_select.py` selects self by matching local `cellId` and skips missing aliases; `frontend/app.js` prints `(current)` based on backend boolean | Trace `lcu → local_cell → alias → API → UI` with only statuses. Compare with sanitized ground truth |
| Self vs bench ranking in synthetic case | **PROVEN as offline contract, not live** after GREEN | `tests/test_f0_trace.py`, `tests/test_f0_replay.py`, JS DOM tests cover independent self marker and bench sorting | F1 corrects only if a RED fixture identifies an actual failure in the production path |
| Augments intermittently unrelated to visible cards | **FAIL (user-observed); root cause BLOCKED** | No time-aligned frames or source-stage telemetry from user's match | Cannot infer whether capture, geometry, OCR, catalog, stale/epoch or rendering failed |
| Level-based scan initiation vs visible offer | **PROVEN by source** | `server.py` starts scanning after eligible level/respawn; C1 independent background cue is shadow-only; production `VerifiedAbsenceGate` lacks approved calibration | F2 must validate presence separately. A due offer is **not** visible-card ground truth |
| L/C/R layout and OCR accuracy on actual Windows game | **NOT TESTED** | `card_title_geometry.py` uses measured 2544×1353 positions scaled to 1080p; historical 19 positive + 7 negative benchmark was on previously collected crops, not this match | Test crop bounds and per-slot ground truth independently; never label offscreen or four-card Maestro as verified |
| Strict OCR, stale epoch and confirmed pick separation | **PROVEN implementation gates; native correctness NOT TESTED** | `MATCH_THRESHOLD=90`, `MIN_MARGIN=8`, two-read per-slot, ledger epoch and explicit user confirmation; existing regression tests; F0 tests add failure classifications | Retain all protections. Being internally consistent does not prove that the accepted ID matches the physical card |
| Arbitrary/unhelpful item recommendation | **FAIL (user-observed); root cause BLOCKED** | No exact game inventory/shop/confirmed augments or shown item from user's match | Cannot claim faulty ranking weights, catalog or enemy context as root cause |
| Build pool gate and confirmation-only augments | **PROVEN by source** | `recommendable_items()` requires two-source patch/availability; `pipeline.py` uses ledger-confirmed augments and inventory to compute `build_state` | Build without a confirmed augment can be context-incomplete; do not fabricate missing selections |
| Shop-open gate in current JS build renderer | **PROVEN by source/DOM contract** after GREEN | `renderUpdate` calls `renderBuild` for each live update; `renderBuild` copies `next_item_name` and gold; no verified shop-open source used here | F4 must gate display at verified shop context, **after** F1–F3 input correctness. This is not proven as cause of the user's item quality complaint |
| Individual item eligibility / score reasons | **PROVEN instrumentation gap** | `_rank_items()` orders by score, role, enemy bonuses; `build_state.reasons` is broad and serialized without winner-vs-exclusion contribution details | F3 may instrument true factors and rejection codes without ranking change; current F0 trace reports `score_breakdown_unavailable`, never invented weights |
| New opt-in whitelist diagnostics | **PROVEN only after passing exact-head Windows CI** | `backend/workflow/f0_trace.py`, existing bounded `diagnostic_events.py`, adversarial sanitization tests | Emits source/status/reason/slot/epoch only if `ARAM_ORACLE_F0_TRACE=1`; no OCR text, names, credentials, screenshots or full window coordinates |
| Controlled custom Mayhem game on user Windows | **NOT TESTED** | No request for additional normal ARAM match captures | Schedule one optional deliberate custom-game validation after offline gate; never claim native PASS from runner success |

## How to run F0 offline evidence

1. `python -m pytest -q` — Python deterministic contracts and existing regressions.  
2. `node --test tests/js/*.cjs` — actual frontend DOM/WebSocket harness including F0 current-marker and next-item source-to-UI synthetic cases.  
3. `node --check frontend/app.js`, `node --check frontend/settings.js`, `node --check frontend/overlay-preferences.js`.  
4. `python -m backend.workflow.f0_replay` — emits a **synthetic-only**, deterministic JSON report with fixed scenario identifiers and enumerated outcomes. It never reads League, OCR or screen pixels.
5. Optional extra local evidence: launch the existing application with `ARAM_ORACLE_F0_TRACE=1` explicitly set in its process environment. New F0 diagnostic events append only to the **existing local rotating diagnostics journal**; inspect and delete locally. Do not enable existing optional screenshot policy, transmit logs, or paste raw player/desktop data into GitHub. Without the env variable, no F0 event is emitted. The original M1 journal remains present as before.

These fixtures are synthetic **contract checks**, not real frame OCR comparisons and not proof that a source is correct in the field. The result records deliberately have no champion/augment raw title, player name, Riot ID, PNG or credentials. When explicitly enabled, live F0 status records may include only validated numeric **public** champion/augment catalog IDs from source-proven mappings, never local cell/player IDs or arbitrary strings. Additional captures are not required to execute them.

## Follow-up queue — independent small draft PRs, NOT implemented here

| Priority | Proposed scope | First RED scenario and evidence target | Offline exit + future Windows custom check |
| --- | --- | --- | --- |
| **P0 F1.1** | Authoritative self/bench LCU cell and alias mapping | Synthetic local self with different bench ID, swap, missing/duplicated cell, numeric/string edge, invalid or delayed alias; assert `current` never inferred from rank | Exact identity for declared matrix, fail closed on unknown. In custom champion select compare self/bench with deliberate user observation |
| **P0 F1.2** | Source freshness and UI `current` consistency | Two successive LCU drafts during swap; late stale WS message must not restore old current | No false current marker in DOM test; one controlled swap in custom lobby |
| **P0 F2.1** | Verified visible-offer and capture reason | At augment level with no cards/dialog, stale or unavailable WGC frame; assert no actionable offer | Presence must have independent evidence; controlled pre-offer/dialog and focused League |
| **P0 F2.2** | True physical L/C/R geometry | Three distinct title-band fixtures, one mismatched DPI/aspect, one four-card layout; assert bounds/order or safe reject | Zero wrong accepted physical slot IDs within declared independent corpus; one intentional reroll left/centre/right on Windows |
| **P0 F2.3** | OCR raw → preprocessing → matching rejection taxonomy | Unseen independent positive/negative per slot, multiline, duplicate/ambiguous result; strict 90/8 unchanged | Classify preproc vs raw OCR vs matcher; do not promote PP-OCR without V1.2 permission |
| **P0 F2.4** | Per-slot reroll, temporal and epoch safety | Changed one card during two-read capture, old epoch finishing late, UI retaining old slot | No stale accepted current ID, no inferred confirmation; custom one-card reroll verification |
| **P0 F3.1** | Build provenance envelope | Champion unknown or changed, item pool patch unknown, unconfirmed augment, inventory contains unknown owned ID | No apparently confident suggestion from unverifiable source; deliberate custom item/pick state |
| **P0 F3.2** | Honest item scoring factors/rejections | Two eligible candidates with controlled enemy pressure, recipe, exclusive group; expect separate bounded contribution and exclusion enums | Explain *why* selected item wins; no ranking weight edits absent new authorization |
| **P0 F3.3** | Mode/shop item feasibility | Verified final vs conditional/quest/augment-only item, owned components, six slots and optional boots | No excluded item marked purchasable; tested shop-open screen on controlled Windows client |
| **P1 F4.1–F4.3** | Contextual HUD visibility | Due level without offer, verified offer, verified shop, combat, stale/Alt+Tab | Only relevant panel appears; user custom HUD/focus acceptance; no click/auto actions |

## Controlled custom-game procedure (preparation only)

**Prerequisite:** exact final F0 Windows Actions SUCCESS with Python/JS/syntax checks; source/report trace is available. No more normal-match screenshots are required.

1. On the user's Windows installation, verify checked-out F0 SHA and single local desktop/API instance; all recording opt-in and local.
2. In a **user-controlled custom ARAM Mayhem game** (if accessible under current client rules), compare visually local champion with bench and the current marker; capture only the enum diagnostic outcomes if needed.
3. At a three-card choice, compare actual **left/centre/right** card titles with statuses, one intentionally rerolled slot and a full fresh epoch; check absence/occlusion cases without forcing hidden desktop capture.
4. Confirm an augment explicitly. In the shop check observed inventory, gold, available item, candidate status and displayed next purchase against the real game, without automatic purchase.
5. Check panel visibility, Alt+Tab, FPS/focus stability and overlay hotkeys separately. Keep any screenshots private unless deliberately redacted and authorized. On an unsupported custom setup, report **BLOCKED** instead of inferring success.
6. Mark each independently PASS/FAIL/BLOCKED/NOT TESTED in `docs/N1_NATIVE_ACCEPTANCE.md` **only after user-provided controlled evidence**.

The optional `f0_geometry` envelope logs the actual *client-relative* L/C/R crop rectangles only after an A3-verified capture and valid geometry. These are crop coordinates, **not confirmation** that the titles line up on the user's unrecorded match. It never logs global desktop origin, HWND or pixels; strict numeric bounds and invalid ROI negative tests are included.

## Gate and outstanding decisions

F0 delivers a map, minimal opt-in classification and sanitized replay, **not gameplay repair**. Specific real-match root causes remain **BLOCKED** until independent aligned ground truth. No F1–F4 modifications, no production OCR engine swap, no WGC/90/8/epoch/pick-rule changes. Public Riot policy review/distribution approval remains a separate BLOCKED decision, not inferred from competitor apps.
