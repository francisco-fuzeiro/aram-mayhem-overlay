# Tier DB — impact metric (owner decision 2026-11-23)

To be used once damage data exists (local LCU match history; AramHex has none).

- **Main impact metric:** Δ damage to champions per minute versus the champion's
  **own** baseline (not the role average). This also holds for tanks: a tank that
  survives long while dealing area damage (e.g. high Heartsteel stacks) deals a lot.
- **Supports:** Δ (healing + shielding) per minute versus the champion's own baseline.
- **Kills / kill participation:** secondary; added only if the temporal holdout
  shows a τ gain.
- Replaces the "combat versus role average" component when available. Shrunk by n
  like the other metrics; never shown as a number in the overlay.
