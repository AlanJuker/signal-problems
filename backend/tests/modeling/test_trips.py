from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn", reason="needs the ml dependency group")

from signal_problems.domain.commute import Trip, chance_of_any
from signal_problems.domain.lines import Line
from signal_problems.domain.stations import TTC_SUBWAY
from signal_problems.modeling import trips

STATIONS = sorted(s.id for s in TTC_SUBWAY.all())
DAYS = pd.date_range("2025-01-06", periods=3, freq="D")  # Monday to Wednesday


def trip(departure: time = time(8, 15)) -> Trip:
    stations = tuple(TTC_SUBWAY.between(Line.YONGE_UNIVERSITY, "bloor-yonge", "union"))
    return Trip(Line.YONGE_UNIVERSITY, stations, 0, departure)


def delays(*rows: tuple[str, str]) -> pd.DataFrame:
    return pd.DataFrame(
        {"station_id": [r[0] for r in rows], "occurred_at": pd.to_datetime([r[1] for r in rows])}
    )


def test_sample_covers_every_run_of_neighbouring_stations() -> None:
    sample = trips.sample_trips(TTC_SUBWAY)
    # Line 1 has 38 stations, Line 2 31 and Line 4 5; Line 4 is too short for 6 or 10
    runs = (36 + 33 + 29) + (29 + 26 + 22) + 3
    assert len(sample) == runs * len(trips.DEPARTURES)
    assert {len(t.stations) for t in sample} == set(trips.LENGTHS)


def test_a_delay_counts_inside_the_window_at_a_trip_station() -> None:
    end = trip().window()[1]
    late = datetime.combine(DAYS[1], end) + timedelta(minutes=1)
    times = delays(
        ("tmu", f"2025-01-06 {end:%H:%M}"),  # window end, Monday
        ("tmu", f"{late:%Y-%m-%d %H:%M}"),  # a minute after it, Tuesday
        ("finch", "2025-01-08 08:10"),  # not on the trip
        ("union", "2025-01-09 08:10"),  # outside the days scored
    )
    hit = trips.hits([trip()], times, STATIONS, DAYS)
    assert hit.tolist() == [[True, False, False]]


def test_chances_match_the_commute_check() -> None:
    t = trip()
    predictions = pd.DataFrame(
        {
            "station_id": ["tmu", "union", "tmu", "tmu"],
            "date": pd.to_datetime(["2025-01-06", "2025-01-06", "2025-01-06", "2025-01-07"]),
            "hour": [8, 8, 12, 8],  # 12 is outside the window
            "p": [0.1, 0.2, 0.9, 0.3],
        }
    )
    chance = trips.chances([t], predictions, STATIONS, DAYS)

    share = dict(t.hours_covered())[8]
    assert chance[0, 0] == pytest.approx(chance_of_any([(0.1, share), (0.2, share)]))
    assert chance[0, 1] == pytest.approx(chance_of_any([(0.3, share)]))
    assert chance[0, 2] == 0.0


def test_evaluate_scores_both_methods_on_every_trip_day() -> None:
    history = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    test = pd.date_range("2025-01-01", "2025-03-31", freq="D")
    rng = np.random.default_rng(0)
    # TMU is delayed at 08:20 on about a third of days, in both periods
    days = [d for d in history.append(test) if rng.random() < 0.3]
    times = delays(*(("tmu", f"{d.date()} 08:20") for d in days))
    predictions = pd.DataFrame(
        {"station_id": "tmu", "date": test, "hour": 8, "p": 0.3 / dict(trip().hours_covered())[8]}
    )
    sample = [trip(), trip(time(14, 0))]

    report = trips.evaluate(sample, STATIONS, predictions, times, history)

    assert report.trip_days == 2 * len(test)
    assert [s.name for s in report.scores] == [
        "frequency, 2014–2024",
        "gradient boosting, cells combined",
    ]
    assert report.observed == pytest.approx(np.isin(test, days).mean() / 2)
    assert list(report.by_length.index) == [7]
