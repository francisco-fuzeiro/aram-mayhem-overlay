# One-match test checklist (owner, Windows)

One ARAM Mayhem match covers every feature. Do not test per sub-phase.

## Before

1. Update the local copy to the branch under test and start ARAM Oracle as usual.
2. Wait about 1 minute on first start: the tier list downloads in the background.
   Settings → Build Preferences → "Mayhem tier lists" should show `On · patch …`.

## During (no screenshots needed)

1. **Champion select:** check that a line `Mayhem strength: … · Potential: …` appears
   under some champions.
2. **First augment offer:** check that each card shows a `Tier … · #…/…` line
   (or `No tier data for this champion`).
3. Optional: in Settings switch the tier lists off and check that the lines disappear at
   the next offer, then switch them back on.
4. Play normally to the end.

## After

1. Close the match. With ARAM Oracle still open, open
   `http://127.0.0.1:8765/api/diagnostics/features`, or in the project folder run
   `python -m backend.feature_diagnostics --out feature_report.md`.
2. Paste the table into the chat. It holds only ids, verdicts, reasons and counts:
   no names, paths or win rates.
3. Note in one line what you saw: yes/no for each of the two checks above.

## Reading the report

- **OK**: worked at least once this session.
- **FAILED / NOT FIRED** in bold: a feature that should have run did not. The reason
  (e.g. `failed/champion_not_in_tierlist`, `failed/export_missing`) points to the cause.
- **SKIPPED**: the feature chose not to act (e.g. switched off).

New features add their lines here (see `FEATURE_DIAGNOSTICS.md`).
