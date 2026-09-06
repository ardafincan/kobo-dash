# Kobo Clara 2E E-Ink Dashboard — Build Instructions

Instructions for Claude Code. Read this file fully before you write any code.

---

## 0. Scope and rules

You will build a dashboard system in two phases.

**Phase 1 — Server.** You build this yourself on the Mac Mini. You have full
control. Finish it completely and verify it before you move on.

**Phase 2 — Device.** You cannot touch the Kobo. It is not on the network and
you have no shell on it. Your job in Phase 2 is to **guide the user through each
step and wait for confirmation** before you give the next one.

**Rules for Phase 2:**

- Give one step at a time. Do not dump the whole procedure.
- After each step, ask the user what they saw. Wait for their answer.
- Do not proceed past a gate check that failed.
- Do not invent device commands. Where this document says to copy a script from
  an upstream project, tell the user to copy it. Do not write your own.

---

## 1. Locked decisions

These are already decided. Do not re-open them or propose alternatives.

| Item | Decision |
|---|---|
| Device | Kobo Clara 2E (codename `goldfinch`), i.MX SoC, not MediaTek |
| Panel | 1072 x 1448 px native portrait, 6", 300 ppi, 16 grey levels |
| Orientation | **Landscape.** Draw at 1448 x 1072, rotate at write time |
| Screens | 3 rendered: `day`, `news`, `quote` |
| Sequence | 4 slots: `day, news, day, quote` |
| Display cycle | 5 minutes |
| Fetch cycle | 15 minutes |
| Server | Mac Mini M4, headless, always on |
| Transport | Plain HTTP over LAN. **Do not use Tailscale on the Kobo.** |
| Dithering | **None.** Quantize to 16 levels only. |
| Error handling | Per-region "can't fetch". Never a full-screen error. |

---

## 2. Screen contents

**`day`** — calendar agenda plus weather, merged. Weather occupies a fixed-width
left column. The agenda fills the right column. A last-updated timestamp sits in
the bottom right.

**`news`** — Hacker News top 5. Headlines only. No URLs, no scores, no comments.

**`quote`** — one quote, large, centred, from a local file.

---

## 3. Phase 1 — Server

### 3.1 Project layout

```
kobo-dash/
  config.toml            # user secrets and settings. gitignored.
  config.example.toml    # committed template
  quotes.json            # local quote list
  assets/fonts/          # Inter or IBM Plex Sans, Medium + SemiBold
  src/
    __init__.py
    config.py            # load and validate config.toml
    theme.py             # ALL layout constants. See 3.4.
    render.py            # canvas helpers, text, rotation, quantization
    screens/
      day.py
      news.py
      quote.py
    sources/
      weather.py
      calendar.py
      hn.py
      quotes.py
    main.py              # entry point
  out/                   # rendered PNGs + manifest.json. gitignored.
  preview/               # preview renders for the MacBook. gitignored.
```

Use Python 3.11+. Use `uv` if available, otherwise a venv. Dependencies:
`pillow`, `requests`, `icalendar`, `tomli` (or stdlib `tomllib`).

### 3.2 Ask the user for these before you start

Do not guess them.

1. **Google Calendar private ICS URL.** Not the API. Google Calendar exposes a
   secret iCal address per calendar under calendar settings. There is no OAuth
   and no token to expire. Tell the user to treat this URL as a password.
2. **Latitude and longitude** for weather. Their location is Istanbul, so
   `41.0082, 28.9784` is a reasonable default — confirm it.
3. **Timezone string.** Likely `Europe/Istanbul`.
4. **The LAN IP of the Mac Mini.** Needed later in Phase 2.

Write these into `config.toml`. Commit `config.example.toml` with placeholders.
Add `config.toml`, `out/`, and `preview/` to `.gitignore`.

### 3.3 Data sources

**Weather — Open-Meteo.** No API key. One request returns current conditions
plus hourly and daily forecast.

```
https://api.open-meteo.com/v1/forecast
  ?latitude=..&longitude=..
  &current=temperature_2m,weather_code
  &daily=temperature_2m_max,temperature_2m_min,weather_code
  &timezone=Europe/Istanbul
```

Map WMO weather codes to a small set of your own condition names. Do not try to
cover all codes with distinct glyphs. Group them: clear, cloudy, rain, snow,
storm, fog.

