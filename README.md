# kobo-dash

E-ink dashboard for a Kobo Clara 2E. A Mac Mini renders three greyscale screens
(`day`, `news`, `quote`), rotates them to portrait, and serves them over the LAN.
The Kobo fetches and displays them on a timer. This repo is **Phase 1: the
server.** Phase 2 (the device) is a guided manual procedure — see `INSTRUCTIONS.md`.

## Screens

- **day** — weather (fixed left column: current temp + glyph, condition, hi/lo,
  sunrise/sunset, 3-day forecast, and an hourly strip) + a 3-day calendar agenda
  (right column, grouped by day), with a last-updated timestamp bottom-right.
- **news** — Hacker News top 5, headlines only, five fixed-height slots.
- **quote** — one quote of the day, large and centred, from `quotes.json`.

All three render on a 1448x1072 landscape canvas, quantized to 16 grey levels
(no dithering), then rotated to 1072x1448 portrait on write.

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

    uv sync                              # install deps into .venv
    cp config.example.toml config.toml   # then fill in real values

`config.toml` holds secrets (the calendar ICS URL) and is gitignored.

## Rendering

    uv run python -m src.main            # -> out/  (portrait PNGs + manifest.json)
    uv run python -m src.main --preview  # -> preview/ (landscape, framed, no rotation)

Use `--preview` for fast layout iteration on the MacBook. Previews are landscape
with a 1px border and grey surround so panel edges are visible.

`uv run python -m src.config` prints the loaded config (without the secret URL)
to sanity-check `config.toml`.

## Output

`out/` contains `day.png`, `news.png`, `quote.png`, and `manifest.json`:

    {
      "hash": "sha256 of the three PNGs concatenated",
      "sequence": ["day.png", "news.png", "day.png", "quote.png"],
      "generated_at": "2026-09-06T13:29:01+03:00"
    }

PNGs are written atomically (temp file + os.replace) so the device never fetches
a half-written image.

### Changing the rotation sequence

The **sequence lives on the server**, in `[display].sequence` of `config.toml`.
Edit it there and re-render (or wait for the next timer). The device reads the
sequence from `manifest.json`, so changing it needs **no redeploy to the Kobo**.
Slots may repeat, e.g. `["day.png", "news.png", "day.png", "quote.png"]`.

### Portrait rotation direction

`[display].rotate` is `90` or `270`. Which one depends on the side you want the
USB-C port. Verified on-device in Phase 2, step 4.

## Deploy on the Mac Mini (launchd)

Two launchd jobs: a renderer on a 15-minute timer, and a static server bound to
the LAN IP. From the project directory on the Mac Mini:

    ./deploy/install.sh      # generate + load both LaunchAgents
    ./deploy/uninstall.sh    # stop + remove them

`install.sh` fills the plist templates in `deploy/` with absolute paths and the
host/port from `config.toml`, installs them to `~/Library/LaunchAgents`, and
loads them. Logs go to `logs/render.log` and `logs/serve.log`.

Verify from the MacBook:

    curl http://<mac-mini-ip>:<port>/manifest.json

The server binds explicitly to the LAN IP and serves only `out/`. Do not expose
it beyond the LAN. **No Tailscale on the Kobo** (see `INSTRUCTIONS.md`).

## Error handling

Each data source returns data or a failure marker; it never raises. A failed
fetch renders a per-region "can't fetch" — other regions render normally and the
rotation always has three images. The quote is local and cannot fail over the
network. The last-updated timestamp on `day` is what makes stale data safe.

## Project layout

    config.toml            # secrets + settings (gitignored)
    config.example.toml    # committed template
    quotes.json            # local quote list
    assets/fonts/          # IBM Plex Sans Medium + SemiBold
    src/
      config.py            # load + validate config.toml
      theme.py             # ALL layout constants + font loading
      render.py            # canvas, text, weather glyphs, quantize, rotate, save
      screens/             # day.py, news.py, quote.py
      sources/             # weather.py, calendar.py, hn.py, quotes.py
      main.py              # entry point
    deploy/                # launchd templates + install/uninstall scripts
    out/                   # rendered PNGs + manifest.json (gitignored)
    preview/               # preview renders (gitignored)
