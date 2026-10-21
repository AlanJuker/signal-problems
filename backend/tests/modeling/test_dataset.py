from datetime import date

import pandas as pd
import pytest

pytest.importorskip("sklearn", reason="needs the ml dependency group")

from signal_problems.modeling.dataset import SERVICE_HOURS, build_cells


def events(*rows: tuple[str, str, int]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "station_id": [r[0] for r in rows],
            "date": pd.to_datetime([r[1] for r in rows]),
            "hour": [r[2] for r in rows],
        }
    )


def cell(cells: pd.DataFrame, station: str, day: str, hour: int) -> pd.Series:
    match = cells[
        (cells["station_id"] == station)
        & (cells["date"] == pd.Timestamp(day))
        & (cells["hour"] == hour)
    ]
    assert len(match) == 1
    return match.iloc[0]


def test_one_cell_per_station_date_and_service_hour() -> None:
    cells = build_cells(events(), ["a", "b"], date(2024, 1, 1), date(2024, 1, 3))
    assert len(cells) == 2 * 3 * len(SERVICE_HOURS)
    assert set(cells["hour"]) == set(SERVICE_HOURS)


def test_label_marks_hours_with_a_delay_once() -> None:
    cells = build_cells(
        events(("a", "2024-01-02", 8), ("a", "2024-01-02", 8)),
        ["a", "b"],
        date(2024, 1, 1),
        date(2024, 1, 3),
    )
    assert cell(cells, "a", "2024-01-02", 8)["label"] == 1
    assert cell(cells, "a", "2024-01-02", 9)["label"] == 0
    assert cell(cells, "b", "2024-01-02", 8)["label"] == 0
    assert cells["label"].sum() == 1


def test_recent_counts_only_look_at_earlier_days() -> None:
    cells = build_cells(
        events(("a", "2024-01-10", 8)), ["a", "b"], date(2024, 1, 1), date(2024, 2, 20)
    )

    # The delay's own day must not see it: that would leak the label into the features
    assert cell(cells, "a", "2024-01-10", 9)["station_7d"] == 0
    assert cell(cells, "a", "2024-01-11", 9)["station_7d"] == 1
    assert cell(cells, "a", "2024-01-17", 9)["station_7d"] == 1
    assert cell(cells, "a", "2024-01-18", 9)["station_7d"] == 0
    assert cell(cells, "a", "2024-02-06", 9)["station_28d"] == 1
    assert cell(cells, "a", "2024-02-08", 9)["station_28d"] == 0
    assert cell(cells, "b", "2024-01-11", 9)["station_7d"] == 0
    assert cell(cells, "b", "2024-01-11", 9)["system_7d"] == 1


def test_calendar_features() -> None:
    cells = build_cells(events(), ["a", "b"], date(2024, 3, 4), date(2024, 3, 4))
    row = cell(cells, "b", "2024-03-04", 17)
    assert (row["weekday"], row["month"], row["station"]) == (0, 3, 1)
