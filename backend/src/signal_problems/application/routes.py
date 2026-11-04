"""Read-side use cases for streetcar and bus routes (issue #28)."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from signal_problems.application.queries import CauseCount
from signal_problems.domain.causes import CauseCategory, cause_for
from signal_problems.domain.delays import SIGNIFICANT_DELAY_MINUTES
from signal_problems.domain.surface import Mode, route_label


@dataclass(frozen=True, slots=True)
class RouteFact:
    """The columns route queries need from a stored streetcar or bus delay."""

    occurred_at: datetime
    route: int
    route_name: str
    location: str
    cause_code: str
    minutes: int

    @property
    def is_significant(self) -> bool:
        return self.minutes >= SIGNIFICANT_DELAY_MINUTES


@dataclass(frozen=True, slots=True)
class RouteTotals:
    route: int
    names: dict[str, int]  # logged spellings ("504 KING", "504A KING") → rows
    incidents: int
    significant: int
    minutes_lost: int


class RouteQueries(Protocol):
    def totals(self, mode: Mode, since: date | None = None) -> list[RouteTotals]:
        """Per-route counts, aggregated in the database: buses have 100,000+ rows."""
        ...

    def facts(
        self, mode: Mode, route: int | None = None, since: date | None = None
    ) -> list[RouteFact]:
        """Delays of one mode, optionally on one route and from a given day on."""
        ...


class RouteNotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class RouteHeat:
    route: int
    name: str
    incidents: int
    significant: int
    minutes_lost: int


@dataclass(frozen=True, slots=True)
class RouteProfile:
    heat: RouteHeat
    categories: dict[CauseCategory, int]  # 5+ minute delays by cause category
    top_causes: list[CauseCount]
    top_locations: list[tuple[str, int]]  # where 5+ minute delays were logged, as written
    by_weekday_hour: list[list[int]]  # [weekday][hour] → 5+ minute delays


def route_ranking(queries: RouteQueries, mode: Mode, since: date | None = None) -> list[RouteHeat]:
    """Every route with a logged delay, the most 5+ minute delays first."""
    heat = [
        RouteHeat(t.route, _name(t.names), t.incidents, t.significant, t.minutes_lost)
        for t in queries.totals(mode, since)
    ]
    return sorted(heat, key=lambda h: (-h.significant, h.route))


def route_profile(
    queries: RouteQueries, mode: Mode, route: int, since: date | None = None
) -> RouteProfile:
    facts = queries.facts(mode, route, since)
    if not facts:
        raise RouteNotFoundError(f"{mode} {route}")
    significant = [f for f in facts if f.is_significant]
    grid = [[0] * 24 for _ in range(7)]
    for fact in significant:
        grid[fact.occurred_at.weekday()][fact.occurred_at.hour] += 1
    causes = Counter(f.cause_code for f in significant)
    return RouteProfile(
        heat=_heat(route, facts),
        categories=dict(Counter(cause_for(f.cause_code, mode).category for f in significant)),
        top_causes=[CauseCount(cause_for(code, mode), n) for code, n in causes.most_common(5)],
        top_locations=Counter(f.location for f in significant if f.location).most_common(5),
        by_weekday_hour=grid,
    )


def _name(spellings: dict[str, int]) -> str:
    """Spellings vary ("504 KING", "504A KING"); the most common one names the route."""
    return route_label(max(spellings, key=lambda name: (spellings[name], name)))


def _heat(route: int, facts: Sequence[RouteFact]) -> RouteHeat:
    return RouteHeat(
        route,
        _name(Counter(f.route_name for f in facts)),
        incidents=len(facts),
        significant=sum(f.is_significant for f in facts),
        minutes_lost=sum(f.minutes for f in facts),
    )
