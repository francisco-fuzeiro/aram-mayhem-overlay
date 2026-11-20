# Open-source LoL overlay feature map — 2026-11-20

**Purpose:** persist the 2026-11-20 cross-repository research requested by the user, mapped to ARAM Oracle's approved [TODO](TODO.md), [implementation phases](IMPLEMENTATION_PHASES.md), [architecture](DESKTOP_ARCHITECTURE.md), and [reuse register](REUSE_CANDIDATES.md). **This document authorizes no source import, release, or gameplay feature.**

## Verification scope and confidence

The GitHub repositories, metadata, top-level licenses where present, repository trees, selected source files, and/or READMEs were inspected on 2026-11-20. The table separates **implemented files inspected** from **README claims**. No external project was executed or benchmarked in a live Mayhem game; no external OCR accuracy, scoring quality, integration compatibility, Riot compliance, or commercial data rights are certified. Before importing, pin an upstream commit and review the exact copied files, dependencies and non-code data licenses.

**Avoid a false new integration:** `fabs133/league-aram-builder` is related to the current project's own starting code. On 2026-11-20, `backend/engine/scoring.py` had **identical blob SHA `bdc3bd2f8c12f34a661402fc3bb7324ba47344a0`** in the external `master` and our `feat/m5-c4-offer-lifecycle` branch. Our existing Python scoring/build stack must be inventoried and improved, not re-imported as a novel external component.

## Candidate inventory