**Calendar — the ICS URL.** `requests.get`, then parse with `icalendar`. Filter
to events on today's date in the configured timezone. Handle all-day events
(they use `date` not `datetime`) — this will crash your code if you ignore it.
Sort by start time. Recurring events need `rrule` expansion; if that is too much
for v1, note the limitation to the user rather than silently dropping them.

**News — Hacker News Firebase API.** No key, no auth.

1. `GET https://hacker-news.firebaseio.com/v0/topstories.json` → ranked ID array.
2. Take the first 5.
3. `GET https://hacker-news.firebaseio.com/v0/item/{id}.json` for each.
4. Read the `title` field only.

Six requests per cycle. Note that Ask HN and Show HN items have no `url` field.
This does not matter here, but do not write code that assumes it exists.

**Quotes — local.** `quotes.json` is a flat array of `{text, author}`. Select
deterministically by date so the quote is stable all day:

```python
idx = int(hashlib.md5(date.today().isoformat().encode()).hexdigest(), 16) % len(quotes)
```

Do not use a quotes API. They go down and change terms, and the failure mode is
a blank screen.

### 3.4 `theme.py` — shared constants

Every screen imports from here. No screen module defines its own sizes.

If each screen grows its own type scale, text will visibly jump position between
rotation steps. On a flashing e-ink refresh that jump is very obvious.

```python
CANVAS_W, CANVAS_H = 1448, 1072    # landscape drawing canvas
MARGIN = 40
USABLE_W = CANVAS_W - 2 * MARGIN   # 1368
USABLE_H = CANVAS_H - 2 * MARGIN   # 992

GREY_LEVELS = 16

# type scale
SIZE_HERO   = 180   # big temperature
SIZE_H1     = 96
SIZE_H2     = 60    # news headlines
SIZE_BODY   = 44
SIZE_SMALL  = 28    # timestamp, source labels

# greys (0 = black, 255 = white)
INK        = 0
INK_MUTED  = 96
RULE       = 160
PAPER      = 255
```

### 3.5 Layout specifications

All coordinates are on the 1448 x 1072 landscape canvas.

**`day` — two columns**

- Weather column: x 40 to 480 (440 wide).
  - Temperature at `SIZE_HERO`, top of column.
  - Condition glyph, about 160 px.
  - Hi/Lo below at `SIZE_BODY`.
  - Three-day forecast strip stacked vertically at `SIZE_SMALL`.
- Vertical rule at x 500, 1 px wide, colour `RULE`.
- Agenda column: x 540 to 1408 (868 wide).
  - Rows of 100 px. Fits 9 events.
  - Time on the left of the row, title to its right, truncated with an ellipsis.
- Last-updated timestamp, bottom right, `SIZE_SMALL`, colour `INK_MUTED`.

**`news` — five fixed slots**

Header 110 px. Then five slots of 176 px each. 110 + 880 = 990, which fits 992.

- Each slot: two lines at `SIZE_H2` (60 px), 72 px leading, 32 px gap after.
- Rank number in a 70 px left gutter, colour `INK_MUTED`.
- Text area is therefore about 1298 px wide, which is roughly 45 characters per
  line at 60 px. Two lines covers about 90 characters. HN caps titles at 80, so
  nearly every headline fits.
- **Slots are fixed height.** If a title overflows two lines, truncate with an
  ellipsis. Never let slot height vary — the screen stops being scannable.

**`quote`**

- Constrain the text block to about 1000 px wide, centred. Do not use the full
  1368 px. Target 45 to 70 characters per line.
- Quote at `SIZE_H1` (96 px), or drop to 72 px if the quote is long.
- Author below, `SIZE_BODY`, colour `INK_MUTED`.
- Whitespace is the point of this screen. Do not fill it.

### 3.6 Rendering rules

**Mode.** Create canvases as `Image.new("L", (1448, 1072), PAPER)`. Greyscale
throughout. Never RGB.

**Fonts.** Download Inter or IBM Plex Sans into `assets/fonts/`. Use a **Medium
or SemiBold** weight for body text. E-ink contrast is lower than paper and
Regular weights look washed out at a glance. Do not rely on macOS system fonts —
the render must be reproducible.

**Quantization — no dithering.** These screens are pure text. Error-diffusion
dithering scatters noise into antialiased glyph edges and makes text fuzzy. With
16 levels available, antialiased text maps cleanly to the nearest level.

```python
img = img.quantize(colors=16, dither=Image.Dither.NONE).convert("L")
```

Render at 1x. Do not supersample. Let the font rasterizer antialias.

