"""Quote of the day.

Two paths, both stable for the whole day:

  * local  — deterministic pick from quotes.json by date. The default, and the
             fallback. Local on purpose: it cannot fail over the network.
  * gemini — ask Gemini once per day for a real, attributed quote, cached to
             quote_cache.json. On ANY failure we fall back to the local pick, so
             the screen never blanks.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import Result

_ROOT = Path(__file__).resolve().parent.parent.parent
QUOTES_PATH = _ROOT / "quotes.json"
CACHE_PATH = _ROOT / "quote_cache.json"


@dataclass(frozen=True)
class Quote:
    text: str
    author: str


def fetch(today: date | None = None, path: Path | None = None) -> Result[Quote]:
    """Deterministic local pick from quotes.json (the fallback path)."""
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


def _read_cache(cache_path: Path, today: date) -> Quote | None:
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if data.get("date") == today.isoformat() and data.get("text") and data.get("author"):
            return Quote(text=str(data["text"]), author=str(data["author"]))
    except Exception:  # noqa: BLE001 — a missing/corrupt cache is not an error
        pass
    return None


def _write_cache(cache_path: Path, today: date, q: Quote) -> None:
    payload = {"date": today.isoformat(), "text": q.text, "author": q.author, "source": "gemini"}
    tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, cache_path)


def quote_of_day(
    today: date | None = None,
    *,
    use_gemini: bool = False,
    api_key: str = "",
    model: str = "",
    prompt: str = "",
    cache_path: Path | None = None,
    quotes_path: Path | None = None,
) -> tuple[Result[Quote], str]:
    """Return (result, source) where source is 'gemini', 'cache', or 'local'.

    Calls Gemini at most once per day (cached by date); falls back to the local
    deterministic pick on any failure. Never blanks the screen.
    """
    today = today or date.today()
    cache_path = cache_path or CACHE_PATH

    if use_gemini and api_key:
        cached = _read_cache(cache_path, today)
        if cached is not None:
            return Result.good(cached), "cache"

        from . import gemini

        res = gemini.fetch_quote(api_key, model, prompt.format(date=today.isoformat()))
        if res.ok and res.value is not None:
            try:
                _write_cache(cache_path, today, res.value)
            except Exception:  # noqa: BLE001 — cache write failure is non-fatal
                pass
            return res, "gemini"
        # else: fall through to local, keep the failure reason for logging
        return fetch(today, quotes_path), "local"

    return fetch(today, quotes_path), "local"
