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
- Sources: AramHex (CC BY-NC 4.0, allowed because the app is **non-commercial**; must be removed or authorised in writing if that changes), arammayhem.com/data (CC BY 4.0, pick rate only), the user's own local LCU history. Attribution in `THIRD_PARTY_NOTICES.md` and in the app.
- **The empirical tier list is shown in the overlay now**, without waiting for Riot (owner decision against the reviewer's recommendation; risk recorded in the design §0). It sits behind `empirical_tiers_enabled` (default **on**); switching it off in Settings must revert to the curated level instantly, without restart.
- The overlay **never shows win rate, sample size, wins or lift** — only tier, rank, tie group, source level and confidence.
- No fabricated data. Every stored value keeps provenance (source, snapshot SHA-256, patch, region) and its sample size `n`.
- No scraping of sites with prohibitive or unknown terms (OP.GG, METAsrc, U.GG, Mobalytics, ARAMKit, MayhemMeta). arammeta.com data has no licence → not usable without written permission (an email asking for it is pending; do not send anything).
- No private data in this public repo (logs, screenshots, Riot IDs, personal paths, local history). The tier DB lives on the user's machine.

## Decided later on 2026-11-23 (whole design approved)
- Champion **Strength** = tier from WR 50 (shrunk, k = 500) / leverage 23 / combat vs role 19 / consistency 8. Leverage is **absolute**: E[max of 3 offered] shrunk logit win rate of champion+augment, by rarity. With AramHex only, v1 is effectively WR 68 / leverage 32.
- Champion **Potential** = relative augment gain over the champion's own baseline (E[max of 3 offered ΔWR]), shown as **five qualitative levels** (very_low, low, medium, high, very_high; quintiles), never as a number. Potential also orders champions inside a statistical tie group; it never changes tier or tie group. Both fields are shown to the user (ARAM is for fun: a mid/weak champion with high potential is worth trying).
- Reason: relative gain as a score weight anti-correlates with winning (holdout τ −0.25; composite 0.644 vs 0.860 WR-only). Absolute leverage keeps 0.844; with the potential tie-break 0.839.
- Tier thresholds: percentiles of the patch reference distribution: OP ≥ P97 (champion level only and P20 also above), S ≥ P85, A ≥ P65, B ≥ P40, C ≥ P20, D ≥ P7, E below.
- Shrinkage: ΔWR k = 300 (holdout shows k barely matters at AramHex sample sizes); hierarchy k1/k2/k3 = 200/500/1000.

## Known facts that limit v1
- The public Riot API returns 403 for Mayhem (queue 2400): the match-v5 collector is **blocked**.
- AramHex gives games/wins per champion and champion+augment (CN server). Damage/min, KP, deaths, duration, enemy comp and build only come from the local LCU history (small n) or future opt-in telemetry. So in v1 the augment list is ≈ 100 % ΔWR plus the heuristic level; the code must support the other metrics without inventing them.

## Implementation status (draft PR #106; UI wiring done, Windows CI SUCCESS on 60df345), branch `feat/tierdb-augment-champion-tiers`, Windows CI SUCCESS on 0f867fe)
Read `backend/tierdb/` and `tests/test_tierdb_*.py` before changing anything; 57 tier DB tests.

| Phase | Deliverable | Status |
| --- | --- | --- |
| F0 | Real AramHex format pinned (meta.json maps file → SHA-256 string; Riot numeric champion keys; rarity in augments.json; `excluded_augments`) | Done |
| F1 | SQLite store with per-value provenance (`store.py`) | Done |
| F2 | AramHex importer with checksum/licence/mode checks and quarantine (`aramhex.py`) | Done |
| F3/F4 | Augment tiers per champion and rarity (`augment_tiers.py`) | Done |
| F5 | Champion Strength + Potential (`champion_tiers.py`) | Done |
| F6 | Pipeline, export without WR/n, `TierListProvider` with live `empirical_tiers_enabled` switch in `~/.aram-oracle/tierlist_preferences.json` (default on), CLI `python -m backend.tierdb update` | Done (backend only) |
| F7 | `scripts/validate_tierdb_holdout.py`, first 16.22→16.23 report | Done |
| **UI1** | Settings toggle for `empirical_tiers_enabled` (save via `save_empirical_tiers_enabled`) | **Next** |
| **UI2** | Augment tier/rank/tie group/level/confidence on each offered card (from `TierListProvider.augment_tier`), curated fallback when the switch is off | **Next** |
| **UI3** | Champ select: Strength (tier) and Potential (5 levels) side by side for the player's and bench champions | **Next** |
| D1 | arammayhem.com CC BY pick-rate importer (prior only) | Open |
| D2 | LCU local-history importer (combat, KP, deaths, duration) | Open |
| D3 | Automatic `update` on patch change | Open |

## Testing policy for every phase, including your P0s (owner, 23/11)

The owner runs **one** end-to-end Mayhem match at the end, not one per sub-phase. Every
feature you build must therefore be diagnosable from that single run:

- Give each feature a dotted id (`area.name`, e.g. `ocr.offer_titles`, `build.next_item`)
  with closed enum reasons in `backend/feature_registry.py`.
- Call `feature_diagnostics.record(feature, "ok"|"failed"|"skipped", reason, count)` at the
  decision point. When the user sees the result, also send a `feature_ack` from the overlay
  and add the id to `UI_FEATURES`. A feature that does not act must record why.
- In the RED commit, add a test that asserts the exact `(feature, status, reason)`.
- Add one line per feature to `docs/plans/SINGLE_MATCH_TEST_CHECKLIST.md`.
- Never log names, Riot IDs, paths, OCR text, screenshots or win rates.

Reference implementation and the full pattern are in draft PR #106 (commit 871d4a8):
`backend/feature_diagnostics.py`, `docs/plans/FEATURE_DIAGNOSTICS.md`. The report comes
from `python -m backend.feature_diagnostics` or `GET /api/diagnostics/features`.

## Superseded
- Audit §16 / §18.2 note 4 ("empirical layer only with Riot's written approval; overlay shows only level 4") → superseded by the owner decision to show it now behind the flag.
- Audit §18.1 initial weights 35/20/15/10/10/10 → superseded by 50/15/12/8/8/7.
- Audit §17.8 D2 (match-v5 collector) → blocked (403).
