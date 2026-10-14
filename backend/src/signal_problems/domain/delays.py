from dataclasses import dataclass
from datetime import datetime

from signal_problems.domain.causes import DelayCause
from signal_problems.domain.lines import Line
from signal_problems.domain.resolver import ResolvedLocation

SIGNIFICANT_DELAY_MINUTES = 5


@dataclass(frozen=True, slots=True)
class Delay:
    """One incident from the TTC delay log."""

    fingerprint: str  # identifies the logged row across monthly re-publications of the file
    occurred_at: datetime
    location: ResolvedLocation
    line: Line | None  # None when the log doesn't say and the location is on several lines
    cause: DelayCause
    minutes: int  # how long service was held up
    gap_minutes: int  # time between trains at that point

    @property
    def is_significant(self) -> bool:
        """Zero-minute rows are logged incidents that didn't hold service."""
        return self.minutes >= SIGNIFICANT_DELAY_MINUTES


def infer_line(location: ResolvedLocation) -> Line | None:
    """Pick the line an incident happened on from the logged line and the station's lines."""
    station_lines = (
        frozenset().union(*(s.lines for s in location.stations)) if location.stations else None
    )
    candidates = location.line_hints & station_lines if station_lines else location.line_hints
    if not candidates and station_lines:
        candidates = station_lines
    return next(iter(candidates)) if len(candidates) == 1 else None
