# F1 — Champion Select authoritative identity recovery

**Date:** 2026-11-22
**Branch:** `fix/f1-champion-select-identity-20261122`
**Draft PR:** [#80](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/80) directly stacked on F0 draft [#78](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/78) at `45f2c9e28eeed7e137c0f52237acda63398e409f`.
**Scope:** F1.1 identity/alias/bench abstention; F1.2 ordered source-to-browser current badge; F1.3 fixed synthetic matrix and native follow-up.
**Baseline:** F0 Windows #44981004892 SUCCESS (1,963 Python / 75 JS / 3 syntax). The user's native N1 champion-select observation is a **FAIL without captured source ground truth**; fixing an offline-proven defect does not prove it caused that match.

## Source-proven defects and constrained correction

1. **PROVEN code discrepancy:** F0 diagnostic `classify_champion_identity` rejected duplicate local cells, while production `summarize_champion_select` previously assigned its `local_id` from the last matched row and could show the final row as `(current)`. A missing/unmapped/catalog-unavailable current identity did not have a first-class provenance/status in the user payload. The explicit F1.1 contract adds `current_status` (only `confirmed` or `unresolved`) and `current_champion_id` (catalog alias or null) and uses the already-existing F0 classifier in the production summarizer. Unknown never becomes a guessed current badge. The independently enumerated bench remains visible where catalog data permits.
2. **PROVEN code boundary:** the prior browser rendered any `candidate.current` flag and accepted champion-select messages without ordered revisions. Stale messages could overwrite a newer champion swap. F1.2 stamps a monotonically increasing revision **before** every LCU read and makes the real browser ignore revisions not newer than the last accepted one; when revisions are known, older unversioned messages are rejected. Only exactly one candidate agreeing with the confirmed alias gets the badge. On read failure the polling WebSocket emits an explicit unresolved/empty state.
3. **Scope unchanged:** composite ranking remains bounded 0.0–10.0, sorted by score, and separated from local identity. No new selection, Riot win-rate proxy, augment/OCR/90-8/WGC/epoch/build/item/HUD changes. No privacy credentials, player identifiers, raw payloads or screenshots logged.

## Deterministic declaration and evidence classification

| Case | Contract | Offline stage | Native |
| --- | --- | --- | --- |
| Local champion and multiple bench champions | Exactly one confirmed current; separate bench candidates | **PROVEN by scoped synthetic code contract**, final CI gate separately required | NOT TESTED |
| Current champion below best-scored bench entry | Score sorting must never transfer identity | **PROVEN source contract**, JS DOM regression | NOT TESTED |
| Local self swaps to another available champion | Confirmed alias and current badge migrate, previous self becomes bench if present | **PROVEN source contract**, LCU→backend→poll→WebSocket→real JS harness | NOT TESTED |
| Duplicate local `cellId` | `unresolved`, no falsely confirmed current, bench preserved | **PROVEN code discrepancy before fix**, regression added | NOT TESTED |
| Duplicated local-cell rows misclassified as team roles during abstention | Neither uncertain self row can count as a confirmed ally for the bench team-fit context | **PROVEN source-state regression**, dedicated RED fixture and bounded conditional fix; exact CI still required | NOT TESTED |
| Missing/non-numeric/invalid/ambiguous local cell | `unresolved`; no badge; bench remains independent | **PROVEN deterministic contract** after passing gate | NOT TESTED |
| Local `championId=0`, unmapped numeric ID | `unresolved`, no guessed alias/current | **PROVEN deterministic contract** after passing gate | NOT TESTED |
| Missing alias catalog or missing static champion lookup | No unverified current; known bench may still appear | **PROVEN deterministic contract** after passing gate | NOT TESTED |
| Older WS champion select received after new swap | Ignore stale revision, preserving latest current identity | **PROVEN deterministic browser-harness contract** after passing gate | NOT TESTED |
| LCU temporary communication failure | Broadcast empty candidates plus unresolved local identity (no old selection) | **PROVEN source/poll contract** after passing gate | NOT TESTED |
| User's original in-game incorrect champion | Root cause cannot be reconstructed without independent live evidence | **BLOCKED**; these source-proven defects are not attribution to that incident | FAIL (user-observed), root cause BLOCKED |
| Real custom ARAM Mayhem swap and transport freshness | Validate visible self versus bench and optional intentional swap | NOT TESTED | **NOT TESTED**, user-controlled only |

**Follow-up F1.1 regression:** tests-only `49e31b1100a5a41ffd7083e41bc29e32bec93c14` asserts that duplicate self-cell rows never enter ally team-fit scores; the code correction `7a5b18c140d8a7fa05dbee09d6b269d85686b08b` skips those rows without changing any score weight or sorting. Windows RED/GREEN must be independently checked and cannot be inferred from an earlier F1 code pass.\n\n**RED evidence:** F1.1 tests-only `7e769a4b3f74d4d8f1db8553f2588aae117b1ff6` [Windows #44981614324](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44981614324) failed four new current-source-contract assertions; 1,963 older Python tests passed. F1.2 tests-only `bd6b0baf2801f9e92a1262800a8fc25c757c0dc4` [Windows #44981718994](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/44981718994) failed two new JS tests; 75 older JS tests passed. These are intended RED gates, not the final GREEN.

## Replay and acceptance procedure

- `python -m pytest -q`: F1.1 classifier/current and native-backend polling regression, all existing tests.
- `python -m backend.workflow.f1_replay`: **synthetic-only** LCU drafts sent through `server._read_champ_select_payload` and `server.poll_tick`; packets contain no player identifiers or credentials.
- `node --test tests/js/*.cjs`: real browser WebSocket/DOM handler, including Python subprocess replay and late/duplicate/unconfirmed current badge cases.
- `node --check frontend/app.js`, `node --check frontend/settings.js`, `node --check frontend/overlay-preferences.js`: preserve all JS syntactic gates.
- Exact *final documentation-inclusive PR SHA* must be checked against Windows Actions SUCCESS. If no final gate is proven, remain in F1. A passing synthetic suite is not the N1 user-device pass.
- In a **user-operated controlled custom ARAM Mayhem lobby, if supported**, compare the actual client self name/portrait and bench choices against the Oracle current badge. If a legitimate swap is possible, verify one update and that returning to an old selection does not occur. Optional F0 diagnostic `ARAM_ORACLE_F0_TRACE=1` is local-only and records enums/catalog numeric IDs but never player identities, frames, paths or credentials. Do not request another ordinary ARAM match or upload sensitive logs. If custom lobby is unsupported, classify native validation **BLOCKED**, not PASS.

## Remaining gates

The original user's real-match champion root cause remains **BLOCKED**; actual custom-game identity and LCU communication/dropout timing are **NOT TESTED** on the user's Windows system. F2 must not begin unless F1's required gate is satisfied. Existing draft #78/#76 dependencies, OCR research #72/#74/#75 and `main` must remain untouched.
