# Mayhem Advisor — functional and architectural reference audit
**Date:** 2026-11-22. **Status:** documentation research only, no source reuse or runtime implementation.

This report is a **clean-room-inspired, high-level feature study**, not an implementation guide or a port of upstream intellectual property. It compares publicly stated capabilities and high-level verified component responsibilities with the existing ARAM Oracle requirements and evidence gates. Read alongside the [Mayhem Overlay functional audit](MAYHEM_OVERLAY_FUNCTIONAL_AUDIT_2026-11-22.md), the [TODO](../TODO.md), [implementation phases](../IMPLEMENTATION_PHASES.md), and [project state](../PROJECT_STATE.md).

## 1. Rights, sources, and verification labels

**Upstream:** [ItzStorDz/mayhem-advisor](https://github.com/ItzStorDz/mayhem-advisor) (public source). The upstream [LICENSE](https://github.com/ItzStorDz/mayhem-advisor/blob/main/LICENSE) explicitly states **copyright (c) 2026 ItzStorDz, ALL RIGHTS RESERVED**. It permits reading and personal, noncommercial use of official installers; it does **not** permit copying, modification, translation, derivative works or redistribution of its code, interface, text, images or icons without written permission. Do not copy or translate its functions, ranking mathematics, datasets, layouts, wording or assets. Its repository being publicly readable is not an open-source reuse license.

**Evidence hierarchy:**
- **DOCUMENTED:** explicitly advertised by the current upstream README, privacy notice or credits; not independently runtime-tested.
- **STRUCTURE OBSERVED:** selected source files confirm the presence and responsibility of a subsystem. Reading the source is permitted by LICENSE; only public-domain *functional ideas* and independently phrased conceptual observations are recorded here. No source implementation is reproduced.
- **PROPOSED:** an original ARAM Oracle product decision or acceptance test, not a claim about upstream behavior.
- **UNKNOWN:** cannot be proven from the inspected public artifacts; no inference of PASS.

**External policy:** The [official Riot LoL policy](https://developer.riotgames.com/docs/lol) currently prohibits showing augment win rates, game-session information previously unknown to the player and apps dictating decisions; static pregaming overlays and player-history tools are examples of potentially permitted categories. This research does not establish that Mayhem Advisor (or any ARAM Oracle feature) has Riot approval. A numerically transformed win-rate-based signal is **not automatically compliant**; require explicit policy review before release.

**Third-party datasets:** The upstream credits identify CommunityDragon, MayhemMeta, ARAMKit and AramHex. The upstream [data notices](https://github.com/ItzStorDz/mayhem-advisor/blob/main/datos/CREDITOS.txt) explicitly identify **AramHex as CC BY-NC 4.0**; no commercial reuse rights should be presumed. The upstream application license does not sublicense third-party datasets, assets, fonts or models.

### Public sources inspected

| Source | Evidence type | File SHA (read 2026-11-22) |
| --- | --- | --- |
| [README.md](https://github.com/ItzStorDz/mayhem-advisor/blob/main/README.md) | DOCUMENTED feature list, components, installation | 4dc29b104e840e43857edc96032225a5807d0547 |
| [LICENSE](https://github.com/ItzStorDz/mayhem-advisor/blob/main/LICENSE) | RESTRICTION: all rights reserved | ce26d56e0137dbc7f3da5fbd0175e394c905c330 |
| [PRIVACY.md](https://github.com/ItzStorDz/mayhem-advisor/blob/main/PRIVACY.md) | DOCUMENTED opt-out telemetry, retention and feedback | 6281558e4959840a3d2374b97b6e49cb95718cac |
| [CREDITOS.md](https://github.com/ItzStorDz/mayhem-advisor/blob/main/CREDITOS.md) | DOCUMENTED game/community-data provenance | 31b314810572ff90ca003f47fb539dc9e3c7ef95 |
| [datos/CREDITOS.txt](https://github.com/ItzStorDz/mayhem-advisor/blob/main/datos/CREDITOS.txt) | DOCUMENTED external datasets and CC BY-NC condition | a54cf77230ae20dbe12c5a4690dd7a9e08ad9758 |
| [src/Core/AugmentScore.cs](https://github.com/ItzStorDz/mayhem-advisor/blob/main/src/Core/AugmentScore.cs) | STRUCTURE OBSERVED: augment rating and evidence-confidence subsystem | 6e9ea8d2e69e3a863cc764d932fda8d888d449c8 |
| [src/Core/AugmentBuilds.cs](https://github.com/ItzStorDz/mayhem-advisor/blob/main/src/Core/AugmentBuilds.cs) | STRUCTURE OBSERVED: build-style data and augment effects | 59454b5922315043a3b2ef70c8072dfa8e0e1b56 |
| [src/Core/MayhemBuilds.cs](https://github.com/ItzStorDz/mayhem-advisor/blob/main/src/Core/MayhemBuilds.cs) | STRUCTURE OBSERVED: per-champion build statistics | 6bfcd40e58508255368c4bcee8b77051b9e76ad4 |
| [src/Core/AugmentMatcher.cs](https://github.com/ItzStorDz/mayhem-advisor/blob/main/src/Core/AugmentMatcher.cs) | STRUCTURE OBSERVED: recognized text to card-name correspondence | dc085640f8c4db24919bba93856e27b95ca4aa98 |
| [src/Overlay/ScreenReader.cs](https://github.com/ItzStorDz/mayhem-advisor/blob/main/src/Overlay/ScreenReader.cs) | STRUCTURE OBSERVED: Windows local screen/OCR adapter | 57fcf6b2b740265918605d38f49e1ad3107796bb |
| [src/Overlay/ElectronBridge.cs](https://github.com/ItzStorDz/mayhem-advisor/blob/main/src/Overlay/ElectronBridge.cs) | STRUCTURE OBSERVED: separate renderer communication/lifecycle | f73cdba53dc38d395ed148de04bc3ad5105d3afa |
| [overlay-electron/main.js](https://github.com/ItzStorDz/mayhem-advisor/blob/main/overlay-electron/main.js) | STRUCTURE OBSERVED: game-following transparent window | 50968251b7d64bee04bd25b4ed286b49e9dc6f76 |
| [src/Overlay/App.ChampSelect.cs](https://github.com/ItzStorDz/mayhem-advisor/blob/main/src/Overlay/App.ChampSelect.cs) | STRUCTURE OBSERVED: champion-select companion integration | 9befae7e489d7b4c3368ef7b3f91194935aef200 |
| [src/Core/GameReports.cs](https://github.com/ItzStorDz/mayhem-advisor/blob/main/src/Core/GameReports.cs) | STRUCTURE OBSERVED: postgame report | e89e71df27f6f579de596b816c341f50a35a2f9d |
| [src/Core/GameTips.cs](https://github.com/ItzStorDz/mayhem-advisor/blob/main/src/Core/GameTips.cs) | STRUCTURE OBSERVED: evidence-backed postgame guidance | df3d25d33321db9462a24c00671120f510feb4e1 |
| [src/Core/Stats.cs](https://github.com/ItzStorDz/mayhem-advisor/blob/main/src/Core/Stats.cs) | STRUCTURE OBSERVED: history and statistical record types | a7c0baa411637868a93ccd9f454bd98e0356311a |
| [src/Overlay/Cloud.cs](https://github.com/ItzStorDz/mayhem-advisor/blob/main/src/Overlay/Cloud.cs) | STRUCTURE OBSERVED: optional remote-data pipeline | d4bc7ab1ab204ff7919395a7cd87321db3c6f4c0 |
| [src/Overlay/App.Feedback.cs](https://github.com/ItzStorDz/mayhem-advisor/blob/main/src/Overlay/App.Feedback.cs) | STRUCTURE OBSERVED: voluntary feedback | 4e4d704d8428ca9d7431bea5bfb30d3bfea503b0 |
| [src/Overlay/Settings.cs](https://github.com/ItzStorDz/mayhem-advisor/blob/main/src/Overlay/Settings.cs) | STRUCTURE OBSERVED: preferences | ebc676f87de9ec1395b2e780ed98147a5ace7fc1 |
| [instalador/README-en.txt](https://github.com/ItzStorDz/mayhem-advisor/blob/main/instalador/README-en.txt) | DOCUMENTED user onboarding | 83dc210510e6b22e304220a87cfbbcba47f66ca5 |

Only the referenced public files and their visible portions were inspected. No executable, OCR screenshot, bundled private dataset, third-party API or game session was run.

## 2. Functional mechanism map (conceptual, not source algorithms)

### 01 — Product split: engine, desktop and in-game renderer
- **DOCUMENTED:** the repository separates a C#/.NET 9 core (game records and guidance), a WPF + WebView2 desktop UI, an Electron in-game renderer, tools for patch data and an Inno Setup installer.
- **STRUCTURE OBSERVED:** the Windows companion and overlay communicate via an interprocess channel, while the separately managed overlay visually follows the game window.
- **PROPOSED:** retain **our already approved** Python/FastAPI/PyQt6 desktop and backend. Keep a single source of scoring truth with a simple read-only rendering contract; do **not** import another runtime or redesign our architecture just to resemble this competitor.
- **Acceptance:** one reliable application owner, no unplanned duplicate service, safe focus and restart; actual Windows tests required.

### 02 — Game phase, observable inputs and confidence
- **DOCUMENTED:** game facts originate from the local League Client API and the Live Client Data API; the app says it does not inspect game memory or inject into League.
- **PROPOSED:** continue our LCU/LCDA source contract and preserve explicit player visibility, freshness, match/offer identity and fallback. An API-visible fact should remain distinguishable from an OCR guess or a modeled enemy profile.
- **UNKNOWN:** third-party documentation is not proof of our native source accuracy or permissions.

### 03 — Automatic augment-card text recognition
- **DOCUMENTED:** reads augment cards from the screen using built-in Windows OCR rather than memory access.
- **STRUCTURE OBSERVED:** screen-reader and augment-name matching components exist, with a separate rendering layer for cards.
- **PROPOSED:** our physical L/C/R title-specific recognition, strict catalog mapping, multiple independent frames, negative/dialogue evidence, and fail-closed unknown cards remain authoritative. Windows OCR is a technology to benchmark independently only if required; do not port upstream matching code, heuristics or UI.
- **Acceptance:** correct title-to-position mapping, single-card rerolls, no false accepted IDs, safe Alt+Tab; user native proof still open.

### 04 — Per-card rating and suggested build style
- **DOCUMENTED:** offers visible cards a 0–100 rating, a tier/grade and a likely build archetype.
- **STRUCTURE OBSERVED:** a rating/evidence subsystem exists. Its high-level documentation ties the rating to performance-related evidence, even though the README says the *display* is not a raw augment win rate. The absence of a displayed percentage is **not** proof the derived signal satisfies Riot rules.
- **PROPOSED:** our independently designed 0.0–10.0 score must have explainable champion, already-picked augments, current items, matchup, patch/data provenance and confidence. Keep empirical augment evidence disabled pending explicit compliance resolution. Show short reasons, not competitor badge design.
- **Acceptance:** no raw win-rate exposure, no hidden win-rate proxy, no unsupported precision or decision-forcing.

### 05 — Build archetypes change with the augments
- **DOCUMENTED:** chosen augments affect the recommended build type (e.g. damage-oriented vs survival/support archetypes), rather than blindly locking a pre-game item list.
- **STRUCTURE OBSERVED:** per-augment build-style and per-champion build-statistic data components are separate from general match history.
- **PROPOSED:** compare our owned-augment/effects model with **original** explicit synergy, counter and exclusivity rules. If the selected augment is unconfirmed, label build assumptions rather than silently treating it as verified.
- **Acceptance:** deterministic tests where a **verified** augment alters eligible build choices for a reason; unverified selection does not.

### 06 — Enemy team pressure and adaptive counters
- **DOCUMENTED:** build guidance considers opponents' itemization; it can flag a strong enemy and describe that champion's damage type.
- **PROPOSED:** keep our original team-threat profiles, differentiate observed enemy items from predicted damage composition and clearly distinguish qualitative estimates from actual measured percentages. Explain the specific defensive, armor-penetration or anti-sustain reason, **only** if data supports it.
- **Acceptance:** a visible enemy change causes a justified, legal choice; missing source or uncertainty causes downgrade/abstention instead of fake exact percentages.

### 07 — Next item and purchase explanation
- **DOCUMENTED:** in-game panel presents what to buy and why, while the overall path adapts to the game.
- **PROPOSED:** our **shop-verified-only** next feasible purchase plus optional alternative and expandable explanation. Preserve patch-verified shop pool, component prices, ownership/evolutions, six slots, boots replacement, uniqueness and alternative mobility.
- **Acceptance:** no item excluded by mode/patch, quest-only or otherwise unbuyable; no persistent build instruction occupying combat HUD. Existing F3 and D8 are the implementation owners.

### 08 — Game shop item-set export
- **DOCUMENTED:** a recommended item set can be sent to the League shop, in addition to displaying a panel.
- **STRUCTURE OBSERVED:** champion-select integration is represented separately from the scoring core.
- **PROPOSED:** **research only** whether a documented/permitted LCU workflow can stage an **opt-in, reversible** suggestion set without removing the player's decision, using valid item identifiers. Do not copy the upstream request mechanism or implement writes during this audit.
- **Acceptance:** no unsupported client writes, no gameplay purchase automation, no corruption of existing custom sets, no implementation before policy and native authorization.

### 09 — Champion select: pre-game guidance
- **DOCUMENTED:** provides augment/build preparation for the current champion. Optional queue auto-accept is listed.
- **PROPOSED:** strengthen our original 0–10 champion comparison, bench/current self identity, allied team fit and honest candidate confidence; pre-game configuration belongs in desktop Settings. Do not adopt auto-accept or auto-swap/auto-pick as part of the current read-only ARAM Oracle contract.
- **Acceptance:** F1.3 native self vs bench and swap test; no stale selection marker, no hidden information.

### 10 — Post-game explanation and next-game learning
- **DOCUMENTED:** after each match the app offers a score, ranking among ten players, improvement ideas and a comparison between the actual purchases and its earlier recommendation.
- **STRUCTURE OBSERVED:** a report subsystem combines local match details with a contemporaneous log of previous app advice; another component produces post-game tips.
- **PROPOSED:** **high-value new product opportunity**: an original local decision ledger recording what our app recommended, **why**, confidence, data patch, visible context/time, and whether the player followed it; show post-game review with hypothetical alternatives clearly marked, not unjustified causal claims.
- **Acceptance:** distinguish recommendation quality from simply winning/losing; never claim the unpurchased item would have won. Handle match/history gaps, stale advice, and no-data explicitly; player-local by default.

### 11 — Personal history, progress and player context
- **DOCUMENTED:** records local ARAM Mayhem games, personal win/loss and KDA trends, frequently selected champions, and match-specific summaries.
- **PROPOSED:** continue our opt-in local SQLite per-player history with patch and sample confidence, correct queue/match IDs and optional diagnostics. Distinguish facts from advice and do not claim a small personal sample predicts future performance.
- **Acceptance:** import only eligible own matches, deduplicate safely, show meaningful data coverage and errors.

### 12 — Anonymous game sharing and community feedback loop
- **DOCUMENTED:** [PRIVACY.md](https://github.com/ItzStorDz/mayhem-advisor/blob/main/PRIVACY.md) says anonymized game data plus observations/recommendations can be uploaded to the author's service for shared statistics. Sharing is **enabled by default after a notice**, with an opt-out. It describes 10 players' champion/team/results/augments/items and selected combat metrics, offered/picked cards, decisions and timestamps, as well as redacted error summaries. It states no screenshots/names are uploaded; remote feedback is a separate explicit send.
- **PROPOSED:** **do not imitate default-on collection**. ARAM Oracle should remain local-first with a separate explicit opt-in, minimization, clear retention/deletion and security review before any aggregate or telemetry server. Do not assume redaction and HMAC remove all privacy or legal risks.
- **Acceptance:** privacy threat model, consent, data contract, no sensitive raw League/UI/OCR traces in GitHub or reports, and independent opt-out/erasure tests.

### 13 — External stats, kit metadata and patch awareness
- **DOCUMENTED:** champion/item/augment metadata are tied to CommunityDragon; upstream credits mention hand-reviewed champion-kit facts and third-party Mayhem statistics. Its privacy document says it retrieves versioned statistics separately from binary updates.
- **LIMIT:** external statistics may be patch-mismatched, unreliable, licensed noncommercially or prohibited for use/display. **AramHex CC BY-NC 4.0** must not be folded into an anticipated commercial product without suitable permission. The upstream's claims do not grant rights to MayhemMeta or ARAMKit datasets.
- **PROPOSED:** patch-stamped source ledger with hashes, explicit origin and permitted-use classification, confidence suppression when missing/mismatched, and no unreviewed scraping or downloads in the installer.
- **Acceptance:** every signal traceable to a checked source, compatible rights and exact game mode/patch; fail closed for unsupported material.

### 14 — Contextual UI and attention management
- **DOCUMENTED:** moving, minimizing and resizing the in-game panel is supported; on-card recommendations coexist with a larger readout.
- **PROPOSED:** improve beyond a permanent advice panel: champion-select preparation; **three aligned augment ratings only when a verified offer exists**; **one item when shop is verified open**; no overlay during combat by default; user-invoked expansion outside urgent decisions. A compact why/uncertainty hint is preferable to opaque badges.
- **Acceptance:** no HUD obstruction, click-through and no focus capture, no false stale panels, verified shop signal (not death/gold), 1080p/1440p/DPI/Alt+Tab native testing. No copying layout/colors/UI text.

### 15 — Settings, accessibility and feedback
- **DOCUMENTED:** English/Spanish UI, player preferences, optional data sharing, feedback flow and Windows tray controls. Privacy notice describes voluntary rating/bug/idea sending and post-game prompts.
- **PROPOSED:** independent pre-game Settings for build style, overlay placement, scale, opacity, hotkeys, diagnostics and an optional feedback composer. Keep **user feedback** separate from automatic telemetry, never require clicks during combat. Make prompts dismissible, non-intrusive and disabled in sensitive moments.
- **Acceptance:** source-of-truth preferences, keyboard accessibility, no hotkey/game focus regressions, no upload without user consent.

### 16 — Installer, binary update and offline data continuity
- **DOCUMENTED:** Windows 10/11 x64 installer through GitHub Releases; the update flow checks a downloaded version, avoids restarting while League is running and says user data survives. README states a SHA-256 download verification; the installer is not yet code-signed in the inspected README.
- **PROPOSED:** use our approved PyInstaller/Inno Setup D9–D11 milestones, no mid-game install/restart, signed/integrity-checked releases, rollback, clear uninstall choices, no silent extra dependencies, safe first-run path, and tested native Qt/overlay startup. No reuse of upstream installer scripts/icons/wording.
- **Acceptance:** clean Windows VM and user's Windows smoke testing; code signing, update manifest trust and privacy/policy reviews before release.

### 17 — Testing and evidence quality
- **DOCUMENTED:** the repository describes simulated-game and English-text checks; public test-tool paths indicate several recommendation and item-scenario test suites.
- **UNKNOWN:** we did not run the app or test suites, review test outputs, reproduce OCR accuracy, validate scores, benchmark performance or confirm Riot recognition/approval.
- **PROPOSED:** keep our test-first small PR discipline and exact-SHA Windows Actions, but label source-code inspection distinct from native product acceptance. Record regressions as reproducible scenarios with independent synthetic fixtures.

## 3. Differentiation vs Mayhem Overlay and our existing work

| Theme | [Mayhem Overlay reference](MAYHEM_OVERLAY_FUNCTIONAL_AUDIT_2026-11-22.md) | Mayhem Advisor documented emphasis | ARAM Oracle independent target |
| --- | --- | --- | --- |
| OCR/cards | Screen capture, changed offers, on-card badges | Windows OCR and per-card grade/style | Proven physical L/C/R, no guessed picks, safe rerolls |
| Augment advice | Player ratings, community trends, unseen pool | Champion-specific statistical grading + build influence | Explainable context and confidence, policy-reviewed evidence |
| Builds | Own/saved/community paths shown in strips | Adaptive path, opponent-specific next-buy reasons, shop item set | One legal shop-only purchase plus optional alternate |
| Prep | Rich saved-build/bench companion and layout editor | Champion preparation and optional client convenience | Correct self/bench composite, desktop settings, no automation |
| Post-match | Own games, saved-build history | Rich game report, rank, decision retrospective and feedback | **Own recommendation audit ledger + evidence-backed improvement report** |
| Data model | Local personal history + external community references | Local plus optional contributed anonymous records | **Local-first** and opt-in privacy; legal data provenance |
| Packaging | Electron installer/self-update | .NET/WPF + Electron with installer/version integrity | Existing Python/Qt single-owner, gated package/install/update |

**Not a ranking of product quality:** none of these systems were executed or benchmarked. The evidence differs by repository; descriptions and code structure are not live performance.

## 4. Small, scoped follow-up tickets (no new implementation authorized here)

- **MA-REF-01 — DONE (research only):** primary-source feature/architecture/rights map and independent comparison documented.
- **MA-REF-02 — OPEN, Riot and score provenance:** establish whether any empirical augment feature can lawfully be displayed live; no transformed-win-rate workaround; preserve disabled experimental augment evidence.
- **MA-REF-03 — OPEN, F2/F3:** independent offer/pick/augment-to-build and enemy-context/next-purchase safety test cases. Do not duplicate already accepted fixtures.
- **MA-REF-04 — OPEN, postgame design:** draft an original local advice journal schema and user-facing evaluation criteria; leave game scoring unchanged until approved.
- **MA-REF-05 — OPEN, future shop integration:** assess read-only vs reversible item-set export mechanisms and Riot scope before coding or touching existing item sets.
- **MA-REF-06 — OPEN, data and privacy:** rights matrix for AramHex, MayhemMeta, ARAMKit, CommunityDragon; explicit local-first consent and redaction review. No external service/telemetry added by this task.
- **MA-REF-07 — OPEN, D6–D11:** incorporate UX and packaging evaluation criteria into existing contextual controller and release gates; no unreviewed architecture migration.

**Suggested order:** first close F1.3/F2/F3 native correctness and provider/Riot gates; then D6–D8 contextual UI, independently scoped postgame design and optional item-set research; installer/updates only behind D9–D11 release gates. Do not move or check off pre-existing work based on competitor research.

## 5. Explicit exclusions and status

**Never adopt by copying:** proprietary source snippets, score formulas, matching methods, item rankings, tier thresholds, UI placement, visual assets, localized wording, analytics code, installer assets or bundled datasets. Permission is required for any of those.

**Do not adopt without separate review:** inferred augment selections from weak evidence, derived win-rate proxy, precise enemy damage percentages based only on heuristics, queue auto-accept, client writes, default-on telemetry, commercial usage of noncommercial external datasets, cross-player match publication.

**Verification:** research and upstream code structure **inspected**; **no app run**; **no screenshot OCR test**; **no Windows/League native test**; **no tests run** for this documentation-only change; **no product code changed**, no new dependencies, no copied content/assets or proprietary data; no branch merge or release. Native gameplay, Riot policy and legal/data rights remain OPEN/BLOCKED as documented.
