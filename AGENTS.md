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

## Phase completion and response contract (owner decision, 2026-11-23)

This is the current authoritative rule; it supersedes older instructions to
produce a conversation-transfer prompt at every checkpoint or subphase:

1. A phase is **complete only after every mandatory acceptance criterion is supported by evidence**, including exact final HEAD Windows Actions and user-controlled native validation when that phase requires it. Synthetic/CI success, completed substeps, a documentation checkpoint, or a blocked validation never completes a phase.
2. **If COMPLETE:** report evidence and remaining out-of-scope risks, then automatically supply the full next-conversation prompt for the next phase.
3. **If INCOMPLETE / BLOCKED / NOT TESTED:** do **not** automatically supply a new-chat prompt. Stay on the same branch, PR and phase. Give an explicit blocker table with PROVEN / SUSPECTED / BLOCKED / NOT TESTED status and an executable, ordered resolution plan: what can be done remotely, the smallest evidence needed from the owner, the RED→GREEN repair if justified, the exact-head Windows CI gate, and native acceptance. Do as much unblocked work as possible now, without guessing.
4. Exception: if the owner **explicitly asks to transfer/prepare a new conversation**, provide a same-phase continuity prompt, clearly stating that the phase remains incomplete; never imply phase completion or transition to the next phase.
5. Continue documenting factual progress safely; do not create unnecessary commits or Actions runs solely to manufacture a handoff. Protect `main`, stacked draft PRs, privacy and Riot restrictions.


## Language and priorities

- All application copy, source code comments, commit messages and documentation must be in English.
- User communication should be European Portuguese.
- Functional correctness, deterministic scoring and state capture before UI polish.
- Prefer bounded 0.0–10.0 contextual scores with provenance/confidence, not disguised win-rate displays.
- No automatic champion, augment, item or skill selection; use only available and permitted data.

## Repository visibility (explicit user decision, 2026-11-22)

- **This GitHub repository is intentionally PUBLIC.** Public visibility is the
  user's desired configuration; do not suggest privatizing it or silently
  change its visibility.
- Public code and documentation are allowed. Do not commit real personal
  game screenshots, private holdout crops, OCR transcripts, diagnostic logs,
  Windows paths, Riot IDs, credentials, secret tokens, or unreviewed third-party
  assets. Keep personal samples and model caches outside the Git checkout.
- Public status does not make restricted third-party code or private gameplay
  data reusable. Continue to respect licenses, privacy and Riot policies.

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
