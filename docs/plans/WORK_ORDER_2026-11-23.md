# Work order (owner decision, 2026-11-23)

**Decided (Francisco, 23/11):** fix the features first, then the full plan. This order
overrides every earlier plan, including the v3 plan of 20/11 (superseded).

| Step | What | Who | Where | State |
| --- | --- | --- | --- | --- |
| 1 | Fix the 3 P0s: augment parser, item eligibility, Stat Anvil trigger | GPT | its own draft PRs | In progress |
| 2 | Tier list DB: augment tiers on offers, champion strength + potential in champ select, Settings switch, per-feature diagnostics | Claude | draft #106 | Done (Windows CI green) |
| 3 | **One** end-to-end ARAM Mayhem test match with steps 1 and 2 together | Owner | `docs/plans/SINGLE_MATCH_TEST_CHECKLIST.md` (#106) | After 1 |
| 4 | Only then: the full plan from the independent audit of 23/11 | GPT + Claude | `docs/audits/AUDITORIA_INDEPENDENTE_2026-11-23.md` | After 3 |

Rules for steps 1–3:

- No in-game test per sub-phase. Each feature must be diagnosable from the single match:
  per-feature diagnostics (id + enum reasons) as in `docs/plans/FEATURE_DIAGNOSTICS.md` (#106).
- Do not start step 4 work, and do not reopen the v3 plan, before step 3 is reported.
- Draft PRs only, no merge. Never show win rates. No private data in the repo.
- Step 1 and step 2 do not touch each other's files: the tier list work avoids the augment
  parser, item eligibility and the Anvil trigger.
