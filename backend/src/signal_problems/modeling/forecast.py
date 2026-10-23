"""Next week's delay probabilities per station and hour, for the commute check (issue #25).

The model from #24, trained on every day in the data, applied to the seven days after it ends.
"""

from datetime import date, timedelta

import pandas as pd

from signal_problems.modeling.dataset import FEATURES, build_cells
from signal_problems.modeling.experiment import fit_model

ITERATIONS = 50  # boosting rounds the #24 experiment chose on 2024


def forecast_week(events: pd.DataFrame, stations: list[str], last: date) -> pd.DataFrame:
    """station_id, date, hour and probability for each of the seven days after `last`.

    Recent counts are the ones known on `last`, for every day: later days haven't happened yet.
    """
    first = events["date"].min().date()
    next_day = last + timedelta(days=1)
    cells = build_cells(events, stations, first, next_day)
    model = fit_model(cells[cells["date"] <= pd.Timestamp(last)], ITERATIONS)

    latest = cells[cells["date"] == pd.Timestamp(next_day)]
    week = pd.concat(
        latest.assign(date=pd.Timestamp(next_day + timedelta(days=k))) for k in range(7)
    )
    week["weekday"] = week["date"].dt.weekday.astype("int8")
    week["month"] = week["date"].dt.month.astype("int8")
    week["probability"] = model.predict_proba(week[FEATURES])[:, 1]
    return week[["station_id", "date", "hour", "probability"]].reset_index(drop=True)
