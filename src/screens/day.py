"""`day` screen: weather (fixed left column) + agenda (right column).

Per-region failure: if weather fails only the weather column says "can't fetch";
if the calendar fails only the agenda says so. Neither blanks the other. The
last-updated timestamp bottom-right is what makes stale data safe.
"""

from __future__ import annotations

from datetime import datetime

from PIL import Image

from .. import render
from ..render import text, truncate
from ..sources import CANT_FETCH, Result
from ..sources.calendar import Event
from ..sources.weather import Weather
from ..theme import (
    CANVAS_H,
    CANVAS_W,
    INK,
    INK_MUTED,
    MARGIN,
    RULE,
    SIZE_BODY,
    SIZE_HERO,
    SIZE_SMALL,
    font,
)

# Weather column: x 40..480. Rule at x 500. Agenda column: x 540..1408.
WX0 = MARGIN                 # 40
WCOL_W = 440
WCX = WX0 + WCOL_W // 2      # 260
RULE_X = 500
AX0 = 540
AX1 = CANVAS_W - MARGIN      # 1408
AGENDA_W = AX1 - AX0         # 868

ROW_H = 100
MAX_ROWS = 9
TIME_COL_W = 150


def _cant_fetch(draw, x0: int, x1: int, cy: int) -> None:
    f = font(SIZE_BODY, bold=True)
    text(draw, ((x0 + x1) // 2, cy), CANT_FETCH, font=f, fill=INK_MUTED, anchor="mm")


def _draw_weather(draw, w: Weather) -> None:
    y = MARGIN
    # Current temperature, hero size.
    text(draw, (WX0, y), f"{w.temp}°", font=font(SIZE_HERO, bold=True), fill=INK)
    y += SIZE_HERO + 10

    # Condition glyph, centred in the column.
    glyph = 160
    render.weather_glyph(draw, WCX, y + glyph // 2, glyph, w.condition, fill=INK)
    y += glyph + 20

    # Condition name.
    text(draw, (WX0, y), w.condition.title(), font=font(SIZE_BODY, bold=True), fill=INK)
    y += SIZE_BODY + 12

    # Hi / Lo.
    text(draw, (WX0, y), f"H {w.today_hi}°   L {w.today_lo}°",
         font=font(SIZE_BODY), fill=INK_MUTED)
    y += SIZE_BODY + 24

    # Three-day forecast strip, stacked.
    small = font(SIZE_SMALL)
    small_b = font(SIZE_SMALL, bold=True)
    for d in w.forecast:
        text(draw, (WX0, y), d.label, font=small_b, fill=INK)
        text(draw, (WX0 + 90, y), f"{d.hi}° / {d.lo}°", font=small, fill=INK_MUTED)
        text(draw, (WX0 + WCOL_W, y), d.condition, font=small, fill=INK_MUTED, anchor="ra")
        y += SIZE_SMALL + 14


def _draw_agenda(draw, events: list[Event]) -> None:
    if not events:
        # Deliberate empty state — never an empty box.
        text(draw, ((AX0 + AX1) // 2, MARGIN + 3 * ROW_H),
             "Nothing scheduled", font=font(SIZE_BODY, bold=True),
             fill=INK_MUTED, anchor="mm")
        return

    # Reserve the last row for a "+N more" summary if we overflow.
    rows = events[:MAX_ROWS]
    overflow = len(events) - len(rows)
    if overflow > 0:
        rows = events[: MAX_ROWS - 1]
        overflow = len(events) - len(rows)

    time_f = font(SIZE_BODY, bold=True)
    title_f = font(SIZE_BODY)
    title_x = AX0 + TIME_COL_W
    title_w = AX1 - title_x

    y = MARGIN
    for ev in rows:
        cy = y + ROW_H // 2
        if ev.all_day:
            text(draw, (AX0, cy), "all day", font=font(SIZE_SMALL, bold=True),
                 fill=INK_MUTED, anchor="lm")
        else:
            text(draw, (AX0, cy), ev.start.strftime("%H:%M"), font=time_f,
                 fill=INK, anchor="lm")
        text(draw, (title_x, cy), truncate(title_f, ev.title, title_w),
             font=title_f, fill=INK, anchor="lm")
        render.hrule(draw, y + ROW_H, AX0, AX1, fill=RULE, width=1)
        y += ROW_H

    if overflow > 0:
        cy = y + ROW_H // 2
        text(draw, (AX0, cy), f"+{overflow} more", font=font(SIZE_SMALL, bold=True),
             fill=INK_MUTED, anchor="lm")


def render_screen(weather: Result[Weather], calendar: Result[list[Event]],
                  now: datetime) -> Image.Image:
    img, draw = render.new_canvas()

    if weather.ok:
        _draw_weather(draw, weather.value)
    else:
        _cant_fetch(draw, WX0, WX0 + WCOL_W, CANVAS_H // 2)

    render.vrule(draw, RULE_X, MARGIN, CANVAS_H - MARGIN, fill=RULE, width=1)

    if calendar.ok:
        _draw_agenda(draw, calendar.value)
    else:
        _cant_fetch(draw, AX0, AX1, CANVAS_H // 2)

    # Last-updated timestamp, bottom right.
    stamp = "Updated " + now.strftime("%a %d %b %H:%M")
    text(draw, (CANVAS_W - MARGIN, CANVAS_H - MARGIN), stamp,
         font=font(SIZE_SMALL), fill=INK_MUTED, anchor="rd")

    return img
