"""Canvas helpers: text layout, weather glyphs, quantization, rotation, save.

All drawing happens on a landscape 'L' (greyscale) canvas. Rotation to portrait
is the very last step, applied only when writing to out/. Preview mode skips
rotation so the layout reads naturally on the MacBook.
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw

from . import theme
from .theme import CANVAS_H, CANVAS_W, GREY_LEVELS, INK, PAPER

ELLIPSIS = "…"


# --- canvas -----------------------------------------------------------------
def new_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("L", (CANVAS_W, CANVAS_H), PAPER)
    return img, ImageDraw.Draw(img)


# --- text -------------------------------------------------------------------
def measure(font, text: str) -> float:
    return font.getlength(text)


def text(draw, xy, s, *, font, fill=INK, anchor="la") -> None:
    draw.text(xy, s, font=font, fill=fill, anchor=anchor)


def truncate(font, s: str, max_w: float, ellipsis: str = ELLIPSIS) -> str:
    """Trim `s` to fit `max_w`, appending an ellipsis when characters are cut."""
    if measure(font, s) <= max_w:
        return s
    while s and measure(font, s + ellipsis) > max_w:
        s = s[:-1]
    return (s.rstrip() + ellipsis) if s else ellipsis


def wrap(font, s: str, max_w: float, max_lines: int) -> list[str]:
    """Word-wrap `s` into at most `max_lines`. Overflow ends with an ellipsis.

    Lines are always trimmed to `max_w` (defends against a single word that is
    itself wider than the column).
    """
    words = s.split()
    lines: list[str] = []
    cur = ""
    idx = 0
    while idx < len(words):
        w = words[idx]
        trial = f"{cur} {w}".strip()
        if not cur or measure(font, trial) <= max_w:
            cur = trial
            idx += 1
        else:
            lines.append(cur)
            cur = ""
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
        cur = ""

    overflow = idx < len(words) or cur != ""
    fitted = [truncate(font, ln, max_w) for ln in lines[:max_lines]]
    if overflow and fitted and not fitted[-1].endswith(ELLIPSIS):
        fitted[-1] = truncate(font, fitted[-1] + ELLIPSIS, max_w)
    return fitted


# --- primitives -------------------------------------------------------------
def vrule(draw, x: int, y0: int, y1: int, *, fill: int, width: int = 1) -> None:
    draw.line([(x, y0), (x, y1)], fill=fill, width=width)


def hrule(draw, y: int, x0: int, x1: int, *, fill: int, width: int = 1) -> None:
    draw.line([(x0, y), (x1, y)], fill=fill, width=width)


# --- weather glyphs ---------------------------------------------------------
# Solid, high-contrast line art. One large glyph reads from across the room;
# detail is wasted on 16 grey levels, so we keep strokes thick and shapes bold.
def weather_glyph(draw, cx: int, cy: int, size: int, condition: str, fill: int = INK) -> None:
    r = size // 2
    lw = max(4, size // 22)

    def sun(scx, scy, sr):
        draw.ellipse([scx - sr, scy - sr, scx + sr, scy + sr], outline=fill, width=lw)
        import math
        for i in range(8):
            a = math.pi * i / 4
            x0 = scx + int((sr + lw) * math.cos(a))
            y0 = scy + int((sr + lw) * math.sin(a))
            x1 = scx + int((sr + sr * 0.55) * math.cos(a))
            y1 = scy + int((sr + sr * 0.55) * math.sin(a))
            draw.line([(x0, y0), (x1, y1)], fill=fill, width=lw)

    def cloud(ccx, ccy, cw):
        # A rounded cloud built from overlapping ellipses + a flat base.
        h = int(cw * 0.62)
        base_y = ccy + h // 2
        left = ccx - cw // 2
        draw.rounded_rectangle(
            [left, ccy - h // 6, ccx + cw // 2, base_y],
            radius=h // 3, outline=fill, width=lw,
        )
        draw.ellipse([left, ccy - h // 3, left + h, ccy - h // 3 + h], outline=fill, width=lw)
        draw.ellipse([ccx - h // 2, ccy - h // 2, ccx + h // 2, ccy - h // 2 + h],
                     outline=fill, width=lw)
        return base_y

    if condition == "clear":
        sun(cx, cy, int(r * 0.62))
    elif condition == "cloudy":
        cloud(cx, cy, int(size * 0.9))
    elif condition == "fog":
        for i, dy in enumerate((-r // 2, 0, r // 2)):
            inset = (i % 2) * (size // 8)
            draw.line([(cx - r + inset, cy + dy), (cx + r - inset, cy + dy)],
                      fill=fill, width=lw)
    elif condition == "rain":
        base = cloud(cx, cy - r // 5, int(size * 0.85))
        for i, dx in enumerate((-r // 2, 0, r // 2)):
            x = cx + dx
            draw.line([(x, base + lw), (x - size // 14, base + size // 5)],
                      fill=fill, width=lw)
    elif condition == "snow":
        base = cloud(cx, cy - r // 5, int(size * 0.85))
        for dx in (-r // 2, 0, r // 2):
            x, y = cx + dx, base + size // 8
            f = size // 18
            draw.line([(x - f, y), (x + f, y)], fill=fill, width=lw)
            draw.line([(x, y - f), (x, y + f)], fill=fill, width=lw)
    elif condition == "storm":
        base = cloud(cx, cy - r // 5, int(size * 0.85))
        bx = cx
        draw.line(
            [(bx + size // 12, base), (bx - size // 18, base + size // 6),
             (bx + size // 20, base + size // 6), (bx - size // 12, base + size // 3)],
            fill=fill, width=lw,
        )
    else:
        cloud(cx, cy, int(size * 0.9))


# --- output -----------------------------------------------------------------
def _quantize(img: Image.Image) -> Image.Image:
    # No dithering: these screens are pure text. Error-diffusion scatters noise
    # into antialiased glyph edges. With 16 levels, text maps cleanly.
    return img.quantize(colors=GREY_LEVELS, dither=Image.Dither.NONE).convert("L")


def _atomic_save(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    img.save(tmp, format="PNG")
    os.replace(tmp, path)   # device never fetches a half-written PNG


def save_final(img: Image.Image, path: Path, rotate: int) -> None:
    """Quantize, rotate to portrait, and atomically write the device PNG."""
    q = _quantize(img)
    transform = Image.ROTATE_90 if rotate == 90 else Image.ROTATE_270
    out = q.transpose(transform)   # 1448x1072 -> 1072x1448 portrait
    _atomic_save(out, path)


def save_preview(img: Image.Image, path: Path) -> None:
    """Quantize but do NOT rotate; frame the canvas so panel edges are visible."""
    q = _quantize(img)
    pad = 2
    framed = Image.new("L", (CANVAS_W + pad * 2, CANVAS_H + pad * 2), theme.RULE)
    framed.paste(q, (pad, pad))
    d = ImageDraw.Draw(framed)
    d.rectangle([pad - 1, pad - 1, pad + CANVAS_W, pad + CANVAS_H], outline=INK, width=1)
    _atomic_save(framed, path)
