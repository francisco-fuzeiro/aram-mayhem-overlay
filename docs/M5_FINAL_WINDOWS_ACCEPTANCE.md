# ARAM Oracle — M4/M5 C1–C4 grouped native acceptance plan

**Status: plan only. No Windows/League acceptance executed.**

This is the single, controlled end-of-development test campaign requested
by the user. Do not ask for interim game launches or treat Windows CI as a
substitute for real screen evidence. A ten-offer sample generally spans more
than one match; run it as one coordinated campaign, not ten unrelated
debugging requests. All app code and prior PRs remain unmerged/draft.

## Gate before requesting this test

- Latest exact-HEAD Windows Actions for C4b/C4c must pass Python and JS.
- M4 focused League-client capture and current C1 title geometry must be
  installed on the local Windows machine. Confirm Tesseract executable is
  available and the OCR setting persists/reflects the current session.
- A **real independent absent/dialogue marker is not implemented or
  calibrated yet**. Until reviewed marker evidence exists, disappearance
  must remain `uncertain` or require the player's own confirmation.
  Never claim automatic gone was validated just because names vanished.
- All diagnostic screenshot saving defaults **OFF**. Enable explicitly
  only to collect a few client-bound title-only crops, verify each crop is
  free of HUD, map, chat, players and personal/account information, and
  disable the opt-in immediately afterwards. No raw full-window images
  should be placed in public Git.
- Name, score and reroll truth must come from the real current three
  visible cards and the permitted local catalog, never from a synthetic
  fixture or guessed win rate.

## One grouped play campaign — record outcomes per actual offer

Use neutral case IDs, local dates, physical client width/height, window
mode, DPI and display signed origin. Capture **at least ten actual offers /
thirty physical card positions** across consecutive controlled games.
For every offer, manually verify L/C/R names and exact catalog ID or
`unknown`, record any rerolls and relevant negative/occlusion conditions.
Never infer that the card was chosen from its disappearance alone.

1. Start at champion select, loading and a live custom Mayhem match.
   Validate the overlay clears the previous champion, gold and time and
   never treats a disconnected Live Client Data API as game ended on one miss.
2. Observe the first actual three-card offer. Before two consistent title
   reads, no L/C/R advice should appear; after verification, show exactly
   the currently visible L/C/R positions or explicit `unknown`.
   No fabricated `2.1/10` or other ungrounded rating.
3. Reroll **left, centre, right at least once**, plus **twice in the same
   slot** during the campaign. Confirm the first provisional visual
   transition hides old advice immediately, the other two slot identities
   are never reassigned, and the final displayed identities require two
   fresh C3-confirmed OCR observations.
4. Show a tooltip/dialogue on top of an offer if safely possible. The
   overlay must not assert a vanished offer, a chosen card or an OCR match
   from covered text. A truthful `uncertain` state is acceptable.
5. Verify player-confirmed actual picks close that offer once, without
   reopening from late OCR WS/REST results. Later eligible levels must
   create a **new** generation, not revive the prior choices.
6. Disable and re-enable OCR during a valid pending offer from outside
   the live overlay (Settings): old advice must hide immediately.
   A new verified reading is required after re-enable.
7. Alt+Tab, restore focus, temporarily remove OCR availability, and
   recover: no full-desktop capture or old-epoch offer can become current.
   Check Qt transparency/click-through/Alt+O/Alt+H independently.
8. Exercise game exit, reconnect and next-game start. Old champions,
   augments, scores, manual confirmation panels, gold and time must not
   leak across matches.
9. Check any available 1080p and 1440p / windowed and borderless displays,
   DPI 100/125/150%, and signed-origin secondary monitor on the actual
   machine. Mark untested configurations **not tested**, not passing.
10. Inspect diagnostic cropped PNGs only if explicitly opted in:
    three correct complete title bands, all glyphs and wrapped titles,
    no HUD or unrelated UI; confirm per-file retention and disabling
    debug screenshots restores zero persistence.

## Independent negative/dialogue calibration — separate hard release gate

The existing production watcher has **no approved negative anchor**.
The three-title OCR bands cannot distinguish closed offers from occlusion.
If the controlled session also yields permissioned source frames, locally
review a **separate non-title, client-relative UI marker** for
present, absent, dialogue and animation. Measure actual geometry and
collect multiple consecutive frames per state with held-out negatives.
Keep source images private and raw account/HUD/chat content out of public Git;
record only neutral numeric annotations and redacted minimal crops after
explicit review. Follow `tests/fixtures/offer_visibility/README.md`.
If independent separation cannot be proven, leave auto-gone disabled.
Do not fabricate calibration IDs or coordinates.

## Stop conditions / report

Stop the test if overlay blocks gameplay, persists desktop/private
screenshots, guesses an absent or covered card, assigns a score to the wrong
physical slot, auto-selects an augment, leaks choices across sessions,
or misreports offer closure. Record `pass / fail / not tested` **for each
case and gate**, attach only privacy-reviewed minimal permitted evidence
and a reproducible description. Repeat tests only after a code fix and a
green final-head CI; never quietly close native TODO items based on synthetic
tests.

The user is explicitly postponing this campaign until the C4b/C4c
implementation phase finishes. **This document is not evidence of execution.**
