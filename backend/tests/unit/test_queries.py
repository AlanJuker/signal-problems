from collections.abc import Sequence
from datetime import date, datetime, time

import pytest

from signal_problems.application import queries
from signal_problems.application.queries import DelayFact
from signal_problems.domain.causes import CauseCategory
from signal_problems.domain.lines import Line
from signal_problems.domain.stations import TTC_SUBWAY

MONDAY = datetime(2026, 8, 31)


def fact(  # noqa: PLR0913 (test builder: every field has a default)
    station: str,
    *,
    hour: int = 8,
    minute: int = 10,
    minutes: int = 6,
    code: str = "MUIS",
    line: Line | None = Line.YONGE_UNIVERSITY,
    segment_end: str | None = None,
    day: datetime = MONDAY,
) -> DelayFact:
    at = day.replace(hour=hour, minute=minute)
    return DelayFact(at, station, segment_end, line, code, minutes)


class FakeQueries:
    def __init__(
        self,
        facts: list[DelayFact],
        coverage: tuple[date, date] | None,
        forecast: queries.Forecast | None = None,
    ) -> None:
        self.facts = facts
        self._coverage = coverage
        self._forecast = forecast

    def coverage(self) -> tuple[date, date] | None:
        return self._coverage

    def at_stations(
        self, station_ids: Sequence[str], line: Line | None = None, since: date | None = None
    ) -> list[DelayFact]:
        return [
            f
            for f in self.facts
            if (f.station_id in station_ids or f.segment_end_id in station_ids)
            and (line is None or f.line in (line, None))
            and (since is None or f.occurred_at.date() >= since)
        ]

    def totals(self) -> tuple[int, int, int]:
        return len(self.facts), sum(f.is_significant for f in self.facts), 0

    def forecast(self, station_ids: Sequence[str], weekday: int) -> queries.Forecast | None:
        return self._forecast


FOUR_MONDAYS = (date(2026, 8, 10), date(2026, 8, 31))


def test_summary() -> None:
    s = queries.summary(FakeQueries([fact("union"), fact("union", minutes=0)], FOUR_MONDAYS))
    assert (s.first_day, s.incidents, s.significant) == (date(2026, 8, 10), 2, 1)


def test_summary_of_an_empty_database() -> None:
    s = queries.summary(FakeQueries([], None))
    assert (s.first_day, s.last_day, s.incidents) == (None, None, 0)


def test_line_heat_lists_every_station_in_order() -> None:
    facts = [fact("union"), fact("union", minutes=0), fact("kipling", line=Line.BLOOR_DANFORTH)]
    heat = queries.line_heat(FakeQueries(facts, FOUR_MONDAYS), TTC_SUBWAY, Line.YONGE_UNIVERSITY)

    assert len(heat) == 38
    assert heat[0].station.id == "vaughan-metropolitan-centre"
    union = next(h for h in heat if h.station.id == "union")
    assert (union.incidents, union.significant, union.minutes_lost) == (2, 1, 6)


def test_station_profile() -> None:
    facts = [
        fact("union", code="SUDP"),
        fact("union", code="SUDP", hour=17),
        fact("union", code="PUSI", minutes=12),
        fact("union", minutes=0),
        fact("finch", segment_end="union"),  # a segment ending here isn't a delay at Union
    ]
    p = queries.station_profile(FakeQueries(facts, FOUR_MONDAYS), TTC_SUBWAY, "union")

    assert (p.incidents, p.significant, p.minutes_lost) == (4, 3, 24)
    assert p.categories == {CauseCategory.SECURITY: 2, CauseCategory.INFRASTRUCTURE: 1}
    assert p.top_causes[0].cause.code == "SUDP"
    assert p.by_weekday_hour[0][8] == 2
    assert p.by_weekday_hour[0][17] == 1


def test_unknown_station() -> None:
    with pytest.raises(queries.StationNotFoundError):
        queries.station_profile(FakeQueries([], None), TTC_SUBWAY, "leaside")


