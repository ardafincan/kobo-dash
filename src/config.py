"""Load and validate config.toml."""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.toml"


class ConfigError(Exception):
    pass


# Default prompt for the daily Gemini quote. {date} is filled in at runtime to
# nudge day-to-day variation. The schema (see sources/gemini.py) forces a
# {text, author} JSON object, so the prompt only needs to shape the content.
DEFAULT_QUOTE_PROMPT = (
    "Give me one inspiring or thought-provoking quotation that was genuinely "
    "said or written by a real, identifiable person — historical or "
    "contemporary. It must be a real, accurately attributed quote: do not "
    "invent quotations or attributions, and only include it if you are "
    "confident the wording and the author are correct. Prefer something that is "
    "not an overused cliche. Keep it under 200 characters. Vary your choice for "
    "the date {date}."
)


@dataclass(frozen=True)
class Config:
    ics_url: str
    latitude: float
    longitude: float
    timezone: str
    rotate: int
    sequence: list[str]
    host: str
    port: int
    # Daily Gemini quote (optional; falls back to local quotes.json).
    quote_use_gemini: bool
    gemini_api_key: str
    gemini_model: str
    quote_prompt: str


def _require(d: dict, path: str):
    """Fetch a nested key like 'a.b' or raise a helpful ConfigError."""
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise ConfigError(f"config.toml is missing required key: {path!r}")
        cur = cur[part]
    return cur


def load(path: Path | None = None) -> Config:
    path = path or CONFIG_PATH
    if not path.exists():
        raise ConfigError(
            f"{path} not found. Copy config.example.toml to config.toml and fill it in."
        )
    with path.open("rb") as f:
        raw = tomllib.load(f)

    rotate = int(_require(raw, "display.rotate"))
    if rotate not in (90, 270):
        raise ConfigError(f"display.rotate must be 90 or 270, got {rotate}")

    sequence = _require(raw, "display.sequence")
    if not isinstance(sequence, list) or not sequence:
        raise ConfigError("display.sequence must be a non-empty list")
    allowed = {"day.png", "news.png", "quote.png"}
    bad = [s for s in sequence if s not in allowed]
    if bad:
        raise ConfigError(
            f"display.sequence contains unknown screens {bad}; allowed: {sorted(allowed)}"
        )

    quote = raw.get("quote") if isinstance(raw.get("quote"), dict) else {}
    quote_use_gemini = bool(quote.get("use_gemini", False))
    gemini_api_key = str(quote.get("gemini_api_key", "")).strip()
    gemini_model = str(quote.get("gemini_model", "gemini-2.5-flash")).strip()
    quote_prompt = str(quote.get("prompt", DEFAULT_QUOTE_PROMPT))

    return Config(
        ics_url=str(_require(raw, "calendar.ics_url")),
        latitude=float(_require(raw, "location.latitude")),
        longitude=float(_require(raw, "location.longitude")),
        timezone=str(_require(raw, "location.timezone")),
        rotate=rotate,
        sequence=list(sequence),
        host=str(_require(raw, "server.host")),
        port=int(_require(raw, "server.port")),
        quote_use_gemini=quote_use_gemini,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        quote_prompt=quote_prompt,
    )


if __name__ == "__main__":
    try:
        cfg = load()
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        sys.exit(1)
    # Don't print the ICS URL — it's a secret.
    print("config OK:")
    print(f"  location : {cfg.latitude}, {cfg.longitude} ({cfg.timezone})")
    print(f"  rotate   : {cfg.rotate}")
    print(f"  sequence : {cfg.sequence}")
    print(f"  server   : {cfg.host}:{cfg.port}")
    if cfg.quote_use_gemini:
        key = "set" if cfg.gemini_api_key else "MISSING (will fall back to local)"
        print(f"  quote    : gemini {cfg.gemini_model} (key {key})")
    else:
        print("  quote    : local quotes.json")
