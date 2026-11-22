# ARAM Oracle — Mayhem scoring data lineage and native OCR/reroll triage

**Date:** 2026-11-22  
**Scope:** read-only source review and bounded native observations; separate from a new scoring model.  
**Baseline:** draft PR #83, source code at `d24d544c839aae3637b6328db41f2821cd12ff46`. Code-only UI race candidate at `0b32d229ad6a2e12e3e7da12f715a4808521a0e5`; Windows GREEN and native retest must be checked independently.  
**Tracking:** OCR #82 (blocker), scoring/calibration #84 (separate), deferred build #49. Public repo: no private captures, raw OCR, logs, player names/IDs or local paths.

## Native observations and what they establish

- V12-N00 Windows dependencies, verified v4 model SHA-256 and independent Tesseract/v4 desktop opt-in launches: **user-observed preflight PASS**, not a per-frame proof that v4 ran.
- V12-N01: one three-card offer, **3/3 user-observed physical identities correct**, <=6 s categorical first stable recommendation; user reported correct own current champion in one champion-select observation (not complete F1.3).
- V12-N02: user observed **one incorrect named augment after first reroll**. The centre and last reroll were reported correct. First offer also displayed **`Not Rated`**. Thus V12-N02 **FAIL / no v4 promotion**, the specific native wrong-identity root cause remains **undetermined**.
- Inspection of backend and UI messaging found a **separate provable race:** `backend/api/server.py` sends `ocr_result` after confirmed new physical slots without the refreshed OfferLedger `offers`; `frontend/app.js` previously rendered old `currentOffers` using newly `detected` OCR phase until a following authoritative `update`. A tests-only synthetic RED (`tests/js/overlay-messages.test.cjs`, `a1d55486e220e5931d29c95693a553694ad25902`) failed exactly this stale-name contract in [Windows Actions 45066399248](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45066399248): 1/79 JS fail, 1,977 Python pass / 27 skip, real-v4 job PASS. A narrow `offerCanOpen` guard now withholds mismatched OCR/ledger snapshots; confirm subsequent Windows GREEN and one native reroll retest separately. This is **a real code race**, not proof it was the user's specific native false-positive cause.
- Other possible causes **remain unproven**: wrong title crop/DPI, PP-OCRv4 transcription, similar-title catalog match, perceptual-hash collisions, temporal state or stale WebSocket ordering. Do not patch these without a reproducer or relax 90/8 strict matching, two independent reads or focus/epoch rules.

## Actual score data sources (source-derived)

| Stage | Actual source | Signal | Proven limitation |
| --- | --- | --- | --- |
| Champion catalog | `data/champions/champions.json`, 172 entries generated using `scripts/generate_champions.py` from Riot Data Dragon role tags + six manually authored role vectors and champion-specific overrides | 12-dimensional gameplay preferences and hard/soft CC approximations | **Not observed ARAM Mayhem strength**; manual reruns needed to refresh bundled file |
| Champion multipliers | `data/champions/synergies.json`, 25 champion keys | Stat-specific custom modifiers | Partial hand-authored coverage, no patch-scoped win evidence |
| Champion draft context | Local LCU `/lol-champ-select/v1/session` + `backend/engine/champion_select.py` | Available own/bench candidates, team role balance | Missing alias/ID or local-player certainty can skip candidates; F1.3 is separate |
| Augment catalog | CommunityDragon `cherry-augments.json` latest (primary), `cdragon/arena/en_us.json` descriptions by name (supplement) | Mayhem augment names, tiers, Arena-derived descriptions | Arena descriptions may not cover Mayhem-only effects; unknown titles can remain unmodeled |
| Augment feature model | `backend/static_data/loader.py`: ~12 dimension keyword parser, limited exact-name hints, `data/augments/overrides.json` with 2 ID keys, `data/augments/scaling.json` with 27 ID keys | Approximate stat affinity, rarity, CC, scaling | Proc, conditional/quest, champion-specific and item-dependent interactions are not fully represented; scaling-only contribution must be tested for accidental `Not Rated` gating |
| Personal outcomes | Local DB; optional LCU Mayhem history import `MAYHEM_QUEUE_ID=2400` | Self win/loss record only when imported | `lcu_history_enabled=False` and `experimental_augment_evidence=False` by default; no integrated global Mayhem performance sample |
| Enemy and build context | LCDA player-visible team/enemy data, item and augment catalog | Visible role threats, confirmed chosen augment IDs and verified shop pool | Neither an exposed enemy nor an OCR candidate is proof of an actual chosen augment or an eligible item |

