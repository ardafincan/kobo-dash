"""`quote` screen: one quote, large, centred. Whitespace is the point."""

from __future__ import annotations

from PIL import Image

from .. import render
from ..render import text, wrap
from ..sources import CANT_FETCH, Result
from ..sources.quotes import Quote
from ..theme import (
    CANVAS_H,
    CANVAS_W,
    INK,
    INK_MUTED,
    SIZE_BODY,
    SIZE_H1,
    font,
)

BLOCK_W = 1000       # do not use the full 1368; target 45-70 chars/line
CX = CANVAS_W // 2


def render_screen(quote: Result[Quote]) -> Image.Image:
    img, draw = render.new_canvas()

    if not quote.ok:
        text(draw, (CX, CANVAS_H // 2), CANT_FETCH,
             font=font(SIZE_H1, bold=True), fill=INK_MUTED, anchor="mm")
        return img

    q = quote.value

    # Start at H1; drop to 72 if the quote is long.
    size = SIZE_H1
    qf = font(size, bold=True)
    lines = wrap(qf, f"“{q.text}”", BLOCK_W, max_lines=6)
    if len(lines) > 4:
        size = 72
        qf = font(size, bold=True)
        lines = wrap(qf, f"“{q.text}”", BLOCK_W, max_lines=8)

    line_h = int(size * 1.3)
    author_gap = 60
    author_h = SIZE_BODY if q.author else 0
    total_h = len(lines) * line_h + (author_gap + author_h if q.author else 0)

    y = (CANVAS_H - total_h) // 2
    for line in lines:
        text(draw, (CX, y), line, font=qf, fill=INK, anchor="ma")
        y += line_h

    if q.author:
        text(draw, (CX, y + author_gap), f"— {q.author}",
             font=font(SIZE_BODY), fill=INK_MUTED, anchor="ma")

    return img
