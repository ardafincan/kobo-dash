"""Hacker News top 5 headlines from the Firebase API. No key, no auth."""

from __future__ import annotations

import requests

from . import Result

TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
TIMEOUT = 10
COUNT = 5


def fetch() -> Result[list[str]]:
    try:
        r = requests.get(TOP, timeout=TIMEOUT)
        r.raise_for_status()
        ids = r.json()[:COUNT]

        titles: list[str] = []
        for item_id in ids:
            ri = requests.get(ITEM.format(id=item_id), timeout=TIMEOUT)
            ri.raise_for_status()
            item = ri.json() or {}
            # Read `title` only. Ask HN / Show HN items have no `url`; we never
            # touch that field, so their absence is irrelevant here.
            title = str(item.get("title", "")).strip()
            if title:
                titles.append(title)

        if not titles:
            return Result.fail("hn: no stories returned")
        return Result.good(titles)
    except Exception as e:  # noqa: BLE001 — never raise to caller
        return Result.fail(f"hn: {type(e).__name__}: {e}")
