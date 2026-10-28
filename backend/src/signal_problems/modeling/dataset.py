"""Station-by-date-by-hour cells for the commute risk experiment (issue #21).

A cell is positive when the station had at least one 5+ minute delay in that hour. Features only
look at days before the cell's date, so a model can't see the future it is asked to predict.
"""

from datetime import date

import pandas as pd

# The subway runs from about 6 a.m. to 1:30 a.m.; 2–4 a.m. has almost no delays.
SERVICE_HOURS = (0, 1, *range(5, 24))
FEATURES = ["station", "weekday", "hour", "month", "station_7d", "station_28d", "system_7d"]


def significant_delays(connection: object) -> pd.DataFrame:
    """One row per 5+ minute delay at a known station: station_id, date, hour."""
    events = pd.read_sql(
        "SELECT station_id, occurred_at FROM delays WHERE minutes >= 5 AND station_id IS NOT NULL",
        connection,
        parse_dates=["occurred_at"],
    )
    return pd.DataFrame(
        {
            "station_id": events["station_id"],
            "date": events["occurred_at"].dt.normalize(),
            "hour": events["occurred_at"].dt.hour,
        }
    )


def build_cells(events: pd.DataFrame, stations: list[str], first: date, last: date) -> pd.DataFrame:
    """Every station, date and service hour between two dates, with its label and features."""
    dates = pd.date_range(first, last, freq="D")
    cells = pd.MultiIndex.from_product(
        [stations, dates, SERVICE_HOURS], names=["station_id", "date", "hour"]
    ).to_frame(index=False)

    hit = events.drop_duplicates()[["station_id", "date", "hour"]].assign(label=1)
    cells = cells.merge(hit, on=["station_id", "date", "hour"], how="left")
    cells["label"] = cells["label"].fillna(0).astype("int8")

    # Daily counts per station, summed over the previous 7 and 28 days (shifted: today excluded)
    daily = (
        events.groupby(["date", "station_id"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=dates, columns=stations, fill_value=0)
    )
    recent = {
        "station_7d": daily.rolling(7, min_periods=1).sum().shift(1),
        "station_28d": daily.rolling(28, min_periods=1).sum().shift(1),
    }
    for name, frame in recent.items():
        long = frame.stack().rename(name).reset_index()
        long.columns = ["date", "station_id", name]
        cells = cells.merge(long, on=["date", "station_id"], how="left")
    system = daily.sum(axis=1).rolling(7, min_periods=1).sum().shift(1).rename("system_7d")
    cells = cells.merge(system, left_on="date", right_index=True, how="left")

    cells[["station_7d", "station_28d", "system_7d"]] = (
        cells[["station_7d", "station_28d", "system_7d"]].fillna(0).astype("float32")
    )
    cells["station"] = pd.Categorical(cells["station_id"], categories=stations).codes.astype(
        "int16"
    )
    cells["weekday"] = cells["date"].dt.day_of_week.astype("int8")
    cells["month"] = cells["date"].dt.month.astype("int8")
    cells["hour"] = cells["hour"].astype("int8")
    return cells
