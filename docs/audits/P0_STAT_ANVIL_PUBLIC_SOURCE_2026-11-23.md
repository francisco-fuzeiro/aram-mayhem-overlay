# P0 — Stat Anvil public source discovery and scoring gate (2026-11-23)

## RESOLVED — real 16.23 source (later on 2026-11-23)

The hashed 16.22 file was renamed by CommunityDragon. On 16.23 the shards are
in `game/maps/modespecificdata/statanvils.bin.json` (index `/json/16.23/game/maps/modespecificdata/` lists it, 74,980 B).
Verified content: 37 `AnvilData` (14/14/8 + 1 mixed `Pristine`), each with
`RootSpell.mSpell.DataValues`; 34 offerable after `Enabled=false` rows.
The MIT tracker comment in `service/src/upstream/documents.ts` predicted
exactly this ("once CommunityDragon names the file it moves and this entry
404s"). The paged 471-file discovery is no longer needed for 16.23.

## Purpose and evidence levels

**OWNER-OBSERVED:** OP.GG overlay displays a rating for Stat Anvils. Its exact
formula, rank dataset and legality for reuse are unknown; we will not scrape or
copy them. The Oracle will use an independently designed 0.0–10.0 contextual
rating only after verified identities.

**PUBLIC DESIGN EVIDENCE:** A separate MIT project, [Sygnano/aram-mayhem-tracker](https://github.com/Sygnano/aram-mayhem-tracker),
implements Stat Anvil card rankings, read via local screen/OCR. Read its public
README, `service/src/domain/anvils.ts`, `service/src/upstream/documents.ts`,
`crates/mayhem-core/src/anvils.rs` and `crates/mayhem-vision/src/anvil.rs`.
Its documentation identifies a critical mistake in our earlier candidate-only
tier-zero augment report: **Stat Anvil options are not normal
`cherry-augments.json` rows.** They live as `AnvilData` entries in
CommunityDragon's public patch-specific game bins and reference spells with
`mSpell.DataValues`; their localized names are keys into public
`lol.stringtable.json`.

The public project's own research reports that before patch 16.22 entries
resided in `game/data/maps/shipping/map12/map12.bin.json` and in 16.22
moved to `game/unknown/507cdd64276919f5.bin.json`.
The availability/location in **patch 16.23 remains to be verified by the
owner-side source command**. Ordinary shard names can be shared by Silver,
Gold and Prismatic versions. Only independent title AND numeric value
evidence can justify a tier. A voucher stack edge never proves visible cards.
Some public bin shards (Random/Shardholder) are not offered in Mayhem and
must remain excluded.

Riot's official [patch 25.23 notes](https://www.leagueoflegends.com/en-us/news/game-updates/patch-25-23-notes/)
confirm the historical introduction of Stat Anvils after level 9 with
Silver, Gold and Prismatic rarities; do not assume every such detail is
unchanged in the current patch.

## Code and tests on P0 #107

- `backend/static_data/anvil_public_catalog.py`: strict immutable
  patch-agnostic decoder of public AnvilData/spell values, known rarity
  codes, name keys and excluded IDs; rejects malformed/contradictory
  sources. A pure post-observation matcher requires **complete** 3/4
  distinct stat + value pairs mapping to unique identities in one tier;
  it has NO ability to see or control the game.
- `scripts/stat_anvil_catalog_report.py`: existing default local
  augment cache check remains explicitly **not authoritative**. Added
  opt-in `--public-patch 16.23` fetch of *only* public, pinned
  CommunityDragon bins (HTTP 404 allowed for a moved bin), with
  `--locale en_us` to fetch a substantial (~31 MB) public stringtable
  for actual names. No filesystem write, LCDA, LCU, OCR or user data.
  Sanitized outputs flag `live_popup_verified: false` and
  `rankings_verified: false`.
- `tests/test_p0_anvil_public_source.py`: synthetic source fixtures,
  spell/value/tier mapping, source exclusion, invalid/missing source,
  shared-stat rarity ambiguity, strict complete offer matching,
  same-patch URL constraints and opt-in title reading.

No OP.GG code, proprietary rank data, other vendor's public fixtures,
player images or private logs have been copied. Source design was
implemented independently; the competitor's license is MIT.

## Next gates — do not declare P0 complete

1. Verify **exact latest HEAD Windows Actions** after all code and docs commits.
2. With game/Oracle closed, owner safely fast-forward-pulls draft #107 and
   runs `py -3.11 -m scripts.stat_anvil_catalog_report --public-patch 16.23`;
   if it returns a valid nonempty public source report, optionally run
   `py -3.11 -m scripts.stat_anvil_catalog_report --public-patch 16.23 --locale en_us`.
   Share public counts/names only; no full local paths/private screenshots.
3. Integrate verified *current patch* ids and localized titles into dedicated
   Stat Anvil detection, including OCR of card value lines and actual popup
   timing. Do **not** treat normal augment OCR or a voucher as proof.
4. Map verified shard effects into our custom contextual 0–10 model,
   distinguish missing evidence/unmodelled; add exact tuple tests and genuine
   `feature_ack` only after rendering.
5. Include actual shop item buy candidates and conditional Anvil UI in
   **one** supported owner-operated custom Mayhem acceptance test; reconcile
   skipped/failed/not fired feature outcomes. Reverify final exact-head
   CI and keep #107 draft, no merge to parent/main or TierDB changes.

**Current status:** SOURCE RESEARCH/STRICT OFFLINE DECODER IMPLEMENTED,
current patch direct source/locale extraction and all live/anvil-score
requirements **NOT TESTED/BLOCKED**. This is not an accepted P0 phase.

## 2026-11-23 — Owner-real 16.23 result and next public index search

**PROVEN owner output:** after `git pull --ff-only` to P0 HEAD `9d3b29f`,
`py -3.11 -m scripts.stat_anvil_catalog_report --public-patch 16.23`
returned `patch=16.23 bins=['map12.bin.json'] total=0
tiers={'silver':0,'gold':0,'prismatic':0}`,
`live_popup_verified=False` and `rankings_verified=False`.
This supersedes earlier assumptions from mocked tests/old-patch examples;
the two hard-coded paths did not yield real 16.23 AnvilData. It does NOT
prove Anvils are missing from Mayhem or that any new path is correct.

Rechecked MIT [ARAM Mayhem Tracker](https://github.com/Sygnano/aram-mayhem-tracker)
`service/src/upstream/documents.ts`: exact old candidates
`game/data/maps/shipping/map12/map12.bin.json` and
`game/unknown/507cdd64276919f5.bin.json`. Its bundled screenshot
and shard test examples refer to 16.19, not verified 16.23 content.
[CommunityDragon's docs](https://communitydragon.org/docs/assets)
confirm public JSON directory listings under `/json/<patch>/...`.

**New approach and current evidence boundary:** mocked RED→GREEN
`tests/test_p0_stat_anvil_source_index.py` and
`tests/test_p0_stat_anvil_discovery.py`, plus
`scripts.stat_anvil_catalog_report --public-patch 16.23 --discover --json`.
This explicitly scans bounded selected public index paths, fetches
plausible `.bin.json` contents, distinguishes keyword hit versus
actual `AnvilData` + spell shape, reports exact `source_paths`,
`keyword_paths`, scanned candidate/dir counts, failures and
completeness. Optional bounded expansion:
`--discovery-bins 200 --discovery-dirs 100`.
No private game data, OCR captures, disk writes or gameplay actions.
First GREEN scanner code commit `4a199e6` passed
[Windows #45220848233](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45220848233)
(2,102 Python pass/27 skip; 89 JS pass; pinned model 35 pass).
Subsequent docs/CLI changes need new exact HEAD Actions.

**Do NOT mark 16.23 catalogue resolved** until a real public report
shows `total>0`, **each** Silver/Gold/Prismatic count >0,
and exact public source path(s). Point normal parser there only
after observing those values, with patch-specific RED→GREEN.
Then validate live popup OCR title+values and own contextual score
in one user-controlled end-of-P0 Mayhem test. This gate is currently
BLOCKED pending real public indexed scan on owner PC.

## 2026-11-23 — Owner real indexed scan, 2 public keyword references

Owner ran `--public-patch 16.23 --discover --json` after pulling P0
HEAD `47fa24b`: `candidate_bin_files=471`,
`bin_files_inspected=80`, `downloaded_bytes=2039856`,
`index_directories_scanned=21`, `index_failures=0`,
`source_files_unavailable_or_invalid=0`, `scan_complete=false`,
`status=scan_incomplete`, `source_paths=[]`, `total=0`,
Silver=Gold=Prismatic=0. Thus **not verified**, not proof of absence.

Only two literal keyword files:
`game/gameplay.bin.json` and
`game/maps/modespecificdata/cherry.bin.json`.
A string reference is not a validated choice. The broad scanner examined
only 80 of 471 plausible bin filenames.

New P0 synthetic tests `tests/test_p0_stat_anvil_keyword_probe.py`
and patch-pinned, read-only direct probe
`py -3.11 -m scripts.stat_anvil_catalog_report --public-patch 16.23
--probe-keyword-paths` inspect these two public JSONs and report
bounded matching key/value paths, plus top-level and nested
`__type=AnvilData` counts. Probe always outputs
`catalogue_verified=false`: it cannot validate an in-game popup.
Code HEAD `96a8f0b` passed
[Windows #45224141982](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45224141982).
This documentation HEAD awaits exact-head CI.

Next verify actual public reference structure on owner's PC and
follow any discovered real bin paths. Source gate remains
**16.23 total>0, Silver>0, Gold>0, Prismatic>0** with exact bin(s),
then independently detect popup, title+numeric values and custom
0–10 score; final one controlled Mayhem match verifies native.

## 2026-11-23 — Real exact 16.23 CommunityDragon hash URL 404 (do not infer a catalogue)

Owner supplied `https://raw.communitydragon.org/16.23/game/unknown/507cdd64276919f5.bin.json`
and a historical patch 16.22 count of 37 `AnvilData` source rows
(14 Silver, 14 Gold, 8 Prismatic, 1 mixed). We used Windows GitHub
Actions as an independent public-only HTTP client to avoid trusting
synthetic fixtures or a guessed URL.

**Real evidence:** [Windows run #45228414820](https://github.com/francisco-fuzeiro/aram-mayhem-overlay/actions/runs/45228414820),
commit `5b88846d0630c1d0b96410bfab6db990d5227413`:
exact 16.23 URL GET returned HTTP **404**;
same-patch index `https://raw.communitydragon.org/json/16.23/game/unknown/`
returned successfully and `exact_filename_in_index=false`,
`index_named_candidates=[]`. Thus no current-patch source,
raw AnvilData=0, parser_total=0, Silver=Gold=Prismatic=0 and
`source_verified=false` **at that path only**. This independently
corroborates the owner's previous zero report. It does NOT prove
Stat Anvils are absent from ARAM Mayhem, and the 16.22 data
must NOT be relabeled as current 16.23.

The verified read-only tool is `scripts/anvil_source_exact_probe.py`
with `tests/test_p0_anvil_source_exact_probe.py`, counting
raw `__type == AnvilData`, singleton/mixed `AnvilTypes` 0/8/9,
`RootSpell`-resolved parsed records, with same-patch public-index
fallback on 404. No local cache write, League API, account identifier,
private OCR, player path or game screenshot. One-time non-gating
GitHub Actions probe was **removed** after evidence was recorded.
Both suite jobs on probe SHA GREEN: 2,115 Python PASS/27 SKIP,
89 JS PASS, 35 real pinned OCR PASS. Latest docs/cleanup HEAD
requires independent recheck.

**BLOCKER:** Real source relocation on patch 16.23 remains unknown.
Owner's index scan covered only 80/471 candidate BINs, and the two
public keyword matches were TFT UI and DustToDiamonds.AnvilsGranted,
both with no `AnvilData`. The existing safe paged scanner can
inspect 80..279 and 280..470 by explicit offset, without repeating
the first 80, but it must report incomplete/invalid responses
separately; only real `total>0` across Silver/Gold/Prismatic
and an exact current source path clears the gate.

Then implement verified source integration, distinct actual popup
3/4-card layout detection, title AND numeric-value OCR, own contextual
0–10 scores with true client-side `feature_ack`, and validate
shop #49 plus augment/anvil behavior in one final user-operated
supported Mayhem match. P0 #107 remains DRAFT/open, no main/TierDB,
no next phase; user explicitly requests a *continuation* prompt
despite this unresolved source.
