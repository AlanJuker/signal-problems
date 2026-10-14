import pytest

from signal_problems.domain.lines import Line
from signal_problems.domain.stations import TTC_SUBWAY


def test_registry_has_every_station_once() -> None:
    assert len(TTC_SUBWAY.all()) == 70
    assert sum(len(TTC_SUBWAY.on_line(line)) for line in Line) == 74  # 4 interchanges


@pytest.mark.parametrize(
    ("station_id", "lines"),
    [
        ("bloor-yonge", {Line.YONGE_UNIVERSITY, Line.BLOOR_DANFORTH}),
        ("sheppard-yonge", {Line.YONGE_UNIVERSITY, Line.SHEPPARD}),
        ("queens-park", {Line.YONGE_UNIVERSITY}),
        ("kennedy", {Line.BLOOR_DANFORTH}),
    ],
)
def test_station_lines(station_id: str, lines: set[Line]) -> None:
    station = TTC_SUBWAY.get(station_id)
    assert station is not None
    assert station.lines == lines


def test_between_follows_travel_order_in_both_directions() -> None:
    southbound = TTC_SUBWAY.between(Line.YONGE_UNIVERSITY, "bloor-yonge", "union")
    assert [s.id for s in southbound] == [
        "bloor-yonge",
        "wellesley",
        "college",
        "tmu",
        "queen",
        "king",
        "union",
    ]
    northbound = TTC_SUBWAY.between(Line.YONGE_UNIVERSITY, "union", "bloor-yonge")
    assert northbound == list(reversed(southbound))


def test_between_single_station() -> None:
    assert [s.id for s in TTC_SUBWAY.between(Line.SHEPPARD, "leslie", "leslie")] == ["leslie"]


def test_between_rejects_stations_on_another_line() -> None:
    with pytest.raises(ValueError, match="Line 4"):
        TTC_SUBWAY.between(Line.SHEPPARD, "union", "leslie")
