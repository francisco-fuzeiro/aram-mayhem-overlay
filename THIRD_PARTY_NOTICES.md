# Third-party attribution

This project builds on ARAM Oracle (fabs133/league-aram-builder), licensed
under MIT. The original license is retained in the project root.

## Mayhem Overlay — Zac Pitts

Upstream: https://github.com/zp96-cmd/mayhem-overlay

Mayhem Overlay declares "license": "MIT" in package.json (inspected
November 18, 2026). Its root tree did not contain a LICENSE file at the
time of inspection. These ideas and implementations were adapted into Python:

- Additional Windows installation drives and a process-path fallback for
  League client lockfile discovery (backend/collectors/lcu.py).
- Multiline OCR matching with normalized names and adjacent-line joins
  (backend/collectors/screen_ocr.py).

Copyright (c) 2026 Zac Pitts

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

## ARAM Mayhem Tracker — Sygnano (MIT)

Design reference only (no code copied): Stat Anvil data location in
CommunityDragon game bins (`AnvilData`, `RootSpell.mSpell.DataValues`,
`AnvilTypes` 0/8/9), shard titles from `lol.stringtable.json`, shard cards
sharing the augment card frame, and the idea of settling Silver/Gold by the
value lines. https://github.com/Sygnano/aram-mayhem-tracker — MIT License,
Copyright (c) 2026 Sygnano.

## Reviewed but not copied

- Mayhem Advisor (ItzStorDz/mayhem-advisor) is all-rights-reserved.
  Its license prohibits copying or derivatives without written permission.
- ARAMGG Client (valkia/aramgg_client) has no confirmed overall license.

No code or assets from either restricted/unconfirmed project were copied.
Riot game data and intellectual property may have separate terms; this
attribution does not imply Riot approval.

## Third-party data (downloaded at runtime, not redistributed in this repository)

### AramHex — ARAM: Mayhem statistics (CN server)

Source: https://github.com/czgreat/aramhex-data — licensed under
Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
Attribution: "海克斯大乱斗统计数据（github.com/czgreat/aramhex-data），CC BY-NC 4.0".
Not affiliated with Riot Games or Tencent.

ARAM Oracle uses these statistics only while it is a non-commercial
application (owner decision, 2026-11-23). The tier DB (`backend/tierdb/`)
downloads them to the user's machine, verifies their SHA-256 checksums and
derives tiers and ranks; win rates and sample sizes are never displayed. If
the application becomes commercial, this source must be removed or
authorised in writing; `ingest_aramhex(app_mode="commercial")` refuses it.
