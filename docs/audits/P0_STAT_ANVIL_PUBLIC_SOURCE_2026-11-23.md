# P0 — Stat Anvil public source discovery and scoring gate (2026-11-23)

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
