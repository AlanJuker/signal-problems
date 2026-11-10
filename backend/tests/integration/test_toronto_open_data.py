from datetime import datetime, time
from io import BytesIO

import httpx
import pytest
from openpyxl import Workbook

from signal_problems.application.ports import RawDelayRow
from signal_problems.domain.surface import Mode
from signal_problems.infrastructure.toronto_open_data import (
    CKAN_API,
    CURRENT_LOG,
    STREETCAR_HISTORY,
    SURFACE,
    CsvFileSource,
    TorontoOpenDataSource,
    parse_surface_history,
    parse_xlsx,
)
from tests.conftest import SAMPLE_CSV


def test_reads_a_saved_csv() -> None:
    rows = list(CsvFileSource(SAMPLE_CSV).fetch())
    assert len(rows) == 7
    assert rows[0].station == "BATHURST STATION"
    assert rows[0].code == "MUSAN"


def test_downloads_the_current_log_through_ckan() -> None:
    csv_url = "https://example.test/delays.csv"

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(f"{CKAN_API}/package_show"):
            assert request.url.params["id"] == "ttc-subway-delay-data"
            resources = [
                {"name": "ttc-subway-delay-data-2024", "url": "https://example.test/2024.xlsx"},
                {"name": CURRENT_LOG, "url": csv_url},
            ]
            return httpx.Response(200, json={"result": {"resources": resources}})
        assert str(request.url) == csv_url
        return httpx.Response(200, text=SAMPLE_CSV.read_text())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows = list(TorontoOpenDataSource(client).fetch())

    assert len(rows) == 7


def test_surfaces_portal_errors() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(503))
    with httpx.Client(transport=transport) as client, pytest.raises(httpx.HTTPStatusError):
        list(TorontoOpenDataSource(client).fetch())


def workbook(*sheets: list[tuple[object, ...]]) -> bytes:
    book = Workbook()
    book.remove(book.active)  # type: ignore[arg-type]
    for i, rows in enumerate(sheets):
        sheet = book.create_sheet(f"Sheet {i}")
        for row in rows:
            sheet.append(row)
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


HEADER = (
    "Date",
    "Time",
    "Day",
    "Station",
    "Code",
    "Min Delay",
    "Min Gap",
    "Bound",
    "Line",
    "Vehicle",
)


def test_parses_every_sheet_of_a_workbook() -> None:
    data = workbook(
        [
            (*HEADER, None, None),  # some years have empty trailing columns
            (
                datetime(2019, 1, 1),
                "01:08",
                "Tuesday",
                "YORK MILLS STATION",
                "PUSI",
                0,
                0,
                "S",
                "YU",
                5766,
            ),
            (None,),  # blank rows at the end of a sheet
        ],
        [
            HEADER,
            (
                datetime(2019, 2, 1),
                time(7, 5),
                "Friday",
                "KIPLING STATION",
                "MUIS",
                6.0,
                9,
                None,
                "BD",
                5100,
            ),
        ],
        [("Notes",), ("Not a data sheet",)],
    )

    rows = list(parse_xlsx(BytesIO(data)))

    assert rows == [
        RawDelayRow(
            "2019-01-01", "01:08", "YORK MILLS STATION", "YU", "PUSI", "0", "0", "S", "5766"
        ),
        RawDelayRow("2019-02-01", "07:05", "KIPLING STATION", "BD", "MUIS", "6", "9", "", "5100"),
    ]


