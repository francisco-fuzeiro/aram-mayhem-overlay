# N1 v3 — Native Windows ARAM Mayhem acceptance

**Status:** DEVICE PREFLIGHT PARTIAL / N1 CODE CRASH REGRESSION GREEN / NATIVE RETEST AND GAMEPLAY OPEN (2026-11-21). No post-fix native PASS is claimed.

## Authority and scope

- Reference: `docs/plans/ARAM_2026-11-20/README.md`, v3 audit, global rules and **only the N1 section** of `corrections/blueprints/M-D_overlay.md`.
- Parent: D2 draft PR #68, branch `fix/d2-unified-augment-overlay`, SHA `14ed84be8045403bfea9ccb3cad89cf14bf4d494`; D1 draft #67. No merge, no change to `main`.
- Verified exact-parent CI: [Windows #44841552493](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44841552493), 1,944 Python PASS (51 warnings), 72 JS PASS, three syntax-check steps PASS. This is **offline/runner evidence only**.
- Old 2026-11-20 custom game on an earlier build failed to detect three visible augments, gave misleading focus state, proposed unavailable reward items and overlapped the HUD. This is historical FAIL, **not** an executed N1 failure.
- No N1 gameplay/Windows capture run has been performed; no numeric false PASS.
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
