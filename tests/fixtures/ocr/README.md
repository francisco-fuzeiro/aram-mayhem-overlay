# M5/P0.4 — OCR title-band fixtures (pending real Windows collection)

This directory holds only three sanitized title-band PNGs per case and a
`{left, centre, right: augment_id | null}` truth file. **No real League
samples are included by this change.** Synthetic unit-test images are
not calibration evidence. Never commit raw full-screen or full-window images.

## Windows collection (manual gate)

1. Verify the League game and ARAM Oracle on the local Windows device.
   Leave `ocr_debug_screenshots = false` unless actively collecting; add
   `[ocr]\nocr_debug_screenshots = true` to
   `%USERPROFILE%\\.aram-oracle\\config.toml` and restart to opt in.
2. In a permitted custom ARAM Mayhem match, while League is foreground,
   observe an actual three-card offer. B3 should save only
   `card_left_*.png`, `card_centre_*.png` and `card_right_*.png`
   under `%LOCALAPPDATA%\\ARAMOracle\\screenshots`. Confirm they
   *really contain only the card titles* before sharing or committing.
3. Record a full offer; reroll each slot once; reroll one slot twice;
   place a dialogue over a card; record the normal absence of an offer.
   Repeat at **1440p**, and at **1080p** if available. Collect each
   triplet before the 15-file / 72-hour retention policy deletes older ones.
4. For each observed triplet, verify the correct augment ID manually
   against the permitted local catalog. Use `unknown` for obscured,
   unrecognized or ambiguous titles (never guess an ID).
5. Run this offline command on existing cropped files only:

```powershell
python scripts/prepare_ocr_fixtures.py --left "card_left_XXX_0.png" --centre "card_centre_XXX_1.png" --right "card_right_XXX_2.png" --left-id "aug_id" --centre-id unknown --right-id "aug_id" --case-id offer-1440p-01
```

It writes precisely `offer-1440p-01.left.png`,
`offer-1440p-01.centre.png`, `offer-1440p-01.right.png` and
`offer-1440p-01.truth.json`. The source images are never modified or
copied verbatim. Metadata/OCR notes are stripped. Do not put player IDs,
account data, messages, chat, map, HUD, cursor or raw screenshots here.
Review every crop before providing it for review or checking it into Git.

After collection, disable the opt-in and restart. Check the on-device
windowed/borderless, negative-display-origin, DPI, Alt+Tab, focus/stale
state and Qt hotkey matrix from M4; headless tests do not prove these.
No automatic champion/augment selection, no hidden game data.

**C1–C4 remain blocked** until title band locations/visibility and
truth labels are measured against real permissioned Windows samples.
B3's title-band geometry is explicitly provisional.