**No current global ARAM Mayhem match-results ranking is integrated into the code.** Public websites with recent Mayhem statistics exist, but their data methodology, patch compatibility, redistribution terms and Riot policy must be validated **before** evaluating or importing them. Their published win rates must not simply be copied or disguised as scores.

## The actual formula (not a calibrated win probability)

`backend/engine/composite_score.py` describes a target 40% empirical performance / 35% synergy / 25% context:
- **Without compatible performance evidence**, `score = (0.35 × synergy + 0.25 × context) / 0.60`, effectively **58.33% synergy + 41.67% context**; confidence 0 and sample size 0.
- **With evidence**, posterior = (wins + 0.5×40)/(games+40). Performance = clamp(5 + 25×(posterior−0.5), 0,10). Confidence = games/(games+40), optionally reduced for missing patch metadata; empirical weight = 0.4 × confidence. The score interpolates the heuristic toward empirical performance, **not** a fixed 40% term with zero samples.
- **Champion-select** `_fit_score`: base 60/100 plus an 8-point stat breadth term, +14 frontline / +12 magic / +10 physical / +7 utility for missing roles and −6 for duplicated role; normalized /10. `kit_fit = 4 + 4×mean(top four of 12 profile fields)`, clamped to 10. The resulting composites are **kit/team-fit proxies**, not calibrated Mayhem strength. Tiers S>=7.5, A>=7.0, B>=6.5, C otherwise. It is therefore expected that power from unique Mayhem passives, augment pools or patch shifts is absent from the ranking.
- **Augments** `score_augment`: dot(champion role-weighted stats, augment contributions) × tier multiplier, plus modeled scaling, CC-CDR and enemy modifiers, minus overlap; mapped to `synergy = 10×(1−exp(−max(0,raw)/1.2))`. `context` uses a bounded tanh transform of enemy modifiers. This is an **unvalidated heuristic**.
- `AugmentData.modelled` becomes false if all 12 contribution fields are zero; `rate_augment` then returns `score=None`. UI also displays `Not rated` if the offer is not visible, OCR phase != detected, stale, no matching recommendation or a nonfinite/unmodelled score. These **distinct reasons are currently conflated**. Source and patch-scoped actual counts must be collected via `StaticData.augment_coverage_report()`; do not invent coverage percentages.

## Scoped next tasks / release gates

1. **OCR #82 first:** synthetic RED→minimal UI stale-snapshot guard→Windows GREEN on exact SHA, then native reroll retest; any wrong *accepted* physical augment ID remains STOP. The UI race fix cannot prove recognition accuracy.
2. **Scoring #84 separately:** quantify patch-specific modeled/unmodeled catalog coverage and sources with no user data; distinguish `no model` from `verifying/stale` and `data missing`, plus champion current/bench mapping. Add tests-only RED for *actual* bugs including any scaling-only contribution gating, then minimal GREEN; avoid fake numeric scores.
3. **Calibrate:** independently validate permitted, licensed Mayhem patch samples by champion, augment tier, context and holdout, with confidence/coverage and transparent provenance. Avoid making a heuristic tier appear statistically objective.
4. **Operational:** exact SHA Actions, controlled Windows checks for three-card L/C/R, reroll left/centre/right, negative scenes, two-line titles, four-card abstention and latency; preserve Riot review gate before shipping dynamic recommendations.

**Decision:** retain PP-OCRv4 as user-selected experimental engine; do not promote it to default, remove Tesseract fallback, merge any PR or implement automatic gameplay choices. No OCR raw data or identifying evidence is stored in this audit.
