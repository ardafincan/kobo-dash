"""Today's agenda from a Google Calendar private ICS URL.

Handles the things that bite calendar parsers:
  * all-day events use a `date`, not a `datetime`
  * timed events may be tz-aware, or floating (naive) -> interpret in local tz
  * multi-day events should show on every day they cover
  * recurring events (RRULE) are expanded for today, honouring EXDATE
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import requests
from dateutil.rrule import rrulestr
from icalendar import Calendar

from . import Result

TIMEOUT = 15


@dataclass(frozen=True)
class Event:
    all_day: bool
    start: datetime | None   # tz-aware local start; None for all-day
    title: str

    @property
    def sort_key(self) -> tuple[int, float]:
        # All-day events sort first (0), then timed events by clock time.
        if self.all_day or self.start is None:
            return (0, 0.0)
        return (1, self.start.hour * 60 + self.start.minute)


@dataclass(frozen=True)
class DayAgenda:
    date: date
    label: str          # "Today", "Tomorrow", or "Wed 9 Sep"
    events: list[Event]


def _as_datetime(value, tz: ZoneInfo) -> tuple[bool, datetime]:
    """Normalise a DTSTART/DTEND value to (is_all_day, tz-aware datetime)."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=tz)      # floating -> local
        return (False, value.astimezone(tz))
    # bare date -> all-day, anchored at local midnight
    return (True, datetime.combine(value, time.min, tzinfo=tz))


def _exdates(comp, tz: ZoneInfo) -> set[datetime]:
    raw = comp.get("EXDATE")
    if raw is None:
        return set()
    items = raw if isinstance(raw, list) else [raw]
    out: set[datetime] = set()
    for item in items:
        for dt in getattr(item, "dts", []):
            _, norm = _as_datetime(dt.dt, tz)
            out.add(norm)
    return out


def _duration(comp, start_all_day: bool, start_dt: datetime, tz: ZoneInfo) -> timedelta:
    end = comp.get("DTEND")
    if end is not None:
        _, end_dt = _as_datetime(end.dt, tz)
        return end_dt - start_dt
    dur = comp.get("DURATION")
    if dur is not None:
        return dur.dt
    # No end: all-day defaults to 1 day, timed defaults to 0.
    return timedelta(days=1) if start_all_day else timedelta(0)


def _occurrences_today(comp, tz: ZoneInfo, day_start: datetime, day_end: datetime):
    """Yield (all_day, local_start_datetime) occurrences overlapping today."""
    dtstart_field = comp.get("DTSTART")
    if dtstart_field is None:
        return
    all_day, start_dt = _as_datetime(dtstart_field.dt, tz)
    duration = _duration(comp, all_day, start_dt, tz)

    rrule_field = comp.get("RRULE")
    if rrule_field is None:
        # Single event: does [start, start+duration) overlap today?
        if start_dt < day_end and (start_dt + duration) > day_start:
            yield (all_day, start_dt)
        return

    # Recurring: expand around today. Widen the window by the duration so a
    # multi-day or long occurrence that began earlier still counts.
    exdates = _exdates(comp, tz)
    rule_text = rrule_field.to_ical().decode("utf-8")
    try:
        rule = rrulestr(f"RRULE:{rule_text}", dtstart=start_dt)
        window_start = day_start - duration
        for occ in rule.between(window_start, day_end, inc=True):
            if occ.tzinfo is None:
                occ = occ.replace(tzinfo=tz)
            occ = occ.astimezone(tz)
            if occ in exdates:
                continue
            if occ < day_end and (occ + duration) > day_start:
                yield (all_day, occ)
    except Exception:
        # Malformed rule: fall back to the base occurrence only.
        if start_dt < day_end and (start_dt + duration) > day_start:
            yield (all_day, start_dt)


def _collect(vevents, tz: ZoneInfo, day: date) -> list[Event]:
    """All events overlapping a single local day, sorted."""
    day_start = datetime.combine(day, time.min, tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    events: list[Event] = []
    for comp in vevents:
        title = str(comp.get("SUMMARY", "(no title)")).strip() or "(no title)"
        for all_day, occ in _occurrences_today(comp, tz, day_start, day_end):
            events.append(Event(all_day=all_day, start=None if all_day else occ, title=title))
    events.sort(key=lambda e: e.sort_key)
    return events


def _day_label(d: date, today: date) -> str:
    if d == today:
        return "Today"
    if d == today + timedelta(days=1):
        return "Tomorrow"
    return f"{d:%a} {d.day} {d:%b}"


def fetch(ics_url: str, timezone: str, today: date | None = None) -> Result[list[Event]]:
    """Events for a single day (kept for callers that only need today)."""
    try:
        tz = ZoneInfo(timezone)
        today = today or datetime.now(tz).date()
        r = requests.get(ics_url, timeout=TIMEOUT)
        r.raise_for_status()
        vevents = list(Calendar.from_ical(r.content).walk("VEVENT"))
        return Result.good(_collect(vevents, tz, today))
    except Exception as e:  # noqa: BLE001 — never raise to caller
        return Result.fail(f"calendar: {type(e).__name__}: {e}")


def fetch_days(ics_url: str, timezone: str, num_days: int = 3,
               today: date | None = None) -> Result[list[DayAgenda]]:
    """Per-day agendas for today and the following days. One network fetch."""
    try:
        tz = ZoneInfo(timezone)
        today = today or datetime.now(tz).date()
        r = requests.get(ics_url, timeout=TIMEOUT)
        r.raise_for_status()
        vevents = list(Calendar.from_ical(r.content).walk("VEVENT"))

        days = []
        for i in range(num_days):
            d = today + timedelta(days=i)
            days.append(DayAgenda(date=d, label=_day_label(d, today),
                                  events=_collect(vevents, tz, d)))
        return Result.good(days)
    except Exception as e:  # noqa: BLE001 — never raise to caller
        return Result.fail(f"calendar: {type(e).__name__}: {e}")
