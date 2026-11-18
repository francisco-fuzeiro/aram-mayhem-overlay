# ARAM Oracle — Functional Audit Remediation Plan (2026-11-18)

**Status:** Planning / no application code changed. Source: user-supplied **A-FUNC Functional Code Audit Report** excerpt from 2026-11-18 (in the ChatGPT Overlay LoL project). This is a *reported* audit, **not an independently rerun audit** in this GitHub documentation session. The pasted report is truncated during AUD-11; obtain the full original before claiming a complete defect ledger.

**Audited baseline:** `feat/desktop-overlay-preview-apply-d4b` @ `9832fb0`; [draft PR #17](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/17), stacked on #16. Preserve the draft PR chain and `main`. The independent WIP `fix/postgame-stale-match-state` @ `cc4aee7` is **not validated**; reported tests: 1 failed, 303 passed. Do not merge or cherry-pick blindly.

## What the submitted audit establishes

- Audited head: **303 Python tests passed**; **18 JavaScript Settings tests passed**, entry-point syntax checks passed (reported Linux execution). This is *not* a live Windows/League result.
- **AUD-02a (confirmed)**: fixed monitor-relative OCR region captures non-League foreground applications. A saved annotated image recognized ChatGPT text as an augment offer; privacy leak.
- **AUD-02b (confirmed)**: fuzzy-match of arbitrary crop text can invent augments and sorts by match score, losing left/centre/right card identity.
- **AUD-03a (code + reproduction)**: passive level-ups/items can trigger a fake augment pick; Neeko-like reproduction assigned Donation at 0.998 confidence.
- **AUD-03b (measured)**: single-card rerolls changed full-crop average hash by 3–6 bits versus threshold 30; dialogs produced 57. Per-slot title-band hashes show the changed card.
- **AUD-03c/03d (code)**: failed OCR freezes a hash with no effective retry; any damage can prematurely end scan eligibility.
- **AUD-04 (reproduced)**: 2.1/10 score plateau and bad reroll advice are a missing-data artifact, not evidence of bad choices. Neeko 334/600 identical 2.1, many unmodelled entries, wrong substring matching (`ad` in “Upgrade”), wrong Donation `hp` hint, Arena-derived duplicates and placeholders. Display `unrated` instead of invented decimals.
- **AUD-05/06 (code, observed symptoms)**: post-game stale header and independent/unversioned OCR/WS paths permit stale, reordered, or cross-match offers.
- **AUD-01 (partly confirmed, live diagnosis needed)**: transient custom-match “Waiting for game” has several code contributors; do not claim custom games are unsupported.
- **AUD-07 (code)**: one LCDA miss triggers game-end transition; WIP reset could worsen this.
- **AUD-08 (code)**: loopback HTTP/WS endpoints have no origin/host validation and accept unauthenticated browser requests; treat as **security blocker before any public build**, not mere cosmetic P1.
- **AUD-09/10 (code)**: unrestricted diagnostic screenshots and caching empty/misaligned patch catalog responses.
- **AUD-11**: only the initial truncated input-validation finding was supplied. Require full audit report for remaining details or additional findings.

The full private screenshots must **never be committed**; use sanitized, card-title-only crops with explicit user consent. Reports on 18 screenshots are not equivalent to OCR execution (Tesseract absent in audit environment).

## Small implementation phases — A-FIX IDs are separate from existing A-FUNC acceptance gates

These are **proposed implementation slices**. Claude Code should perform a short dependency/contract review before coding, *not repeat the completed source audit*. One narrow branch + stacked draft PR per slice, tests at every step, no merge without explicit user approval. The exact PR boundary may be adapted if a contract genuinely spans two slices; preserve traceability.

| Phase | Scope | Defects / gate |
| --- | --- | --- |
| **A-FIX.0 — Honest output guard** | Suppress automatic reroll advice and precision ratings when slots, mapping or model coverage are uncertain; no fake pick confirmation. Disable screenshot persistence by default pending safe capture. | AUD-03a, AUD-04e, AUD-09; safe degraded behavior first |
| **A-FIX.1 — League-bound safe capture** | Resolve foreground game HWND and client rect with read-only Win32 APIs; stop OCR when not focused; calculate crop in client coordinates with multi-monitor/negative-origin and DPI tests; debug opt-in only, crop-only, privacy retention. | AUD-02a, AUD-09; 1080p/1440p Windows focus tests |
| **A-FIX.2 — Authoritative match/offer lifecycle** | Define `Offer{match_id,generation,slots[3]}`; one serialized OCR command path for manual/automatic triggers; strict match resets and generation checks; suppress level-up/item stat-delta auto-picks; infer closing only from verified offer disappearance; health must not close capture eligibility. Debounce LCDA misses. | AUD-03a/d, AUD-06/07, F-AUD-05 |
| **A-FIX.3 — Positional OCR & rerolls** | OCR individual card-title bands with calibrated thresholds, unique candidate margin, Mayhem catalog filtering; each slot can be `pending/known/unknown`; hashes per title band; two consistent reads before committing; bounded retries and fail-closed clearing; preserve left-centre-right positions and unchanged cards. | AUD-02b, AUD-03b/c; 30/30 known-or-unknown in Windows offer trial, no wrong names |
| **A-FIX.4 — Data integrity & scoring confidence** | Fix catalog source/version/cache poisoning, Mayhem-only normalized unique IDs/names, placeholder rejection, description and hint provenance; word-boundary keyword parsing; explicit `modelled` and `unrated` score state; reroll only if all three observed slots are known and modelled. Calibrate scores separately with legitimate labeled examples and licensing/policy review. | AUD-04a–e, AUD-10; no automatic reroll on incomplete data |
| **A-FIX.5 — Game status and local API hardening** | Explicit loading/live-data-unavailable/in-game/post-game signals (LCU+LCDA; don't assume LCDA matchId), non-blocking poll, safe client clearing/stale-on-disconnect; host/origin validation, per-launch authorization for state-changing REST/WS, strict WS input validation and limits, consent and redaction for bug reports. | AUD-01, AUD-05, AUD-08, partial AUD-11 |
| **A-FIX.6 — Windows acceptance / regression matrix** | Run real League windowed/borderless 1080p/1440p and relevant DPI/multi-monitor; 10 offers, single-card and repeated rerolls, level-up and item changes while offer open, alt-tab, AFK/disconnect, custom-game start/end, consecutive matches. Sanitized evidence, same code SHA as reviewed PR, no UI redesign during stabilization. | Existing `A-FUNC.3` gate |

**Possible parallelism:** A-FIX.5 local API hardening may proceed independently and urgently once message contracts are agreed; avoid conflicting edits to `server.py` during A-FIX.2. A-FIX.0 is deliberately minimal and must not conceal failed detection as success.

## Contracts Claude should confirm before implementation

1. **Match identity:** source actually available from LCU gameflow, fallback semantics, gameTime regression, no `unknown` collisions; inspect real permitted LCU/LCDA traces first.
2. **Offer lifecycle:** authoritative event/poll states; what proves UI disappearance; timing/debounce; no gameplay input automation; never infer a chosen augment from level-up.
3. **Capture geometry:** Windows DPI awareness (logical vs physical pixels), windowed title bar vs borderless, foreground checks, game monitor and OCR box calibration. Confirm game/HUD scale in device trials.
4. **Per-slot OCR:** match uniqueness margin, confidence calibration, failure and retry policy, title-only crop layout; verify false positives and false negatives against sanitized fixtures.
5. **Catalog:** patch-specific Mayhem source, license and provenance, normalized stable IDs, supported names/descriptions/semantics; unknown/zero-feature must remain `unrated`.
6. **Security boundaries:** Qt Settings / browser origin allow-list (including Origin absent), DNS rebinding and API auth; no new privilege or unlocked localhost command paths.
7. **Compliance:** Riot rules for game-specific live rankings, real-time adaptation and win/loss evidence need review before distribution. Another overlay's behavior does not grant authorization.

## Required evidence / completion policy

- Every defect has `confirmed/code-only/likely/hypothesis` label, test case, expected vs observed, responsible fix PR, and Windows gate if applicable.
- Never commit full-screen playtest shots or private desktop data. Use redacted crops, sanitized JSON fixtures and no PII. Diagnostics off by default.
- New `ScreenWatcher`, `_poll_game_loop`, stat-delta, `frontend/app.js` event tests are mandatory; passing the old 303+18 tests alone is not acceptance.
- A PR is code-complete only with targeted regression tests and full suite; final game behavior is accepted only with separately recorded **real Windows** observations.
- Defer score-card badges (F-AUD-07/D7), shop panel, D5c desktop aesthetics and installer until correctness gate. Existing A-FUNC.1/2 cover audit and plan; **A-FUNC.3 remains the overall real-game acceptance gate**, **A-FUNC.4 the UI gate**; do not rename them.
- Preserve `fix/postgame-stale-match-state` WIP unmerged; review its failing test and LCDA miss debounce before considering reuse.

## Next action

Give Claude Code this plan and the **complete** original audit report, ask for a short technical dependency review with any contract corrections and then implement **A-FIX.0** or **A-FIX.1** as the first bounded code PR. No further broad audit is required, but Windows acceptance and data-source verification cannot be shortcut.
