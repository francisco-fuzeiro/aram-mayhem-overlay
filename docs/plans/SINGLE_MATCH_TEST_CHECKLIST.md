# Single Mayhem Match Test Checklist — P0 baseline

## 2026-11-23 — Actual 16.23 hashed Stat Anvil source gate and subsequent native acceptance

- [x] Independent read-only current-patch HTTP check [Windows Actions #45228414820](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45228414820): `/16.23/game/unknown/507cdd64276919f5.bin.json` → **404**. Fallback same-patch CDragon JSON index checked: **exact filename absent, no matching prefix**. This path does NOT supply live current-patch `AnvilData`/RootSpell; historic 16.22 reports do not pass source gate.
- [x] Reusable `scripts.anvil_source_exact_probe` tests distinguish raw 0/8/9 singleton and mixed `AnvilTypes`, parser tiers, 404/index and unavailable source; no account/League or fixture-pretends-live acceptance. Temp public CI probe step removed after collecting evidence. At audited SHA 2,115 Python PASS/27 SKIP, 89 JS PASS, 35 real pinned OCR PASS.
- [ ] **Patch source gate**: find **actual 16.23** public `AnvilData` source file(s) with valid `RootSpell.mSpell.DataValues`, `total>0`, Silver/Gold/Prismatic >0 and exact source paths. Earlier scan was 80/471 indexed candidates; TFT/DustToDiamonds text hits NOT sources. Only then wire current loader, dedicated title/value OCR and strict no-guess abstention with RED→GREEN tests.
- [ ] **Native gate**: actual 3/4-card popup timing, OCR name+number identity, contextual own 0.0–10.0 scores and genuine UI-ACK; shop #49, augment flow and all P0 per-feature reports in ONE user-controlled permitted Mayhem match; any feature not fired stays SKIPPED or NOT FIRED, never PASS. Final exact-head Actions GREEN.
- [ ] **Phase closure** only on complete functional/native evidence. Owner explicitly requested a one-time next-chat P0 continuation prompt while open, with blockers and steps; this is a session handoff, NOT P0 completion. PR #107 draft, no merge/main/TierDB.

## 2026-11-23 — Source-only target check after real 80/471 scan

- [x] Owner real 16.23 public scan: 471 bins indexed, 80 inspected (21 dirs), `scan_complete=false`, `source_paths=[]`, `total=0` and silver/gold/prismatic all 0. Two keyword-only files `game/gameplay.bin.json`, `game/maps/modespecificdata/cherry.bin.json`. No source validated.
- [x] `tests/test_p0_stat_anvil_keyword_probe.py` and focused `--public-patch 16.23 --probe-keyword-paths` produce bounded source-only JSON reference paths and AnvilData counts, never native or catalogue success; tested on [Windows #45224141982](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45224141982).
- [ ] Owner targeted public probe; follow references then confirm real `total>0`, Silver/Gold/Prismatic all>0 and exact current bin paths. No ranking from a keyword or synthetic fixture.
- [ ] Later actual popup OCR/title+stat value/3-or-4 cards and own 0–10 render, live shop and augments in ONE final owner-controlled Mayhem match; P0 OPEN.

## 2026-11-23 — Source-gate correction: zero Stat Anvils on old 16.23 paths

- [x] Actual owner report `--public-patch 16.23` was **total=0, silver=0, gold=0, prismatic=0**, only `map12.bin.json` reported. Older test fixture results do NOT prove live/current source.
- [x] Index/scan code+mocked RED→GREEN tests: `test_p0_stat_anvil_source_index.py`, `test_p0_stat_anvil_discovery.py`; current code scans selected public CDragon `/json/16.23/game/` directory listings and plausible `.bin.json` files. The method itself (not real public source) passed [Windows #45220848233](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45220848233) on code HEAD `4a199e6`.
- [ ] Run real patch source discovery with `py -3.11 -m scripts.stat_anvil_catalog_report --public-patch 16.23 --discover --json`. If incomplete, widen bounded scan with `--discovery-bins 200 --discovery-dirs 100`; inspect status, source_paths, keyword_paths, tiers, bin_files_inspected, candidate_bin_files, index_failures. **Keyword hits are not source validation**.
- [ ] Source gate: only pass with **total>0, silver>0, gold>0, prismatic>0** and patch-matched validated `AnvilData` file(s), then pin that actual file path with focused tests. No guessed map, old-patch fixtures or false current source.
- [ ] Independent real popup/3-4 cards, values OCR and own 0–10 + genuine render ACK, plus one final native Mayhem match and final exact-head CI. Until then P0 OPEN.

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
**Owner OFFLINE v4 cache verification is now PROVEN:** 104 final, 7 boots,
111 recommendable from 863 patch-16.23.1 public entries, two sources
verified; [Windows #45209892347](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45209892347)
SUCCESS on exact code HEAD. **No native game acceptance** exists. This
documentation-only checkpoint needs its own exact-head CI.

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
| `build.item_pool` | DD/CD verified current-policy item cache load (network or warm cache); abstain if unverified | `tests/test_p0_item_source_recipe.py` exact `build.item_pool/ok/final_items` (count), `failed/no_final_items`, `skipped/unverified`; [RED #45207926899](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45207926899) proves 104 terminal DD omitted `into` vs CD `to=[]` | **Code CI GREEN + owner v4 offline counts PROVEN**; native shop NOT TESTED |
| `build.next_item` | Shop decision point; only real eligible final/boots and feasible purchase suggested | Existing shop/build tests must be connected; exact `(build.next_item,ok,recommended)` / `(build.next_item,skipped,no_eligible_item)` RED pending | Shop #49 OPEN; native NOT TESTED |
| `anvil.voucher_purchase` | Active player's purchased voucher stack actually increases; otherwise report safe no-trigger reason | `tests/test_p0_anvil_voucher.py` exists (edge/synthetic poll only); exact `(anvil.voucher_purchase,ok,positive_edge)` / `(anvil.voucher_purchase,skipped,no_edge)` RED pending | Diagnostics PENDING; native NOT TESTED |
| `anvil.offer_detected` | Verified voucher + actual visually confirmed Stat Anvil popup; no invented cards | Current tests only disprove OCR on voucher-only event; exact `(anvil.offer_detected,ok,verified_offer)` / `(anvil.offer_detected,skipped,popup_unverified)` RED pending | Verified option corpus/3-or-4 geometry BLOCKED |
| `anvil.offer_render` | Three/four verified Stat Anvil choices actually appear in overlay, not backend-only decision | Exact UI `feature_ack` test and `(anvil.offer_render,ok,rendered)` / `(anvil.offer_render,skipped,no_verified_offer)` RED pending | UI not implemented; native NOT TESTED |

These are **proposed reason names**, not currently registered production reasons.
At implementation, freeze/validate enums per id; do not emit raw data or free
text in any record. Do not mark a diagnostic PASS merely because a test file
existed before instrumentation.

## 2026-11-23 — Stat Anvil source and rating evidence prerequisites

- [x] `anvil.offer_detected` public **source research** (offline, not a live event):
  independent MIT [ARAM Mayhem Tracker](https://github.com/Sygnano/aram-mayhem-tracker)
  establishes `AnvilData` / `RootSpell.DataValues` game bin instead
  of `cherry-augments.json`; title can be shared across rarities.
- [x] `anvil.offer_detected` pure tests for exact shard source id,
  silver/gold/prismatic tier, spell values, prohibited choices, and
  complete 3/4 stat/value matching:
  `tests/test_p0_anvil_public_source.py`; source parser
  `backend/static_data/anvil_public_catalog.py`.
  This is **offline identity logic only**, no live popup/recognition.
- [ ] Current owner patch `16.23` public game-bin proof via
  `py -3.11 -m scripts.stat_anvil_catalog_report --public-patch 16.23`,
  then optional public title lookup `--locale en_us`. These commands
  are opt-in network-only, no writes/player-data and do not verify the UI.
- [ ] Actual popup visibility/3-or-4 layout and independent title + value
  OCR, distinct from voucher edge, with precise `anvil.offer_detected`
  and `anvil.offer_render` reason tuples and true client UI ACK.
- [ ] Rate actually recognized offered shards on our **own 0–10 model**
  with champion/augments/items/enemy context, never copy OP.GG scoring
  data or display a score for unknown/mixed/stale cards.
- [ ] Latest Windows Actions after source and docs, then **ONE** final
  owner-controlled Mayhem match with real shop + Anvil conditional gates.
  Conditional Anvil not observed is SKIPPED/NOT FIRED, never PASS.

## Before the one permitted final match

- [ ] Owner's Git checkout in the `aram-oracle` child directory is on the
  intended P0 branch and exact latest PR #107 HEAD; keep the untracked local
  `funcionalidades.md` untouched.
- [x] Owner read-only `py -3.11 -m scripts.item_pool_report` proves
  current public `item_pool_v4`: 863 total / 104 final / 7 boots / 111
  recommendable, verified_two_source, no warnings. No private data shared.
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

---

## Tier list features (PR #106): owner checks in the same match

One ARAM Mayhem match covers every feature. Do not test per sub-phase.

### Before

1. Update the local copy to the branch under test and start ARAM Oracle as usual.
2. Wait about 1 minute on first start: the tier list downloads in the background.
   Settings → Build Preferences → "Mayhem tier lists" should show `On · patch …`.

### During (no screenshots needed)

1. **Champion select:** check that a line `Mayhem strength: … · Potential: …` appears
   under some champions.
2. **First augment offer:** check that each card shows a `Tier … · #…/…` line
   (or `No tier data for this champion`).
3. Optional: in Settings switch the tier lists off and check that the lines disappear at
   the next offer, then switch them back on.
4. Play normally to the end.

### After

1. Close the match. With ARAM Oracle still open, open
   `http://127.0.0.1:8765/api/diagnostics/features`, or in the project folder run
   `python -m backend.feature_diagnostics --out feature_report.md`.
2. Paste the table into the chat. It holds only ids, verdicts, reasons and counts:
   no names, paths or win rates.
3. Note in one line what you saw: yes/no for each of the three checks above (champ select, offer, build).

### Reading the report

- **OK**: worked at least once this session.
- **FAILED / NOT FIRED** in bold: a feature that should have run did not. The reason
  (e.g. `failed/champion_not_in_tierlist`, `failed/export_missing`) points to the cause.
  Build features: `items.reference_build`, `items.build_render`, `anvil.stat_estimate`.
- **SKIPPED**: the feature chose not to act (e.g. switched off).

New features add their lines here (see `FEATURE_DIAGNOSTICS.md`).
