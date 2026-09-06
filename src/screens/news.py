"""`news` screen: Hacker News top 5. Headlines only.

Slots are FIXED height. A title that overflows two lines is truncated with an
ellipsis — slot height never varies, or the screen stops being scannable.
"""

from __future__ import annotations

from PIL import Image

from .. import render
from ..render import text, wrap
from ..sources import CANT_FETCH, Result
from ..theme import (
    CANVAS_H,
    CANVAS_W,
    INK,
    INK_MUTED,
    MARGIN,
    RULE,
    SIZE_H1,
    SIZE_H2,
    font,
)

HEADER_H = 110
SLOT_H = 176
GUTTER = 70
LEADING = 72          # baseline-to-baseline within a slot
LINE_TOP = 10         # padding from slot top to first line
TEXT_X = MARGIN + GUTTER
TEXT_W = CANVAS_W - MARGIN - TEXT_X   # ~1298


def render_screen(hn: Result[list[str]]) -> Image.Image:
    img, draw = render.new_canvas()

    # Header.
    text(draw, (MARGIN, MARGIN), "Hacker News", font=font(SIZE_H1, bold=True), fill=INK)
    render.hrule(draw, MARGIN + HEADER_H - 12, MARGIN, CANVAS_W - MARGIN, fill=RULE, width=1)

    slots_top = MARGIN + HEADER_H

    if not hn.ok:
        text(draw, (CANVAS_W // 2, CANVAS_H // 2), CANT_FETCH,
             font=font(SIZE_H2, bold=True), fill=INK_MUTED, anchor="mm")
        return img

    title_f = font(SIZE_H2)
    rank_f = font(SIZE_H2, bold=True)
    for i, headline in enumerate(hn.value[:5]):
        slot_top = slots_top + i * SLOT_H
        # Rank in the left gutter.
        text(draw, (MARGIN, slot_top + LINE_TOP), str(i + 1), font=rank_f, fill=INK_MUTED)
        # Up to two lines, truncated on overflow.
        lines = wrap(title_f, headline, TEXT_W, max_lines=2)
        for j, line in enumerate(lines):
            text(draw, (TEXT_X, slot_top + LINE_TOP + j * LEADING), line,
                 font=title_f, fill=INK)

    return img
