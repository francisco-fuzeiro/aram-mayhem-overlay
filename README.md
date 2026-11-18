<p align="center">
  <h1 align="center">ARAM Oracle</h1>
  <p align="center">Real-time build recommendation engine for League of Legends ARAM Mayhem</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/tests-104%20passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/status-alpha-orange" alt="Alpha">
</p>

---

ARAM Oracle connects to League's Live Client Data API during an ARAM Mayhem match and provides real-time augment recommendations, item build paths, and reroll advice through a lightweight overlay.

## Features

- **Augment Scoring** -- 12-dimensional stat vector model with role weights, synergy multipliers, CC-CDR bonuses, and enemy comp awareness
- **OCR Augment Detection** -- Tesseract-based screen reading with perceptual hashing for fast change detection (~1ms per tick)
- **Stat-Delta Matching** -- Cosine similarity on champion stat changes to auto-detect which augment was chosen
- **Build Path Suggestions** -- Dynamic item recommendations that adapt to your augments and gold
- **Reroll Advisor** -- Compares best option against champion ceiling to suggest when to reroll
- **Enemy Comp Analysis** -- CC profiling of enemies to weight defensive/offensive augments
- **Personal Winrate Tracking** -- SQLite-backed per-champion augment win rates that influence future recommendations
- **Overlay UI** -- 320px dark-themed companion panel with WebSocket live updates

## Quick Start

### Prerequisites

- Python 3.11+
- League of Legends (running an ARAM Mayhem match for live data)
- Tesseract OCR *(optional, for screen-based augment detection)*

### Install

```bash
git clone https://github.com/fabs133/league-aram-builder.git
cd league-aram-builder
pip install -e .
```

For OCR support, install Tesseract:

```bash
winget install UB-Mannheim.TesseractOCR
```

### Run

```bash
# Start the server (polls game API, serves overlay)
python -m backend.main

# Open the overlay in your browser
# http://localhost:8765/overlay
```

The overlay connects via WebSocket and updates automatically when a game is detected.

### Optional: Desktop Overlay

```bash
# PyQt6 overlay (click-through window on top of game)
pip install -e ".[overlay]"
python -m backend.overlay

# Or lightweight pywebview overlay
pip install -e ".[webview-overlay]"
python -m backend.overlay
```

### In-game augment options or build items are missing?

If the overlay badge reads **NO OCR**, the local Tesseract executable could
not be launched. Install Tesseract OCR (separately from the Python packages)
and restart the overlay:

```powershell
winget install --id UB-Mannheim.TesseractOCR --exact
Test-Path 'C:\Program Files\Tesseract-OCR\tesseract.exe'
python -m backend.overlay --renderer qt
```

If installed elsewhere, set `TESSERACT_PATH` to the complete path of
`tesseract.exe` in that PowerShell session before launching.

**Manual fallback:** With the overlay visible, press **Alt+O** to enable
interaction, expand **DETECT AUGMENTS**, search for the three offered
augment names and click **Evaluate**. You can then select your actual
pick using **Choose this**. The manual fallback does not need OCR.

The build planner counts only live-client inventory slots **0–5**.
Trinket-slot objects like Poro-Snax (slot 6) are not equipment and must
not consume a build slot or contribute to enemy equipment coverage.
Different item IDs with the same catalog name are not presented as
separate build alternatives. Actual Mayhem shop eligibility, component
costs and contextual item ranking still need match-level verification.

### Windows overlay has a white background?

The lightweight pywebview/Edge WebView2 backend can render a white rectangle
instead of transparent unused space on some Windows/WebView2 combinations.
This is a native compositor issue; changing the CSS alone will not necessarily
fix it. The launcher defaults to pywebview for backward compatibility.

Try the **PyQt6 transparency fallback** without uninstalling pywebview:

```powershell
python -m pip install -e ".[overlay]"
python -m backend.overlay --renderer qt
```

