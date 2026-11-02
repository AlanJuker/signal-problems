from datetime import date, datetime, time

import pytest

from signal_problems.domain.commute import CommuteRisk, Trip, chance_of_any, count_weekdays
from signal_problems.domain.lines import Line
from signal_problems.domain.stations import TTC_SUBWAY


def trip(departure: time, origin: str = "bloor-yonge", destination: str = "union") -> Trip:
    stations = tuple(TTC_SUBWAY.between(Line.YONGE_UNIVERSITY, origin, destination))
    return Trip(Line.YONGE_UNIVERSITY, stations, weekday=0, departure=departure)


def test_window_covers_travel_time_plus_margins() -> None:
    # Bloor-Yonge → Union is 479 s on the schedule, about 8 min, ±15 min margin
    assert trip(time(8, 15)).travel_seconds() == 479
    assert trip(time(8, 15)).window() == (time(8, 0), time(8, 38))


def test_travel_time_is_the_same_both_ways() -> None:
    there = trip(time(8, 15))
    back = trip(time(8, 15), origin="union", destination="bloor-yonge")
    assert there.travel_seconds() == back.travel_seconds()


@pytest.mark.parametrize("line", list(Line))
def test_every_pair_of_neighbouring_stations_has_a_run_time(line: Line) -> None:
    stations = TTC_SUBWAY.on_line(line)
    whole_line = Trip(line, tuple(stations), weekday=0, departure=time(12, 0))
    assert whole_line.travel_seconds() > 60 * (len(stations) - 1)


@pytest.mark.parametrize(
    ("departure", "window"),
    [
        (time(0, 5), (time(0, 0), time(0, 28))),
        (time(23, 50), (time(23, 35), time.max)),
    ],
)
def test_window_stays_within_the_day(departure: time, window: tuple[time, time]) -> None:
    assert trip(departure).window() == window


@pytest.mark.parametrize(
    ("moment", "affected"),
    [
        (datetime(2026, 8, 31, 8, 0), True),  # Monday, window start
        (datetime(2026, 8, 31, 8, 38), True),  # window end
        (datetime(2026, 8, 31, 7, 59), False),
        (datetime(2026, 9, 1, 8, 15), False),  # Tuesday
    ],
)
def test_affects(moment: datetime, affected: bool) -> None:
    assert trip(time(8, 15)).affects(moment) is affected


@pytest.mark.parametrize(
    ("first", "last", "weekday", "count"),
    [
        (date(2026, 8, 31), date(2026, 8, 31), 0, 1),  # a single Monday
        (date(2026, 8, 31), date(2026, 9, 6), 6, 1),
        (date(2026, 9, 1), date(2026, 9, 6), 0, 0),  # Tue–Sun, no Monday
        (date(2025, 1, 1), date(2026, 8, 31), 0, 87),
        (date(2026, 9, 2), date(2026, 9, 1), 0, 0),
    ],
)
def test_count_weekdays(first: date, last: date, weekday: int, count: int) -> None:
    assert count_weekdays(first, last, weekday) == count


def test_risk_share() -> None:
    assert CommuteRisk(days_observed=87, days_hit=24).share == pytest.approx(0.2759, abs=1e-4)
    assert CommuteRisk(days_observed=0, days_hit=0).share == 0.0


def test_hours_covered_splits_the_window_by_hour() -> None:
    # 6 min of travel: 07:50–08:26, the last 10 minutes of 7 a.m. and 26 minutes of 8 a.m.
    assert trip(time(8, 5), destination="king").hours_covered() == [(7, 10 / 60), (8, 26 / 60)]


def test_chance_of_any_combines_cells() -> None:
    # Two full hours at 10% and 20%: no delay in either is 0.9 x 0.8
    assert chance_of_any([(0.1, 1.0), (0.2, 1.0)]) == pytest.approx(1 - 0.9 * 0.8)
    # Half an hour at 10% is less likely than the full hour, and no cells means no delay
    assert chance_of_any([(0.1, 0.5)]) == pytest.approx(1 - 0.9**0.5)
    assert chance_of_any([]) == 0.0
