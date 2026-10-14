"""Read-side use cases. They aggregate in Python what the repository filters in SQL."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Protocol

from signal_problems.domain.causes import CauseCategory, DelayCause, cause_for
from signal_problems.domain.commute import CommuteRisk, Trip, count_weekdays
from signal_problems.domain.delays import SIGNIFICANT_DELAY_MINUTES
from signal_problems.domain.lines import Line
from signal_problems.domain.stations import Station, StationRegistry


@dataclass(frozen=True, slots=True)
class DelayFact:
    """The columns read-side queries need from a stored delay."""

    occurred_at: datetime
    station_id: str | None
    segment_end_id: str | None
    line: Line | None
    cause_code: str
    minutes: int

    @property
    def is_significant(self) -> bool:
        return self.minutes >= SIGNIFICANT_DELAY_MINUTES


class DelayQueries(Protocol):
    def coverage(self) -> tuple[date, date] | None: ...

    def at_stations(self, station_ids: Sequence[str], line: Line | None = None) -> list[DelayFact]:
        """Delays at these stations (or on segments touching them), optionally on one line.

        Delays with no recorded line are included: they can't be ruled out.
        """
        ...

    def totals(self) -> tuple[int, int, int]:
        """(all incidents, 5+ minute delays, 5+ minute delays caused by signal failures)"""
        ...


class StationNotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class StationHeat:
    station: Station
    incidents: int
    significant: int
    minutes_lost: int


@dataclass(frozen=True, slots=True)
class CauseCount:
    cause: DelayCause
    count: int


@dataclass(frozen=True, slots=True)
class StationProfile:
    station: Station
    incidents: int
    significant: int
    minutes_lost: int
    categories: dict[CauseCategory, int]  # 5+ minute delays by cause category
    top_causes: list[CauseCount]
    by_weekday_hour: list[list[int]]  # [weekday][hour] → 5+ minute delays


@dataclass(frozen=True, slots=True)
class CommuteQuery:
    line: Line
    origin_id: str
    destination_id: str
    weekday: int  # Monday = 0
    departure: time


@dataclass(frozen=True, slots=True)
class CommuteAssessment:
    trip: Trip
    window: tuple[time, time]
    risk: CommuteRisk
    worst_stations: list[tuple[Station, int]]
    top_causes: list[CauseCount]


@dataclass(frozen=True, slots=True)
class Summary:
    first_day: date | None
    last_day: date | None
    incidents: int
    significant: int
    signal_problems: int


def summary(queries: DelayQueries) -> Summary:
    coverage = queries.coverage()
    incidents, significant, signal_problems = queries.totals()
    first, last = coverage or (None, None)
    return Summary(first, last, incidents, significant, signal_problems)


def line_heat(queries: DelayQueries, registry: StationRegistry, line: Line) -> list[StationHeat]:
    stations = registry.on_line(line)
    facts = queries.at_stations([s.id for s in stations], line)
    heat = []
    for station in stations:
        here = [f for f in facts if f.station_id == station.id]
        heat.append(
            StationHeat(
                station,
                incidents=len(here),
                significant=sum(f.is_significant for f in here),
                minutes_lost=sum(f.minutes for f in here),
            )
        )
    return heat


def station_profile(
    queries: DelayQueries, registry: StationRegistry, station_id: str
) -> StationProfile:
    station = registry.get(station_id)
    if station is None:
        raise StationNotFoundError(station_id)
    facts = [f for f in queries.at_stations([station_id]) if f.station_id == station_id]
    significant = [f for f in facts if f.is_significant]
    grid = [[0] * 24 for _ in range(7)]
    for fact in significant:
        grid[fact.occurred_at.weekday()][fact.occurred_at.hour] += 1
    return StationProfile(
        station,
        incidents=len(facts),
        significant=len(significant),
        minutes_lost=sum(f.minutes for f in facts),
        categories=dict(Counter(cause_for(f.cause_code).category for f in significant)),
        top_causes=_top_causes(significant),
        by_weekday_hour=grid,
    )


def assess_commute(
    queries: DelayQueries, registry: StationRegistry, query: CommuteQuery
) -> CommuteAssessment:
    """Raises ValueError when the stations aren't both on the line."""
    stations = registry.between(query.line, query.origin_id, query.destination_id)
    trip = Trip(query.line, tuple(stations), query.weekday, query.departure)
    on_trip = {s.id for s in trip.stations}
    hits = [
        f
        for f in queries.at_stations(list(on_trip), query.line)
        if f.is_significant and trip.affects(f.occurred_at) and _within_trip(f, on_trip)
    ]
    coverage = queries.coverage()
    observed = count_weekdays(*coverage, query.weekday) if coverage else 0
    per_station = Counter(f.station_id for f in hits)
    return CommuteAssessment(
        trip=trip,
        window=trip.window(),
        risk=CommuteRisk(observed, len({f.occurred_at.date() for f in hits})),
        worst_stations=[
            (s, per_station[s.id])
            for s in sorted(trip.stations, key=lambda s: -per_station[s.id])
            if per_station[s.id]
        ][:3],
        top_causes=_top_causes(hits),
    )


def _within_trip(fact: DelayFact, on_trip: set[str]) -> bool:
    """A station must be on the trip; a segment counts only if both of its ends are."""
    return fact.station_id in on_trip and (
        fact.segment_end_id is None or fact.segment_end_id in on_trip
    )


def _top_causes(facts: list[DelayFact], limit: int = 5) -> list[CauseCount]:
    counts = Counter(f.cause_code for f in facts)
    return [CauseCount(cause_for(code), n) for code, n in counts.most_common(limit)]