With either backend, press **Alt+O** to toggle click-through and interact with
the overlay controls, then press it again to return mouse input to the game.

In the **Qt renderer**, the top-right **−** button hides the overlay without
stopping the engine, and **×** quits the application. To click these buttons,
first press **Alt+O** to disable click-through. Press **Alt+H** at any time to
show/hide the overlay (including while League has focus). A Windows notification
area (system tray) icon also has **Show/Hide overlay**, **Toggle interaction**
and **Quit overlay** commands; double-clicking its icon shows/hides the window.
If the Windows notification area is unavailable, the **Alt+H** shortcut still
works. Hiding is different from quitting: to reopen after quitting, run the
launch command again.

If a window shows "Waiting for game..." outside a match, that is normal;
it is not evidence of failed transparency or working in-game detection.

To explicitly compare the original WebView2 renderer:

```powershell
python -m backend.overlay --renderer webview
```

Close the previous overlay before launching another renderer. If Qt also
shows a white background or fails to start, report the terminal message and
Windows screenshot; neither backend is guaranteed without on-device testing.

## Champion Select — experimental composite rating

During ARAM champion select, the app reads the local League Client API
(read-only). It displays your current champion and the visible ARAM bench,
together with explanations of how they complement allied team roles.
It never changes your selection.

**Important:** The 0.0–10.0 score and S/A/B/C labels represent an
*experimental composite rating*, not a win-rate percentage, prediction of
winning, or verified champion-strength ranking. It combines champion kit
compatibility (35%), allied team fit (25%), and empirical personal match
performance (up to 40% when sufficient samples exist). Statistical confidence
gradually increases the weight of match evidence. Missing evidence is excluded,
not replaced by invented data. No augment win rates are displayed.

Champion IDs are resolved using a local read-only champion-summary asset.
If the client data are unavailable, the app does not invent ratings.

When the Champion Select panel is visible, **Sync my Mayhem matches** reads
up to 40 recent games from the local League client, with an explicit click.
The read-only importer identifies only the logged-in player's participant
record and stores outcomes, augments, and final items in local SQLite.
It never returns PUUIDs or opponent player IDs to the overlay.

No automatic external match uploads occur as part of the importer. The sample
size is shown alongside the composite rating, and the 0.0–10.0 rating is not
equivalent to an empirical win percentage.

If the overlay remains on "Waiting for game..." during champion select, open
http://127.0.0.1:8765/api/champ-select/status to check detection (no account
names or client credentials are returned).

For a non-default League installation, set an override to your actual lockfile
path in the same PowerShell terminal before launching the overlay:

    $env:ARAM_ORACLE_LCU_LOCKFILE = "D:\Riot Games\League of Legends\lockfile"
    python -m backend.overlay

The lockfile exists only while the League client is running.

**Riot policy:** The League Developer Policy prohibits displaying augment win
rates and apps that dictate player decisions. Keep this as a private prototype
until the complete experience is registered/reviewed through the Riot Developer
Portal. This screen shows several explained alternatives rather than
automatically choosing a champion.

## Experimental augment score (0.0–10.0)

The augment panel now uses an **absolute 0.0–10.0 composite rating**:
- Champion-kit and already selected augment fit, using the existing
  ARAM Oracle scoring engine.
- Enemy composition from the Live Client Data API, where available.
- An optional *personal* match-history component, confidence-shrunk by
  sample size (minimum 5 games). Missing performance evidence is excluded.

The scoring engine uses a bounded nonlinear normalization of its heuristic
output, **not a transformation of win rate into a 0–10 number**.
A very weak offer does not automatically receive 10/10 because it is the
best of three. Rerolls use a provisional absolute-fit threshold; this is
not a mathematical estimate of future reroll outcomes.

The feature flag `experimental_augment_evidence` is **false by default**.
Only enable it after the app's live recommendation behavior has been reviewed
against Riot's current requirements. This private prototype is not a claim
of Riot approval, and it does not show raw augment win rates.

