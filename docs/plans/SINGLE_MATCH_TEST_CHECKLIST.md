# Single Mayhem Match Test Checklist — P0 baseline

> **Owner rule, 2026-11-23:** Test all prepared P0 features in ONE user-controlled
> Mayhem match at the end, not one match per fix. This checklist is for draft
> P0 #107 only; sibling TierDB draft #106 has another version of this path.
> **Reconcile/add the P0 rows when integrating sibling branches**, preserving
> both sets of feature ids. Do not silently discard either checklist.

## Evidence and diagnostic status

P0 #107 now includes the generic feature registry, journal and offline CLI
following sibling #106's shared pattern, with ONLY `build.item_pool` wired
at catalog-load decision. Other P0 ids and UI acknowledgments are PENDING.
Sibling #106's TierDB features and HTTP report endpoint have NOT been merged;
combine BOTH feature registries/journal schemas when integrating those branches.
No native game acceptance or v4 owner-device validation exists yet.

In each subsequent P0 RED→GREEN change:
1. Register the dotted feature id below with closed reason enum(s).
2. Write an exact `(feature, status, reason)` diagnostic test in the RED commit.
3. Implement a `feature_diagnostics.record` at the actual decision point.
4. If rendered in UI, register id in `UI_FEATURES` and send allowlisted
   `feature_ack` **after** rendering. Silence from a feature that cannot act
   must be replaced with `skipped/<reason>` or `failed/<reason>`.
5. Record exact final-head Actions plus a single final user-controlled test.
   A missing expected feature is NOT FIRED, not a success.

## One row per P0 feature

| Feature id | Condition for one-match check | Existing synthetic test / required diagnostic RED | Native and diagnostic status |
| --- | --- | --- | --- |
| `augment.stats_parser` | Valid current augment catalogue; unsupported MR/MS must not invent HP/pen/shield | `tests/test_p0_audit_parser.py` exists (semantics only); exact `(augment.stats_parser,ok,parsed)` or `(augment.stats_parser,skipped,unmodelled)` RED **pending** | Diagnostics PENDING; native NOT TESTED |
| `augment.cache_schema` | Cached augment catalogue from current parser schema; stale schema rejected | `tests/test_p0_audit_parser.py::test_augment_cache_schema_changes_when_parser_semantics_change` exists (schema only); exact `(augment.cache_schema,ok,current)` / `(augment.cache_schema,skipped,stale)` RED pending | Diagnostics PENDING; native NOT TESTED |
| `build.item_pool` | DD/CD verified current-policy item cache load (network or warm cache); abstain if unverified | `tests/test_p0_item_source_recipe.py` exact `build.item_pool/ok/final_items` (count), `failed/no_final_items`, `skipped/unverified`; [RED #45207926899](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45207926899) proves 104 terminal DD omitted `into` vs CD `to=[]` | **GREEN implementation under exact-head Windows verification**; owner v4 report + native shop NOT TESTED |
| `build.next_item` | Shop decision point; only real eligible final/boots and feasible purchase suggested | Existing shop/build tests must be connected; exact `(build.next_item,ok,recommended)` / `(build.next_item,skipped,no_eligible_item)` RED pending | Shop #49 OPEN; native NOT TESTED |
| `anvil.voucher_purchase` | Active player's purchased voucher stack actually increases; otherwise report safe no-trigger reason | `tests/test_p0_anvil_voucher.py` exists (edge/synthetic poll only); exact `(anvil.voucher_purchase,ok,positive_edge)` / `(anvil.voucher_purchase,skipped,no_edge)` RED pending | Diagnostics PENDING; native NOT TESTED |
| `anvil.offer_detected` | Verified voucher + actual visually confirmed Stat Anvil popup; no invented cards | Current tests only disprove OCR on voucher-only event; exact `(anvil.offer_detected,ok,verified_offer)` / `(anvil.offer_detected,skipped,popup_unverified)` RED pending | Verified option corpus/3-or-4 geometry BLOCKED |
| `anvil.offer_render` | Three/four verified Stat Anvil choices actually appear in overlay, not backend-only decision | Exact UI `feature_ack` test and `(anvil.offer_render,ok,rendered)` / `(anvil.offer_render,skipped,no_verified_offer)` RED pending | UI not implemented; native NOT TESTED |

These are **proposed reason names**, not currently registered production reasons.
At implementation, freeze/validate enums per id; do not emit raw data or free
text in any record. Do not mark a diagnostic PASS merely because a test file
existed before instrumentation.

## Before the one permitted final match

- [ ] Owner's Git checkout in the `aram-oracle` child directory is on the
  intended P0 branch and exact latest PR #107 HEAD; keep the untracked local
  `funcionalidades.md` untouched.
- [ ] Owner read-only `py -3.11 -m scripts.item_pool_report` aggregate results
  demonstrate the actual current `item_pool_v3` status, or clearly explain no
  cache/old policy. No private paths/raw logs or player identifiers.
- [ ] All remaining P0 feature ids, diagnostic tuple tests, backend records
  and real rendered UI acknowledgments integrated; `build.item_pool` alone
  has production code and still needs final CI and owner v4 report.
- [ ] User confirms that a **supported custom Mayhem mode** and test environment
  exist. No need to play a normal competitive match merely to test.

## During the one final user-controlled Mayhem match (only when ready)

- [ ] Confirm intended champion/augment recommendations, no MR/MS proxy stats,
  visible offer only at the actual augment selection, and absence otherwise.
- [ ] Check shop recommendation when shop is appropriate; any unavailable or
  invalid item is a failure of `build.next_item`, not a reason to guess.
- [ ] If a Voucher naturally occurs, confirm separately the inventory edge,
  actual visible Stat Anvil popup, detected options and UI display. If no
  Voucher occurs, mark conditional Anvil checks SKIPPED / not observed, NOT PASS.
- [ ] No automatic clicking or selection; no personal screenshots or match logs
  uploaded to the public repository.

## After the final match

- [ ] At the final single Mayhem acceptance, obtain the safe last-session
  report using `python -m backend.feature_diagnostics` (generic CLI now
  available on P0 #107 for `build.item_pool`). The optional HTTP route
  from sibling #106 is NOT yet integrated. Do not use the isolated P0 pool
  result to claim all other P0 features passed.
- [ ] For every feature above, inspect OK / FAILED / SKIPPED / NOT FIRED and
  closed reasons, cross-check with observed user-visible output; keep unverified
  mandatory cases open. Share sanitized ids/status/reasons/counts only.
- [ ] Close P0 **only after all mandatory native acceptance gates are proven**
  and the final HEAD/Windows CI is reverified. Automatic next-phase chat prompt
  only after closing P0; while blocked, give steps and remain in P0.
