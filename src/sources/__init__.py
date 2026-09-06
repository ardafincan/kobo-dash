"""Data sources.

Every source function returns a Result and NEVER raises out to the caller. A
single Wi-Fi blip must not blank a dashboard whose other data is fine. On
failure the caller renders a per-region "can't fetch" marker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

# Uniform text shown in a region when its source failed.
CANT_FETCH = "can't fetch"


@dataclass(frozen=True)
class Result(Generic[T]):
    ok: bool
    value: T | None = None
    error: str | None = None

    @classmethod
    def good(cls, value: T) -> "Result[T]":
        return cls(True, value, None)

    @classmethod
    def fail(cls, error: str) -> "Result[T]":
        return cls(False, None, error)
