from datetime import date

import pandas as pd
import pytest

pytest.importorskip("sklearn", reason="needs the ml dependency group")

from signal_problems.modeling.dataset import SERVICE_HOURS
from signal_problems.modeling.forecast import forecast_week


def test_forecasts_the_seven_days_after_the_data() -> None:
    days = pd.date_range("2026-07-01", "2026-08-31", freq="D")
    # "a" is delayed every morning at 8, "b" never is
    events = pd.DataFrame({"station_id": "a", "date": days, "hour": 8})

    week = forecast_week(events, ["a", "b"], date(2026, 8, 31))

    assert len(week) == 7 * 2 * len(SERVICE_HOURS)
    assert list(week["date"].drop_duplicates()) == list(pd.date_range("2026-09-01", periods=7))
    assert week["probability"].between(0, 1).all()
    at = week.set_index(["station_id", "date", "hour"])["probability"]
    tuesday = pd.Timestamp("2026-09-01")
    assert at["a", tuesday, 8] > 0.5 > at["b", tuesday, 8]
