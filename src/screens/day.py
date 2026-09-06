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
from ..sources.calendar import DayAgenda
from ..sources.football import Match
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

TIME_COL_W = 130
DAY_HEADER_H = 64
AGENDA_ROW_H = 58
MAX_PER_DAY = 4
AGENDA_BOTTOM = CANVAS_H - MARGIN - 50   # stop above the timestamp row


def _cant_fetch(draw, x0: int, x1: int, cy: int) -> None:
    f = font(SIZE_BODY, bold=True)
    text(draw, ((x0 + x1) // 2, cy), CANT_FETCH, font=f, fill=INK_MUTED, anchor="mm")


def _tri(draw, x: int, cy: int, s: int, *, up: bool, fill: int) -> None:
    """Small filled triangle: up = sunrise, down = sunset."""
    if up:
        draw.polygon([(x, cy + s // 2), (x + s, cy + s // 2), (x + s // 2, cy - s // 2)],
                     fill=fill)
    else:
        draw.polygon([(x, cy - s // 2), (x + s, cy - s // 2), (x + s // 2, cy + s // 2)],
                     fill=fill)


def _section_rule(draw, y: int) -> None:
    render.hrule(draw, y, WX0, WX0 + WCOL_W, fill=RULE, width=1)


def _draw_weather(draw, w: Weather, football: "Result[Match] | None" = None) -> None:
    small = font(SIZE_SMALL)
    small_b = font(SIZE_SMALL, bold=True)

    y = MARGIN
    # Current temperature (hero) on the left, condition glyph to its right.
    text(draw, (WX0, y), f"{w.temp}°", font=font(SIZE_HERO, bold=True), fill=INK)
    glyph = 150
    render.weather_glyph(draw, WX0 + WCOL_W - glyph // 2 - 10, y + glyph // 2 + 8,
                         glyph, w.condition, fill=INK)
    y += SIZE_HERO + 20

    # Condition name.
    text(draw, (WX0, y), w.condition.title(), font=font(SIZE_BODY, bold=True), fill=INK)
    y += SIZE_BODY + 8

    # Hi / Lo.
    text(draw, (WX0, y), f"H {w.today_hi}°   L {w.today_lo}°",
         font=font(SIZE_BODY), fill=INK_MUTED)
    y += SIZE_BODY + 20

    # Sunrise / sunset, one row.
    cy = y + SIZE_SMALL // 2
    _tri(draw, WX0, cy, 20, up=True, fill=INK)
    text(draw, (WX0 + 32, cy), w.sunrise, font=small, fill=INK, anchor="lm")
    _tri(draw, WX0 + 210, cy, 20, up=False, fill=INK)
    text(draw, (WX0 + 242, cy), w.sunset, font=small, fill=INK, anchor="lm")
    y += SIZE_SMALL + 22

    _section_rule(draw, y)
    y += 18

    # Three-day forecast strip, stacked.
    for d in w.forecast:
        text(draw, (WX0, y), d.label, font=small_b, fill=INK)
        text(draw, (WX0 + 90, y), f"{d.hi}° / {d.lo}°", font=small, fill=INK_MUTED)
        text(draw, (WX0 + WCOL_W, y), d.condition, font=small, fill=INK_MUTED, anchor="ra")
        y += SIZE_SMALL + 14

    if w.hourly:
        y += 8
        _section_rule(draw, y)
        y += 18
        # Hourly strip: upcoming hours, stacked.
        text(draw, (WX0, y), "Next hours", font=small_b, fill=INK_MUTED)
        y += SIZE_SMALL + 12
        for h in w.hourly:
            text(draw, (WX0, y), h.label, font=small_b, fill=INK)
            text(draw, (WX0 + 130, y), f"{h.temp}°", font=small, fill=INK_MUTED)
            text(draw, (WX0 + WCOL_W, y), h.condition, font=small, fill=INK_MUTED, anchor="ra")
            y += SIZE_SMALL + 12

    # Next football fixture (optional region).
    if football is None:
        return
    y += 10
    _section_rule(draw, y)
    y += 16
    text(draw, (WX0, y), "Next match", font=small_b, fill=INK_MUTED)
    y += SIZE_SMALL + 8
    if football.ok:
        m = football.value
        line = f"{'vs' if m.is_home else 'at'} {m.opponent}"
        text(draw, (WX0, y), truncate(font(SIZE_BODY, bold=True), line, WCOL_W),
             font=font(SIZE_BODY, bold=True), fill=INK)
        y += SIZE_BODY + 6
        text(draw, (WX0, y), m.start.strftime("%a %d %b · %H:%M"), font=small, fill=INK)
        y += SIZE_SMALL + 4
        if m.league:
            text(draw, (WX0, y), truncate(small, m.league, WCOL_W), font=small, fill=INK_MUTED)
    else:
        text(draw, (WX0, y), CANT_FETCH, font=font(SIZE_BODY, bold=True), fill=INK_MUTED)


def _draw_agenda(draw, days: list[DayAgenda]) -> None:
    header_f = font(SIZE_BODY, bold=True)
    time_f = font(SIZE_SMALL, bold=True)
    title_f = font(SIZE_BODY)
    small = font(SIZE_SMALL)
    title_x = AX0 + TIME_COL_W
    title_w = AX1 - title_x

    y = MARGIN
    for da in days:
        # Need room for at least the day header before starting a new day.
        if y > AGENDA_BOTTOM - DAY_HEADER_H:
            break

        # Day header with an underline rule.
        text(draw, (AX0, y), da.label, font=header_f, fill=INK)
        render.hrule(draw, y + DAY_HEADER_H - 8, AX0, AX1, fill=RULE, width=1)
        y += DAY_HEADER_H

        if not da.events:
            # Deliberate empty state — never an empty box.
            text(draw, (AX0, y + 12), "Nothing scheduled", font=small,
                 fill=INK_MUTED, anchor="lm")
            y += AGENDA_ROW_H
        else:
            shown = da.events[:MAX_PER_DAY]
            overflow = len(da.events) - len(shown)
            for ev in shown:
                if y > AGENDA_BOTTOM - AGENDA_ROW_H:
                    break
                cy = y + AGENDA_ROW_H // 2
                if ev.all_day:
                    text(draw, (AX0, cy), "all day", font=time_f,
                         fill=INK_MUTED, anchor="lm")
                else:
                    text(draw, (AX0, cy), ev.start.strftime("%H:%M"), font=time_f,
                         fill=INK, anchor="lm")
                text(draw, (title_x, cy), truncate(title_f, ev.title, title_w),
                     font=title_f, fill=INK, anchor="lm")
                y += AGENDA_ROW_H
            if overflow > 0:
                text(draw, (AX0, y + 8), f"+{overflow} more", font=time_f,
                     fill=INK_MUTED, anchor="la")
                y += SIZE_SMALL + 16

        y += 20   # gap between days


def render_screen(weather: Result[Weather], calendar: Result[list[DayAgenda]],
                  now: datetime, football: "Result[Match] | None" = None) -> Image.Image:
    img, draw = render.new_canvas()

    if weather.ok:
        _draw_weather(draw, weather.value, football)
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
