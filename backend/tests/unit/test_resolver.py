import pytest

from signal_problems.domain.lines import Line
from signal_problems.domain.resolver import LocationKind, StationResolver, normalize
from signal_problems.domain.stations import TTC_SUBWAY

resolver = StationResolver(TTC_SUBWAY)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("KENNEDY BD STATION - P", ("KENNEDY", {Line.BLOOR_DANFORTH})),
        ("ST. GEORGE YUS STATION", ("ST GEORGE", {Line.YONGE_UNIVERSITY})),
        ("QUEEN'S PARK STATION (", ("QUEENS PARK", set())),
        ("FINCH STATION PLATFORM", ("FINCH", set())),
    ],
)
def test_normalize(raw: str, expected: tuple[str, set[Line]]) -> None:
    assert normalize(raw) == expected


@pytest.mark.parametrize(
    ("raw", "station_id"),
    [
        ("UNION STATION", "union"),
        # Platform names per line
        ("BLOOR STATION", "bloor-yonge"),
        ("YONGE BD STATION", "bloor-yonge"),
        ("ST GEORGE BD STATION", "st-george"),
        # Renamed stations
        ("DUNDAS STATION", "tmu"),
        ("TMU STATION", "tmu"),
        ("EGLINTON WEST STATION", "cedarvale"),
        ("CEDARVALE YU STATION", "cedarvale"),
        ("VMC STATION", "vaughan-metropolitan-centre"),
        # Cut off by the 22-character limit
        ("PIONEER VILLAGE STATIO", "pioneer-village"),
        ("NORTH YORK CTR STATION", "north-york-centre"),
        # Typos
        ("KENENDY STATION", "kennedy"),
        ("YORKDLAE STATION", "yorkdale"),
        ("LANDSDOWNE STATION", "lansdowne"),
        # Similar names must stay distinct
        ("DUNDAS WEST STATION", "dundas-west"),
        ("ST CLAIR STATION", "st-clair"),
        ("ST CLAIR WEST STATION", "st-clair-west"),
    ],
)
def test_resolves_stations(raw: str, station_id: str) -> None:
    location = resolver.resolve(raw)
    assert location.kind is LocationKind.STATION
    assert [s.id for s in location.stations] == [station_id]


def test_keeps_line_hints_from_column_and_name() -> None:
    location = resolver.resolve("SPADINA YUS STATION", "YU/BD")
    assert location.line_hints == {Line.YONGE_UNIVERSITY, Line.BLOOR_DANFORTH}


@pytest.mark.parametrize(
    ("raw", "ends"),
    [
        ("FINCH TO ST CLAIR", ("finch", "st-clair")),
        ("UNION STATION TO KING", ("union", "king")),
        ("UNION TO ST ANDREW STA", ("union", "st-andrew")),
    ],
)
def test_resolves_segments(raw: str, ends: tuple[str, str]) -> None:
    location = resolver.resolve(raw)
    assert location.kind is LocationKind.SEGMENT
    assert tuple(s.id for s in location.stations) == ends


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        ("GREENWOOD YARD", LocationKind.FACILITY),
        ("WILSON CAR HOUSE", LocationKind.FACILITY),
        ("TEDDINGTON EE", LocationKind.FACILITY),
        ("LINE 1 YONGE UNIVERSIT", LocationKind.LINE_WIDE),
        ("YONGE-UNIVERSITY AND B", LocationKind.LINE_WIDE),
        ("BLOOR DANFORTH SUBWAY", LocationKind.LINE_WIDE),
        ("YUS", LocationKind.LINE_WIDE),
        # Not guessed: closed Line 3, a station that isn't on these lines, incomplete segments
        ("SCARBOROUGH CTR STATIO", LocationKind.UNRESOLVED),
        ("LEASIDE STATION", LocationKind.UNRESOLVED),
        ("UNION STATION - NB TO", LocationKind.UNRESOLVED),
        ("", LocationKind.UNRESOLVED),
    ],
)
def test_classifies_other_locations(raw: str, kind: LocationKind) -> None:
    location = resolver.resolve(raw)
    assert location.kind is kind
    assert location.stations == ()


@pytest.mark.parametrize(
    ("raw", "lines"),
    [
        ("LINE 2 BLOOR DANFORTH", {Line.BLOOR_DANFORTH}),
        ("LINE1 - YONGE-UNIVSERS", {Line.YONGE_UNIVERSITY}),
        ("YONGE-UNIVERSITY AND B", {Line.YONGE_UNIVERSITY, Line.BLOOR_DANFORTH}),
        ("SHEPPARD LINE", {Line.SHEPPARD}),
    ],
)
def test_line_wide_locations_keep_the_lines_they_name(raw: str, lines: set[Line]) -> None:
    location = resolver.resolve(raw)
    assert location.kind is LocationKind.LINE_WIDE
    assert location.line_hints == lines
