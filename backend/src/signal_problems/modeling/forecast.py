"""Next week's delay probabilities per station and hour, for the commute check (issue #25).

The model from #24, trained on every day in the data, applied to the seven days after it ends, then
scaled per hour by the correction from #36.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from signal_problems.modeling.dataset import FEATURES, build_cells
from signal_problems.modeling.experiment import CORRECTION_DAYS, fit_model, hour_factors

ITERATIONS = 50  # boosting rounds the #24 experiment chose on 2024


def forecast_week(events: pd.DataFrame, stations: list[str], last: date) -> pd.DataFrame:
    """station_id, date, hour and probability for each of the seven days after `last`.

    Recent counts are the ones known on `last`, for every day: later days haven't happened yet.
    """
    first = events["date"].min().date()
    next_day = last + timedelta(days=1)
    cells = build_cells(events, stations, first, next_day)
    model = fit_model(cells[cells["date"] <= pd.Timestamp(last)], ITERATIONS)

    # The correction needs the model's errors on days it hasn't seen, so it comes from a second
    # model that stops CORRECTION_DAYS before the data ends
    start = pd.Timestamp(next_day - timedelta(days=CORRECTION_DAYS))
    held_out = fit_model(cells[cells["date"] < start], ITERATIONS)
    recent = cells[cells["date"] >= start]
    factors = hour_factors(recent, held_out.predict_proba(recent[FEATURES])[:, 1])

    latest = cells[cells["date"] == pd.Timestamp(next_day)]
    week = pd.concat(
        latest.assign(date=pd.Timestamp(next_day + timedelta(days=k))) for k in range(7)
    )
    week["weekday"] = week["date"].dt.day_of_week.astype("int8")
    week["month"] = week["date"].dt.month.astype("int8")
    factor = week["hour"].map(factors.loc[pd.Timestamp(next_day)]).to_numpy()
    week["probability"] = np.minimum(model.predict_proba(week[FEATURES])[:, 1] * factor, 1.0)
    return week[["station_id", "date", "hour", "probability"]].reset_index(drop=True)
