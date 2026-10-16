from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from signal_problems.api.app import create_app
from signal_problems.application.ingest import to_delay
from signal_problems.application.ports import RawDelayRow
from signal_problems.domain.resolver import StationResolver
from signal_problems.domain.stations import TTC_SUBWAY
from signal_problems.infrastructure.database import SqlDelayRepository

resolver = StationResolver(TTC_SUBWAY)


def row(station: str, when: datetime, code: str = "MUIS", minutes: int = 6) -> RawDelayRow:
    return RawDelayRow(
        date=when.strftime("%Y-%m-%d"),
        time=when.strftime("%H:%M"),
        station=station,
        line="YU",
        code=code,
        min_delay=str(minutes),
        min_gap="8",
        bound="S",
        vehicle="5000",
    )


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    rows = [
        row("TMU STATION", datetime(2026, 8, 10, 8, 20), code="PUSI"),
        row("DUNDAS STATION", datetime(2026, 8, 24, 8, 30)),  # same station, old name
        row("KING STATION", datetime(2026, 8, 31, 12, 0), minutes=0),
    ]
    with Session(engine) as session:
        SqlDelayRepository(session).add_new([to_delay(r, resolver) for r in rows])
    with TestClient(create_app(lambda: Session(engine))) as client:
        yield client


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_summary(client: TestClient) -> None:
    assert client.get("/summary").json() == {
        "first_day": "2026-08-10",
        "last_day": "2026-08-31",
        "incidents": 3,
        "significant": 2,
        "signal_problems": 1,
    }


def test_lines(client: TestClient) -> None:
    lines = client.get("/lines").json()
    assert [line["id"] for line in lines] == ["1", "2", "4"]
    assert lines[2]["stations"][0] == {
        "id": "sheppard-yonge",
        "name": "Sheppard-Yonge",
        "lines": ["1", "4"],
    }


def test_line_heat(client: TestClient) -> None:
    heat = {h["station"]["id"]: h for h in client.get("/lines/1/heat").json()}
    assert heat["tmu"]["significant"] == 2
    assert heat["king"]["incidents"] == 1
    assert client.get("/lines/9/heat").status_code == 422


def test_station(client: TestClient) -> None:
    body = client.get("/stations/tmu").json()
    assert body["significant"] == 2
    assert body["top_causes"][0]["is_signal_problem"] in (True, False)
    assert {c["code"] for c in body["top_causes"]} == {"PUSI", "MUIS"}
    assert body["by_weekday_hour"][0][8] == 2
    assert client.get("/stations/leaside").status_code == 404


def test_commute_risk(client: TestClient) -> None:
    body = client.post(
        "/commute/risk",
        json={
            "line": "1",
            "origin": "bloor-yonge",
            "destination": "union",
            "weekday": 0,
            "departure": "08:15",
        },
    ).json()
    assert (body["days_observed"], body["days_hit"]) == (4, 2)
    assert body["risk"] == 0.5
    assert body["window_start"] == "08:00:00"
    assert body["worst_stations"] == [
        {"station": {"id": "tmu", "name": "TMU", "lines": ["1"]}, "delays": 2}
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {
            "line": "4",
            "origin": "union",
            "destination": "leslie",
            "weekday": 0,
            "departure": "8:00",
        },
        {"line": "1", "origin": "union", "destination": "king", "weekday": 7, "departure": "08:00"},
    ],
)
def test_commute_risk_rejects_invalid_trips(client: TestClient, payload: dict[str, str]) -> None:
    assert client.post("/commute/risk", json=payload).status_code == 422


def test_openapi_schema(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/summary", "/lines", "/lines/{line}/heat", "/stations/{station_id}"} <= set(paths)


def test_since_filters_heat_station_and_commute(client: TestClient) -> None:
    heat = {h["station"]["id"]: h for h in client.get("/lines/1/heat?since=2026-08-20").json()}
    assert heat["tmu"]["significant"] == 1
    assert client.get("/stations/tmu", params={"since": "2026-08-20"}).json()["significant"] == 1

    body = client.post(
        "/commute/risk",
        json={
            "line": "1",
            "origin": "bloor-yonge",
            "destination": "union",
            "weekday": 0,
            "departure": "08:15",
            "since": "2026-08-20",
        },
    ).json()
    assert (body["days_observed"], body["days_hit"]) == (2, 1)


def test_rejects_an_invalid_since(client: TestClient) -> None:
    assert client.get("/stations/tmu?since=yesterday").status_code == 422