def test_assess_commute() -> None:
    facts = [
        fact("tmu", day=datetime(2026, 8, 10)),
        fact("tmu", day=datetime(2026, 8, 10), minute=20),  # same day, counted once
        fact("king", day=datetime(2026, 8, 24)),
        fact("king", day=datetime(2026, 8, 24), hour=12),  # outside the window
        fact("king", day=datetime(2026, 8, 25)),  # Tuesday
        fact("king", day=datetime(2026, 8, 17), minutes=3),  # too short
        fact("finch", day=datetime(2026, 8, 17)),  # not on the trip
        fact("finch", segment_end="king", day=datetime(2026, 8, 17)),  # starts off the trip
        fact("queen", segment_end="union", day=datetime(2026, 8, 31)),  # inside the trip
    ]
    query = queries.CommuteQuery(Line.YONGE_UNIVERSITY, "bloor-yonge", "union", 0, time(8, 15))
    a = queries.assess_commute(FakeQueries(facts, FOUR_MONDAYS), TTC_SUBWAY, query)

    assert (a.risk.days_observed, a.risk.days_hit) == (4, 3)
    # Ties keep travel order: Queen comes before King southbound
    assert [(s.id, n) for s, n in a.worst_stations] == [("tmu", 2), ("queen", 1), ("king", 1)]
    assert a.top_causes[0].count == 4


def test_assess_commute_without_data() -> None:
    query = queries.CommuteQuery(Line.SHEPPARD, "leslie", "bayview", 2, time(9, 0))
    a = queries.assess_commute(FakeQueries([], None), TTC_SUBWAY, query)
    assert a.risk.share == 0.0
    assert [s.id for s in a.trip.stations] == ["leslie", "bessarion", "bayview"]
    assert a.forecast is None  # no model trained


def test_trip_forecast_combines_the_cells_inside_the_window() -> None:
    forecast = queries.Forecast(
        date(2026, 9, 7),
        {
            ("tmu", 8): 0.1,
            ("union", 8): 0.2,
            ("tmu", 12): 0.9,  # outside the window
            ("finch", 8): 0.9,  # not on the trip
        },
    )
    query = queries.CommuteQuery(Line.YONGE_UNIVERSITY, "bloor-yonge", "union", 0, time(8, 15))
    a = queries.assess_commute(FakeQueries([], FOUR_MONDAYS, forecast), TTC_SUBWAY, query)

    # The window is 08:00–08:42: 70% of the 8 a.m. hour at each station
    expected = 1 - (0.9 * 0.8) ** 0.7
    assert a.forecast == queries.TripForecast(date(2026, 9, 7), pytest.approx(expected))


def test_since_limits_every_query() -> None:
    old = fact("union", day=datetime(2026, 8, 10))
    recent = fact("union", day=datetime(2026, 8, 31))
    fake = FakeQueries([old, recent], FOUR_MONDAYS)
    since = date(2026, 8, 20)

    heat = queries.line_heat(fake, TTC_SUBWAY, Line.YONGE_UNIVERSITY, since)
    assert next(h for h in heat if h.station.id == "union").significant == 1
    assert queries.station_profile(fake, TTC_SUBWAY, "union", since).significant == 1


def test_since_starting_mid_week_counts_only_the_days_after_it() -> None:
    facts = [fact("tmu", day=datetime(2026, 8, 10)), fact("tmu", day=datetime(2026, 8, 24))]
    # Thursday 2026-08-20: two Mondays left in the data (24th and 31st)
    query = queries.CommuteQuery(
        Line.YONGE_UNIVERSITY, "bloor-yonge", "union", 0, time(8, 15), since=date(2026, 8, 20)
    )
    a = queries.assess_commute(FakeQueries(facts, FOUR_MONDAYS), TTC_SUBWAY, query)

    assert (a.risk.days_observed, a.risk.days_hit) == (2, 1)


def test_since_before_the_data_starts_counts_the_whole_history() -> None:
    query = queries.CommuteQuery(
        Line.YONGE_UNIVERSITY, "bloor-yonge", "union", 0, time(8, 15), since=date(2020, 1, 1)
    )
    a = queries.assess_commute(FakeQueries([], FOUR_MONDAYS), TTC_SUBWAY, query)
    assert a.risk.days_observed == 4
