# External Companion Code Reuse — Candidate Register

**2026-11-20 external-source review:** See [OPEN_SOURCE_FEATURE_MAP_2026-11-20.md](OPEN_SOURCE_FEATURE_MAP_2026-11-20.md) for a verified cross-repository feature matrix, code paths, license cautions, scoring-baseline duplication and phase-specific evaluation gates. This is research only; no external source imported and no game tests executed.

Reviewed 2026-11-18 for the ARAM Oracle development roadmap. This is a
**source/feature evaluation, not an approval to import code or ship assets**.
Root LICENSE files for smiteless, ez-lol-spell-tracker and mayhem-advisor were read
through the GitHub connector on 2026-11-18. Exact source revisions, component
licenses, notices and data terms must be verified *again for the chosen files*
before integrating anything.

## Reuse policy

1. Prefer existing local ARAM Oracle implementation, official APIs and tested
   open-source libraries to reimplementing already solved components.
2. Reuse from another project only when an explicit applicable license grants
   modification and distribution rights. Publicly visible source without a
   license is not such permission.
3. For every actual import, record upstream repository, commit SHA, source
   file(s), license text/copyright, adaptation, tests and distribution notices
   in `THIRD_PARTY_NOTICES.md`. Assess transitive dependencies and bundled
   art/data separately.
4. Respect API terms, Riot policy and accessible *player-visible* information;
   an MIT license does not authorize use of hidden data or automatic gameplay
   actions.
5. Do not transplant unrelated architectures into Python/FastAPI/PyQt6. Favor
   narrow, independently tested adapters over wholesale copying.

## Candidates to examine in their relevant phase

| Project | License status / evidence | Potential benefit | Decision |
| --- | --- | --- | --- |
| [smiteless](https://github.com/bobbyroylee/smiteless) | Verified root `LICENSE`: MIT, © 2026 bobbyroylee | Python live-item recommendation adapting to visible enemy builds; compact event-driven UI patterns | **Candidate for D8**, after verifying individual files and dependencies; do not copy its ranked-specific assumptions or third-party commercial datasets |
| [ez-lol-spell-tracker](https://github.com/lucas-lima-s/ez-lol-spell-tracker) | Verified root `LICENSE`: MIT, © 2026 Lucas de Lima | Qt/PySide6 tray/Settings patterns and headless UI test structure | **Candidate for D2**, evaluate whether small patterns are worth adapting; different Qt binding from PyQt6 |
| [mayhem-overlay](https://github.com/zp96-cmd/mayhem-overlay) | MIT listed in package metadata in the prior project audit; verify the complete file-level and dependency notices before any further import | Mayhem OCR/client utilities and mode support | **Conditional candidate**; existing permitted adaptations already recorded in `THIRD_PARTY_NOTICES.md` |
| [mayhem-advisor](https://github.com/ItzStorDz/mayhem-advisor) | Verified root `LICENSE`: copyright © 2026 ItzStorDz, all rights reserved, explicit prohibition on copying/derivatives without permission | Feature reference: card OCR, reroll, manual fallback | **Reference only. Do not copy source, assets or algorithms without explicit applicable written authorization.** |
| [OP.GG Desktop](https://www.op.gg/) | No source reuse license established | Desktop navigation, setting hierarchy, contextual overlay behavior | **UX reference only. No code, assets or branded visual copying.** |
| [Ryot](https://github.com/ryanpolasky/Ryot) | License not confirmed in this review | Distinct main/overlay/champion-select window topology | **Reference only pending verification**, Electron design not directly reusable in the PyQt6 shell |
| [ezlol](https://github.com/aarlint/ezlol) | License not confirmed in this review | Tray ownership, desktop preferences, updater lifecycle | **Reference only pending verification**; updater intentionally outside D1 |

## Phase D1 result

The Settings host requires no imported external overlay code: it uses the
existing `backend.api.server`, `backend.overlay.__main__._start_server` and
`frontend/settings.{html,js,css}`, plus installed PyQt6 WebEngine. No new
third-party source, artwork, scoring logic or datasets were copied into D1.

## Review next

- **D2:** Inspect specific Qt/Windows lifecycle implementations from eligible
  projects. Reuse only if simpler and more reliable than the existing code.
- **D5–D7:** Favor tests, OCR readiness and deterministic fixture handling;
  obtain original screenshots for positional calibration rather than cloning
  proprietary augment cards.
- **D8:** Check the exact smiteless item-inventory adapters, their own license
  notices, any external data-source terms, and Mayhem shop restrictions; only
  then decide whether small adapters can be ported and attributed.
