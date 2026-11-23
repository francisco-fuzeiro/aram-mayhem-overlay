# GPT brief: tier-list database (augments per champion + champions)

Date: 2026-11-23. Owner decisions are marked **Decided**; designs not yet approved are marked **Proposal**.
The source documents are in Portuguese; this brief is the English entry point.

## Read first (in this order)
1. `docs/plans/DESENHO_TIERDB_2026-11-23.md` — design: DB schema, per-patch pipeline, formulas, thresholds, phases F0–F7, tests.
2. `docs/audits/FONTES_DADOS_MAYHEM_2026-11-23.md` — which data sources are legal and what each provides.
3. `docs/audits/AUDITORIA_INDEPENDENTE_2026-11-23.md` — independent audit of #103; sections 16–19 are the data/weighting background. **Where it conflicts with this brief, this brief wins** (see "Superseded").
4. `AGENTS.md` and `.agents/skills/continue-aram-oracle/SKILL.md` — repository rules.

## Decided (owner)
- Per-champion augment tier list, computed before the game, for **every augment of the patch**, split by rarity (Silver/Gold/Prismatic). Strict rank 1..N with visible tie groups (adjacent items tie when P(A > B) < 0.75). Tiers OP/S/A/B/C/D/E with thresholds frozen per patch.
- Augment weights (initial; recalibrate out of sample): **ΔWR 50** (shrunk, lower bound) / combat impact by role 15 / kill participation and deaths 12 / game-duration curve 8 / context 8 / consistency 7. All values are deltas against the champion's own baseline; pick rate only as a prior. The composite must beat "ΔWR only" in a temporal holdout, otherwise the overlapping weights drop.
- Missing metric → its weight is redistributed proportionally. Missing ΔWR at a level → fall back one level.
- Few games → hierarchy champion+augment (max tier OP) → role+augment (max S) → global augment (max S) → curated heuristic table (max A) → "no data" (never 0). The source level is visible in the overlay.
- Champion tier list for ARAM Mayhem with win rate ≥ 50 %.
- Sources: AramHex (CC BY-NC 4.0, allowed because the app is **non-commercial**; must be removed or authorised in writing if that changes), arammayhem.com/data (CC BY 4.0, pick rate only), the user's own local LCU history. Attribution in `THIRD_PARTY_NOTICES.md` and in the app.
- **The empirical tier list is shown in the overlay now**, without waiting for Riot (owner decision against the reviewer's recommendation; risk recorded in the design §0). It sits behind `empirical_tiers_enabled` (default **on**); switching it off in Settings must revert to the curated level instantly, without restart.
- The overlay **never shows win rate, sample size, wins or lift** — only tier, rank, tie group, source level and confidence.
- No fabricated data. Every stored value keeps provenance (source, snapshot SHA-256, patch, region) and its sample size `n`.
- No scraping of sites with prohibitive or unknown terms (OP.GG, METAsrc, U.GG, Mobalytics, ARAMKit, MayhemMeta). arammeta.com data has no licence → not usable without written permission (an email asking for it is pending; do not send anything).
- No private data in this public repo (logs, screenshots, Riot IDs, personal paths, local history). The tier DB lives on the user's machine.

## Proposal (awaiting owner approval)
- Champion tier weights: **WR 50** (shrunk lower bound, k = 500) / augment leverage 23 (E[max of 3 offered ΔWR] by rarity) / combat vs role 19 / consistency 8. With AramHex only, v1 is effectively WR 68 / leverage 32.
- Tier thresholds as percentiles of the patch reference distribution: OP ≥ P97 (level 1 only and P20 also above), S ≥ P85, A ≥ P65, B ≥ P40, C ≥ P20, D ≥ P7, E below.
- Shrinkage constants: ΔWR k = 300; hierarchy k1/k2/k3 = 200/500/1000. Calibrate in F7.

## Known facts that limit v1
- The public Riot API returns 403 for Mayhem (queue 2400): the match-v5 collector is **blocked**.
- AramHex gives games/wins per champion and champion+augment (CN server). Damage/min, KP, deaths, duration, enemy comp and build only come from the local LCU history (small n) or future opt-in telemetry. So in v1 the augment list is ≈ 100 % ΔWR plus the heuristic level; the code must support the other metrics without inventing them.

## Phase order (one small draft PR per phase, RED test commit → GREEN code commit, Windows CI)
| Phase | Deliverable | Status |
| --- | --- | --- |
| F0 | Read one patch of AramHex and arammayhem.com; pin the real file format and SHA-256; document fields | Open |
| F1 | SQLite schema + provenance (`backend/tierdb/store.py`) | **Done** on `feat/tierdb-augment-champion-tiers` (12 tests GREEN locally; Windows CI not yet run) |
| F2 | Importers (AramHex, arammayhem, local history) + quarantine of unmapped names; NC sources excluded in commercial mode | Open |
| F3 | Augment math: shrinkage, redistribution, level fallback, caps | Open |
| F4 | Rank, tie groups, frozen thresholds, full catalog coverage per rarity | Open |
| F5 | Champion tier list | Open (weights pending approval) |
| F6 | Export JSON without WR/n, `empirical_tiers_enabled` default on with instant off switch, attribution | Open |
| F7 | Offline temporal-holdout validation (composite vs ΔWR only) | Open |

## Superseded
- Audit §16 / §18.2 note 4 ("empirical layer only with Riot's written approval; overlay shows only level 4") → superseded by the owner decision to show it now behind the flag.
- Audit §18.1 initial weights 35/20/15/10/10/10 → superseded by 50/15/12/8/8/7.
- Audit §17.8 D2 (match-v5 collector) → blocked (403).
