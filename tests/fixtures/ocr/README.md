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

## M5/C1 geometry evidence needed in addition to PNGs (2026-11-19)

The offline P0.4 preparer intentionally strips screenshot metadata and returns
three small title PNGs plus ID/null truth. **These files alone do not locate
those pixels inside the League client.** Before C1 can fit a 16:9 pure
client-rect-to-three-bands function, measure the source title rectangles on a
**real local Windows League client**, not from B3's provisional crops.

For every named offer/reroll/dialogue/absent case, record a privacy-reviewed
numeric annotation (kept alongside sanitized fixtures only after replacing
all missing values with real observations):

```json
{
  "case_id": "offer-1440p-01",
  "client_rect_desktop_xywh_px": [null, null, null, null],
  "titles_client_xywh_px": {
    "left": [null, null, null, null],
    "centre": [null, null, null, null],
    "right": [null, null, null, null]
  },
  "display_mode": "windowed-or-borderless-observed",
  "dpi_scale_percent": null,
  "observed_state": "offer-or-reroll-or-dialogue-or-absent",
  "redaction_reviewed": false
}
```

All `null` coordinates above are **placeholders, not fixture data**. Measure
`x,y,width,height` in physical pixels relative to the League client origin;
record the client's actual desktop `x,y` (negative coordinates are valid),
client width/height, DPI, and whether windowed/borderless. The title boxes
must enclose *visible title glyphs only*, not descriptions or reroll controls.
For a fully obscured or absent title, mark its title box null and its truth
ID null; do not estimate a box from other cards. Use neutral case IDs only.

Capture at 2560x1440 and, if possible, 1920x1080 in 16:9, including a
windowed offset and a signed-origin monitor check, the initial three-card
offer, single rerolls per slot, one double reroll, a dialogue overlapping a
card, and disappearance of all cards. Record whether each B3 provisional
crop actually contains the complete correct title. If not, mark the crop
unusable, and manually crop **only** the needed title band from a permitted
local frame while recording its actual client-relative position. Never
commit the full League window, full desktop, identifiable chat/HUD or
unredacted source. The manual crop still must pass the P0.4 privacy and
shape checks. The numeric annotation is a proposed manual evidence contract,
not a schema currently parsed or emitted by the script.

Review each output PNG and truth ID before upload. Keep original private
images local only; do not put them into Git history. The B3 debug setting is
opt-in, defaults off, and the local diagnostic folder retains at most 15
crops / 72 hours. Disable the setting after collection. No accuracy or C1
completion may be claimed until these measurements are real and reviewed.
16:10 and 21:9 remain explicitly unsupported.
