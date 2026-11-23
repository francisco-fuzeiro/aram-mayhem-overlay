# Per-feature diagnostics (pattern for every phase)

Goal: the owner runs **one** end-to-end Mayhem match at the end, not one per sub-phase.
If something fails, the post-session report must say *which feature* failed and *why*
without screenshots, raw logs or a second test.

## How it works

- Registry: `backend/feature_registry.py`. Each feature has a dotted id
  (`area.name`, e.g. `tierdb.offer_tiers`), a flag "expected during one full match",
  and a closed set of reasons. Free text never reaches the journal.
- Record: `feature_diagnostics.record(feature, status, reason, count=None)` with
  `status ∈ {ok, failed, skipped}`. Consecutive duplicates are suppressed per feature,
  so calling it on every poll tick is fine. It never raises.
- Journal: the existing whitelisted local `events.jsonl`
  (`%LOCALAPPDATA%\ARAMOracle\logs\` on Windows). The app writes `session_start` at startup.
- UI features: the overlay sends `{"type": "feature_ack", feature, status, reason, count}`
  over its WebSocket after it actually drew something. The server accepts this only for
  ids in `UI_FEATURES`.
- Report for the last session:
  - `python -m backend.feature_diagnostics` (Markdown), `--json`, `--out report.md`
  - or `GET http://127.0.0.1:8765/api/diagnostics/features`

  Verdict per feature: `OK`, `FAILED`, `SKIPPED` or `NOT FIRED`; expected features that
  failed or never fired are shown in bold.

## Rules for new features (GPT P0 phases included)

1. Add the id and its reasons to `feature_registry.py` in the RED commit, with a test
   that drives the feature and asserts the exact `(feature, status, reason)` recorded.
2. Record at the decision point (server) **and**, if the user sees it, at render time
   (`feature_ack` from the overlay, id added to `UI_FEATURES`).
3. A feature that cannot act must record *why* (`skipped/<reason>` or `failed/<reason>`);
   silence must only mean "never reached".
4. Reasons are enums. Never log names, Riot IDs, paths, OCR text, screenshots or win rates.
5. Add the feature's line to `docs/plans/SINGLE_MATCH_TEST_CHECKLIST.md`.

## Tier list features

| id | Expected | Reasons |
| --- | --- | --- |
| `tierdb.load` | yes | ok/loaded (count = champions), failed/export_missing, failed/export_invalid |
| `tierdb.update` | no | ok/updated, failed/network, bad_dataset, license, build_failed, unexpected; skipped/already_running, fresh, auto_update_off |
| `tierdb.switch` | yes | ok/enabled, ok/disabled, failed/save_error |
| `tierdb.offer_tiers` | yes | ok/tiers_attached (count), skipped/tiers_off, no_champion, no_visible_augments; failed/export_missing, champion_not_in_tierlist |
| `tierdb.offer_render` | yes | ok/rendered (count), skipped/no_tier_data, tiers_off |
| `tierdb.champselect_tiers` | yes | ok/annotated (count), skipped/tiers_off, no_candidates; failed/export_missing, no_candidate_in_tierlist |
| `tierdb.champselect_render` | yes | ok/rendered (count), skipped/no_tier_data |
