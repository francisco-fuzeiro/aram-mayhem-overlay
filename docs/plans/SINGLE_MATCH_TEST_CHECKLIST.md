# Single Mayhem Match Test — checklist (P0 #107 + Tier DB #108)

Owner rule (2026-11-23): every feature is tested in ONE match at the end, not one
match per fix. Branch under test: `feat/tierdb-items-builds-anvils` (#108), which
already contains #106 and #107. Detailed evidence history:
`SINGLE_MATCH_TEST_HISTORY_2026-11-23.md`.

## Before (5 min)

1. Update the local copy to the branch HEAD given in the chat and start ARAM Oracle.
2. Wait about 1 minute on first start (tier list download).
   Settings → Build Preferences → "Mayhem tier lists" shows `On · patch …`.
3. Join an ARAM Mayhem match. No automatic clicks; nothing to screenshot.

## During the match (just look)

1. **Champion select:** some champions show `Mayhem strength: … · Potential: …`.
2. **Augment offer:** each card shows `Tier … · #…/…`; no MR/MS shown as fake HP/pen.
3. **Build:** after the first augment, the overlay shows `Reference: …`, maybe
   `Adapted: …` with `out → in (reason)` (at most 3 changes) and
   `Stat Anvils (estimate): …`.
4. **Shop:** the next-item suggestion is a real item you can buy.
5. **Stat Anvil (only if you get one):** within ~2 s the panel shows `Best fit`
   with the right tier (Silver/Gold/Prismatic).
6. **Your pick:** after you choose an augment (no Alt+N), the counter goes up and
   the build/tiers adapt. The first augment read takes a few seconds, not ~30 s.
   If the pick is wrong, Alt+N corrects it.

Play normally to the end.

## After

1. With ARAM Oracle still open, open `http://127.0.0.1:8765/api/diagnostics/features`,
   or in the project folder run `py -3.11 -m backend.feature_diagnostics --out feature_report.md`.
   Optional: `py -3.11 -m scripts.validate_impact_holdout` prints only counts
   and a verdict (`insufficient_data` is expected until the local history grows).
2. Paste the table in the chat (ids, verdicts, reasons and counts only: no names,
   paths or win rates) plus one line: yes/no for checks 1–6 above.

## Reading the report

- **OK**: worked at least once. **SKIPPED**: chose not to act, with a reason.
- **FAILED / NOT FIRED**: should have run and did not; the reason points to the cause.
- Features that should fire every session: `build.item_pool`, `augment.cache_schema`,
  `build.next_item`, `anvil.catalog_source`, `tierdb.load`, `tierdb.switch`,
  `tierdb.offer_tiers`, `tierdb.offer_render`, `tierdb.champselect_tiers`,
  `tierdb.champselect_render`, `items.reference_build`, `items.build_render`,
  `anvil.stat_estimate`.
- Conditional (NOT FIRED is acceptable when the event did not happen):
  `augment.stats_parser`, `build.next_item_render`, `tierdb.update`,
  `anvil.voucher_purchase`, `anvil.offer_detected`, `anvil.offer_rating`,
  `anvil.offer_render`, `augment.pick_inferred`, `anvil.pick_inferred`,
  `tierdb.context_adjust`. No Stat Anvil in the match = Anvil popup checks stay
  open, never PASS.

## Closing rule

P0 and the Tier DB items phase close only when this report and checks 1–6 agree,
and Windows CI is green on the exact HEAD tested. New features add one line here
(see `FEATURE_DIAGNOSTICS.md`).
