# ARAM Oracle — Product and UX TODO

> Canonical, persistent backlog for this repository. Created 2026-11-18 (Europe/Lisbon).
> Incorporates the **"Auditoria UX — ARAM Oracle"** discussion in the ChatGPT Overlay LoL project, the user-supplied `funcionalidades.md` specification, the first real in-game Jinx screenshot, and the current stacked PR history.
> The UX audit was recovered from the cross-chat discussion summary; this is an actionable synthesis, **not** a verbatim export of that conversation.

## Working rules

- **Priority:** P0 = missing core behavior or unsafe/confusing output; P1 = contextual experience and usefulness; P2 = polish/robustness.
- `[x]` means the narrowly worded *implementation* or *test* listed on that line has evidence. It **does not** imply live Windows validation. Separate unchecked validation tasks remain until real evidence exists.
- For each completed item, preserve the task ID, check it off, and add the PR/commit, test output or Windows observation to `docs/DEVELOPMENT_LOG.md`. Do not remove historical tasks.
- Keep `docs/PROJECT_STATE.md` synchronized. Run relevant Python/JavaScript tests and verify the **latest** Windows GitHub Actions run after changes. An unfinished/failed run is not a pass.
- The overlay must remain read-only with respect to League. No automatic selections or buys; only player-visible, permitted data. Do not enable experimental empirical augment ratings without Riot policy review.
- All application copy, code, and repository documentation are **English**; user-facing ChatGPT communication is **PT-PT**.
- **Merge gate:** All PRs #1–#12 remain stacked drafts; never merge `main` without explicit user approval.

## UX audit decision: event-driven companion, not a permanent dashboard

Target states and *expected* presentation (**not all implemented**):

| Context | Expected UX |
| --- | --- |
| Loading / no actionable event | Hidden or minimal non-interfering status |
| Active combat | Hidden or nearly invisible; no persistent giant lists |
| Three augment offers / reroll | **Highest priority**: 3 compact scored alternatives, clear uncertainty and short explanations |
| Shop open (when reliably observed) | Next feasible purchase + one optional alternative; no speculative auto-buy |
| Scoreboard (only if reliably and permissibly known) | Optional compact enemy/team summary |
| Death / respawn | Do not confuse respawn with an offer; update or reveal only relevant information |
| Champion Select | Small contextual rating/options panel; never interfere with selection |
| End of game | Close in-game advice; feedback lives on the separate Settings page |

If multiple contexts overlap, priority is **augment offer > shop > optional scoreboard**, and combat/visibility safety takes precedence when game context is uncertain. Until legitimate shop/scoreboard observability is confirmed, do not pretend to detect either.

## P0 — Capture, state, correctness, safety

- [ ] **UX-001 — Explicit context/state controller.** Replace always-visible dashboard logic with stable, debounced states (loading, champion select, combat, augment offer, shop, scoreboard, death, post-game, disconnected). Test transitions, priorities, recovery and stale-event suppression without relying on hypothetical API fields.
- [ ] **UX-002 — Reliable three-option OCR in actual Mayhem.** Verify the Tesseract executable, screen capture crop at the user's DPI, all 3 current names/positions, confidence and failure recovery with real screenshots. Require repeatable correct results before auto-presenting scores.
- [ ] **UX-003 — Augment rerolls.** Recognize each *new* triple after a reroll, invalidate old offers without losing previously chosen augments, suppress duplicate/stale scans, and test real reroll timing.
- [ ] **UX-004 — Offer lifecycle.** Show the augment panel for a verified offer, prioritize it over build panels, hide it promptly after the choice, and avoid stale recommendations across respawns or consecutive matches.
- [ ] **UX-005 — Trustworthy shop-open source.** Investigate permitted shop-state signals; implement only with dependable detection or an explicit player-triggered fallback. Do not infer shop visibility from gold, death or guessed screen state.
- [ ] **UX-006 — Quiet overlay when no action is needed.** Hide/minimize during loading, combat, death and post-game as appropriate, without covering gameplay or capturing mouse input.
- [ ] **UX-007 — OCR failure path on Windows.** Validate that missing OCR clearly switches to a *temporary*, unambiguous manual augment workflow (including Alt+O), never leaves the player with a falsely "scanning"/blank card, and returns to click-through.
- [ ] **UX-008 — 0–10 augment scores in the actual offer panel.** Verify all three available choices receive contextual scores and provenance with champion, picks, items and visible opponents; incomplete data must cause an explicit low-confidence/unknown state, not fabricated precision.
- [ ] **UX-009 — Mayhem-purchasable item logic.** Validate current patch/mode item availability, purchasable components, price/gold, six slots, quest items, exclusivity, consumables, duplicate names, and the optional boots replacement. Never recommend a seventh item as a direct purchase.
- [ ] **UX-010 — Enemy data provenance and utility.** Verify visible item IDs against real LCDA samples; show incomplete-catalog confidence and actionable counter context, not seven unexplained "unknown" values or inaccessible enemy information.
- [ ] **UX-011 — Gameplay and Riot policy gate.** Review real-time recommendations, statistical evidence and UI copy against current Riot rules; keep `experimental_augment_evidence` disabled until cleared. Ensure no auto-select, hidden information or unlicensed code/assets.
- [ ] **UX-012 — State continuity and failure safety.** On WebSocket disconnect, game exit, new game and OCR timeout, clear or mark stale panels; preserve user preferences but reset only match-specific augments, and recover without requiring a manual restart.

