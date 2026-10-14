import httpx
import pytest

from signal_problems.infrastructure.toronto_open_data import (
    CKAN_API,
    CURRENT_LOG,
    CsvFileSource,
    TorontoOpenDataSource,
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
