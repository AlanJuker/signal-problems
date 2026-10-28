from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from signal_problems.application.ports import (
    DelayRepository,
    DelaySource,
    RawDelayRow,
    SurfaceDelayRepository,
)
from signal_problems.domain.causes import cause_for
from signal_problems.domain.delays import Delay, infer_line
from signal_problems.domain.lines import is_scarborough_rt_only
from signal_problems.domain.resolver import LocationKind, StationResolver
from signal_problems.domain.surface import Mode, SurfaceDelay, route_number


@dataclass
class IngestReport:
    rows_read: int = 0
    scarborough_rt: int = 0  # Line 3, closed in 2023: skipped
    malformed: int = 0
    duplicates: int = 0  # identical rows logged more than once
    already_stored: int = 0
    stored: int = 0
    by_kind: Counter[LocationKind] = field(default_factory=Counter)
    unresolved: Counter[str] = field(default_factory=Counter)

    @property
    def resolution_rate(self) -> float:
        """Share of parsed subway rows that resolved to a known kind of location."""
        parsed = self.rows_read - self.scarborough_rt - self.malformed
        return (parsed - self.by_kind[LocationKind.UNRESOLVED]) / parsed if parsed else 0.0


def to_delay(row: RawDelayRow, resolver: StationResolver) -> Delay:
    """Raises ValueError for rows with an unparseable date, time or minutes."""
    location = resolver.resolve(row.station, row.line)
    return Delay(
        fingerprint=row.fingerprint,
        occurred_at=datetime.strptime(f"{row.date} {row.time}", "%Y-%m-%d %H:%M"),
        location=location,
        line=infer_line(location),
        cause=cause_for(row.code),
        minutes=int(row.min_delay or 0),
        gap_minutes=int(row.min_gap or 0),
    )


class IngestDelays:
    def __init__(
        self, source: DelaySource, repository: DelayRepository, resolver: StationResolver
    ) -> None:
        self._source = source
        self._repository = repository
        self._resolver = resolver

    def __call__(self) -> IngestReport:
        report = IngestReport()
        delays: dict[str, Delay] = {}
        for row in self._source.fetch():
            report.rows_read += 1
            if is_scarborough_rt_only(row.line):
                report.scarborough_rt += 1
                continue
            try:
                delay = to_delay(row, self._resolver)
            except ValueError:
                report.malformed += 1
                continue
            report.by_kind[delay.location.kind] += 1
            if delay.location.kind is LocationKind.UNRESOLVED:
                report.unresolved[row.station] += 1
            if delay.fingerprint in delays:
                report.duplicates += 1
            delays[delay.fingerprint] = delay

        report.stored = self._repository.add_new(list(delays.values()))
        report.already_stored = len(delays) - report.stored
        return report


@dataclass
class SurfaceIngestReport:
    rows_read: int = 0
    malformed: int = 0
    duplicates: int = 0
    already_stored: int = 0
    stored: int = 0
    no_route: Counter[str] = field(default_factory=Counter)  # logged line → rows skipped


def to_surface_delay(row: RawDelayRow, mode: Mode, route: int) -> SurfaceDelay:
    """Raises ValueError for rows with an unparseable date, time or minutes."""
    # Bus dates carry a midnight time ("2025-01-01T00:00:00"); streetcar dates don't.
    occurred_at = datetime.strptime(f"{row.date[:10]} {row.time}", "%Y-%m-%d %H:%M")
    return SurfaceDelay(
        fingerprint=row.fingerprint,
        mode=mode,
        route=route,
        route_name=row.line.strip(),
        occurred_at=occurred_at,
        location=row.station.strip(),
        cause=cause_for(row.code, mode),
        minutes=int(row.min_delay or 0),
        gap_minutes=int(row.min_gap or 0),
    )


class IngestSurfaceDelays:
    def __init__(self, source: DelaySource, repository: SurfaceDelayRepository, mode: Mode) -> None:
        self._source = source
        self._repository = repository
        self._mode = mode

    def __call__(self) -> SurfaceIngestReport:
        report = SurfaceIngestReport()
        delays: dict[str, SurfaceDelay] = {}
        for row in self._source.fetch():
            report.rows_read += 1
            route = route_number(row.line)
            if route is None:
                report.no_route[row.line.strip()] += 1  # reported, never guessed
                continue
            try:
                delay = to_surface_delay(row, self._mode, route)
            except ValueError:
                report.malformed += 1
                continue
            if delay.fingerprint in delays:
                report.duplicates += 1
            delays[delay.fingerprint] = delay

        report.stored = self._repository.add_new(list(delays.values()))
        report.already_stored = len(delays) - report.stored
        return report
