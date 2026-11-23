# Single Mayhem Match Test Checklist — P0 baseline

> **Owner rule, 2026-11-23:** Test all prepared P0 features in ONE user-controlled
> Mayhem match at the end, not one match per fix. This checklist is for draft
> P0 #107 only; sibling TierDB draft #106 has another version of this path.
> **Reconcile/add the P0 rows when integrating sibling branches**, preserving
> both sets of feature ids. Do not silently discard either checklist.

## Evidence and diagnostic status

Current P0 branch has offline parser/item-report/voucher tests **but does not yet
contain** sibling #106's `backend/feature_registry.py`,
`backend/feature_diagnostics.py`, server diagnostics endpoint or UI
`feature_ack`. **All live per-feature diagnostic assertions below are
PENDING, not PASS.** The named current tests prove only their stated synthetic
functionality. No game is required or authorised for this checklist yet.

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
| `build.item_pool` | Current-policy, patch-matched DD/CD cache loaded; abstain on unknown/disagreeing source | `tests/test_p0_item_pool_report.py` exists (read-only report only); exact `(build.item_pool,ok,verified)` or `(build.item_pool,failed,source_mismatch)` / `(build.item_pool,skipped,cache_missing)` RED pending | Current owner PC v3 report OPEN; diagnostics PENDING |
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
- [ ] P0 diagnostic ids, exact tuple RED→GREEN tests, backend record and
  rendered UI acknowledgments are integrated and exact-head Windows CI GREEN.
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

- [ ] **Only after #106's generic diagnostics framework is correctly integrated
  and tested on this branch** obtain its safe per-feature report via
  `python -m backend.feature_diagnostics` or the local
  `GET /api/diagnostics/features` route. These are **not currently available
  on #107**; do not ask the owner to execute them now.
- [ ] For every feature above, inspect OK / FAILED / SKIPPED / NOT FIRED and
  closed reasons, cross-check with observed user-visible output; keep unverified
  mandatory cases open. Share sanitized ids/status/reasons/counts only.
- [ ] Close P0 **only after all mandatory native acceptance gates are proven**
  and the final HEAD/Windows CI is reverified. Automatic next-phase chat prompt
  only after closing P0; while blocked, give steps and remain in P0.
