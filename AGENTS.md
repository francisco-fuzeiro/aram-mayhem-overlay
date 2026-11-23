# Repository agent instructions

## 2026-11-23 — Exact 16.23 Stat Anvil source 404; do NOT promote historical bin

- Actual Windows Actions [#45228414820](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45228414820) GET of `https://raw.communitydragon.org/16.23/game/unknown/507cdd64276919f5.bin.json` returned **HTTP 404**. The CDragon `/json/16.23/game/unknown/` index was checked and contains **neither the exact filename nor matching hash-prefixed filenames**. This is a PROVEN missing current public asset path, not proof Stat Anvils are absent from Mayhem. Owner's historical 16.22 37 Anvils (14 silver/14 gold/8 prismatic/1 mixed) cannot be treated as patch 16.23. New read-only public probe `scripts/anvil_source_exact_probe.py` + tests reports HTTP/index status and raw/parsed tier counts; one-time CI live probe removed after evidence.
- P0 source gate remains **BLOCKED**: obtain actual 16.23 `AnvilData` and `RootSpell.mSpell.DataValues` with total>0 and each Silver/Gold/Prismatic >0 plus exact verified file path. Previous owner scan 80/471 indexed candidate bins and TFT/DustToDiamonds keyword paths are incomplete/false positives. Safely inspect remaining bins/updated exports, never guess source or activate ranks.
- After source: real popup 3/4-card detection, title+value OCR, own 0–10 champion/augments/items/enemy-context score with true render ACK; native shop #49 and one final user-operated Mayhem match/diagnostics, then latest exact-head CI. Item pool v4 already validated on owner PC (104 final+7 boots=111); do not ask to repeat. P0 #107 remains draft based on #103; no merge/main/TierDB or private screenshots/logs. User explicitly requested a new-chat P0 continuation prompt now, with blockers, despite phase still open. Normally no automatic prompt until P0 accepted.

## Active P0 Stat Anvil source lead (owner real data, 2026-11-23)

- Owner tested real public patch 16.23 on P0 HEAD `47fa24b`: `candidate_bin_files=471`, `bin_files_inspected=80`, `index_directories_scanned=21`, `index_failures=0`, `scan_complete=false`, `source_paths=[]`, `total=0` and silver/gold/prismatic all 0. This is **not a complete scan or validated source**, and does not prove Mayhem Anvils are absent.
- The only public keyword hits were `game/gameplay.bin.json` and `game/maps/modespecificdata/cherry.bin.json`. Neither is an authoritative AnvilData catalogue merely because the word "Anvil" appears.
- Targeted RED→GREEN source-only probe `tests/test_p0_stat_anvil_keyword_probe.py` and `py -3.11 -m scripts.stat_anvil_catalog_report --public-patch 16.23 --probe-keyword-paths` inspect only those patch-pinned public files, reporting exact JSON Anvil references and top-level/nested `AnvilData` counts. Always `catalogue_verified=false`, with no local writes/League/player data. Follow real public references if present before asking for another broad scan.
- Require **real** patch-16.23 parsed `AnvilData`/RootSpell, `total>0` and each Silver/Gold/Prismatic >0 with exact source path, then real popup OCR/title+value, own contextual score and one final supported Mayhem match. Stay in same P0, draft PR #107 on #103; no merge/main/TierDB/handoff prompt while incomplete.

## P0 source-acceptance override — Stat Anvils patch 16.23 (2026-11-23)

- Owner Windows PC confirmed `--public-patch 16.23` on P0 HEAD `9d3b29f`: only `map12.bin.json` yielded, **total=0, silver=0, gold=0, prismatic=0**. This invalidates the previous hard-coded source assumption; a fixture/keyword hit is NOT current-patch proof. Keep recommendations disabled.
- CommunityDragon offers public directory indexes `/json/<patch>/...`. New opt-in `py -3.11 -m scripts.stat_anvil_catalog_report --public-patch 16.23 --discover --json` traverses bounded plausible game/map/mode/unknown directories, reads candidate public `.bin.json`, and separately reports keyword matches, parsed `AnvilData`, source_paths, tiers, bounds and any index failures. Read-only, explicit public network use; no League/player access.
- **Do not accept this P0 Anvil source until actual patch-16.23 report shows total>0, Silver>0, Gold>0 and Prismatic>0 AND specific public source_paths.** Only then pin verified file paths in the parser with RED→GREEN patch tests; later separately verify popup OCR titles/values, contextual 0–10 and real UI during one supported custom match. If bounded scan is incomplete, expand via `--discovery-bins 200 --discovery-dirs 100` and continue investigation; never fabricate a valid source or auto-transfer chat.
- Exact verified older code HEAD `4a199e6` [Windows #45220848233](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45220848233) SUCCESS (2,102 Python PASS, 27 SKIP; 89 JS PASS; 35 pinned OCR PASS). The new docs/current HEAD must have its own CI check. Keep #107 draft, main/TierDB untouched and local untracked `funcionalidades.md` safe.

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


## P0 Stat Anvil source and scoring guardrails (2026-11-23)

- Owner observed OP.GG overlay scoring Stat Anvils; implement our own 0–10
  champion+augments+items+enemy-context assessment, not a rebranded OP.GG
  statistic or win-rate proxy. OP.GG score formula/data are not publicly
  verified and must not be copied.
- Public MIT reference: https://github.com/Sygnano/aram-mayhem-tracker
  (readme and `service/src/domain/anvils.ts`,
  `crates/mayhem-vision/src/anvil.rs`). Distinguish its design evidence
  from compatibility or permission to use an external statistics service.
  No licensed assets or third-party ratings have been copied here.
- Real public Anvil source is **AnvilData and RootSpell DataValues in
  patch-specific CommunityDragon game bins**, not generic tier-zero
  cherry-augments. Names in the game string table identify a shard's
  stat; tiers may share titles, so visible value OCR is necessary before
  selecting silver/gold/prismatic. An inventory voucher edge alone does
  not identify popup/cards, and no action on League is allowed.
- Pure P0 decoder `backend/static_data/anvil_public_catalog.py`;
  independent synthetic source/value tests. Opt-in public-only, no-write
  diagnostic: `py -3.11 -m scripts.stat_anvil_catalog_report
  --public-patch 16.23 --locale en_us` (locale downloads a sizeable public
  stringtable); patch/locale whitelisted; output is a **public source
  candidate list, never live verification**. Do not default-enable
  network fetches or silently promote this data into gameplay picks.
- P0 Stat Anvil remains **BLOCKED for native popup geometry, 3/4-card
  confirmation, live OCR title+value identity and contextual 0–10 rendering**
  until patch-matched source is verified and one final owner-operated custom
  Mayhem match demonstrates it. Keep all failures as blockers; no early
  prompt to a new phase, no merge/main/TierDB modifications.

## P0 per-feature diagnostics and one-match acceptance (owner decision, 2026-11-23)

This rule applies to **every P0 fix** (new and pending), not only TierDB. Follow
the validated design in `docs/plans/GPT_BRIEF_TIERDB_2026-11-23.md` and
`docs/plans/FEATURE_DIAGNOSTICS.md` on independent draft #106 as the reference;
never assume those files or its generic runtime infrastructure already exist on
the current P0 branch, and do not merge/cherry-pick unrelated TierDB work.

1. Allocate a stable dotted id (`area.feature`) and closed enum status/reason
   vocabulary in `backend/feature_registry.py` when the diagnostic infrastructure
   has been safely integrated; examples: `augment.stats_parser`,
   `build.item_pool`, `anvil.voucher_purchase`. A feature that abstains must
   report a closed `skipped/reason` or `failed/reason`, not silence.
2. In the **tests-only RED** step, assert the exact
   `(feature, "ok"|"failed"|"skipped", reason)` tuple at the decision point;
   implement the smallest GREEN change with
   `feature_diagnostics.record(feature, status, reason, count)`.
   An offline functional test without a diagnostic assertion is NOT proof of
   instrumentation.
3. For actual user-visible rendering, add the feature id to `UI_FEATURES`
   and accept a strictly allowlisted `feature_ack` only after the overlay
   actually renders. No fake UI acknowledgment from backend calculations.
4. Add **one row per feature** to
   `docs/plans/SINGLE_MATCH_TEST_CHECKLIST.md` with trigger, exact test,
   expected safe diagnostic result, and live owner verification status.
5. Run **ONE owner-controlled Mayhem match** at the end of the fully prepared
   feature batch, not a game for each P0 patch. An aggregate report must isolate
   OK / FAILED / SKIPPED / NOT FIRED by id; when an expected feature does not
   fire, its blocker remains open. Do not claim any native PASS from CI.
6. Never emit player names, Riot IDs, paths, raw OCR text, screenshots, win rates
   or private game data in feature events, reports or this public repository.
   Reconcile duplicate infrastructure with #106 before integrating branches.

## Local Windows checkout safety (owner-observed, 2026-11-23)

- The enclosing workspace folder is not a Git repository; the actual checkout
  is a child folder named `aram-oracle`. Locate it with
  `git rev-parse --show-toplevel` and verify `git remote -v` before actions.
- `origin` points to `francisco-fuzeiro/aram-mayhem-overlay`. A separate
  `upstream` points to `fabs133/league-aram-builder`; P0 operations must use
  `origin`, never pull from `upstream`.
- The owner observed `feat/f3-post-full-build-anvil-priorities-20261123`
  as the then-current local branch, and `funcionalidades.md` as an untracked
  local requirements file (`??`). Preserve that file; do not delete, reset,
  clean, overwrite, stage or commit it automatically.
- Safe user-operated sequence AFTER a clean/preflight check:
  `git fetch origin`, non-forced `git switch` to
  `fix/p0-audit-parser-items-voucher-20261123`,
  `git pull --ff-only origin fix/p0-audit-parser-items-voucher-20261123`;
  stop on error. Confirm exact head and run read-only
  `py -3.11 -m scripts.item_pool_report` with League/Oracle closed.
- **Unverified:** no new branch-switch result or owner PC v3 item report has
  been supplied. Never infer either occurred. Never commit a private full
  Windows path/user name or local screenshot to this public repository.

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
