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
- LCU history depth: the sync pages the local client's match list 20 at a time
  (begIndex/endIndex) going back, up to 1000 games, with a short pause, and stops
  as soon as a page brings no new games (client ignoring the indices). A one-off
  backfill is `POST /api/history/import?max_games=1000` (needs the
  `lcu_history_enabled` opt-in). Owner chose LCU only (23/11); SGP is not used.
- **Normal-ARAM damage prior (owner decision 23/11):** `scripts/collect_aram_damage_prior.py`
  (offline, never in the overlay) reads Riot match-v5 queue 450 with the key from
  `RIOT_API_KEY` only (sent as a header, never logged or stored), spaces requests
  1.25 s and backs off on 429/5xx. It stores only per-champion aggregates
  (damage/min, heal+shield/min, n, patch) in `~/.aram-oracle/riot_prior/`.
  `augment_impact(..., prior=load_prior())` rescales them to Mayhem levels (median
  local/prior ratio) and blends them into each champion's baseline as 20
  pseudo-games. The holdout runs with and without it (`--no-prior`). Aggregates
  are not published in the repo until Riot's policy for this use is confirmed.
