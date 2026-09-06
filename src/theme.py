"""Shared layout constants and font loading.

Every screen imports from here. No screen module defines its own sizes. If each
screen grew its own type scale, text would visibly jump position between rotation
steps, and on a flashing e-ink refresh that jump is very obvious.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

# --- canvas -----------------------------------------------------------------
CANVAS_W, CANVAS_H = 1448, 1072    # landscape drawing canvas
MARGIN = 40
USABLE_W = CANVAS_W - 2 * MARGIN   # 1368
USABLE_H = CANVAS_H - 2 * MARGIN   # 992

GREY_LEVELS = 16

# --- type scale -------------------------------------------------------------
SIZE_HERO   = 180   # big temperature
SIZE_H1     = 96
SIZE_H2     = 60    # news headlines
SIZE_BODY   = 44
SIZE_SMALL  = 28    # timestamp, source labels

# --- greys (0 = black, 255 = white) -----------------------------------------
INK        = 0
INK_MUTED  = 96
RULE       = 160
PAPER      = 255

# --- fonts ------------------------------------------------------------------
_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONT_MEDIUM   = _FONT_DIR / "IBMPlexSans-Medium.ttf"
FONT_SEMIBOLD = _FONT_DIR / "IBMPlexSans-SemiBold.ttf"


@lru_cache(maxsize=None)
def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Return a cached IBM Plex Sans face at the given pixel size.

    Body text uses Medium; bold=True selects SemiBold for headings/labels.
    E-ink contrast is lower than paper, so we never use a Regular weight.
    """
    path = FONT_SEMIBOLD if bold else FONT_MEDIUM
    return ImageFont.truetype(str(path), size)
