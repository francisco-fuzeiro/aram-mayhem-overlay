# P0 item eligibility: owner-operated offline cache report (2026-11-23)

Source: independent audit in draft #105, based on #103. This document is independent of the parallel TierDB work.

## Purpose and evidence boundaries

The independent audit counted **0 classified final items** (and seven tier-2 boots) in an **owner-device cache labelled item_pool_v2**, but did **not** run the current policy v3 on the owner's real cached public item data. This is an observed old-cache fact, not proof that v3 is defective or healthy. Do not claim "Next: unavailable" is repaired from synthetic fixtures.

From the repository checkout on Windows, with League and the Oracle application closed:

```powershell
py -3.11 -m scripts.item_pool_report
py -3.11 -m scripts.item_pool_report --json
```

Both commands read `data/cache/items_v5_*.json` and print aggregate public catalogue counts only. You may pass `--cache-dir <directory>` to inspect a different pre-existing cache folder. They never contact LCDA, LCU, game, Riot or public HTTP, and never write or invalidate a cache.

For each cache, capture just these aggregate fields in a follow-up: `schema`, `policy_version`, `ddragon_version`, `source_status`, `final`, `boots_tier2`, `recommendable`, `unknown` and warnings. **Do not publish local paths, any personal game data or full raw logs.** If the file is absent, the script exits 2 and says there is no cache; do not treat it as zero purchasable items. If a cache is structurally incomplete, it also exits 2. A valid classification report does not mean any specific item is actually purchasable in the current Mayhem shop.

## Next evidence gate

1. Distinguish genuine `item_pool_v3` and current-patch snapshots from historical `item_pool_v2` reports.
2. If current v3 still has zero final items, obtain an independently reproducible *public-source* DD/CD disagreement (price, `from` or `into`/`to`) without using game data.
3. Only then write a small tests-only RED, correct the minimum verified item-classification rule, demonstrate that reward/conditional/mode items remain excluded, run exact Windows CI and defer actual shop availability to a user-operated custom Mayhem check.

The report intentionally does not fetch or fabricate raw two-source disagreement details: the saved cache contains final classes, not the original per-source recipes. Expanding it requires an explicit, reproducible public-source diagnostic, not permissive classification heuristics.

## Voucher/Anvil limitation

The two public catalogue item IDs (`220008` and `220009`) are used *only* to observe positive owned-stack transitions in LCDA. A purchase event does **not** prove a popup is visible or identify any option. Production has no verified Stat Anvil choice catalogue or independently validated layout; no fabricated entries, OCR scoring or automatic pick are allowed. Native availability and timing remain **NOT TESTED**.

## 2026-11-23 — Verified owner-device v3 root cause; v4 repair awaiting CI/native

The owner rebuilt the item cache through the current public sources and
reported `item_pool_v3`, patch `16.23.1`, `source=network`,
`verified_two_source`, **863 items / 0 final / 7 tier-2 boots**;
`unknown=130`, `mode_variant=152`. This proves the false-empty pool
persists with new v3 cache (not just old v2).

Owner-operated read-only independent public-source comparison found
**104 otherwise eligible terminal final items**, all 104 rejected by
`sources_agree`, because Data Dragon omits `into` while CommunityDragon
explicitly uses `to=[]`. Examples include public item IDs `3031` Infinity
Edge, `3089` Rabadon's Deathcap, `3074` Ravenous Hydra. This is
distinct from 152 excluded mode variants, which are **not** promoted.

Tests-only [Windows RED #45207926899](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45207926899):
4 new FAIL (including one overly strict test string/int comparison, corrected
in GREEN), 2,069 other Python PASS / 27 SKIP; real pinned OCR model job PASS.
Minimal repair: DD absent terminal `into` = [] ONLY when CD supplies an
explicit matching `to` array; preserve DD `from` multiset, CD field
presence, exact price, mode/reward/conditional exclusions. Bump
`ITEM_POLICY_VERSION` v3→v4 so stale classified v3 caches are rejected;
re-download current public sources on next loader use. No blanket
eligibility relaxation.

Added backend diagnostic `build.item_pool` reporting exact enumerated
`ok/final_items` (count), `failed/no_final_items`,
`skipped/unverified`, with privacy-safe generic report CLI
`python -m backend.feature_diagnostics`; no UI ack needed because it is an
internal backend decision. The parent TierDB draft #106 keeps its
independent feature list until careful reconciliation.

**Not yet established:** new exact HEAD Windows GREEN, owner Windows v4 pool
counts, actual Mayhem shop availability, popup/Stat Anvil support, full
P0 phase completion. One owner-controlled custom Mayhem match at the END
for the complete P0 batch, never one match per partial repair.