## P1 — Contextual UI and pre-game flow

- [ ] **UX-101 — Augment choice micro-panel.** Replace a large expandable list with 3 simultaneously visible, ordered cards (name, contextual 0–10 rating, data confidence and one-line reason) during a detected offer. Make alternative choices obvious; no forced "best" decision.
- [ ] **UX-102 — Shop-focused recommendation.** When shop state is verified, show the next *feasible* item, affordable component path and one meaningful alternative; expandable detail explains enemy counters and chosen-augment synergy.
- [ ] **UX-103 — Optional scoreboard summary.** Only after validating a permissible scoreboard signal or an explicit manual toggle, show a compact, useful opponent/team summary; otherwise keep it collapsed and never assert that the scoreboard is open.
- [ ] **UX-104 — Remove redundant HUD and debug noise.** Avoid repeating game clock, level, gold, all enemies and technical status continuously. Reserve raw data and diagnostics for Settings or expandable debug views; retain only decision-relevant labels.
- [ ] **UX-105 — Progressive disclosure.** Default to one decision and one short rationale; details, item comparison, counter analysis and source confidence expand only on deliberate user action (or outside the match).
- [ ] **UX-106 — Contextual overlay priority and layout.** Augment > shop > optional scoreboard, single small surface at a time; prevent simultaneous panels, flicker, overlaps with Riot HUD and repetitive toast interruptions.
- [ ] **UX-107 — Pre-game Settings Windows walkthrough.** Open via Qt tray **Open Settings**, change build style before League, refresh/restart the app, ensure the value persists in `~/.aram-oracle/preferences.json`, and confirm the in-game indicator uses it.
- [ ] **UX-108 — Live preference sync in a real match.** Change build style in Settings while Qt overlay stays open, see recomputed build suggestions without restart; verify Alt+H, Alt+O and click-through still behave correctly.
- [ ] **UX-109 — Feedback Windows walkthrough.** Submit a report from Settings, inspect the actual local JSON description, verify helpful errors for cooldown or disk failure and preserve unsent text. No typing required during gameplay.
- [ ] **UX-110 — Transparent overlay in League borderless mode.** Verify the already-confirmed Qt desktop transparency also works on top of the game; check window location, mouse pass-through and recovery after Alt+Tab.
- [ ] **UX-111 — Champion Select minimal view.** Validate bench/own champion detection, clear heuristic confidence and at least two contextual alternatives without cluttering selection or falsely presenting Mayhem win rates.
- [ ] **UX-112 — Manual interaction as fallback, not default.** If OCR fails, manual choices should be usable without trapping focus; outside an offer the click-through overlay should not expose editing fields or dropdowns.
- [ ] **UX-113 — Clear UI state messaging.** Distinguish offline/disconnected, waiting for match, OCR not installed, scan in progress, uncertain detection and incomplete catalog; never display "success" for an unsuccessful operation.

## P2 — Stability, accessibility, polish and validation

