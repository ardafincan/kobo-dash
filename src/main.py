"""Render the three dashboard screens and write out/ + manifest.json.

Usage:
    python -m src.main            # render to out/ (rotated portrait) + manifest
    python -m src.main --preview  # render to preview/ (landscape, framed)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config, render
from .screens import day, news, quote
from .sources import calendar, hn, quotes, weather

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
PREVIEW_DIR = ROOT / "preview"

# The three distinct rendered screens (the sequence may repeat these).
SCREENS = ("day.png", "news.png", "quote.png")


def _status(name: str, r) -> str:
    return f"  {name:9} {'ok' if r.ok else 'FAIL: ' + (r.error or '')}"


def _write_manifest(cfg: config.Config, generated_at: str) -> None:
    h = hashlib.sha256()
    for name in SCREENS:
        h.update((OUT_DIR / name).read_bytes())

    manifest = {
        "hash": h.hexdigest(),
        "sequence": cfg.sequence,
        "generated_at": generated_at,
    }
    tmp = OUT_DIR / "manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, OUT_DIR / "manifest.json")   # atomic


def run(cfg: config.Config, preview: bool) -> None:
    tz = ZoneInfo(cfg.timezone)
    now = datetime.now(tz)

    # Fetch every source. None of these raise; each returns ok/fail.
    w = weather.fetch(cfg.latitude, cfg.longitude, cfg.timezone)
    c = calendar.fetch_days(cfg.ics_url, cfg.timezone, num_days=3)
    hnews = hn.fetch()
    q = quotes.fetch(now.date())

    print("sources:")
    print(_status("weather", w))
    print(_status("calendar", c))
    print(_status("hn", hnews))
    print(_status("quotes", q))

    images = {
        "day.png": day.render_screen(w, c, now),
        "news.png": news.render_screen(hnews),
        "quote.png": quote.render_screen(q),
    }

    if preview:
        for name, img in images.items():
            render.save_preview(img, PREVIEW_DIR / name)
        print(f"\nwrote preview/ (landscape, framed): {', '.join(images)}")
    else:
        for name, img in images.items():
            render.save_final(img, OUT_DIR / name, cfg.rotate)
        _write_manifest(cfg, now.isoformat(timespec="seconds"))
        print(f"\nwrote out/ (portrait, rotate={cfg.rotate}) + manifest.json")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Render the Kobo dashboard screens.")
    p.add_argument("--preview", action="store_true",
                   help="write to preview/ without rotation, framed for the MacBook")
    args = p.parse_args(argv)

    try:
        cfg = config.load()
    except config.ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 1

    run(cfg, preview=args.preview)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