## Dynamic enemy and allied-team context (experimental)

The shared game-state pipeline now considers known allied champion roles and
the opponent champions, items, and kill/death figures that League's local
Live Client API already exposes to the player. Unknown or hidden champions
and items are **never guessed**.

- Enemy Threat Profile: tank-like frontline, CC, burst, sustain, shields,
  visible armor/magic resistance items, and high-kill opponents.
- Ally Profile: known frontline, magic damage roles, physical damage roles,
  and utility role coverage.
- The **same profiles** influence augment context and the item build planner.
  The build panel presents Balanced (default), Damage, Survival, and Utility
  routes, while preserving items you already own.
- Estimated pressure values are **kit-based heuristics, not observed damage
  percentages**. Known enemy items are counted only when matched in the
  local item catalogue. The scores still require calibration with Mayhem
  gameplay data; no win chances are asserted.
- The normal item catalogue currently cannot prove every Mayhem shop or
  quest constraint. Strict item-buyability, component paths, and conditional
  augment requirements remain follow-up validation tasks.

All new code was independently implemented from our own product specification.
Mayhem Advisor was examined only as a **functionality reference**. Its
all-rights-reserved source, assets, algorithms, and wording were not copied.

## Architecture

```
League Client (port 2999)
       |
       v
  +-----------+     +-------------+     +----------+
  | Collectors |---->|   Engine    |---->| Pipeline |
  | lcda.py   |     | scoring.py  |     |          |
  | screen_ocr|     | ranker.py   |     +----+-----+
  +-----------+     | augment_det.|          |
                    | build_sugg. |          v
                    +-------------+     +----------+     +-----------+
                                        | FastAPI  |---->| Frontend  |
                                        | server.py|     | (overlay) |
                                        | /ws/game |     +-----------+
                                        +----------+
                                             |
                                             v
                                        +----------+
                                        | SQLite   |
                                        | winrates |
                                        +----------+
```

| Layer | Description |
|-------|-------------|
| **Collectors** | Poll Live Client Data API, OCR screen capture, LCU client |
| **Engine** | Pure scoring functions -- dot products on stat vectors, overlap penalties, scaling specs |
| **Pipeline** | Orchestrates engine calls, resolves augment/item/champion data |
| **API** | FastAPI + WebSocket server, augment detection state machine, poll loop |
| **Frontend** | Vanilla HTML/CSS/JS overlay, 320px dark layout, WS-driven updates |
| **Storage** | SQLite personal winrate tracking, game history |

## Configuration

Create `~/.aram-oracle/config.toml` (all values are optional):

```toml
[server]
port = 8765
poll_interval = 2.0

[ocr]
match_threshold = 65          # Fuzzy match score (0-100)
hash_change_threshold = 30    # Perceptual hash sensitivity
# ocr_region = [0.15, 0.22, 0.85, 0.50]  # Custom screen region

[augment_detector]
confidence_threshold = 0.3    # Minimum cosine similarity for auto-confirm
confidence_gap = 0.05         # Min gap between best and second-best

[overlay]
overlay_width = 320

[github]
# github_token = "ghp_..."   # For automatic bug report filing
# github_repo = "owner/repo"
```

## Tech Stack

- **Backend:** Python 3.11, FastAPI, WebSocket, NumPy, aiosqlite
- **OCR:** Tesseract, Pillow, rapidfuzz
- **Overlay:** PyQt6 / pywebview (optional)
- **Data Sources:** Riot DataDragon, CommunityDragon
- **Packaging:** PyInstaller

## Anti-Cheat Compliance

ARAM Oracle only reads data from Riot's officially sanctioned **Live Client Data API** (`https://127.0.0.1:2999`). It does not inject code, modify game memory, or interact with the game process. This is the same API used by approved third-party tools like Overwolf apps.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding conventions, and how to submit changes.

## License

[MIT](LICENSE) -- see the LICENSE file for details.