- [ ] **UX-201 — Real screen matrix.** Test 1920×1080 and 2560×1440, Windows scaling (100%/125%/150% where available), borderless windowed LoL, screenshot capture coordinates and screen-edge anchoring.
- [ ] **UX-202 — Lifecycle matrix.** Test death/respawn, rerolls, Alt+Tab, shop opening/closing, match end, reconnect, overlay hide/restore and two consecutive games; record screen evidence and exact failures.
- [ ] **UX-203 — Low-attention presentation.** Check readability at game distance, contrast, font size, optional opacity/scale, keyboard accessibility and reduced-motion preference without blocking gameplay.
- [ ] **UX-204 — Performance under a full match.** Measure CPU, memory, OCR polling cost, WS reconnection and update latency; avoid unnecessary recalculation of unchanged score/build inputs.
- [ ] **UX-205 — Test fixtures per patch and UI state.** Store sanitized fixture captures for 3-card OCR/reroll, old/new item catalogs, full inventory, unknown enemies and disconnected state. Keep real participant identifiers out.
- [ ] **UX-206 — Feedback privacy and consent.** Review local log/state payload for sensitive identifiers; make optional upload to GitHub visibly opt-in before transmission and surface upload failures accurately.
- [ ] **UX-207 — Layout refinement only after stable detection.** Improve spacing, card hierarchy, animation and adaptive positioning after real OCR + state-driven modes pass; do not spend the P0 budget on cosmetic polish.
- [ ] **UX-208 — Scenario-based acceptance recording.** Record for each P0/P1 behavior: screenshot/fixture, expected overlay state, observed state, pass/fail, tested revision and Windows resolution; link evidence to the task ID.


## Desktop app and installer roadmap — OP.GG-inspired usability, original implementation

> Added after reviewing the user-provided OP.GG Settings and overlay screenshots (2026-11-18). This is a **proposed product direction**, not a claim that the desktop app or installer already exists. Use familiar Windows UX patterns; do not copy OP.GG assets, protected artwork, code, or distinctive UI.

- [ ] **UX-D01 — Native desktop control center (P1).** Open a normal, resizable Qt desktop window from the tray/Start menu, reusing the existing local Settings page. Keep the transparent overlay as a separate, lightweight Qt window backed by the same local engine; avoid introducing a second backend.
- [ ] **UX-D02 — Clear Settings navigation (P1).** Organize General, Overlay, Build Preferences, Augment Detection/OCR, Diagnostics, Feedback, and About into a consistent desktop navigation. Persist settings with validation, helpful errors, and clear 'Saved' states; no in-game forms.
- [ ] **UX-D03 — Overlay customization with preview (P1).** Configure anchor/corner, offsets, opacity, scale, compact vs expanded mode, visibility and safe click-through from the desktop app, with a simulated preview. Never use fake game-state detection in a real match.
- [x] **UX-D04 — One-engine lifecycle and tray behavior (P1).** Enforce single instance, no duplicate port 8765 servers, reliable Open Settings/Show Overlay/Quit actions, explicit background-vs-exit behavior, no elevation needed for ordinary use. Preserve Alt+O and Alt+H.
- [ ] **UX-D05 — Windows installer and uninstaller (P1 after core validation).** Produce a reproducible installer (evaluate PyInstaller onedir + Inno Setup first) with Start menu/desktop shortcuts, sensible install path, clean uninstall and optional user-data retention. User should never need Python, pip or PowerShell.
- [ ] **UX-D06 — First-run onboarding / OCR readiness (P1).** Detect Tesseract and required executables, explain installation or legally compatible bundling with notices, let the user test OCR, and provide manual fallback. Do not silently download or install third-party packages.
- [ ] **UX-D07 — Distribution safeguards (P2).** Validate clean Windows install/uninstall/upgrade, antivirus false positives, packaging of local frontend/static assets, process shutdown, minimum permissions, and code signing/SmartScreen strategy before public distribution.
- [ ] **UX-D08 — Updates and rollback (P2).** Design a versioned, opt-in update path with integrity verification, visible release notes, no disruptive update mid-match and rollback/recovery. Do not introduce auto-updates before a reliable package exists.
- [ ] **UX-D09 — Desktop/overlay smoke matrix (P1).** Test app launch, minimize to tray, Settings persistence, reopening an overlay, switching modes, exit and restart on real Windows at 1080p/1440p, including League borderless and Alt+Tab. Attach evidence to each item.
- [ ] **UX-D10 — Branding and licensing (P2).** Build original ARAM Oracle icon, typography, layout and visual hierarchy; use OP.GG only as an interaction reference, check Riot requirements and every bundled dependency's license/attribution.

