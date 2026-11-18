# Repository agent instructions

## Session startup

Before changing code, read:

1. `docs/PROJECT_STATE.md` — current architecture, branches, PR dependencies, validation status and open risks.
2. `docs/TODO.md` — canonical product/UX backlog with task IDs, completion criteria, and evidence.
3. `docs/IMPLEMENTATION_PHASES.md` and `docs/DESKTOP_ARCHITECTURE.md` — small-phase plan and approved desktop/overlay architecture.
4. `docs/DEVELOPMENT_LOG.md` — chronological work record.
5. `.agents/skills/continue-aram-oracle/SKILL.md` — cross-chat project continuity procedure.
6. The product specification `funcionalidades.md` when provided in the ChatGPT Overlay LoL project; it is **not automatically assumed to exist in this Git repository**.

Work from the current feature branch and inspect open stacked draft PRs before merges. Protect `main`. Confirm live GitHub Actions results rather than trusting old documentation.

## Mandatory functional-fix execution policy (2026-11-18)

**This is a project rule for all agents (Claude Code, Codex, ChatGPT) performing functional-fix work.** Before changing code, read [the canonical M1–M8 implementation plan](docs/FUNCTIONAL_FIX_IMPLEMENTATION_PLAN_2026-11-18.md) and its phase checkboxes in [TODO](docs/TODO.md), as well as the already-required project state/log documents. The older [A-FUNC recovery plan](docs/A_FUNC_REMEDIATION_PLAN_2026-11-18.md) is historical/high-level and must not override the granular P0.1–G6 phase IDs.

1. **One phase = one new branch = one focused draft PR**, stacked against the immediately preceding implementation phase. The first code-fix phase starts from `feat/desktop-overlay-preview-apply-d4b` (PR #17) unless explicitly re-planned; documentation-only PR #18 does not mean that code has been merged. A chat may execute more than one phase **sequentially** but must preserve distinct branches, PRs and gates. A mid-phase chat handoff resumes the same branch/PR.
2. **Scope and size:** S target ≤150 changed lines, M target ≤400 (excluding fixtures/tests); split work above M. No unrelated cosmetic redesign. Reverts must safely restore the prior behaviour; config keys additive/defaulted; no migrations without explicit review.
3. **Test first:** introduce a regression that fails on the prior head before each fix. For harness-only phases, preserve existing behaviour; link known defects with explicit `xfail(strict=True)` until the corresponding fix. Convert expected failures to passing tests when fixed. Run the full Python and JavaScript suites, check final-head **Windows GitHub Actions**, and report actual results only.
4. **Acceptance:** mark implementation and tests complete only on real evidence. Maintain a separate **Windows-device acceptance** checkbox for each applicable gate. Update `docs/TODO.md`, `docs/PROJECT_STATE.md` and append `docs/DEVELOPMENT_LOG.md` at each phase; never silently mark full M7 acceptance from CI alone.
5. **Safety:** no mandatory player interaction during combat; uncertain augments or scores remain unknown/unrated instead of invented. Captures and fixtures must exclude private desktop content; debug screenshots off by default and opt-in. The local HTTP/WS Origin/Host/auth flaw (AUD-08/G4) is a **release blocker**. Mode-specific data provenance and score calibration (G1/G2/G5) are needed before presenting accuracy as validated. Respect Riot policy and licensing.
6. **Gates and authority:** first execution milestone is M1 (P0.1–P0.3), followed by the tracked phases and approved dependency choices. M7 means real Windows correctness for the observable lifecycle, not statistical score validation by itself. Defer F-AUD-07 badges, D5c visual work and public distribution until their required gates are truly met. **Do not change or merge `main` without explicit user approval.**
7. **Proposal vs instruction:** the user-provided detailed technical design is a proposal until dependencies are checked; these execution/traceability/safety rules are mandatory. If a phase detail proves incorrect, document the deviation and reason in the plan/TODO before implementing it; do not silently substitute a different roadmap.

## Cross-chat trigger convention

When the user says **`ARAM Oracle: preparar passagem`**, run the
documentation/checkpoint/CI handoff in
`.agents/skills/continue-aram-oracle/SKILL.md` and return a next-chat
prompt. When a new ChatGPT project conversation starts with
**`ARAM Oracle: continuar`**, fetch that skill and the current GitHub
state before proceeding. These phrases are **not** built-in slash commands,
a scheduler, or a way to create the next chat automatically.
For a mid-phase rotation, continue on the same branch/PR; create a new
stacked branch/PR only when beginning the next phase.

## Language and priorities

- All application copy, source code comments, commit messages and documentation must be in English.
- User communication should be European Portuguese.
- Functional correctness, deterministic scoring and state capture before UI polish.
- Prefer bounded 0.0–10.0 contextual scores with provenance/confidence, not disguised win-rate displays.
- No automatic champion, augment, item or skill selection; use only available and permitted data.

## License and policy guardrails

- Mayhem Advisor (`ItzStorDz/mayhem-advisor`) has an all-rights-reserved license. Reference its publicly described **features**, but **do not copy or translate its source, assets, UI text, or algorithms** without written authorization.
- Mayhem Overlay (`zp96-cmd/mayhem-overlay`) declares MIT in package metadata; preserve attribution for any reused licensed code in `THIRD_PARTY_NOTICES.md` and verify exact applicable notices.
- Respect Riot policy. An augment score derived from win/loss data is not automatically permitted merely because it is labeled 0–10. Keep `experimental_augment_evidence` disabled until reviewed. Never reveal hidden players, hidden items or information not legitimately exposed to the user.
- Third-party gameplay datasets have independent licensing/provenance constraints.

## End of each meaningful work unit

1. Add tests and report verified results (`passed`, `failed`, or `not run`).
2. Update `docs/PROJECT_STATE.md` to reflect the latest actual state.
3. Append a dated factual entry to `docs/DEVELOPMENT_LOG.md` with branch/PR, code changed, tests and next steps.
4. Update `docs/TODO.md`: check off only narrow items supported by code/test or Windows evidence; keep separate user-device validation items unchecked until verified, preserving task IDs.
5. Keep pull requests as drafts until validated, including Windows in-game tests where necessary.

These files are a **handoff**, not background execution or an automatic logging service. Update them explicitly whenever you work on this repository.