**Icons.** If you draw weather glyphs, use solid high-contrast line art or a
weather icon font. Do not use photographic or gradient icons. They break down on
16 levels. One large glyph at 160 px reads from across the room; a detailed 64 px
icon does not.

**Rotation is the last step.** Draw landscape, rotate to portrait on write.

```python
img.transpose(Image.ROTATE_90).save(path)
```

FBInk sees a portrait framebuffer. The rotation is purely an output transform.
The direction depends on which side the user wants the USB-C port. This is
verified in Phase 2, step 4 — leave it configurable in `config.toml` as
`rotate = 90` or `rotate = 270`.

### 3.7 Error handling — per region

This is the part people get wrong. A single Wi-Fi blip must not blank a
dashboard whose other data is fine.

- Each source function returns either data or a failure marker. It never raises
  out to the caller.
- If the calendar fetch fails, the **agenda region** renders "can't fetch". The
  weather region still renders normally.
- If weather fails, the **weather column** renders "can't fetch". The agenda is
  unaffected.
- If HN fails, the news screen renders "can't fetch" in the list area. The day
  screen is untouched.
- The quote is local and cannot fail over the network.
- **Never render a full-screen error, and never skip a screen.** The rotation
  always has three images.

The last-updated timestamp on the day screen is what makes stale data safe. Do
not omit it.

### 3.8 Output and manifest

Write to `out/`:

```
out/day.png
out/news.png
out/quote.png
out/manifest.json
```

`manifest.json`:

```json
{
  "hash": "sha256 of the three PNG files concatenated",
  "sequence": ["day.png", "news.png", "day.png", "quote.png"],
  "generated_at": "2026-09-06T14:15:00+03:00"
}
```

**The sequence lives here, not on the device.** The user changes the rotation by
editing this list on the server. No redeploy to the reader. They will change this
more often than they expect.

Write to a temp file and `os.replace` into place, so the device never fetches a
half-written PNG.

### 3.9 Preview mode

Add `--preview` to `main.py`. It writes to `preview/` instead of `out/`, skips
rotation, and draws a 1 px border plus a light grey background around the canvas
so the user can see the panel edges.

The user will do fifty render iterations on the MacBook and about five device
tests. Make the fast loop good.

### 3.10 Scheduling and serving

Two launchd jobs on the Mac Mini.

1. **Renderer**, `StartInterval` 900. Runs `main.py`.
2. **Static server**, `KeepAlive` true. Serves `out/` on a port, bound to the LAN.
   `python -m http.server` is acceptable. Bind explicitly; do not expose it
   beyond the LAN.

Write the plists, tell the user where they are, and give them the `launchctl`
commands to load them.

### 3.11 Phase 1 gate check

Do not move to Phase 2 until all of these pass.

- [ ] `main.py --preview` produces three PNGs that look correct on the MacBook.
- [ ] Every PNG is exactly 1072 x 1448 in `out/` (portrait, after rotation).
- [ ] Killing the network mid-run produces per-region "can't fetch", not a crash
      and not a blank screen.
- [ ] An empty calendar day renders a deliberate state, not an empty box.
- [ ] `curl http://<mac-mini-ip>:<port>/manifest.json` works from the MacBook.
- [ ] The renderer has run unattended for at least an hour on its timer.

---

## 4. Phase 2 — Device

Stop. Read section 0 again. You are guiding, not executing.

Tell the user upfront: the whole procedure takes about two hours, and the first
step is a test that may end the project early. Better to find that out now.

### Step 1 — GATE: the Wi-Fi toggle test

**Nothing else happens until this passes.**

The Clara 2E has a reported history of freezing when Wi-Fi is turned off. One
tester needed a full factory reset. The design toggles Wi-Fi 96 times a day, so
this path must be proven first.

Guide the user to:

1. Install NickelMenu. Copy `KoboRoot.tgz` into the `.kobo` folder on the device
   over USB, eject, and reboot. A NickelMenu entry appears in the menu.
2. Get a shell on the device (telnet or SSH, via developer options).
3. Obtain the Wi-Fi scripts. **Do not write these.** Copy `enable-wifi.sh` and
   `disable-wifi.sh` from the KOReader repo, or from `usetrmnl/trmnl-kobo`,
   which already borrowed them. Verify the current paths in those repos.
4. Loop the on/off cycle 20 times with a sleep between each.

**If it hangs:** stop. Tell the user the options are (a) leave Wi-Fi on
permanently and accept much shorter battery life, or (b) abandon suspend and run
the device on USB power. Do not proceed as if it passed.

