# ARAM Oracle — historical UX audit source notes (privacy-safe)

**Source:** Project-supplied Portuguese text `Audita overlays de jogo.txt`, a screenshot-based UX audit originally discussing the state of the overlay at that time. **This is a faithful, condensed text-only record of its design recommendations, not a new code audit.** The source included render-only media widgets, third-party comparison references and screenshot descriptions; do **not** copy its private game screenshots or unsupported source-link placeholders into the PUBLIC repository. No player identities or private OCR data are included.

## Core finding

The historic screenshot showed an overlay organized by available *features* rather than by the user's decision. A visible three-card augment selection was given less prominence than full build, configuration and enemy panels; the OCR panel said `NO OCR` despite cards being present. The audit's governing principle: **right information, right moment, right place, minimal duration**. These are historical observations; confirm which have been fixed in the live #103 branch.

## Context rule and priority

| Independently established state | Minimal intended content | Hide/stop rule |
| --- | --- | --- |
| Verified champion select | Candidate champion fit/ranking and short explanation | Leave champion select |
| Verified augment selection | Cards in true positions, contextual rating, short reason | Verified close/expiry/supersession |
| Verified purchased Stat Anvil popup (later product addition) | Actual stat choices, source-bound score and brief recommendation | Verified popup close/epoch/match change |
| Verified shop open | Single next *eligible* purchase or optional confirmed boots/MS swap, details on demand | Verified shop close |
| Verified scoreboard | Optional enemy context, no game-long panel | Leave scoreboard |
| Combat/loading/death without proven relevant decision | Hide unnecessary guidance | — |
| Postgame | Desktop summary, not persistent combat HUD | — |

**Priority:** a verified augment/Anvil choice before shop guidance, then optional scoreboard, then no panel. A dead character or gold amount does **not** establish that the shop is open. Contradictory/weak evidence should abstain rather than show unrelated/stale advice.

## UX issues to re-audit against current source

1. Overlay should not repeat native champion name, clock, gold or debug connection diagnostics over vital League HUD; verify collision-free placement, scale/opacity and 1080p/1440p/DPI/Alt+Tab handling.
2. One compact augment/Anvil decision panel, not simultaneous OCR technical panels, builds, enemy lists and multiple alternative build paths. Reroll controls must remain accessible; cards should disappear on actual close and update only changed individual reroll positions.
3. A single adaptive build, avoiding unreachable/duplicated/exclusive items and unverified enemy stats. Show next action contextually; full recipe/alternatives/threat explanations only when expanded. When full build, preserve meaningful optional boots swap and Anvil advice.
4. Move build strategy, OCR technical settings, diagnostics, hotkeys, opacity, visibility rules and feedback into the **desktop app**, not interactive controls over the game. Preserve click-through/focus and a quiet manual recovery affordance.
5. Visual decision timing is a functional correctness problem: independent presence/absence of offer, shop or scoreboard; fresh epoch; uncertainty and no wrong physical mapping. No invented confidence, no unstable flicker and no permanently stale recommendation.
6. Source/legal/compliance: the historic comparison mentioned OP.GG Desktop, Blitz, Hexgate, DPM.LOL, Mobalytics and Invade as product references; **do not copy protected layouts/assets or assume their behavior or Riot approval is current without checking their up-to-date sources**. Review Riot developer policy before shipping live dynamic decisions.

## Original audit limitations

The source explicitly said it was a screenshot/research audit and **did not modify source code or validate behavior in the repository**. Third-party product assertions and policy interpretations require current, independent checking. This summary preserves its recommendations without treating it as a regression result. Refer separately to `docs/PLAYTEST_FINDINGS_2026-11-20.md`, `docs/audits/F0_DIAGNOSIS_2026-11-22.md` and issue #82/#84/#85/#86 for directly tracked observed failures and exact provenance.
