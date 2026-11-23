# ARAM Oracle — Adaptive scoring, tier lists, full build and Stat Anvil product contract

**Decision date:** 2026-11-23. **Status:** user-requested behavior and acceptance specification; NOT a claim of production implementation, model calibration, Riot approval, or native Windows validation. **Active design baseline:** draft [#103](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/pull/103), `5c8d819ce6c14bff1b7ecf444c271b40fc2f7ce0`. Source of truth for actual code/tests is the current branch, not this proposal.

## 1. The player outcome

An ARAM Mayhem assistant that is nearly invisible outside a real decision. When a **champion selection**, **augment offer**, **purchased Stat Anvil offer**, or **verified shop** is in progress, show the smallest possible actionable, contextual, evidence-based comparison; never dictate a gameplay action or automate League input. The user wants **one** adaptive build, not multiple fixed alternative build lists. Out-of-game Settings configure strategy and overlay behavior.

### Augment offer — desired compact card

`8.7 / 10 · S · #17/120` is a **format example only**: not a real calculated value, established grade boundary or verified eligible roster size. Each card must present:
- **0.0–10.0 score:** the explicit model's contextual and uncertainty-bounded fit; **never a displayed win rate** or covert rescaling of augment win rate.
- **OP/S/A/B/C/D/E grade:** a calibrated, stable interpretability band, not a gratuitous quantile label. This does **not** yet exist for augment choices. The current champion-select S/A/B/C grading is unrelated and unvalidated as Mayhem power.
- **Rank and denominator:** position among the actually assessed **eligible, modelled, patch-specific comparable candidates**, with rank scope stated. User wants a full-roster per-champion tier list (not merely the current three offers), contextual to selected augments, current owned build, known ally/enemy composition and other lawful visible match state. **Global cross-rarity rank versus same-rarity ranking remains a calibration/design decision**: do not present a cross-rarity #17/200 as an objective comparison if tier multipliers, availability, pool restrictions or unequal evidence make it misleading. Offer a full-roster and per-rarity view only when each has a defensible comparison contract.
- **Tie and uncertainty:** scores may round to the same displayed tenth. Rank using an internally retained unrounded model signal **only if a nontrivial, validated difference exists**; otherwise show tied rank/indistinguishable choices. Alphabetical order is display stability, not evidence that the item is better. Ranking #17 over #23 with both 8.7 is NOT by itself a proven superiority claim.
- **Unknown:** no model, incomplete catalog, wrong patch, unverified physical card, stale state or low-confidence evidence means abstention or a clearly explained unranked/uncertain label, never fake grade, denominator or misleading zero.
- **Why:** brief high-impact factors and confidence/coverage in an expandable explanation, without private player stats or augment win rates.

The full tier list belongs in an optional expanded or out-of-game UI. In combat, do not display the full table. Rankings update on **confirmed** augment picks, verified inventory purchases, champion selection and meaningful observed ally/enemy changes; debounce, use deterministic cached signatures and prevent rankings from flickering between nearly tied candidates. Offered augment IDs are **not** acquired augments.

### Data and scoring evidence gate

At present `backend/engine/ranker.py` scores only the offered cards using `rate_augment`, not a complete patch-scoped roster. `backend/engine/composite_score.py` returns a rounded tenth and experimental confidence; without empirical evidence it blends 35/60 synergy + 25/60 context (approximately 58.3%/41.7%) and **zero empirical contribution**. `backend/engine/augment_rating.py` and `scoring.py` are heuristic dot-product/scaling/CC/enemy models; Mayhem-specific conditional/proc/item effects, patch-calibrated outcomes and full coverage are not established. Champion profiles derive largely from role vectors, not Mayhem results. **Do not disguise a generic role heuristic as empirically valid champion/augment strength.** A review must establish current patch, legal data lineage, model coverage, calibration/holdout and uncertainty before promoting tiers/rank into user-facing recommendations. Check Riot developer rules and relevant current product permissions explicitly; other overlays are not authorization.

## 2. Full build is NOT the end of recommendations

After six physically observed owned final items:
1. If **verified tier-two boots are owned**, evaluate an optional replacement by an independently eligible **movement-speed-bearing** full item. Consider item/champion/confirmed augment synergy, enemy context, real listed unconditional movement speed, lost mobility, item access, slot/gold/recipe constraints, and whether it truly improves the selected build. Never frame a seventh purchase without selling, never automatically sell/buy, and never suggest an unavailable Mayhem quest/reward item.
2. Regardless of whether a legitimate boot-swap is possible, continue useful **Stat Anvil attribute priorities**. Show the strongest *modelled* stat directions and a brief rationale in expanded details; they are **not** the user's exact currently offered Anvil cards. Unknown or incomparable stat dimensions must abstain.

The current `#102` `Build complete` label indicates inventory completion only; it must not imply the assistant has no further advice. `#103` added source-constrained heuristic stat priorities and kept an optional boot-swap before them; **native shop legality and effectiveness remain untested**. Build advice should normally be presented only when the **shop is independently observed open** or on a user-explicit request. Death and gold are not proof of shop visibility.

## 3. Purchased Stat Anvil — a separate live decision

**At any time in the match, not just at full build**, when the player buys an Anvil and its option cards visibly appear, the desired runtime is:
1. Independently detect the **visible Anvil offer/popup**, not merely a gold change, item inventory delta, level/respawn, partial title OCR, or shop intent.
2. Determine actual physical option count and card bounds for that specific scene; source-calibrated 3 vs 4, DPI, HUD scaling, occlusion, transitions and individual rerolls. If unverified/4-card unsupported, **show no misaligned numeric scores**.
3. OCR only current card titles/attributes from the focused verified League client; match against patch-verified Stat Anvil catalog and preserve title, slot, match/epoch, freshness and 90/8 strict matcher/two-read/absence safeguards unless justified by proven independent evidence.
4. For each **currently proven option**, compute a 0.0–10.0 **heuristic** fit using actual champion, confirmed augments, already owned items/build and visible team/enemy context. Where a stat/effect is not modelled, show `No model` rather than 0 or fabricated strength. Compare only confirmed on-screen options, show the highest cautiously, suppress ordinary augment reroll banner.
5. Remove advice when the offer has independently ended, on match change or verified supersession. A card being clicked, hovered or disappearing does **not** prove which Anvil was acquired; integrate only with a valid independent chosen-ID source or explicit manual fallback. No automation of League actions.
6. If popup detection is unreliable, retain a **quiet explicit/manual recovery** outside combat (never a false automatic score).

**CURRENT BLOCKER:** The existing `ScreenWatcher` scan window opens from level/respawn, not purchased Anvil appearance. Tier-zero titles in `_ocr_title_catalog` do not establish popup presence. #103 supplies the **scoring and guarded three-slot presentation path only**, not the trigger, four-card support or current-patch native acceptance. `anvil_priorities.py` presently models AP/AD/attack speed/HP/crit/CDR/lethality, but has no verified complete set of real available Anvil stat quantities/effects. Investigate, do not infer armor/MR/tenacity/movement speed coverage.

## 4. Event-driven, minimally intrusive overlay

- **Champion select:** only verified self/bench candidates, appropriate calibrated fit/rank; hide on exit.
- **Actual augment offer:** highlight only freshly mapped cards, concise score/grade/rank once lawful/calibrated; hide after verified close; no stale rerolls.
- **Actual purchased Stat Anvil popup:** compact corresponding option comparison; no permanent Anvil side panel.
- **Verified shop open:** one feasible next item or optional full-build boots replacement, expandable details; no permanent six-item inventory list or debug HUD.
- **Normal combat/loading/postgame:** mostly hidden, diagnostic controls outside game. Optional scoreboard threat summary only when independently verified, not permanently.
- **Priority:** proven option-selection popup over shop advice; if simultaneous/conflicting evidence is unresolved, abstain. No click/typing during combat; keep client click-through and no obstruction of League HUD.
- Controls for style, transparency, positions, hotkeys, diagnostics and opt-in OCR remain in desktop Settings.

This behavior is inspired by the user's historical screenshot-based UX audit (`docs/audits/UX_AUDIT_SOURCE_NOTES_2026-11-23.md`); it is a **design requirement**, not a claim of native acceptance.

## 5. Acceptance and implementation sequencing

1. **Audit first:** Claude independent read-only review of actual baseline and existing tests, root-cause candidates separated from demonstrated bugs.
2. **#84 score data/rank:** enumerate current patch roster and rarity, modelled/unknown coverage and lineage, identify ranking signal and meaningful ties; calibrate by legally sourced independent data and holdouts; check Riot, no grade promotion before proof. Propose test-first pure rank engine with deterministic change triggers only after evidence.
3. **#49 full-build/shop:** prove boot swap, actual Mayhem eligibility and full inventory; no unreachable item.
4. **#82/#85/#86 Anvil/augment popup:** permitted independently verified presence/absence, 3/4 physical mapping, OCR title/attribute, chosen ID and hidden-after-choice; real Windows custom Mayhem acceptance needed.
5. **D6–D11 UI/release:** actual native Settings, focus, click-through, opacity, shop detection, installer and compliance gates, no release from Python/JS CI alone.

Use **RED→GREEN**, small stacked draft PRs, exact final code+docs SHA Windows Actions, never merge or edit `main` without explicit user permission. The repository is intentionally PUBLIC: no player identifiers, screenshots, raw OCR, private paths/logs, credentials, model binaries or unlicensed copied data.
