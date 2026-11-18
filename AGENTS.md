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
