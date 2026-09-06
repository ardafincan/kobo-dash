"""Weather from Open-Meteo. No API key."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from . import Result

API = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 10


# WMO weather codes grouped into a small set of our own condition names. We do
# not try to cover every code with a distinct glyph.
def condition_from_code(code: int) -> str:
    if code == 0:
        return "clear"
    if code in (1, 2, 3):
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "storm"
    return "cloudy"


@dataclass(frozen=True)
class DayForecast:
    label: str          # e.g. "Mon"
    hi: int
    lo: int
    condition: str


@dataclass(frozen=True)
class Weather:
    temp: int           # current temperature, rounded
    condition: str      # current condition name
    today_hi: int
    today_lo: int
    forecast: list[DayForecast]   # next days (excludes today)


_WEEKDAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _weekday_label(iso_date: str) -> str:
    # iso_date like "2026-09-06"; avoid importing datetime just for a label.
    from datetime import date

    y, m, d = (int(x) for x in iso_date.split("-"))
    return _WEEKDAY[date(y, m, d).weekday()]


def fetch(latitude: float, longitude: float, timezone: str) -> Result[Weather]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,weather_code",
        "timezone": timezone,
    }
    try:
        r = requests.get(API, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()

        cur = data["current"]
        daily = data["daily"]
        dates = daily["time"]
        highs = daily["temperature_2m_max"]
        lows = daily["temperature_2m_min"]
        codes = daily["weather_code"]

        forecast = [
            DayForecast(
                label=_weekday_label(dates[i]),
                hi=round(highs[i]),
                lo=round(lows[i]),
                condition=condition_from_code(int(codes[i])),
            )
            for i in range(1, min(4, len(dates)))   # next 3 days, skip today
        ]

        return Result.good(
            Weather(
                temp=round(cur["temperature_2m"]),
                condition=condition_from_code(int(cur["weather_code"])),
                today_hi=round(highs[0]),
                today_lo=round(lows[0]),
                forecast=forecast,
            )
        )
    except Exception as e:  # noqa: BLE001 — never raise to caller
        return Result.fail(f"weather: {type(e).__name__}: {e}")
