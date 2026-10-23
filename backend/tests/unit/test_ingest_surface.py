from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from signal_problems.application.ingest import IngestSurfaceDelays
from signal_problems.application.ports import RawDelayRow
from signal_problems.domain.surface import Mode, SurfaceDelay
from signal_problems.infrastructure.toronto_open_data import CsvFileSource

FIXTURES = Path(__file__).parent.parent / "fixtures"


class FakeRepository:
    def __init__(self) -> None:
        self.stored: dict[str, SurfaceDelay] = {}

    def add_new(self, delays: Sequence[SurfaceDelay]) -> int:
        new = [d for d in delays if d.fingerprint not in self.stored]
        self.stored.update((d.fingerprint, d) for d in new)
        return len(new)


class FakeSource:
    def __init__(self, rows: list[RawDelayRow]) -> None:
        self.rows = rows

    def fetch(self) -> list[RawDelayRow]:
        return self.rows


def test_streetcar_rows_are_grouped_by_route() -> None:
    repository = FakeRepository()
    source = CsvFileSource(FIXTURES / "streetcar_sample.csv")
    report = IngestSurfaceDelays(source, repository, Mode.STREETCAR)()

    assert (report.rows_read, report.duplicates, report.stored) == (6, 1, 4)
    assert report.no_route == {"": 1}  # skipped and reported, not guessed
    branch = next(d for d in repository.stored.values() if d.route_name == "504A KING")
    assert (branch.route, branch.location) == (504, "KING AND GEORGE")
    assert branch.cause.description == "AUTO FOUL RAIL"  # from the streetcar code list


def test_bus_dates_carry_a_midnight_time() -> None:
    repository = FakeRepository()
    report = IngestSurfaceDelays(CsvFileSource(FIXTURES / "bus_sample.csv"), repository, Mode.BUS)()

    assert (report.rows_read, report.duplicates, report.stored) == (5, 1, 2)
    assert report.no_route == {"": 1, "LINE 1 SHUTTLE": 1}
    markham = next(d for d in repository.stored.values() if d.route == 102)
    assert markham.occurred_at == datetime(2025, 1, 1, 2, 15)
    assert (markham.minutes, markham.cause.description) == (20, "NO OPERATOR AVAILABLE DUE TO ESA")


def test_rerunning_stores_nothing_new() -> None:
    repository = FakeRepository()
    source = CsvFileSource(FIXTURES / "bus_sample.csv")
    IngestSurfaceDelays(source, repository, Mode.BUS)()
    report = IngestSurfaceDelays(source, repository, Mode.BUS)()
    assert (report.stored, report.already_stored) == (0, 2)


def test_malformed_rows_are_counted() -> None:
    row = RawDelayRow(
        "2025-01-01", "25:99", "QUEEN AND LESLIE", "501 QUEEN", "MTS", "5", "10", "E", "1"
    )
    report = IngestSurfaceDelays(FakeSource([row]), FakeRepository(), Mode.STREETCAR)()
    assert (report.malformed, report.stored) == (1, 0)
