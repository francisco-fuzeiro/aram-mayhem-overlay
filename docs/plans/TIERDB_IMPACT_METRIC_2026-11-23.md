# Tier DB — impact metric (owner decisions 2026-11-23)

Source: local LCU match history of finished Mayhem games (AramHex has no damage).
`backend/storage/history_import.py` stores all 10 players per game in the local
`participants` table: champion, team, result, augments, items, damage to
champions, heal+shield on teammates (fallback: total heal), K/D/A, game length.
No names, PUUIDs, summoner IDs or match IDs (the game key is a salted local
hash); the table is never submitted or exported. Remakes (< 300 s) are skipped.

- **Per-game impact:** z(damage to champions/min) + z(heal+shield/min), each
  against that **champion's own** baseline in the local history, summed.
- **No role labels** (refinement 23/11): a full-AP Sona counts by damage, a
  healing Sona by heal+shield, a tank by the area damage it really deals
  (e.g. high Heartsteel stacks).
- Per (champion, augment): mean score, shrunk by n/(n+20), squashed with tanh
  to [-1, 1]; needs >= 5 games with the augment and >= 10 of the champion.
  Code: `backend/tierdb/impact.py`.
- **Kills / kill participation:** secondary; added only if the holdout improves.
- **Activation gate:** it is an `impact` vote in `context_adjust` with weight 0
  (off). Turn it on only when `py -3.11 -m scripts.validate_impact_holdout`
  (temporal split, AUC of ΔWR vs ΔWR + w·impact) says `enable`: >= 500 test
  rows and an AUC gain >= 0.01. Never shown as a number in the overlay.
- LCU limit: the client match list returns at most 20 games per sync, so the
  history grows over time; ~1000 games at once would need Riot's SGP service
  (owner decision pending).
