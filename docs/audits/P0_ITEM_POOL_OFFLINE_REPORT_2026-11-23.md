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