**If it passes:** continue.

### Step 2 — Install FBInk and curl

Guide the user to install, each as a `KoboRoot.tgz` into `.kobo`:

- **FBInk** (NiLuJe). This is what actually draws to the panel.
- **KoboStuff** (NiLuJe), for `curl`.

Verify with `fbink -h` over the shell.

### Step 3 — GATE: one static PNG on the panel

Have the user copy one rendered PNG to the device and run:

```
fbink -f -c -g file=/tmp/test.png
```

`-f` forces a full refresh. `-c` clears first. Use both on every draw — the whole
image changes each cycle, and a partial update will ghost.

Ask the user to confirm: does the image fill the screen, and is it the right way
up?

### Step 4 — Fix the rotation direction

If the image is upside down or the USB-C port is on the wrong side, change
`rotate` in `config.toml` from 90 to 270 and re-render.

Suggest the user render a test PNG with "TOP" printed on it. This takes one
minute now and saves confusion later.

### Step 5 — Frontlight and LED off

The frontlight is the largest single power draw. Have the user turn it off in
the Nickel UI before launching the dashboard.

Note that the Clara 2E controls frontlight intensity and warmth differently from
older Kobos, so setting it in the UI is more reliable than writing to sysfs.

The top-right LED stays lit outside standby. Setting the LED output device to 0
turns it off.

### Step 6 — The loop script

Now write the device script. Place it under `/mnt/onboard/.adds/dash/`.

```
loop:
  if (now - last_fetch) > 900:
      enable-wifi.sh
      fetch manifest.json
      if hash changed:
          fetch each PNG in sequence into /tmp/screens/
      disable-wifi.sh
      last_fetch = now
  fbink -f -c -g file=/tmp/screens/${sequence[i]}
  i = (i + 1) % len(sequence)
  sleep 300
```

Notes:

- Write PNGs to `/tmp`. It is tmpfs, so you avoid eMMC wear from writing every
  15 minutes, and it survives suspend.
- If the manifest fetch fails, **keep the existing files and keep rotating.**
  Never blank the screen. Never exit the loop on a network error.
- Read the sequence from the manifest. Do not hardcode it.
- Use plain `sleep` at this stage, not `rtcwake`.

### Step 7 — Add the NickelMenu entry

In `.adds/nm/config`:

```
menu_item :main :Dashboard :cmd_spawn :/mnt/onboard/.adds/dash/run.sh
```

Keep it as a manual launch. **Do not auto-start at boot yet.**

The script kills `nickel`, so NickelMenu is gone while the dashboard runs. The
recovery path is a hard reset: hold power for about 30 seconds. Because the
dashboard only starts when tapped, the device always boots back to normal
firmware. That safety net disappears the moment you auto-start it.

### Step 8 — Run it for a week on USB power

Do not add suspend yet. Let it run on the charger with plain `sleep`.

Have the user log battery capacity on each cycle from
`/sys/class/power_supply/battery/capacity`. Full charge is about 1400 mAh
(`charge_full_design` reads roughly 1406000 µAh).

What you are looking for: does it survive a week without intervention? Does it
recover from Wi-Fi dropping overnight? Does the screen ghost?

### Step 9 — Add `rtcwake`, last

Only after step 8 has run clean.

Replace `sleep 300` with an RTC wake alarm and suspend. **Do not write this
yourself.** `usetrmnl/trmnl-kobo` ships a patched `rtcwake` binary for the Kobo
and a working sleep/wake cycle. Copy their approach.

Expected result: two of every three wakes are about 2 seconds long (wake, draw,
suspend). Only the third adds Wi-Fi. That should give **one to two weeks on
battery**. This is an estimate. The battery log from step 8 gives the real curve.

### Step 10 — Auto-start, optional

Only after the whole thing has run a week on battery without intervention.
Explain the recovery trade-off from step 7 before the user commits.

---

## 5. Things that are already decided — do not propose these

- Screenshotting a webpage with headless Chromium. Rejected. Pillow renders
  these layouts directly with no browser dependency.
- Using the Kobo's built-in browser. Rejected. It is an ancient WebKit build, it
  blocks device suspend, and it gives no control over the e-ink refresh.
- Dithering the text screens. Rejected. See 3.6.
- Tailscale on the Kobo. Rejected. Old glibc, painful toolchain. LAN only.
- A separate server-status screen. Cut deliberately.
- A stock ticker screen. Replaced by news deliberately.
- Auto-starting at boot in v1. Deferred to step 10.
