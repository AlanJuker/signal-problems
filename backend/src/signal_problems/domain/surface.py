"""Streetcar and bus delays, by route (issue #28).

Their logs name a route ("504 KING") and a free-text location, mostly an intersection. There's no
fixed list of stops to resolve those against, the way the subway has 70 stations, so the route is
the unit.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from signal_problems.domain.causes import DelayCause
from signal_problems.domain.delays import SIGNIFICANT_DELAY_MINUTES

_ROUTE = re.compile(r"\s*(\d{1,3})(?!\d)")


class Mode(StrEnum):
    STREETCAR = "streetcar"
    BUS = "bus"


def route_number(line: str) -> int | None:
    """The route a logged line belongs to: "504 KING" and the branch "504A KING" are both 504.

    None when the line doesn't start with one ("LINE 1 SHUTTLE", "RAD", empty).
    """
    match = _ROUTE.match(line)
    return int(match.group(1)) if match else None


@dataclass(frozen=True, slots=True)
class SurfaceDelay:
    """One incident from the streetcar or bus delay log."""

    fingerprint: str
    mode: Mode
    route: int
    route_name: str  # as logged, e.g. "504 KING"
    occurred_at: datetime
    location: str  # as logged, usually an intersection
    cause: DelayCause
    minutes: int
    gap_minutes: int

    @property
    def is_significant(self) -> bool:
        return self.minutes >= SIGNIFICANT_DELAY_MINUTES
