from datetime import datetime, time
from io import BytesIO

import httpx
import pytest
from openpyxl import Workbook

from signal_problems.application.ports import RawDelayRow
from signal_problems.infrastructure.toronto_open_data import (
    CKAN_API,
    CURRENT_LOG,
    CsvFileSource,
    TorontoOpenDataSource,
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
