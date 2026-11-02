"""Is the commute check's chance right for whole trips?

The model from #24 is scored per station and hour. The commute check combines a trip's cells with
`chance_of_any`, which treats them as independent. This compares that combined chance with what
happened, for a fixed set of trips on every day of the test period.
"""

from dataclasses import dataclass
from datetime import time

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from signal_problems.domain.commute import Trip
from signal_problems.domain.lines import Line
from signal_problems.domain.stations import StationRegistry
from signal_problems.modeling.experiment import Scores, calibration, score

LENGTHS = (3, 6, 10)  # stations, both ends included
DEPARTURES = (time(8, 0), time(12, 0), time(17, 30), time(21, 0))


def sample_trips(registry: StationRegistry) -> list[Trip]:
    """Every run of 3, 6 and 10 neighbouring stations on each line, at four times of day."""
    trips = []
    for line in Line:
        stations = registry.on_line(line)
        for length in LENGTHS:
            for start in range(len(stations) - length + 1):
                trips += [
                    # The weekday is unused: each trip is scored on every day
                    Trip(line, tuple(stations[start : start + length]), 0, departure)
                    for departure in DEPARTURES
                ]
    return trips


def _minutes(moment: time) -> int:
    return moment.hour * 60 + moment.minute


def hits(
    trips: list[Trip], times: pd.DataFrame, stations: list[str], days: pd.DatetimeIndex
) -> NDArray[np.bool_]:
    """Trips by days: whether a 5+ minute delay at one of the trip's stations fell in its window.

    `times` has one row per delay: station_id and occurred_at.
    """
    day = days.get_indexer(times["occurred_at"].dt.normalize())
    known = day >= 0
    day = day[known]
    station = pd.Categorical(times["station_id"][known], categories=stations).codes
    minute = (times["occurred_at"].dt.hour * 60 + times["occurred_at"].dt.minute)[known].to_numpy()

    hit = np.zeros((len(trips), len(days)), dtype=bool)
    for k, trip in enumerate(trips):
        start, end = trip.window()
        ids = [stations.index(s.id) for s in trip.stations]
        on_trip = np.isin(station, ids) & (minute >= _minutes(start)) & (minute <= _minutes(end))
        hit[k, day[on_trip]] = True
    return hit


def chances(
    trips: list[Trip], predictions: pd.DataFrame, stations: list[str], days: pd.DatetimeIndex
) -> NDArray[np.float64]:
    """Trips by days: `chance_of_any` over the trip's cells, from the model's probabilities.

    `predictions` has station_id, date, hour and p. Hours it doesn't cover count as no delay.
    """
    p = np.zeros((len(stations), len(days), 24))
    station = pd.Categorical(predictions["station_id"], categories=stations).codes
    p[station, days.get_indexer(predictions["date"]), predictions["hour"]] = predictions["p"]
    log_none = np.log1p(-p)

    chance = np.empty((len(trips), len(days)))
    for k, trip in enumerate(trips):
        ids = [stations.index(s.id) for s in trip.stations]
        none = sum(
            (share * log_none[ids, :, hour].sum(axis=0) for hour, share in trip.hours_covered()),
            start=np.zeros(len(days)),
        )
        chance[k] = -np.expm1(none)
    return chance


@dataclass(frozen=True)
class TripReport:
    trip_days: int
    observed: float  # share of trip-days with a 5+ minute delay in the window
    predicted: float  # mean combined chance
    scores: list[Scores]
    calibration: pd.DataFrame
    by_length: pd.DataFrame


def evaluate(
    trips: list[Trip],
    stations: list[str],
    predictions: pd.DataFrame,
    times: pd.DataFrame,
    history: pd.DatetimeIndex,
) -> TripReport:
    """The model's combined chance against the frequency the commute check shows, on the days
    `predictions` covers.

    The frequency is the share of `history` days with the same weekday on which the trip was hit.
    """
    test = pd.DatetimeIndex(predictions["date"].drop_duplicates().sort_values())
    observed = hits(trips, times, stations, test)
    model = chances(trips, predictions, stations, test)
    past = hits(trips, times, stations, history)
    by_weekday = np.stack(
        [past[:, history.day_of_week == w].mean(axis=1) for w in range(7)], axis=1
    )
    frequency = by_weekday[:, test.day_of_week]

    labels = pd.Series(observed.ravel().astype(int))
    lengths = pd.DataFrame(
        {
            "stations": np.repeat([len(t.stations) for t in trips], len(test)),
            "predicted": model.ravel(),
            "observed": labels,
        }
    )
    return TripReport(
        trip_days=observed.size,
        observed=float(observed.mean()),
        predicted=float(model.mean()),
        scores=[
            score("frequency, 2014–2024", labels, frequency.ravel()),
            score("gradient boosting, cells combined", labels, model.ravel()),
        ],
        calibration=calibration(labels, model.ravel()),
        by_length=lengths.groupby("stations")[["predicted", "observed"]].mean(),
    )
