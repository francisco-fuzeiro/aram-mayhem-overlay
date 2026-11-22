# F1.3 — Controlled Native Champion Select Validation (Windows)

**Prepared:** 2026-11-22. **Status:** protocol PREPARED, native validation NOT TESTED. This is a documentation-only preparation, not a new bug fix or native PASS.

- Repo: `francisco-fuzeiro/aram-mayhem-overlay`; branch `fix/f1-champion-select-identity-20261122`; open draft PR [#80](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/80), directly stacked on open draft #78 (on #76). OCR drafts #72/#74/#75 are independent. No merge or main changes.
- Pre-protocol verified F1.1/F1.2 SHA: `50138b091ec897c62b84d82cabbffe2878626379`; [Windows Actions #44982404803](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44982404803) SUCCESS with 1,969 Python, 78 JS and three syntax checks. Any later documentation HEAD must be independently verified by Windows Actions.
- User's original real-match self-champion error: FAIL (user observed), root cause BLOCKED. CI/synthetic correctness does not prove that cause or native recovery.

## Feasibility and preflight

Riot officially announced custom ARAM Mayhem in [patch 25.22](https://www.leagueoflegends.com/en-us/news/game-updates/patch-25-22-notes/). The previously reported League client path is Play → Create Custom → ARAM → Game Type: ARAM Mayhem. **Do not assume this exact UI, available bench/swaps, player minimums or current server settings:** check the actual Windows client. If a compatible custom lobby cannot enter Champion Select, record the mandatory native feasibility case BLOCKED, not PASS; never substitute a normal ARAM match or an undocumented mode workaround.

1. On user Windows, verify the checkout with `git rev-parse HEAD` and `git status --short`; compare exact SHA against draft #80 and completed Windows Actions; do not overwrite uncommitted work.
2. Start the existing desktop/Settings and read-only LCU connection according to the project's existing launch instructions; keep one local desktop/API instance.
3. By default leave `ARAM_ORACLE_F0_TRACE` off. If the user consciously opts in, `ARAM_ORACLE_F0_TRACE=1` enables bounded local allowlisted enum diagnostics and verified *public catalog* numeric IDs only; inspect and delete locally, never publish raw journals. No screenshots, raw League/LCU payloads, player names, PUUIDs, Riot identifiers, lockfile credentials, HWND, unrelated screen contents or private file paths.
4. Visually compare the champion portrait/name on the **user's own device** against the Oracle `(current)` badge, but report only the yes/no/count/status observations below; do not transmit the actual champion names or screenshots. Do not automate any champion choice, reroll, purchase or League control.
5. If a case is impossible within the allowed custom lobby, mark that case BLOCKED or NOT TESTED with the reason rather than fabricating a PASS. Use another *custom* lobby only if needed and allowed.

## Fixed native case matrix (all initially NOT TESTED)

| Case | User-operated observation | Acceptance and safe fallback | Native state |
| --- | --- | --- | --- |
| **F1-N00** | Custom Mayhem Champion Select can be entered | Client-supported custom lobby reached; otherwise BLOCKED | **NOT TESTED** |
| **F1-N01** | Self champion portrait versus Oracle current badge | Exactly one `(current)` matching actual assigned self; if unresolved, no confident badge | **NOT TESTED** |
| **F1-N02** | Available bench and any allies | Bench stays independently listed, allies do not become current | **NOT TESTED** |
| **F1-N03** | A bench champion happens to score higher than self | Ranking order may differ but `(current)` remains on actual self; if no such bench, NOT TESTED | **NOT TESTED** |
| **F1-N04** | Manually swap one champion if the client permits | New self becomes the only confirmed current and old self is not current; unavailable swap BLOCKED for this case | **NOT TESTED** |
| **F1-N05** | Observe after F1-N04 for old marker resurrection | Old current does not return; observation alone does **not** prove a delayed packet was delivered | **NOT TESTED** |
| **F1-N06** | Observe naturally occurring LCU interruption or ambiguous identity if encountered | When unresolved, no falsely confirmed current, no stale old badge; never force a client disconnect, alter lockfiles or inject packets | **NOT TESTED** |

**Evidence labels:** PROVEN is directly source-backed/targeted offline code evidence or a separately identified user-observed native outcome; SUSPECTED is a plausible hypothesis without a validated cause; BLOCKED means a needed prerequisite/source truth is unavailable; NOT TESTED means no observation. Report user-observed native FAIL explicitly, even if the technical cause remains BLOCKED. All native statuses above stay NOT TESTED until actual user-device evidence. Offline replay of delayed WebSocket packets is already PROVEN at code-contract level; never claim native late-packet injection occurred.

## Privacy-safe result report (to share without screenshots)

```text
F1.3 controlled Windows report (no names, IDs, images, private logs)
Tested HEAD SHA: <full SHA or not verified>
Custom ARAM Mayhem available / lobby started: yes/no/unknown
F1-N00: PROVEN / SUSPECTED / BLOCKED / NOT TESTED | reason:
F1-N01: PROVEN / SUSPECTED / BLOCKED / NOT TESTED | correct self: yes/no/unobserved | current badge count: 0/1/>1/unknown
F1-N02: PROVEN / SUSPECTED / BLOCKED / NOT TESTED | bench distinct: yes/no/unobserved | allies distinct: yes/no/unobserved
F1-N03: PROVEN / SUSPECTED / BLOCKED / NOT TESTED | higher-rated bench existed: yes/no | self kept badge: yes/no/unobserved
F1-N04: PROVEN / SUSPECTED / BLOCKED / NOT TESTED | swap available: yes/no | updated correctly: yes/no/unobserved
F1-N05: PROVEN / SUSPECTED / BLOCKED / NOT TESTED | previous current returned: yes/no/unobserved | delayed packet independently evidenced: yes/no
F1-N06: PROVEN / SUSPECTED / BLOCKED / NOT TESTED | natural LCU loss witnessed: yes/no | badge withheld while unresolved: yes/no/unobserved
Unexpected behavior: sanitized reason only, never account/champion identities
```

## Test ladder and gate

Existing deterministic tests are already present; do **not** reimplement or re-investigate F1.1/F1.2 without a reproducing defect:

```sh
python -m pytest -q
python -m backend.workflow.f1_replay
node --test tests/js/*.cjs
node --check frontend/app.js
node --check frontend/settings.js
node --check frontend/overlay-preferences.js
```

A documentation-only protocol requires **full exact-final SHA Windows Actions**, not a manufactured new RED/GREEN. If a real problem is observed, record FAIL and isolate a minimal source-to-UI deterministic **tests-only RED**, reproduce on Windows CI, implement only the proven fix, verify targeted GREEN, replay/integration, all suites and exact-final code+docs Windows Actions, then retest natively. Do not change score weights without separate authorization.

**Exit:** a verified native test matrix with correct self/bench/current and swap behavior where permitted, absence of false certainty, a clear adjudication of inaccessible optional cases, and exact latest SHA Windows SUCCESS. Until the *required* native gates are satisfied, `FR-F1.3` stays unchecked, N1 NOT ACCEPTED and F2 NOT STARTED; preserve all drafts, no merge/main edit, no OCR/matching 90/8/Tesseract/WGC/augment epochs/build/item/HUD changes, no automated League actions and no unreviewed Riot policy claims.