| Repository | Evidence and useful already-existing functionality | Root license as observed / reuse decision |
| --- | --- | --- |
| [Sygnano/aram-mayhem-tracker](https://github.com/Sygnano/aram-mayhem-tracker) | Inspected `crates/mayhem-vision/src/{offer,ocr,matcher,reroll,frames,paddle}.rs`, Windows capture, OCR fixtures for multiple resolutions and reroll states, `apps/desktop/src-tauri/src/{overlay,updates}.rs`, champion select/augment UI; README describes item-set export, installer and updater. | **MIT**; strongest candidate for studying robust card detection, slot/reroll fixtures, and optional UI/lifecycle patterns. Rust/Tauri integration is not a drop-in Python/Qt module; inspect included OCR model/artifact licenses and data-service terms. |
| [michadasis/Counterbuild](https://github.com/michadasis/Counterbuild) | Inspected `ocr_windows.go` (WinRT Windows OCR) and `app/augments.go` (per-card text matching/fuzzy confidence), repository tree and README. README describes enemy-profile-aware item scores, actual purchased items, affordable components, urgent counters, lightweight click-through overlay, focus safety and champion-specific augment tiers. | **MIT**; strongest reference for D8 item scoring / opponent context and efficient capture. Go native implementation requires careful port or adapter, original benchmarking and verification of OP.GG source terms. |
| [Clarinet-koiyun/hex-companion](https://github.com/Clarinet-koiyun/hex-companion) | Inspected `README.en.md` and code tree including `electron/{ocr,ocr-scheduler,native-ocr}.js`, `shared/builds.js`, OCR verification scripts and tests. Multi-language OCR, champion detection, build explanations and reference-stat provenance are documented. | **MIT** for stated original code; potential recognition/localization fixture reference, not a whole Electron migration. Verify snapshots, bundled models, commercial datasets and separate third-party notices. |
| [ishtartec/query-lol-desktop](https://github.com/ishtartec/query-lol-desktop) | Inspected metadata, root MIT text and Tauri/Rust/React tree including `src-tauri/src/{config,lcu,lib}.rs`, `src/App.tsx`, installer workflow. README documents desktop companion, phase detection and app UX. | **MIT**; consult only for D9–D11 install/config/lifecycle patterns if beneficial to existing PyQt6. Not a plug-compatible dependency. |
| [fabs133/league-aram-builder](https://github.com/fabs133/league-aram-builder) | Inspected `backend/engine/{scoring,build_suggester}.py`; scoring includes champion vectors, tier factors, prior-augment overlap and enemy-context modifications; build suggester remains basic on ownership/gold/slots. Identical scoring blob observed in our branch. | **MIT**, but **already present / related to our base**: avoid duplicate import. Any improvements should be original, test-driven changes to the current engine. |
| [ItzStorDz/mayhem-advisor](https://github.com/ItzStorDz/mayhem-advisor) | Inspected README and source tree: `src/Core/{AugmentScore,AugmentBuilds,MayhemBuilds}.cs`, screen reader, item links, Electron panels, Windows installer. README claims augment scoring, build adaptation, opponent context and post-game summaries. | **All rights reserved** with explicit prohibition on copying/derivatives. **Feature-level reference only**; do not copy, translate or port code, assets, UI text, or algorithms without written permission. |
| [zp96-cmd/mayhem-overlay](https://github.com/zp96-cmd/mayhem-overlay) | Inspected tree with `src/main/{ocr,ocr-match,ocr-preprocess,liveclient}.js`, OCR tests and augment data. Readme/repository describes OCR/build/context and app packaging. Existing ARAM Oracle adaptation/attribution is documented elsewhere. | **No root LICENSE detected** in this review; earlier project register identified an MIT claim in package metadata. **Conditional**: confirm precise scope/copyright/dependency notices before any *further* source reuse. |
| [Danielxpj/Paradox-LoL-Companion](https://github.com/Danielxpj/Paradox-LoL-Companion) | GitHub description describes .NET/WPF opponent-kit-aware real-time item/build advice. | No root license identified; **reference only** until explicit rights and exact implementation are checked. |
| [minseop8787/lol-overlay](https://github.com/minseop8787/lol-overlay) | Directly inspected `backend/shop_detector.py`: screen capture + OpenCV template matching with 0.9 threshold. `backend/augment_watcher.py`: OCR of three regions, confirm-button template, two-frame stability and scan loop. | No root license identified; **reference only**. Shop detector is a brittle single-template proof of concept, not verified across resolution/HUD/DPI/locales. |
| [DigitalSyntrex/lol-aram-augment-overlay](https://github.com/DigitalSyntrex/lol-aram-augment-overlay) | Inspected tree showing C#/WPF screen capture, champion detection, augment recommendation services. | No root license identified; reference only. |

## Feature → candidate map (not an implementation-complete checklist)

| ARAM Oracle requirement | Existing candidate | Recommended handling |
| --- | --- | --- |
| Three physical augment cards with title identity | Sygnano; Counterbuild; Hex Companion | **P0 / M4–M5 and D7:** compare capture geometry, confidence gates and multilingual matching with existing C1–C4. Preserve current stacked PR work; do not replace it wholesale. |
| Single-slot / double reroll, stale-offer prevention | Sygnano test fixtures and reroll engine; our existing C3/C4 | **P0:** extend *our* tests and native ground-truth matrix; require per-slot identity and epoch-based stale rejection. |
| Ranks / badges aligned to cards | Sygnano `AugmentPanels.tsx` and `TierBadge.tsx` | **D7 only after truthful OCR**; use original UI, do not expose forbidden win-rate fields or misleading derived win-rate scores. |
| Champion-select tiers and bench options | Sygnano; our existing Champion Select | Compare UX/phase indicators; never automate a selection. |
| Augment synergy with prior picks / current items | Our scoring engine (also `league-aram-builder`), Hex Companion, Mayhem Advisor as feature reference | **Do not re-import our own base.** Improve original deterministic score, provenance/confidence and validation. |
| Enemy composition, kit traits and real purchased items | Counterbuild; Paradox feature reference | **D8:** compare counter-item coverage against our existing `team_context` and LCDA item provenance; use player-visible data only. |
| Next purchase, owned components and available gold | Counterbuild | **D8:** adapt concepts with independent buyability tests, item legality and patch/mode catalog. |
| Shop-open visibility | `minseop8787/lol-overlay` proof-of-concept | **UX-005/D8:** validate permitted real shop signal and multiple screen/HUD configurations first; no assumption that death/gold means shop open. |
| Fully contextual, minimal state-driven UI | Counterbuild focus/click-through; Sygnano card-only view; our approved D6 design | **D6–D8:** own state reducer; augment > shop > optional scoreboard, otherwise hidden. Avoid always-on lists. |
| Late-game boots replacement / 6-slot legality | No verified complete implementation found | Keep **UX-009** open; original optimizer with mobility trade-off, component/slot legality, uniqueness, and test cases. |
| Traditional desktop app / installer / updater | Sygnano; QueryLoL | **D9–D11 only:** compare packaging/updates with our already approved Python/FastAPI/PyQt6 topology; require Windows acceptance, privacy, notices and user approval. |
| Data quality / confidence / score calibration | Existing ARAM Oracle + selected upstream ideas | Preserve unknown/unrated, provenance and policy gate; do not claim a 0–10 scale makes empirical win-rate-derived advice compliant. |

## Integration priorities and blockers

1. **P0 research (existing M4/M5, then D7):** Sygnano's detection/slot/reroll layout, fixtures and confidence gates; compare with *implemented* C1–C4. No new OCR engine until regression evidence shows a gap. Respect existing M5/C4b independent negative-cue blocker and delayed native acceptance.
2. **P1 research (future D8):** Counterbuild's threat-informed item ranking, component affordability and defensive counters. Determine data provenance and compatibility with current LCDA/item metadata before any code port.
3. **P2 scoring improvement (existing engine):** use `league-aram-builder` only as a baseline comparison because the same scoring file already exists here; strengthen synergy, sample confidence, zero-data behavior, patch/catalog validity and boots replacement.
4. **P3 release/desktop (D9–D11):** Sygnano and QueryLoL as installer/settings/update references; do not switch framework or distribute until current desktop, gameplay and policy gates are met.

### Per-candidate acceptance before source import

- [ ] Pick a **specific upstream commit** and the exact files; read applicable root and per-file licenses and preserve notices/copyrights.
- [ ] Review bundled OCR models, fonts, images, augment catalogs and **third-party data licenses/ToS** separately; MIT repository code does not clear them.
- [ ] Validate code interoperability with Python/FastAPI/PyQt6 and our existing state contracts; prefer minimal, tested adapters over wholesale subsystem replacement.
- [ ] Add deterministic unit/integration tests, original privacy-safe OCR fixtures and Windows in-game acceptance *only in the planned grouped campaign*.
- [ ] Review Riot policy and third-party endpoints, rate limits, visible-data boundaries; keep `experimental_augment_evidence` off pending approval.
- [ ] Record each actually imported external file, upstream SHA and attribution in `THIRD_PARTY_NOTICES.md`; do not mark product TODOs complete on research alone.

**2026-11-20 result:** research documented, **zero new gameplay code or external assets imported**, zero real-game verification, zero changes to `main`; existing M5/C4 work and native acceptance remain open.
