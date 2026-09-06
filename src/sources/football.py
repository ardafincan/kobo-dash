"""Next football fixture from TheSportsDB. Free public API key.

Returns the team's nearest upcoming match. Like every source, it returns a
Result and never raises out to the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

from . import Result

API = "https://www.thesportsdb.com/api/v1/json/{key}/eventsnext.php"
TIMEOUT = 10


@dataclass(frozen=True)
class Match:
    opponent: str       # the other team
    is_home: bool       # True if our team plays at home
    league: str
    start: datetime     # tz-aware, in the configured local timezone


def _parse_start(ev: dict, tz: ZoneInfo) -> datetime | None:
    # TheSportsDB timestamps are UTC. Prefer strTimestamp, else dateEvent+strTime.
    ts = ev.get("strTimestamp")
    if ts:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", ""))
            return dt.replace(tzinfo=timezone.utc).astimezone(tz)
        except Exception:
            pass
    date = ev.get("dateEvent")
    time = ev.get("strTime") or "00:00:00"
    if date:
        try:
            dt = datetime.fromisoformat(f"{date}T{time[:8]}")
            return dt.replace(tzinfo=timezone.utc).astimezone(tz)
        except Exception:
            pass
    return None


def fetch(team_id: str, team_name: str, timezone_str: str, api_key: str = "3") -> Result[Match]:
    try:
        tz = ZoneInfo(timezone_str)
        r = requests.get(API.format(key=api_key), params={"id": team_id}, timeout=TIMEOUT)
        r.raise_for_status()
        events = r.json().get("events") or []
        if not events:
            return Result.fail("football: no upcoming fixtures")

        # eventsnext is already ordered nearest-first; take the first parseable one.
        for ev in events:
            start = _parse_start(ev, tz)
            if start is None:
                continue
            tid = str(team_id)
            id_home = str(ev.get("idHomeTeam", ""))
            id_away = str(ev.get("idAwayTeam", ""))
            home = (ev.get("strHomeTeam") or "").strip()
            away = (ev.get("strAwayTeam") or "").strip()
            if id_home == tid:
                is_home, opponent = True, away
            elif id_away == tid:
                is_home, opponent = False, home
            elif team_name and team_name.lower() in home.lower():
                is_home, opponent = True, away
            else:
                is_home, opponent = False, home
            return Result.good(
                Match(
                    opponent=opponent.strip() or "?",
                    is_home=is_home,
                    league=(ev.get("strLeague") or "").strip(),
                    start=start,
                )
            )
        return Result.fail("football: no fixture with a valid date")
    except Exception as e:  # noqa: BLE001 — never raise to caller
        return Result.fail(f"football: {type(e).__name__}: {e}")