**Delivery order:** finish current PR #12 Windows checks and P0 augment detection first; then implement the native desktop window and settings structure; package the installer once app start/stop, OCR and contextual overlay are reliable. Do not treat a pretty installer as evidence that live recommendations work.

## Small desktop development phases — implementation checklist

> Authoritative phase scope and gates: [`docs/IMPLEMENTATION_PHASES.md`](IMPLEMENTATION_PHASES.md). Architectural contract: [`docs/DESKTOP_ARCHITECTURE.md`](DESKTOP_ARCHITECTURE.md). These checkboxes represent **new development work**, not completed work.

### G0 — Baseline (verification only)

- [x] **PH-G0.1:** Reconfirm current draft PR #12 head, its PR #11 base, unchanged main, and the latest Windows Actions results immediately before starting development.
- [x] **PH-G0.2:** Inspect the actual launcher/Qt/API source and record any blockers for a separate normal desktop window; preserve the tested Qt renderer as the baseline.

### D1 — First implementation phase: native Settings shell

- [x] **PH-D1.1:** Add `backend/desktop` normal Qt window hosting the existing `/settings` page (no transparency, topmost or click-through).
- [x] **PH-D1.2:** Add `python -m backend.desktop` dev entrypoint and clear error handling for missing Qt, unavailable API or unexpected port conflict; use **one** local backend.
- [x] **PH-D1.3:** Add automated tests for launch/URL/readiness and legacy `python -m backend.overlay --renderer qt` compatibility; keep Alt+O / Alt+H unchanged.
- [x] **PH-D1.4:** Create a draft PR stacked on `feat/pregame-settings-feedback`, verify its Windows CI at final code head and update TODO/state/log.
- [ ] **PH-D1.5 (Windows):** Confirm actual standard Qt Settings window (focus, resize, preferences, feedback) and old transparent overlay behavior. **Never check from CI alone.**

