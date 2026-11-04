from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from signal_problems.api.app import create_app
from signal_problems.application.ingest import IngestSurfaceDelays
from signal_problems.domain.surface import Mode
from signal_problems.infrastructure.database import SqlSurfaceDelayRepository
from signal_problems.infrastructure.toronto_open_data import CsvFileSource
from tests.conftest import SAMPLE_CSV


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    source = CsvFileSource(SAMPLE_CSV.parent / "streetcar_sample.csv")
    with Session(engine) as session:
        IngestSurfaceDelays(source, SqlSurfaceDelayRepository(session), Mode.STREETCAR)()
    with TestClient(create_app(lambda: Session(engine))) as client:
        yield client


def test_routes_are_ranked_by_5_minute_delays(client: TestClient) -> None:
    assert client.get("/routes", params={"mode": "streetcar"}).json() == [
        # "504 KING" twice and the 504A branch once
        {
            "mode": "streetcar",
            "route": 504,
            "name": "504 King",
            "incidents": 3,
            "significant": 3,
            "minutes_lost": 42,
        },
        {
            "mode": "streetcar",
            "route": 500,
            "name": "500",
            "incidents": 1,
            "significant": 0,
            "minutes_lost": 0,
        },
    ]
    assert client.get("/routes", params={"mode": "bus"}).json() == []


def test_since_filters_routes(client: TestClient) -> None:
    body = client.get("/routes", params={"mode": "streetcar", "since": "2025-02-01"}).json()
    assert [(r["route"], r["incidents"]) for r in body] == [(504, 1)]


def test_route_profile(client: TestClient) -> None:
    body = client.get("/routes/streetcar/504").json()
    assert body["route"]["significant"] == 3
    assert body["top_locations"][0] == {"location": "KING AND PARLIAMENT", "delays": 1}
    assert {c["code"] for c in body["top_causes"]} == {"MTSAN", "MTVIS", "MTAFR"}
    assert body["by_weekday_hour"][2][2] == 1  # Wednesday 2 a.m.


@pytest.mark.parametrize(
    ("path", "status"),
    [("/routes/bus/504", 404), ("/routes/ferry/504", 422), ("/routes?mode=ferry", 422)],
)
def test_route_errors(client: TestClient, path: str, status: int) -> None:
    assert client.get(path).status_code == status
