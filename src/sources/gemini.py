"""Fetch a single quote from the Google Gemini API.

Used once per day by src/sources/quotes.py, which caches the result and falls
back to the local quotes.json on any failure. This module never raises.
"""

from __future__ import annotations

import json

import requests

from . import Result
from .quotes import Quote

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT = 20

# Force a {text, author} JSON object so parsing is deterministic.
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "author": {"type": "string"},
    },
    "required": ["text", "author"],
}


def fetch_quote(api_key: str, model: str, prompt: str) -> Result[Quote]:
    try:
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": _RESPONSE_SCHEMA,
                "temperature": 0.9,
            },
        }
        r = requests.post(
            API.format(model=model),
            params={"key": api_key},
            json=body,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()

        # A blocked/empty response has no candidates.
        candidates = data.get("candidates") or []
        if not candidates:
            return Result.fail(f"gemini: no candidates ({data.get('promptFeedback', {})})")
        parts = candidates[0].get("content", {}).get("parts") or []
        raw_text = "".join(p.get("text", "") for p in parts).strip()
        if not raw_text:
            return Result.fail("gemini: empty response text")

        obj = json.loads(raw_text)
        text = str(obj.get("text", "")).strip().strip('"“”')
        author = str(obj.get("author", "")).strip()
        if not text or not author:
            return Result.fail("gemini: missing text or author")

        return Result.good(Quote(text=text, author=author))
    except Exception as e:  # noqa: BLE001 — never raise to caller
        return Result.fail(f"gemini: {type(e).__name__}: {e}")
