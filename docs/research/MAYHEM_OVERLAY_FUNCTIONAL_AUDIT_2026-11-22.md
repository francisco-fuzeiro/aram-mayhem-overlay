# Mayhem Overlay functional audit — independent design research (2026-11-22)

> **Research only. No imported source, no translated algorithms, no copied assets, no new runtime behaviour.**
> This is a source-inspection map, **not** proof that the upstream works correctly in real League matches. Use alongside [the separate cross-project reference inventory](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/blob/docs/open-source-feature-map-2026-11-20/docs/OPEN_SOURCE_FEATURE_MAP_2026-11-20.md) if/when that separate research PR is integrated, the [functional recovery plan](../plans/ARAM_FUNCTIONAL_RECOVERY_2026-11-22.md), and [TODO](../TODO.md).

## Scope, rights, evidence

- Upstream inspected: [zp96-cmd/mayhem-overlay](https://github.com/zp96-cmd/mayhem-overlay), on 2026-11-22. Its `package.json` declares **MIT** (reported version `0.3.51`); no root `LICENSE` file was retrievable at the inspected default branch. **No source reuse is authorized by this audit**; verify exact current rights, any file-specific notices and third-party dependencies if that changes.
- Distinguish [ItzStorDz/mayhem-advisor](https://github.com/ItzStorDz/mayhem-advisor), documented separately as **All Rights Reserved**, from this similarly named project. Their rights are not interchangeable.
- Read-only evidence: upstream README and selected implementation files listed below. These are **technical observations and functional abstractions**, not instructions to port their expressions, code, UI or scoring formula.
- Our project is deliberately **PUBLIC** per `AGENTS.md`. This audit contains no screenshots, player names, client paths, logs, credentials or scraped gameplay datasets.
- **Unverified:** upstream app execution, real-world OCR recall/precision, Windows focus/click-through behaviour, data-service licenses/ToS, external sample correctness, item purchase legality and Riot approval. Do not turn observed code paths into PASS claims.
- **Product policy:** retain our read-only/opt-in principles, bounded 0.0–10.0 original contextual ratings with confidence and provenance; do not show augment win rates or proxy them through another scale; no automatic gameplay inputs.

### Source index (upstream files observed)

| Source | Observed responsibility | Inspected blob SHA |
| --- | --- | --- |
| [README.md](https://github.com/zp96-cmd/mayhem-overlay/blob/main/README.md) | User-visible functions, fallback controls, installer/updates | `b7f756b912ed672b92a07efb98399f08d9292014` |
| [package.json](https://github.com/zp96-cmd/mayhem-overlay/blob/main/package.json) | Electron packaging, declared MIT metadata, dependencies | `e13ea6cd2435be0e1f45fac7008d35410baf25a0` |
| [src/main/main.js](https://github.com/zp96-cmd/mayhem-overlay/blob/main/src/main/main.js) | Phase orchestration, transparent windows, offer watcher, tray and update flow | `92dedb4d642941aaab39a445ca668c3862023318` |
| [src/main/ocr.js](https://github.com/zp96-cmd/mayhem-overlay/blob/main/src/main/ocr.js) | Local screen capture and OCR pipeline | `500c09b84699997166582a4f684c524268cb3e50` |
| [src/main/ocr-match.js](https://github.com/zp96-cmd/mayhem-overlay/blob/main/src/main/ocr-match.js) | Closed-vocabulary fuzzy name matching | `c80e51dcfb9831a89e31e6098bb9c39da19b8ea6` |
| [src/main/liveclient.js](https://github.com/zp96-cmd/mayhem-overlay/blob/main/src/main/liveclient.js) | In-game LCDA polling and player snapshot | `70344652d6fb61894ac8f48fe15414fb35fa4590` |
| [src/main/lcu.js](https://github.com/zp96-cmd/mayhem-overlay/blob/main/src/main/lcu.js) | Local LCU phases, champion select and match history | `bbf91749d08c61202f9862632d32529d96ef6140` |
| [src/main/history.js](https://github.com/zp96-cmd/mayhem-overlay/blob/main/src/main/history.js) | Match import and saved-build enrichment | `d51cc26dcc013481af3f42b1e16c7a20f07bafb8` |
| [src/main/aramgg.js](https://github.com/zp96-cmd/mayhem-overlay/blob/main/src/main/aramgg.js) | Community build variants, cached provider parsing | `a53f1a9aa68db67971e1ab347b09009893164a09` |
| [src/main/aramkit.js](https://github.com/zp96-cmd/mayhem-overlay/blob/main/src/main/aramkit.js) | Versioned external champion/augment statistics | `ff1215728e9268f9be67a976111611f9d67ce3ec` |
| [src/main/fetch-data-core.js](https://github.com/zp96-cmd/mayhem-overlay/blob/main/src/main/fetch-data-core.js) | Patch data acquisition and normalization | `eaf41d127f1b4ce40795b076627ac0b545cbf46f` |
| [src/main/champselect.js](https://github.com/zp96-cmd/mayhem-overlay/blob/main/src/main/champselect.js) | Champion bench/team indicator placement | `96eb5245cd344262aa9bca554f6b4d02d1ea28ba` |
| [src/main/layout.js](https://github.com/zp96-cmd/mayhem-overlay/blob/main/src/main/layout.js) | Position presets and bounds validation | `e36cbbb8607eadb396e3b430e774e1184ee2432a` |
| [src/main/store.js](https://github.com/zp96-cmd/mayhem-overlay/blob/main/src/main/store.js) | Local state persistence, backup/recovery | `3000196972617aa13f8acc3a5ea3a7e3ba98434b` |
| [src/renderer/app.js](https://github.com/zp96-cmd/mayhem-overlay/blob/main/src/renderer/app.js) | Augment display, scoring signals, reroll/priority, item paths, interaction | `f331fe254cb8f7e6e849d5b1a213c43113f3ad13` |
| [src/renderer/prep.js](https://github.com/zp96-cmd/mayhem-overlay/blob/main/src/renderer/prep.js) | Champion comparison and pre-game companion | `0bcc163ef8dedcda74a87962b3b959a377fab2c9` |

## Feature-by-feature behavioural and mechanism audit

**Legend:** `OBSERVED` means the listed source supports a mechanism; `CLAIMED` is README-only; `DESIGN` is an independent proposal for ARAM Oracle, not upstream behaviour. None means native-verified.

### 01 — League phase and live snapshot
- **OBSERVED:** an LCU reader resolves the local client and checks the gameflow phase; a separate LCDA poller reads the active champion, items, gold, level, deaths and player-visible game data while playing. The main process dispatches renderer updates and uses game transitions to reset transient state.
- **Limit:** an in-game level breakpoint or death is a hint that an augment *may become available*, not proof the cards are visible. The public LCDA should not be assumed to expose a `picked_augment` event.
- **DESIGN:** preserve our typed LCU/LCDA adapters, source freshness and game/match identity. Use **verified visual offer evidence**, not level/death alone; uncertain state renders nothing. Existing F0/F1/F2 contracts take precedence.

### 02 — Champion-select comparison and second-screen preparation
- **OBSERVED:** LCU champion-select session supplies local-player cell, bench and team champions; the companion follows champion swaps and allows browsing a different champion then returning to the live pick. A separate transparent layer positions badges against measured client geometry.
- **Limit:** upstream displays community win-rate measures and uses coordinate assumptions; neither establishes correct self identity across all swaps/DPI. We already had a user-observed wrong-current-champion defect.
- **DESIGN:** keep our **original 0–10 champion comparison** and F1 verified-local-cell/revision fencing; desktop may show candidates, team fit, sources and confidence. Never automate swaps; do not imitate its badge artwork.

### 03 — Augment catalog and source refresh
- **OBSERVED:** CommunityDragon/wiki text and external community datasets are assembled into local versioned JSON. Bundled data supports a fresh/offline install; patch checks can refresh the local catalog.
- **Limit:** raw catalog entries, disabled/mode variants and third-party datasets require independent provenance, license, mode availability and version checks. A patch fetch failure must not imply fresh data.
- **DESIGN:** our own canonical ID and source ledger; patch-stamped stale/unavailable status; verified item/augment eligibility; avoid scraping HTML or Cloudflare-gated endpoints merely because source code shows it.

### 04 — Local offer OCR and three-card recognition
- **OBSERVED:** screen image -> region crop -> local Tesseract -> text normalization/fuzzy matching against a fixed augment vocabulary -> line/location filtering. Adjacent OCR lines may be considered for long names; OCR bounding boxes support on-card badges. A manual scan/search fallback is offered.
- **Limit:** source matching can rank names independently and return ambiguous/incomplete results; one shared crop and score order do **not** guarantee stable physical left/centre/right identity. It can save a debug screenshot automatically, which is unsuitable for our public-repo/private-capture policy.
- **DESIGN:** keep **our** verified client bounds, per-card title crops, physical L/C/R identities, strict 90/8 matching, temporal confirmation, epoch fences, redacted diagnostics and safe abstention. Existing Tesseract default and experimental v4 remain unchanged. Compare ideas, **not** thresholds or matching code.

### 05 — Offer lifecycle / appearance / disappearance
- **OBSERVED:** a periodic watcher scans while an offer is expected or visible; it uses repeated missing reads to clear on-screen badges. Pending state can be initiated by level breakpoints and accelerated around death.
- **Limit:** absence of an OCR match is not proof an offer ended (occlusion, animation, capture loss, focus change). A missing read cannot safely confirm a pick.
- **DESIGN:** independent visual presence/absence proof and a closed fail-safe state machine; preserve match+offer+epoch gates and do not regress C4/F2. Keep the explicit independent absence-cue blocker open until evidence exists.

### 06 — Single-card reroll
- **OBSERVED:** cursor activity near a configurable reroll region can trigger a quicker re-scan; the watcher also checks for changed recognized names.
- **Limit:** pointer movement is **not** a confirmed reroll, and an unchanged/reordered OCR result is not a reliable slot mapping. Client geometry/resolution and transition animation complicate the observation.
- **DESIGN:** reroll = **evidence of a changed physical slot over stable captures**, recompute all three candidates in the same current offer epoch; never infer a button press from cursor movement.

### 07 — Determining the chosen augment
- **OBSERVED:** upstream may attribute a picked augment using the last card region visited by the cursor when the offer subsequently disappears; manual `pick` remains available. The selected list affects downstream suggestions.
- **Critical distinction:** this is **probabilistic attribution**, not an authoritative chosen-ID read. Hover != click and disappearance != source proof. Never turn this into silent confirmed state.
- **DESIGN:** current #86/#87 provider-neutral exact-once accepted-ID work remains disabled until an authorized real source; alternatively allow explicit user confirmation **outside high-pressure play**. Unknown picked ID must remain unknown, never fabricated.

### 08 — Augment comparison, synergy and reroll advice
- **OBSERVED:** personal ratings, broad champion archetypes, previously picked categories, external champion-specific samples/combination references and unseen-offer candidates contribute to its recommendations. A visible priority list highlights promising remaining options. It models a potential future draw when suggesting reroll.
- **Limit:** inspectable upstream behaviour is **not proof of statistical validity**; the assumption that an offered augment cannot recur must be verified for the exact mode/patch. The source displays augment win rates, including on in-game badges; this conflicts with the Riot-policy caution documented for ARAM Oracle. Do not copy its scoring/reroll expressions.
- **DESIGN:** keep our original evidence-confident 40% performance / 35% synergy / 25% context framework **only where policy permits the specific signal**, plus champion/owned augments/items/enemy context, provenance and explainable `0.0–10.0` scores. A reroll indicator should say `uncertain` when the pool/offer evidence is incomplete; do not promise future augments.

### 09 — In-game augment badges and priority UI
- **OBSERVED:** a separate non-focusable transparent window renders short on-card comparisons; optional left/right panels show combos and augments not yet offered. Windows can be re-positioned independently.
- **Limit:** rendering win rates and several simultaneous panels adds visual load and potentially violates policy. Badges relying on OCR location inherit OCR/DPI error.
- **DESIGN:** **just-in-time** compact rating anchored to *verified* cards, one short reason, no raw WR, no persistent priority lists. Desktop-only expandable analysis; offer > verified shop > optional scoreboard > hidden, following D6/D7/F4.

### 10 — Adaptive item/build suggestions
- **OBSERVED:** the renderer merges several candidate paths: own winning-match consensus, saved builds and external community archetypes. It considers current owned item IDs and upgrade ancestry, a boots display preference and affordability to highlight a next item. Some candidates are hidden by user action. An in-game strip may show **multiple rows simultaneously** throughout the match.
- **Limit:** a filtered ordered list is not proof of legal, affordable *purchase action* or optimal stats for this match. External HTML can change; displayed game counts in some fallback parsing are ordering proxies, not measured samples. Multiple persistent paths violate our contextual UX objective.
- **DESIGN:** show **one verified, feasible next purchase only while the shop is independently confirmed open**, with optional situational alternative and expanded reasoning. Check patch/mode purchase pool, price after owned components, slots, mutually exclusive items, transformations, inventory visibility, boots-to-move-speed replacement and enemy threats. Fail closed if source facts are missing (F3/D8).

### 11 — Enemy team and saved other-player builds
- **OBSERVED:** LCDA player items are visible in the companion. Users can save an observed build during play and later enrich that saved entry with post-game augment/final-item details from match history, if matching evidence is available.
- **Limit:** another player's augments are not assumed visible during the match; approximate post-game identity matching can be wrong. Player identifiers should not be copied into diagnostics or public fixtures.
- **DESIGN:** typed visible-enemy/ally threat profiles and explainable counter-item recommendations. Saved examples must be opt-in, privacy-minimized, explicitly labeled as observed vs historically matched, never automatically promoted as the optimal build.

### 12 — Own history and preferences
- **OBSERVED:** recent Mayhem matches are imported via local LCU into JSON stores; records include result, champion, augments and items. Picked/seen augments and hidden item preferences can survive an overlay restart during the same match. Storage attempts backup and recovery after corrupt files.
- **Limit:** local history is convenience data, not independent community evidence; small sample sizes need shrinkage. Clock/champion matching alone is not a definitive match identity.
- **DESIGN:** preserve our existing opt-in SQLite history and authorized own-data imports. Distinguish verified picked augments from manually recorded/uncertain ones, use match-safe identity, user consent, retention policy and safe backups; never introduce shared identifiable player history by default.

### 13 — Desktop companion and layout editor
- **OBSERVED:** separate companion window offers overview, champion prep, saved builds and a preview where panels can be moved and positions saved. It remembers per-window placement and has tray access.
- **DESIGN:** map to existing PyQt/FastAPI desktop settings architecture. Preview must be non-live until explicit Apply; allow reset, safe screen bounds, DPI and multiple monitors. All game-time strategy choices belong **outside gameplay** (D4/D5, D6).

### 14 — Click-through, hotkeys, fallback control
- **OBSERVED:** Electron creates dedicated transparent/non-focusable overlay windows; tray and shortcuts toggle visibility/click-through. Because global hotkeys may fail, a small scan button offers a fallback.
- **Limit:** a permanent scan button or mouse-interactive panel can obstruct the game or steal attention. Source code is not a Windows/League focus test.
- **DESIGN:** no mouse capture during combat; toggles and fallback outside high-pressure moments; optional manual trigger only, explicit opt-in diagnostics and no source-confidence claims without native Alt+Tab/focus tests (D1/D4/F4).

### 15 — Installer, patch and binary updates
- **OBSERVED:** Electron Builder emits a Windows installer; `electron-updater` uses GitHub Releases; installed app data persists across updates. The updater attempts to avoid applying binary changes mid-session; patch data updates independently. A single-instance lock and mocked sessions aid startup/testing.
- **Limit:** updater/install behaviour was inspected, **not executed**. Upstream Electron packaging is not a drop-in match for our Python/PyQt app; avoid silent installs, unreviewed model downloads or interrupting League.
- **DESIGN:** keep our D9 → D10 → D11 release gates: packaged standalone executable, intuitive Windows installer/uninstaller, explicit user-data choices, permissioned/signed update policy, version and integrity validation, rollback, no update during gameplay; no release until license/Riot/privacy and native acceptance pass.

## Best independent improvements to prioritize

| Priority | Original observation / proposed ARAM Oracle advantage | Existing gate to respect |
| --- | --- | --- |
| P0 | Reliable **self champion** and bench comparison, not merely a stat pill | F1.3 native acceptance still open |
| P0 | Verified **physical L/C/R** offers, rerolls and absence; never turn cursor hover into a confirmed pick | F2, C4 independent absence, #86/#87 chosen-source contract |
| P0 | Deterministic **source-to-reason** item decision and unknown-context abstention | F3; no unsupported shop buyability |
| P1 | Truly contextual **shop-only** next purchase and offer-only augment badges | F4 / D6–D8 only after F1–F3 gates |
| P1 | Persistent, versioned settings and controllable pre-game layout, no game-time dropdowns | Existing desktop architecture and D4/D5 |
| P2 | Opt-in personal build library, safe post-match enrichment and annotated provenance | Separate privacy and consent checks |
| P2 | Patch-aware catalogs, safe fallback and local data durability | Existing data provenance / D11 |
| P3 | Polished installation and idle-safe updates | D9–D11 after functional/native/policy acceptance |

## Risks explicitly NOT adopted from upstream

1. In-game presentation of augment win rates or a number that is effectively a relabeled win rate.
2. Inferring chosen augments from cursor/hover plus OCR silence; infer no actual game input.
3. Trusting fuzzy text order as physical card order or accepting partially verified cards.
4. Assuming death, gold, or level breakpoint proves a visible offer or open shop.
5. Persistently occupying the game HUD with multiple build variants/priority panels.
6. Treating unverified scraped stats, synthetic fallback counts, third-party copyright or unreliable HTTP parsing as measured evidence.
7. Auto-saving private full-screen debug images or leaking other player identifiers.
8. Copying/porting external UI, source, formulas, assets, text or proprietary libraries.

## Actionable follow-up / acceptance criteria

- **MO-REF-01 (research complete):** source-to-feature map documented without reuse.
- **MO-REF-02 (open):** compare our F2 offer/slot/absence/selection contracts against this risk map; add *original* negative tests for cursor hover, OCR blank, Alt+Tab, one-card reroll and old epochs before changing behaviour.
- **MO-REF-03 (open):** compare F3 against independent buyability/owned-component/boots/full-slot tests; forbid uncertain item recommendation.
- **MO-REF-04 (open):** after F1–F3 gates, D6/D7/D8 acceptance: an offer shows three grounded compact ratings only; a verified shop shows one next purchase only; combat shows nothing by default.
- **MO-REF-05 (open):** D9–D11 external-installation comparison, with clean Windows smoke test, rollback, permissions and source licensing before public release.
- **MO-REF-06 (open):** review Riot third-party policy and each proposed data-provider license/ToS **before** enabling empirical live scores, ingesting third-party data, or distributing a release.

### Test and change status

**No tests run** for this documentation-only research. Upstream program not installed or exercised. No ARAM Oracle runtime/score/OCR/UI code changed; no new external dependency, scraped dataset, player data or asset added. The **source inspection** is complete, but all downstream product gates above remain unverified/open until their existing independent tests/PRs pass.
