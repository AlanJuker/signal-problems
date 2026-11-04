from collections import Counter
from datetime import date, datetime

import pytest

from signal_problems.application import routes
from signal_problems.application.routes import RouteFact, RouteTotals
from signal_problems.domain.surface import Mode, route_label

MONDAY_8AM = datetime(2025, 1, 6, 8, 0)


def fact(  # noqa: PLR0913 (test builder: every field has a default)
    route: int,
    name: str,
    *,
    minutes: int = 10,
    code: str = "MTSAN",
    at: datetime = MONDAY_8AM,
    location: str = "KING AND BAY",
) -> RouteFact:
    return RouteFact(at, route, name, location, code, minutes)


class FakeRouteQueries:
    def __init__(self, facts: list[RouteFact]) -> None:
        self._facts = facts

    def facts(
        self, mode: Mode, route: int | None = None, since: date | None = None
    ) -> list[RouteFact]:
        return [
            f
            for f in self._facts
            if (route is None or f.route == route)
            and (since is None or f.occurred_at.date() >= since)
        ]

    def totals(self, mode: Mode, since: date | None = None) -> list[RouteTotals]:
        by_route: dict[int, list[RouteFact]] = {}
        for f in self.facts(mode, since=since):
            by_route.setdefault(f.route, []).append(f)
        return [
            RouteTotals(
                route,
                dict(Counter(f.route_name for f in fs)),
                len(fs),
                sum(f.is_significant for f in fs),
                sum(f.minutes for f in fs),
            )
            for route, fs in by_route.items()
        ]


def test_ranking_puts_the_most_5_minute_delays_first() -> None:
    facts = [
        fact(501, "501 QUEEN"),
        fact(504, "504 KING"),
        fact(504, "504 KING"),
        fact(504, "504A KING"),
        fact(505, "505 DUNDAS"),
        fact(505, "505 DUNDAS", minutes=0),  # logged, but didn't hold service
    ]
    ranking = routes.route_ranking(FakeRouteQueries(facts), Mode.STREETCAR)

    # 501 and 505 tie on one 5+ minute delay: lower route number first
    assert [(h.name, h.significant) for h in ranking] == [
        ("504 King", 3),
        ("501 Queen", 1),
        ("505 Dundas", 1),
    ]
    assert ranking[2].incidents == 2


def test_route_profile() -> None:
    facts = [
        fact(504, "504 KING", code="MTSAN", location="KING AND BAY"),
        fact(
            504, "504 KING", code="MTSAN", location="KING AND BAY", at=datetime(2025, 1, 7, 17, 5)
        ),
        fact(504, "504 KING", code="ETBO", location="DUNDAS WEST STATION"),
        fact(504, "504 KING", minutes=0, location="BROADVIEW STATION"),  # not counted below
        fact(501, "501 QUEEN"),
    ]
    p = routes.route_profile(FakeRouteQueries(facts), Mode.STREETCAR, 504)

    assert (p.heat.incidents, p.heat.significant, p.heat.minutes_lost) == (4, 3, 30)
    assert p.top_locations == [("KING AND BAY", 2), ("DUNDAS WEST STATION", 1)]
    assert [(c.cause.code, c.cause.description, c.count) for c in p.top_causes] == [
        ("MTSAN", "UNSANITARY VEHICLE", 2),  # described from the streetcar code list
        ("ETBO", "BODY", 1),
    ]
    assert p.by_weekday_hour[0][8] == 2  # Monday 8 a.m.
    assert p.by_weekday_hour[1][17] == 1


def test_unknown_route() -> None:
    with pytest.raises(routes.RouteNotFoundError):
        routes.route_profile(FakeRouteQueries([]), Mode.BUS, 999)


@pytest.mark.parametrize(
    ("logged", "label"),
    [("504 KING", "504 King"), ("939 FINCH EXPRESS", "939 Finch Express"), ("500", "500")],
)
def test_route_label(logged: str, label: str) -> None:
    assert route_label(logged) == label
