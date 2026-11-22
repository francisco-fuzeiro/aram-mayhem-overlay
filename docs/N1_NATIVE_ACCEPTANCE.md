# N1 v3 — Native Windows ARAM Mayhem acceptance

## 2026-11-22 — F1.3 custom Windows acceptance protocol prepared

The [F1-N00–F1-N06 native matrix](docs/plans/F1_3_CONTROLLED_NATIVE_VALIDATION_2026-11-22.md) has been documented but **not executed on the user's Windows client**. Custom Mayhem was added by Riot in patch 25.22; the current lobby UI, starting conditions, self/bench availability and manual swaps are **NOT TESTED**. The exact earlier F1.1/F1.2 code+docs SHA `50138b091ec897c62b84d82cabbffe2878626379` passed [Windows #44982404803](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44982404803) (1,969 Python, 78 JS, three syntax). Any new documentation HEAD requires its own gate. No personal screenshots/IDs/logs requested. The original real-game champion FAIL remains, root cause BLOCKED, N1 overall NOT ACCEPTED, F1.3 open and F2 NOT STARTED.


## 2026-11-22 — F1 Champion Select recovery, pending real-game validation

F1 in open direct-child [draft #80](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/80) on audited F0 #78; see [synthetic matrix and evidence](audits/F1_CHAMPION_SELECT_2026-11-22.md). Its source-to-UI fixes address demonstrable ambiguous-local-cell and late-WS-packet boundaries, but cannot retroactively prove the cause of the user's unrecorded ARAM wrong-current symptom.

| Acceptance case | Classification | Current evidence or next native action |
| --- | --- | --- |
| F1-01 self from unique local LCU cell and alias | PROVEN as code contract after exact GREEN | Synthetic LCU → API → backend poll → WebSocket → real JS DOM tests, not native |
| F1-02 bench ranked above current / distinct allies | PROVEN as code contract after exact GREEN | No rank-to-current inference; bench candidate remains independent |
| F1-03 one champion swap / late old packet | PROVEN as code contract after exact GREEN | Monotonic read revision + DOM last-revision guard; native timing NOT TESTED |
| F1-04 duplicate/missing/invalid cell, unmapped alias/catalog | PROVEN as code contract after exact GREEN | Identity unresolved, no false badge; bench may remain |
| F1-05 temporary LCU outage | PROVEN as code contract after exact GREEN | Poll emits unresolved/empty candidate list; real outage NOT TESTED |
| F1-06 custom-game visual self/bench/swap | NOT TESTED | User-controlled custom ARAM Mayhem lobby only if supported; no ordinary live-match request |
| N1 original wrong champion | FAIL (user-observed); root cause BLOCKED | No contemporaneous client source / UI record from original match; an offline fix does not establish attribution |

**Required controlled check:** On user Windows at the latest verified F1 SHA, open a permitted controlled custom ARAM Mayhem champion-select lobby. Independently note the real selected champion portrait/name and available bench; compare exactly one `(current)` marker. If swapping is available, change self once and verify the badge migrates while the old champion may appear in bench; if the LCU temporarily disconnects, no previous current may be presented as verified. Do not disrupt a normal competitive ARAM, request personal IDs/screenshots, or enable capture without consent. On unsupported custom mode, mark this native check BLOCKED, not PASS. `ARAM_ORACLE_F0_TRACE=1` is optional local-only enum logging and never transmits player identity.

**CI at documentation checkpoint:** F1.1 [RED #44981614324](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44981614324), F1.2 [RED #44981718994](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44981718994). Exact final documentation SHA Actions SUCCESS still to confirm; native N1 product overall remains FAIL/NOT ACCEPTED.

## 2026-11-22 — F0 source-to-UI audit (not native acceptance)

Draft [#78](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/78) was stacked on verified #76 to map source-to-UI chains and introduce opt-in local evidence diagnostics and synthetic replay. See [F0 source map](audits/F0_FUNCTIONAL_LINEAGE_2026-11-22.md) and [classified F0 report](audits/F0_DIAGNOSIS_2026-11-22.md). Public numeric champion/augment catalog IDs may now be emitted locally only after LCU mapping/strict OCR acceptance, never player identities; this does not prove the IDs match the unrecorded live game. The N1 champion/augment/build observations above remain **FAIL (user-observed)**; specific causes still **BLOCKED** absent contemporaneous source and screen ground truth. Passing synthetic fixtures cannot reverse that FAIL.

| F0-specific check | Current status | Native acceptance boundary |
| --- | --- | --- |
| LCU self/bench/alias and actual JS badge replay | SOURCE REVIEW / offline tests committed | Live self champion/swaps on user Windows **NOT TESTED** |
| Offer capture/physical L/C/R/strict match/epoch | SOURCE REVIEW / synthetic traces committed | Client-relative bounds are now available from opt-in F0 diagnostics, but ground-truth native cards, rerolls, WGC/Vanguard and four-card **NOT TESTED** |
| Verified item-pool/inventory/confirmed augments/build UI | SOURCE REVIEW / synthetic traces committed | Item eligibility and decision usefulness in real shop **NOT TESTED** |
| F0 privacy | Opt-in bounded local allowlist + adversarial test committed | F0 offline gate [Windows #44980777980](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44980777980) PASS at `c665f1eb` (1,963 Python, 75 JS, 3 syntax); final checklist-only SHA CI pending; no automatic screenshots |
| N1 product state | **FAIL / NOT ACCEPTED** | Controlled custom game only after offline gate; no additional normal game requests |


**Status (2026-11-22):** #73 AUTONOMOUS DESKTOP START NARROW PASS / FIRST REAL ARAM GAME FUNCTIONAL FAIL / N1 PRODUCT NOT ACCEPTED / F0–F4 RECOVERY PLANNED. No game feature PASS or numeric accuracy is claimed.

## 2026-11-22 — First real ARAM match: user-reported functional FAIL

The user verified that desktop Settings opened **autonomously** from exact #73 N1 on Windows; this is a **narrow cold-start PASS** with the local state/cache on that machine, not a proof about fresh installs or patch changes. They then played a genuine ARAM match, **not a controlled validation game**. They intentionally did not take screenshots/logs while playing. Their reported experience:

| Area | Native status | Observation and unresolved source |
| --- | --- | --- |
| Desktop cold start on #73 | **PASS narrow** | Settings started without manually launching the API; cached-patch condition, longer stability, no-cache path and tray checks are independent |
| Champion select | **FAIL, user-observed** | Bench champions recognized, own currently selected champion misidentified; LCU cell/id mapping, frontend current badge and update ordering unresolved |
| Augments | **FAIL, user-observed** | Occasional apparent detections with unrelated names; capture/geometry, raw OCR, matching, offer state, stale/epoch and UI unproven |
| Build | **FAIL, user-observed** | Item recommendation appeared arbitrary/unhelpful; champion/augments/inventory/enemy inputs, item eligibility and scoring source unresolved |
| Actual recommendation usefulness | **FAIL, user-observed** | User did not identify a useful in-game recommendation; not an objectively scored outcome |
| Full N1 native functional acceptance | **FAIL / NOT ACCEPTED** | No screenshots, precise cases, timings or rates; do not infer exact root causes or claim a controlled L/C/R success |

**Correction path:** [functional recovery F0–F4](plans/ARAM_FUNCTIONAL_RECOVERY_2026-11-22.md) recorded on documentation-only [draft #76](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/76), directly on #73. F0 safe data lineage + deterministic/sanitized replay first; then F1 local champion, F2 augments, F3 build correctness, F4 contextual HUD. Each bounded correction must have RED→GREEN, exact-head Windows CI, and its own native evidence. Do not ask user for more disruptive normal-match screenshots; test with an intentional **custom game** only after offline gate. OCR independent #72/#74/#75: no inference that same 26 historical offline samples prove live recognition, and **V1.2 engine change NO-GO**.

**Historical sections below were written before this user's #73 game and are preserved as the event timeline; their older `NOT TESTED` statements are superseded by the specific 2026-11-22 user-reported FAIL above.** Earlier D2 custom tests are distinct from this N1 real-game observation.

## Authority and scope

- Reference: `docs/plans/ARAM_2026-11-20/README.md`, v3 audit, global rules and **only the N1 section** of `corrections/blueprints/M-D_overlay.md`.
- Parent: D2 draft PR #68, branch `fix/d2-unified-augment-overlay`, SHA `14ed84be8045403bfea9ccb3cad89cf14bf4d494`; D1 draft #67. No merge, no change to `main`.
- Verified exact-parent CI: [Windows #44841552493](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44841552493), 1,944 Python PASS (51 warnings), 72 JS PASS, three syntax-check steps PASS. This is **offline/runner evidence only**.
- Old 2026-11-20 custom game on an earlier build failed to detect three visible augments, gave misleading focus state, proposed unavailable reward items and overlapped the HUD. This is historical FAIL, **not** an executed N1 failure.
- At checklist preparation on 2026-11-21, no N1 gameplay/Windows capture run had yet been performed; this historical statement is superseded by the 2026-11-22 user-reported real ARAM functional FAIL recorded above. No numeric false PASS.
- C1 `offer_cue` is shadow-only; no independently approved negative cue; visual disappearance alone never closes or confirms a pick. S1/C3 and click hints are OFF and not N1 prerequisites. Four-card Maestro remains unsupported and must fail closed, not be treated as three cards.
- Repository visibility is reported **public** by the connected GitHub repository metadata on 2026-11-21, although described as private in the user request. No visibility change is authorized. Do **not** commit unredacted screenshots, logs, game identities, user paths or secrets.

## 2026-11-21 native preflight findings and targeted N1 correction

Evidence is from the user's local Windows PowerShell/browser screenshots, not from Windows Actions or a real League gameplay validation. Tesseract executable exists with English `eng`; Python `windows-capture==2.0.1` was installed. A separately started local API eventually returned `/health` HTTP 200 with `data_loaded=true`, 172 champions, 328 augments and 863 items; `/settings` and `/api/ocr/status` returned HTTP 200. These are **preflight-only PASS**, not OCR/gameplay or purchasable Mayhem item proof.

| ID | Preflight check | Evidence-based status | Action / limitation |
|---|---|---|---|
| N1-PF-01 | Python, WGC package, Tesseract `eng`, local API health + Settings HTTP | PASS (user device) | No live OCR/gameplay inference |
| N1-PF-02 | Managed desktop can remain running | **FAIL observed on D2**, new code retest **NOT TESTED** | Settings opened then closed spontaneously. Native traceback `TypeError: '>=' not supported between instances of 'JavaScriptConsoleMessageLevel'` from `backend/overlay/window.py:102` |
| N1-PF-03 | Cold managed desktop starts from no API within its readiness gate | **FAIL observed on D2**, root-cause attribution **BLOCKED** | `ManagedApi.start(timeout=15.0)` timed out. Separately started API eventually completed startup; synchronous `StaticData.load()` may involve network calls. No measured cold-start duration or proof of precise delay yet; threshold unchanged |
| N1-PF-04 | In-game native Qt + League/OP.GG, HUD, focus, OCR | NOT TESTED | Do not run while desktop preflight is unresolved |
| N1-PF-05 | No unconsented debug screenshots | PASS (user config log) | Second startup reports `ocr_debug_screenshots = False`; do not commit private captures |

**Crash correction authorized by user:** branch `fix/n1-qt-console-crash`, stacked draft PR #70 directly on #69. Tests-only `d3417ebc6c8e693c57e014810317e80218df82cf` [Windows RED #44953828531](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44953828531): exactly one `test_n1_qt_console_levels_do_not_raise_and_only_log_errors` FAIL with the same enum `>=` TypeError, 1,944 other Python tests PASS. Production `34e60d789a7e0985dad5f845a0a1b4ce6f8cc324` [Windows code GREEN #44953995394](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44953995394): **1,945 Python PASS, 72 JavaScript PASS, three JS syntax checks PASS**, 51 Python warnings. Only the Qt callback comparison changes from enum ordering to `level.value >= ...ErrorMessageLevel.value`; no user actions, new gameplay, OCR, fallback, HUD geometry or build code changed. This proves the **offline regression fix only**. Exact final documentation-HEAD Windows success must be verified separately.

**Next native preflight:** use the final PR #70 SHA, first with a compatible API already running to isolate Qt; observe whether the Settings window/tray persists and verify console errors no longer close the app. Then, in a separate run without an existing API, measure the cold-start duration and actual API readiness stage. A code fix for the 15s timeout is **not yet authorized or justified by an exact causal measurement**. Preserve fail-closed behavior, no repeated League session.

## 2026-11-21 N1 browser bootstrap correction — PR #71 (separate from OCR V1)

**Native user observation:** On the patched Qt-host commit from PR #70 and with a separately running API, Windows desktop Settings opened quickly and remained visible long enough for the user to interact. **Alt+H displayed the overlay**. The visible `Live game data temporarily unavailable` message and sparse content are **not, by themselves, a no-League defect**, but cannot validate the WebSocket or gameplay. The terminal disclosed a definite frontend error: `JS [http://localhost:8765/static/app.js:70]: Uncaught ReferenceError: loadBuildPreference is not defined`. The historical `loadBuildPreference()` call remained in `init()` after pre-game build-style selection was moved into desktop Settings; it prevented subsequent `bindNativeWindowControls()` from executing.

| Subcase | Status | Evidence and limitation |
|---|---|---|
| N1-PF-02b | **PASS initial** | User Windows screenshot: Qt Settings opened on PR #70; Alt+H revealed overlay. Long-duration stability, other shortcuts and native focus still NOT TESTED |
| N1-PF-06a | **FAIL reproduced on pre-fix version** | Native Qt JS console ReferenceError at frontend/app.js:70, independent of the missing League game |
| N1-PF-06b | **PASS automated only; NOT TESTED native on new SHA** | `frontend/app.js` stale call removed; full browser `init()` regression now completes and wires WebSocket, Qt hide/quit, window messages and keyboard listener |
| N1-PF-03 | **BLOCKED causal attribution** | Original 15s cold API timeout remains under investigation, unmodified |
| N1 gameplay | **NOT TESTED** | OCR, L/C/R, rerolls, HUD, in-game build, monitor/DPI, privacy and Riot release remain open |

**Authorized correction and audit:** [draft PR #71](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/71) is stacked directly on #70 → #69 → #68. Tests-only `2c631fa5d8c1eb0d21de84af17c8d7c70854454f` [Windows RED #44955660838](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44955660838): 1,945 Python PASS, 72 older JS PASS, **exactly one JS FAIL** `ReferenceError: loadBuildPreference is not defined` from executing the real browser initialization branch. Production `f7801669580b6557f5104c2fcdd0335e3f316b11` [Windows code GREEN #44955851710](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44955851710): **1,945 Python PASS (51 warnings), 73 JavaScript PASS (zero failures, zero skips), three syntax checks PASS**. Source change is solely removal of `await loadBuildPreference();` in `frontend/app.js`; test harness only elsewhere. Earlier test-only attempts #44955076665 (test syntax error) and #44955293039 (unrelated intermittent Python async timeout) **were not accepted as valid RED evidence**; the valid RED is #44955660838. Check exact final documentation SHA in Windows Actions before declaring documentation gate passed. No game, OCR thresholds, WGC, stale/epoch rules, selection, HUD, recommendation, Riot or future V1 change.

**Next user PC actions after final CI:** checkout exact final PR #71 SHA; launch with compatible API already ready; confirm Settings/tray, Alt+H, Qt hide/quit controls and no ReferenceError in terminal. Then measure cold-start without API separately, before any minimal timeout proposal. No need for League until preflight is stable.

## 2026-11-21 — Cold desktop startup preflight, cache-first patch and safety limits

**Native device evidence:** User's Windows PowerShell ran exact #71 commit `7624b27c1d025c4183c2a78aa11609dda45ecf71` with a prestarted compatible API: Settings opened promptly, remained running and Alt+H showed overlay with **no previous Qt enum or JavaScript `loadBuildPreference` crash observed**. This is a narrow native warm-start PASS; other focus, tray menu, live gameplay and OCR remain untested.

After closing the desktop and stopping the manual API, port 8765 was free. A standalone managed desktop attempt started around 22:36:18 and failed around 22:36:41 after its unchanged 15s readiness deadline plus shutdown handling. Separate diagnostic `backend.main --no-browser` did not return fully probe-ready within **90.87s** on that run (`API_READY=False`); later log text includes application startup completion but lacks a trustworthy precise elapsed completion timestamp.

The user captured live repeated `faulthandler` traceback during blocked ASGI startup: `backend/api/server.py:349` → `StaticData.load()` → `backend/static_data/loader.py:230` → `_load_items():972` → `requests.get()` → `urllib3.connection.create_connection()`. The offending source request is the patch-specific CommunityDragon item catalog; prior DD version/item/CommunityDragon metadata lookups are also possible. Later stacks in `asyncio._poll` indicate a normally idling loop, **not** continuing proof of a network stall.

| Case | Evidence-based status | Required next verification |
|---|---|---|
| N1-PF-02b, #71 warm Qt | PASS narrow | Verify tray, hide/quit actions and other focus scenarios separately |
| N1-PF-06c, #71 JS startup | PASS narrow | No `ReferenceError` seen in exact Windows run; no game inference |
| N1-PF-03, #71 autonomous cold startup | **FAIL on user device** | 15s desktop startup exceeded; versioned item-source network stack captured |
| N1-PF-03a, #73 verified item-cache fast path | **PASS offline Windows CI, NOT TESTED native** | With exact same patch, policy, two-source metadata and overrides, return cache before network; `4e076624593631e72fd5588f2ce48bb253d3670b` [RED #44959410686](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44959410686) = one expected FAIL / 1,946 Python PASS; `cc9ac27fbcfaa0232422d79eb4c20bf06e0ca732` [code GREEN #44959582650](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44959582650) = 1,947 Python PASS / 73 JS PASS / three JS syntax PASS, 51 Python warnings |
| N1-PF-03b, no verified matching cache or patch change | **OPEN — potential remaining timeout** | Falls through to existing network, source conflict protections and recognition-only fail-closed catalog; first-install/offline guarantees are **not** established |
| Native ARAM Mayhem game | NOT TESTED | Only after autonomous desktop preflight is safe |

**Scope:** [draft #73](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/73) is a direct child of #71, with a single localized early cache lookup in `_load_items()` and two deterministic tests. Cache is only trusted after existing `_verified_cached_items` same-version / policy / overrides / two-source provenance checks; corrupt SHA proof or unavailable sources leave shop recommendation IDs empty. Explicit `/api/refresh` / forced refresh still deletes caches before fetching. A matching cache may avoid the observed CD item network wait; no claim of a universal first-install fix, no elapsed native measurement yet. Backend startup deadline remains 15s. No OCR/V1, WGC, HUD, recommendation algorithm, Riot policy or `main` changes. Check final documentation SHA CI independently.

## Status vocabulary

- **PASS:** observed and supported by a named artifact, run, output or inspected code invariant; source evidence clearly labeled as automated vs native.
- **FAIL:** actual reproducible failure in this N1 version, with timestamp, expected/observed, diagnostic stage and sanitized evidence.
- **BLOCKED:** a dependency/access/policy/unsupported state prevents testing; name the blocker.
- **NOT TESTED:** executable but not performed. Never turn automated runner success into native PASS.

## Checklist and evidence ledger (initial)

| ID | Acceptance criterion | Status | Evidence / missing proof |
|---|---|---|---|
| N1-00 | D2 final SHA and full Windows CI | PASS (CI only) | #68 SHA above; #44841552493 success and job log: 1944/72, 3 syntax |
| N1-01 | League client-window capture with proven `capture_backend` | NOT TESTED | Native WGC/source-proven `capture_backend`; no other-window pixels |
| N1-02 | League focused and unfocused; no focus-dependent permanent lock | NOT TESTED | Native foreground reason, Alt+Tab and OP.GG |
| N1-03 | First three physical L/C/R cards correctly recognized within <=6s untouched | NOT TESTED | Ground-truth L/C/R and time + anonymized stage events |
| N1-04 | Per-slot left/centre/right reroll, changed slot only | NOT TESTED | For each slot old/new and unchanged neighbors |
| N1-05 | Animation, dialogue, tooltip, occlusion and invalid-frame fail-closed | NOT TESTED | No invented identity/pick/closed state; classify each |
| N1-06 | Two fresh proven reads, stale recovery and epoch fencing | NOT TESTED | Snip/Alt+Tab, rescan, old-epoch rejection |
| N1-07 | Transparent, default click-through, no stolen League focus | NOT TESTED | In-game click, Alt+O, Alt+H, Qt affinity report |
| N1-08 | Alt+S, Alt+1/2/3 and Alt+B perform their documented local actions | NOT TESTED | Action time + corresponding events; no League input sent |
| N1-09 | Actual HUD exclusion across visible League HUD | NOT TESTED | Private one-frame full screenshot; measure seven provisional zones |
| N1-10 | Resolution/DPI/monitor/HUD-scale physical-to-logical alignment | NOT TESTED | 1080p/1440p and available 100/125/150%, negative origin; record untested configs |
| N1-11 | Due offer remains quiet without opening card list | NOT TESTED | No automatic open from due alone |
| N1-12 | Verified/awaiting/recovered offers show only current L/C/R identities | NOT TESTED | Offer ID, epoch, state and slot order |
| N1-13 | Manual identity only; no counter/build mutation without explicit Pick | NOT TESTED | Identify via Alt+O; check unchanged chosen/build; then Pick |
| N1-14 | Explicit in-game choice + Alt+1/2/3 confirmation, correct counter | NOT TESTED | Confirmed ID/offer/epoch; no inference from disappearance |
| N1-15 | Tab/shop shown on cards does not fabricate choice/update build | NOT TESTED | No confirmed pick while covered |
| N1-16 | Subsequent offer k+1 independent; old confirmation cannot mutate it | NOT TESTED | Two offer IDs/epochs, stale attempt |
| N1-17 | One eligible build, next purchase in correct order, no reward-only items/duplicates | NOT TESTED | Compare available shop/owned components to recommendations |
| N1-18 | Compact build in combat; detail on death or Alt+B, closes on respawn | NOT TESTED | UI at live/dead/respawn and hotkey pin |
| N1-19 | Settings OCR toggle, manual scan and phase/foreground/backend diagnostics | NOT TESTED | Pre-game save, test, restart, re-enable & scan |
| N1-20 | Settings preferences persist and hotkeys are descriptive, not in-game controls | NOT TESTED | File/API preference value before/after restart |
| N1-21 | No old offers, picks, champion or build after respawn/match change/loss | NOT TESTED | Two independent offer epochs; next game only if available |
| N1-22 | `offer_cue` and `item_outside_pool` event semantics checked | NOT TESTED | Events present only where emitted; absence not automatically a defect |
| N1-23 | Riot third-party product compliance / permission for public distribution | BLOCKED | Developer Portal registration/review not evidenced; dynamic immediate advice unresolved |
| N1-24 | Public GitHub evidence privacy | PASS (read-only observation) | Repository visibility confirmed public; no sensitive evidence committed in N1 preparation |

`N1-10` is an environment matrix: each unavailable configuration stays NOT TESTED; do not imply full coverage. `N1-22`: `item_outside_pool` fires only if that condition occurs; no event in an ordinary game is not proof of a defect.

## Native test protocol: one custom match, borderless + OP.GG enabled

### Preflight, without opening League
1. Use an unchanged checkout of D2 SHA `14ed84be8045403bfea9ccb3cad89cf14bf4d494`. Record `git rev-parse HEAD` and `git status --short`; do not overwrite local changes. Do **not** test the N1 docs branch as if it contained new app code.
2. From the repository directory, ensure Python 3.11+, Tesseract `eng` and Qt/WebEngine are installed. Existing documented commands: `python -m pip install -e ".[overlay]"`, `python -m backend.desktop` (managed Settings/tray), or `python -m backend.overlay --renderer qt` (existing standalone).
3. Before play, open Settings (tray or `http://127.0.0.1:8765/settings`), check backend OCR status, change a harmless overlay preference, save, exit/restart, verify restore, then revert; toggle OCR off/on. Confirm that `Alt+S` is displayed but is **not** currently rebindable in Settings.
4. Query `http://127.0.0.1:8765/api/ocr/status` and record sanitized `phase`, `foreground`, `capture_backend` and readiness. A pre-game `capture_backend = null` does not prove live capture failure.
5. Record primary monitor resolution, physical scaling (100/125/150%), League borderless mode, HUD/minimap scales, signed monitor position and OP.GG enabled. Do not change capture thresholds, fallback opt-in, safety settings, or HUD JSON during test.

### During the **same match**, chronological
1. Join a **custom ARAM Mayhem** game in borderless with OP.GG active. Verify unobstructed HUD, click-through, focus and idle/contextual minimality before the first offer.
2. At first L/C/R offer, do not touch keys/overlay for six seconds. Write down real left/centre/right names and whether recommendations appear in <=6s; capture once privately with the offer visible, for D1 HUD-zone measurements. This image **must not** enter GitHub; share privately/redact when needed.
3. With offer still visible, Win+Shift+S once; restore game focus if needed. Observe stale badge, recovery and whether Alt+S is necessary. Test Alt+O only outside dangerous fight moments; unknown-card manual identity must not confirm.
4. Reroll each physical slot (left, centre, right) once if rerolls are available; record before/after names and exact unchanged neighbors. If rerolls are limited, mark unexecuted slots NOT TESTED, not PASS. Briefly show a tooltip/dialogue/animation and verify fail-closed behavior.
5. Where feasible, open Tab and shop while cards are present; check no inferred pick. Choose a card **in the game yourself**, then explicitly press the corresponding Alt+1/2/3 to register the chosen slot; verify chosen count and next build only change after confirmation.
6. At subsequent offer k+1, verify different offer ID/epoch, no confirmation of previous offer affects this one. Exercise manual identify/Pick only when safe; do not send additional in-game automation.
7. During combat, observe compact next item only; at death see full list; respawn should collapse unless manually pinned Alt+B. Verify purchase feasibility versus current in-game shop and reject reward-only/duplicate suggestions. Try Alt+B and Alt+H.
8. If safe and within the same game, open Settings from tray to disable/re-enable OCR; check old advice clears and a new verified observation is required. Alt+Tab to and from another app, observing privacy/focus/capture stage.
9. Finish/leave the match and verify no old offer persists. A second match is **not** requested by default. If clearing between matches remains unobservable, mark that subset NOT TESTED; only plan another later with explicit need.

### After the match (no more matches)
1. Stop ARAM Oracle normally through tray > Quit ARAM Oracle. Collect `%LOCALAPPDATA%\ARAMOracle\logs\events.jsonl` **privately**, plus a sanitized table of timestamps, source, backend, OCR phase, offers, rerolls, confirmations and observed problems. No raw log in the public repo.
2. Keep one private full-screen image of the offer for seven-zone HUD measurements. If shared, redact account names, chat, private content and any identifiers; crop only where needed.
3. Record expected/actual per case, case ID, Windows DPI/resolution/origin, OP.GG state, version SHA and timestamps. A failure must be reproducible before proposing a minimal in-scope N1 fix.
4. Classify failure as application bug vs unsupported native environment vs calibration. No automatic threshold changes, WGC fallback enablement, geometry JSON changes, scoring changes, main merges or C3/S1.
5. Maintain status per checklist case. A scoped code fix requires separate user authorization, fresh child branch/stacked draft PR, tests RED->GREEN, all regressions and exact-final-SHA Windows Actions SUCCESS. Document final acceptance as OPEN until all required native cases pass.

## Riot policy (public sources reviewed 2026-11-21)

- Confirmed official LOL game policy: augment/Arena-item win-rate presentation prohibited; session-specific otherwise unknown information prohibited; apps dictating decisions not approved. Official policy lists static pre-game-data overlays as examples for personal projects. [Riot LoL developer docs](https://developer.riotgames.com/docs/lol).
- Confirmed general policy: products must not remove choices; registration and audit on Developer Portal required, with non-endorsement notice. [Riot general policies](https://developer.riotgames.com/policies/general).
- Riot's Vanguard FAQ expects overlays/API-based tools to work but does not grant case-specific authorization; Riot announced restrictions on unapproved third-party direct game-memory access from 2026-10-06. Neither is proof our OCR/LCDA combination is approved. [Vanguard FAQ](https://www.riotgames.com/en/DevRel/vanguard-faq); [2026 support note](https://support.riotgames.com/en-us/riot/performance/game-memory-access-removed-for-third-party-apps).
- **Unresolved interpretation:** contextual real-time augment/item scoring based on visible choices, even without numerical win rates, may be considered dictating decisions; requires Riot review before public distribution. No approval evidenced. Keep default-off click hints, local-history reads, experimental win evidence; no automated game decisions or input.

## End-state and handoff

Current N1 state: **PREPARED, NATIVE ACCEPTANCE OPEN**. No native FAIL/PASS or calibration changes. Next potentially authorizable action is **an evidence-based correction within N1 only**, if a reproducible defect appears, followed by N1 re-test. Features, S1/C3, installer, remapping Alt+S and other phases remain blocked without fresh explicit authorization.
