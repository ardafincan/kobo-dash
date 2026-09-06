"""Local quote of the day. Deterministic by date so it is stable all day.

Local on purpose: quote APIs go down and change terms, and the failure mode is
a blank screen.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import Result

QUOTES_PATH = Path(__file__).resolve().parent.parent.parent / "quotes.json"


@dataclass(frozen=True)
class Quote:
    text: str
    author: str


def fetch(today: date | None = None, path: Path | None = None) -> Result[Quote]:
    path = path or QUOTES_PATH
    today = today or date.today()
    try:
        with path.open("r", encoding="utf-8") as f:
            quotes = json.load(f)
        if not quotes:
            return Result.fail("quotes: quotes.json is empty")
        idx = int(hashlib.md5(today.isoformat().encode()).hexdigest(), 16) % len(quotes)
        q = quotes[idx]
        return Result.good(Quote(text=str(q["text"]), author=str(q.get("author", ""))))
    except Exception as e:  # noqa: BLE001 — never raise to caller
        return Result.fail(f"quotes: {type(e).__name__}: {e}")