def test_downloads_history_before_the_current_log() -> None:
    history = workbook(
        [
            HEADER,
            (datetime(2018, 5, 1), "08:00", "Tuesday", "UNION STATION", "MUIS", 5, 8, "N", "YU", 1),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(f"{CKAN_API}/package_show"):
            resources = [
                {"name": "ttc-subway-delay-codes", "url": "https://example.test/codes.xlsx"},
                {"name": "ttc-subway-delay-data-2018", "url": "https://example.test/2018.xlsx"},
                {"name": CURRENT_LOG, "url": "https://example.test/current.csv"},
            ]
            return httpx.Response(200, json={"result": {"resources": resources}})
        if url.endswith("2018.xlsx"):
            return httpx.Response(200, content=history)
        if url.endswith("current.csv"):
            return httpx.Response(200, content=b"\xef\xbb\xbf" + SAMPLE_CSV.read_bytes())
        raise AssertionError(f"unexpected request: {url}")  # the code table must not be fetched

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows = list(TorontoOpenDataSource(client, include_history=True).fetch())

    assert rows[0].date == "2018-05-01"
    assert len(rows) == 1 + 7


OLD_HEADER = ("Report Date", "Route", "Time", "Day", "Location", "Incident", "Min Delay", "Min Gap")


def test_parses_surface_history_whatever_its_columns_are_called() -> None:
    data = workbook(
        [  # 2014–2019: "Report Date", "Route", "Direction"
            (*OLD_HEADER, "Direction", "Vehicle"),
            (
                datetime(2014, 1, 2),
                505,
                time(6, 31),
                "Thursday",
                "Dundas and Roncesvalles",
                "Late Leaving Garage",
                4,
                8,
                "E/B",
                4018,
            ),
        ],
        [  # 2019–2020: "Delay" and "Gap", sometimes with an "Incident ID"
            (
                "Report Date",
                "Route",
                "Time",
                "Day",
                "Location",
                "Incident ID",
                "Incident",
                "Delay",
                "Gap",
                "Direction",
                "Vehicle",
            ),
            (
                datetime(2019, 9, 3),
                501,
                time(8, 0),
                "Tuesday",
                "Queen and Bay",
                7,
                "Late  ",
                6,
                12,
                "W/B",
                4400,
            ),
        ],
        [  # 2020–2024: "Date", "Line", "Bound", times as text
            (
                "Date",
                "Line",
                "Time",
                "Day",
                "Location",
                "Incident",
                "Min Delay",
                "Min Gap",
                "Bound",
                "Vehicle",
            ),
            (
                datetime(2024, 3, 1),
                "504",
                "17:45",
                "Friday",
                "King and Bathurst",
                "e",
                None,
                0,
                "E",
                4500,
            ),
        ],
    )

    rows = list(parse_surface_history(BytesIO(data), STREETCAR_HISTORY))

    assert rows == [
        RawDelayRow(
            "2014-01-02",
            "06:31",
            "Dundas and Roncesvalles",
            "505",
            "LATE LEAVING GARAGE",
            "4",
            "8",
            "E/B",
            "4018",
        ),
        RawDelayRow(
            "2019-09-03", "08:00", "Queen and Bay", "501", "LATE", "6", "12", "W/B", "4400"
        ),
        RawDelayRow("2024-03-01", "17:45", "King and Bathurst", "504", "", "", "0", "E", "4500"),
    ]


def test_downloads_a_surface_mode_s_history() -> None:
    history = workbook(
        [
            (*OLD_HEADER, "Direction", "Vehicle"),
            (
                datetime(2020, 1, 6),
                504,
                time(8, 0),
                "Monday",
                "King and Bay",
                "Mechanical",
                9,
                18,
                "E",
                4400,
            ),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(f"{CKAN_API}/package_show"):
            assert request.url.params["id"] == "ttc-streetcar-delay-data"
            resources = [
                {"name": "ttc-streetcar-delay-data-readme", "url": "https://example.test/readme"},
                {"name": "ttc-streetcar-delay-data-2020\t", "url": "https://example.test/copy"},
                {"name": "ttc-streetcar-delay-data-2020", "url": "https://example.test/2020.xlsx"},
                {
                    "name": "TTC Streetcar Delay Data since 2025.csv",
                    "url": "https://example.test/c",
                },
            ]
            return httpx.Response(200, json={"result": {"resources": resources}})
        if url.endswith("2020.xlsx"):
            return httpx.Response(200, content=history)
        if url.endswith("/c"):
            return httpx.Response(
                200, text="Date,Time,Station,Line,Code,Min Delay,Min Gap,Bound,Vehicle\n"
            )
        raise AssertionError(
            f"unexpected request: {url}"
        )  # the readme and the tab copy aren't read

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        source = TorontoOpenDataSource(
            client, include_history=True, package=SURFACE[Mode.STREETCAR]
        )
        rows = list(source.fetch())

    assert [(r.date, r.line, r.code) for r in rows] == [("2020-01-06", "504", "MECHANICAL")]


def test_bus_history_skips_the_sheets_copied_from_the_streetcar_log() -> None:
    new_header = ("Date", "Time", "Day", "Location", "Incident", "Min Delay", "Min Gap", "Vehicle")
    data = workbook(
        [  # June 2021, a real bus sheet
            (*new_header[:1], "Route", *new_header[1:], "Direction"),
            (
                datetime(2021, 6, 1),
                52,
                "08:00",
                "Tuesday",
                "Lawrence and Keele",
                "Mechanical",
                10,
                20,
                8100,
                "E",
            ),
        ],
        [  # July 2021 in the bus workbook: the streetcar sheet, headed Line and Bound
            (*new_header[:1], "Line", *new_header[1:], "Bound"),
            (
                datetime(2021, 7, 1),
                510,
                "02:30",
                "Thursday",
                "Spadina and Queens Qua",
                "Operations",
                9,
                18,
                4432,
                "N",
            ),
        ],
    )

    rows = list(SURFACE[Mode.BUS].parse_history(BytesIO(data)))

    assert [(r.date, r.line) for r in rows] == [("2021-06-01", "52")]