**D1 code/CI evidence (2026-11-18):** [draft PR #13](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/13), [Windows run 44336280007](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44336280007) at code head `d5aff632`: **234 Python passed, 1 warning; 4 Node tests passed and both JS syntax checks passed**. The 19 new tests cover API fingerprint, reuse, occupied port, failure, host URL and legacy overlay contract. **PH-D1.5 remains unverified on a real Windows GUI.** UX-D01 and UX-D04 are broader than this shell and remain unchecked. See [external reuse candidates](REUSE_CANDIDATES.md) for separately licensed opportunities; none imported in D1.

**Windows evidence, 2026-11-18 (partial D1.5 only):** User screenshots confirm `python -m backend.desktop` opened and loaded the normal PyQt6 Settings window, with the saved `Balanced` style displayed. User explicitly confirmed that `python -m backend.overlay --renderer qt` remains transparent and that both **Alt+O** interaction and **Alt+H** hide/restore work; terminal shows both shortcut transitions. User installed the separately required UB-Mannheim Tesseract executable after the previous `OCR unavailable` warning, and explicitly confirmed the OCR status indicator turned green. **Do not mark PH-D1.5 complete:** resizing/focus, saving and persisting a changed build style across restart, and local feedback submission have not been explicitly verified. **Green OCR is only dependency readiness, not proof of three-card recognition or reroll accuracy in a Mayhem match.** No normal-match abandonment is required for a smoke test; keep in-game OCR validation open and use a permitted custom/test session if supported or observe a naturally completed match.

### D2 — Stable single instance and tray lifecycle

- [x] **PH-D2.1:** Reuse one ASGI server and one tray owner; prevent duplicate instances and conflicting port starts.
- [x] **PH-D2.2:** Implement reliable Open Settings, Show/Hide Overlay, Close/Minimize and Quit behavior without orphaned processes; test failures and recovery.
- [x] **PH-D2.3 (Windows):** Validate startup, repeat launch, taskbar/tray, close/reopen and keyboard shortcuts.

**D2 automated implementation evidence (2026-11-18):** [draft PR #14](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/14), [Windows CI 44345555542](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44345555542) at D2 code head `0b4a563b`: **253 Python passed, 1 warning; 4 Node tests passed; JavaScript syntax checks passed**. New headless tests cover OS-held lock, local activation, duplicates, error/stop paths and Qt launcher contract; they do **not** prove real tray, focus, close/hide or no orphan processes on the user's Windows machine. At this historical automated-test checkpoint the Windows validation was pending; later user-device evidence below confirms **PH-D2.3 and UX-D04**. **UX-D09 and PH-D1.5 remain unchecked**. The explicit legacy `--renderer webview` fallback is not part of the unified Qt tray lifecycle.

**D2 on-device tray acceptance, 2026-11-18 (completed for lifecycle/tray):** The user launched the D2 branch on Windows. The first process logged `Settings hidden to notification area`, and the user confirmed the tray icon remains in the Windows `^` notification area rather than in the taskbar. They confirmed all three right-click actions: **Open Settings**, **Show/Hide Overlay**, and **Quit** (full app exit). A second `python -m backend.desktop` logged `Activated existing ARAM Oracle settings window`; a deliberate foreign `python -m http.server 8765 --bind 127.0.0.1` listener was correctly rejected as incompatible when the overlay launcher was attempted. An earlier `KeyboardInterrupt` reflects manually interrupting the Python process, not proof of a tray regression. **Follow-up Windows screenshot and logs:** the D2 Qt launcher logged `Qt overlay hidden (Alt+H or tray to restore)`, `Qt click-through OFF` and `Qt overlay shown`, confirming Alt+H hide/restore and Alt+O interaction switching. After the user exited with Quit, `Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue` produced no listener rows. This validates the expected lifecycle and release of the managed API port; it does not prove every process/thread is absent. **PH-D2.3 and UX-D04 accepted.** Keep `UX-D09` (broader Windows/display matrix), `PH-D1.5` (focus/resize, preference save/restart and feedback), real borderless League transparency, OCR three-card/reroll accuracy and shop detection open.

### D3 — Desktop Settings information architecture

- [ ] **PH-D3.1:** Group General, Overlay, Build Preferences, OCR, Diagnostics, Feedback and About as focused navigable areas using current Settings implementation.
- [ ] **PH-D3.2:** Add keyboard/ARIA navigation and clear loading/save/error feedback; do not expose inaccessible features as functional.
- [ ] **PH-D3.3:** Run UI interaction tests and validate real Windows navigation/resize.

### D4 — Overlay customization, split into two PRs

- [ ] **PH-D4a.1:** Add validated, versioned local preferences/API for anchor, offsets, opacity and scale with safe defaults.
- [ ] **PH-D4a.2:** Test invalid settings and migration/restart persistence without changing Qt renderer semantics.
- [ ] **PH-D4b.1:** Add safe preview in desktop Settings and controlled application of user preferences to Qt overlay.
- [ ] **PH-D4b.2 (Windows):** Confirm 1080p/1440p scaling, positioning, click-through and no white background.

### D5 — OCR diagnostics and onboarding

- [ ] **PH-D5a.1:** Detect Tesseract availability/path and show helpful first-run status; no silent installation.
- [ ] **PH-D5b.1:** Add a user-triggered OCR diagnostic/preview with confidence and safe manual fallback.
- [ ] **PH-D5b.2 (Windows):** Confirm three real Mayhem cards and rerolls at the actual user's HUD scaling.

### D6–D8 — Contextual overlay engine (separate small PRs)

- [ ] **PH-D6.1:** Build tested deterministic/permission-aware overlay context controller, debouncing and stale-state handling; unknown shop must not be inferred from death/gold.
- [ ] **PH-D6.2:** Default to hidden during combat/loading and ensure augment > verified shop > optional scoreboard priority.
- [ ] **PH-D7.1:** Show concise score/reason for each of three **confirmed** augment cards, including rerolls; hide when selection vanishes.
- [ ] **PH-D7.2 (Windows):** Validate alignment, calibration and failure fallback in an actual match.
- [ ] **PH-D8.1:** Verify legitimate shop-open signal and Mayhem purchasability before presenting one next item/alternative.
- [ ] **PH-D8.2 (Windows):** Confirm recommendations appear only with shop open and do not suggest impossible/duplicate items.

### D9–D11 — Packaging and release (not in first PR)

- [ ] **PH-D9.1:** Produce local onedir executable, package Qt WebEngine/frontend/data and verify clean Windows launch without Python.
- [ ] **PH-D10.1:** Create installer/uninstaller with Start menu shortcut, optional desktop shortcut, error/rollback and user-data retention choice.
- [ ] **PH-D11.1:** Audit privacy, optional bug-report upload consent, third-party license notices, Riot compliance and release readiness.
- [ ] **PH-D11.2:** Investigate signing/SmartScreen and opt-in safe updates only after a tested installer.

## Completed implementation milestones (Windows in-game validation may still be open above)

- [x] ~~**UX-C01 — Baseline transparent Qt renderer.**~~ User confirmed the white desktop rectangle disappeared with `--renderer qt`; PR #9 Windows CI passed. **Real LoL overlay still open:** UX-110.
- [x] ~~**UX-C02 — Window controls and keyboard/tray hooks.**~~ Qt Alt+H/Alt+O, hide/quit actions and tray menu implemented; PR #10 CI passed. **Real interactions still open:** UX-108/UX-202.
- [x] ~~**UX-C03 — Existing context-aware scoring/build pipeline.**~~ Original 0–10 augment model, enemy/team signals, four build styles and optional boot swap implemented/tested across PRs #4–#8. **End-to-end accuracy open:** UX-008/UX-009.
- [x] ~~**UX-C04 — Initial real game-state integration.**~~ Champion, level, gold and five enemies were recognized in the first live screenshot. **Completeness open:** UX-010/UX-111.
- [x] ~~**UX-C05 — Non-equipment trinkets and duplicate build names filtered in code.**~~ PR #11: Poro-Snax excluded from main item slots; same-name Phantom Dancer variants deduplicated; Windows CI **200 passed**. **Actual shop test open:** UX-009.
- [x] ~~**UX-C06 — Level-triggered scan and manual augment fallback implemented.**~~ PR #11: initial eligible levels, manual search and match reset; **200 Python tests** passed. **Real three-card detection open:** UX-002/UX-003/UX-007.
- [x] ~~**UX-C07 — Separate pre-game Settings page and local style persistence implemented.**~~ PR #12 `/settings`, `GET/PUT /api/preferences`, WebSocket updates, disk persistence and Qt tray link; Windows Actions **215 Python + 4 Node tests passed**. **Real Windows verification open:** UX-107/UX-108.
- [x] ~~**UX-C08 — Remove in-game build dropdown and feedback entry.**~~ PR #12 leaves a read-only style label and post-game Settings guidance; JavaScript handlers cleaned up and checked by CI. **Manual augment input remains temporary fallback.**
- [x] ~~**UX-C09 — Local feedback description and failures handled in code.**~~ PR #12 saves user text into local JSON, reports HTTP 429/500 and preserves draft text on error; Windows CI passed. **User device test open:** UX-109.
- [x] ~~**UX-C10 — GitHub Windows automated regression gate.**~~ Workflow runs Python suite, syntax checks for both JS entrypoints and 4 DOM-stub Settings interaction tests; last verified [Actions run 44331470781](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44331470781) passed at `7912f471`. Later documentation-only commits require their own check.

## Immediate next execution order

1. **UX-107/108/109/110**: quick real Windows smoke test of PR #12 Settings/Qt transparency and feedback.
2. **UX-002/003/007/004**: capture and validate 3 augment options and rerolls; preserve a safe OCR fallback.
3. **UX-001/005/006/012**: implement trustworthy contextual state controller and quiet in-game presentation.
4. **UX-008/009/010**: guarantee useful ratings/builds with transparent confidence and verified item feasibility.
5. **UX-101–106**, then **UX-201–208**: compact decision UI and broad validation/polish.

Do not mark implementation or in-game validation as done solely because a draft PR exists, a historical CI run passed or a mocked UI test succeeds.
