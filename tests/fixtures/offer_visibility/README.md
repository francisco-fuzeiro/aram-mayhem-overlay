# M5/C4b — Independent visual presence/absence evidence contract

**Status: evidence required; no League images or trained detector included.**
This document describes the smallest permissioned, privacy-reviewed evidence
needed to enable the currently disabled `VerifiedAbsenceGate`. Synthetic test
pixels demonstrate control flow ONLY, not actual LoL UI reliability.

## Why title-only OCR is insufficient

A dialogue, tooltip, reroll animation, an unavailable capture, a temporarily
blank title and the real end of an offer can all result in zero recognized card
names. **No number of blank title reads can certify a disappeared offer.**
Even a perceptual hash of a title band is not independent proof.

The runtime `ScreenWatcher` currently passes **no**
`independent_observer` and **no** `approved_calibration`; therefore it
will not automatically emit `disappeared`. An approved independent visual
cue may eventually return `absent`, `occluded` or `unknown`. These values
must come from an independently measured on-screen affordance, NOT by
relabeling a failed title match. The safety gate then requires three
consecutive focused scans of the SAME calibrated League client geometry,
after a real C3-confirmed offer was observed. Focusing a different window or
changing client identity revokes prior negative evidence. Three is a debounce
policy, not a measured detection accuracy or timing guarantee.

## Native evidence required before implementing a classifier

Use **one future, grouped controlled Windows acceptance session**, rather
than asking the player to repeatedly start games during incremental work.
A reviewed tester must record the exact observed game/UI mode and ensure no
third-party game data or inputs are accessed.

For each actual display mode/resolution, record four cases:
1. A fully visible, recognized three-card offer (including a reroll)
2. The normal screen after the offer has really closed, with no cards
3. An on-top dialogue, tooltip or temporary occlusion while the offer remains
4. In-progress card reroll/transition animation before new names settle

For each case obtain **at least three distinct, consecutive source frames**
at the runtime polling cadence, and independently annotate the factual
state and whether any card was still visible. Add negative cases such as
focus loss/Alt+Tab, client resizing, new-game reset and overlapping UI if
available. First validate the already-open C1 three-title crop/ID ground
truth and M4 focused-client-only capture. The previous source crop review
at a 2544×1353 client is **positive-title geometry evidence only**, not
evidence for a missing offer or a dialogue marker.

Choose a **small, stable, client-relative, non-text card-chrome/offer UI
anchor**, if such a marker is actually observable in every required state.
The anchor must be independent from the three recognized title bands and
must not include chat, player identity, HUD, map, account data or other
unrelated content. **Do not invent coordinates:** measure the same x/y/w/h
rectangle on actual permissioned local frames, and verify it stays inside
the focused League client. If no independent marker reliably separates
absent from occluded, the classifier remains blocked; do not train a guess
from title-only PNGs.

A metadata annotation for each reviewed *local* crop can look like:

```json
{
  "case_id": "neutral-case-id",
  "state": "present | absent | occluded | animating",
  "client_width_px": null,
  "client_height_px": null,
  "client_origin_x_px": null,
  "client_origin_y_px": null,
  "window_mode": "observed-windowed-or-borderless",
  "dpi_scale_percent": null,
  "anchor_client_xywh_px": [null, null, null, null],
  "frame_sequence": null,
  "independent_marker_verified": false,
  "redaction_reviewed": false
}
```

All `null` fields are **placeholders, not evidence**. Do not store HWND,
player names, chat text, account data, unredacted desktop/window screenshots
or raw telemetry in a public GitHub repository. Keep source frames private
and local; manually inspect, crop, strip metadata and review each permitted
minimal artifact **before** any transfer. Do not enable broad automatic
screenshot collection. The existing debug opt-in saves only title-band crops,
not independent negative-marker screenshots.

## Calibration / code-release gate

- Prove an independent, measured marker works on real positive/negative/
  occluded/animated cases, including at least one held-out case per state.
- Bind an approved detector revision and its real client-relative geometry
  to each supported viewport; reject unsupported aspect ratio/DPI/focus
  and any wrong calibration/version. No hard-coded coordinates from guesswork.
- Keep the minimum three-scan absence confirmation and abort on any
  conflicting, occluded or unfocused observation; never infer a chosen augment.
- Add new regression tests with reviewed redacted fixtures (plus synthetic
  controls), verify fresh Windows Actions on the exact PR HEAD, then conduct
  one short native League acceptance of M4/C1–C4 including ten offers/thirty
  cards and rerolls. Keep C4b and all native gates OPEN until that evidence
  exists.

This file is a specification only. It does not certify that League has a
particular offer/absence UI marker, nor does it activate a detector.
