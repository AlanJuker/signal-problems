from collections.abc import Sequence
from dataclasses import replace

from signal_problems.application.ingest import IngestDelays, IngestReport
from signal_problems.application.ports import RawDelayRow
from signal_problems.domain.delays import Delay
from signal_problems.domain.resolver import LocationKind, StationResolver
from signal_problems.domain.stations import TTC_SUBWAY

ROW = RawDelayRow(
    date="2026-08-31",
    time="08:12",
    station="BLOOR STATION",
    line="YU",
    code="MUIS",
    min_delay="6",
    min_gap="9",
    bound="S",
    vehicle="5231",
)


class FakeSource:
    def __init__(self, rows: list[RawDelayRow]) -> None:
        self.rows = rows

    def fetch(self) -> list[RawDelayRow]:
        return self.rows


class InMemoryRepository:
    def __init__(self) -> None:
        self.delays: dict[str, Delay] = {}

    def add_new(self, delays: Sequence[Delay]) -> int:
        new = [d for d in delays if d.fingerprint not in self.delays]
        self.delays.update((d.fingerprint, d) for d in new)
        return len(new)


def ingest(rows: list[RawDelayRow], repository: InMemoryRepository) -> IngestReport:
    return IngestDelays(FakeSource(rows), repository, StationResolver(TTC_SUBWAY))()


def test_stores_parsed_delays() -> None:
    repository = InMemoryRepository()
    report = ingest([ROW], repository)

    assert report.stored == 1
    (delay,) = repository.delays.values()
    assert delay.location.stations[0].id == "bloor-yonge"
    assert delay.minutes == 6
    assert delay.is_significant


def test_rerunning_stores_nothing_new() -> None:
    repository = InMemoryRepository()
    ingest([ROW], repository)
    report = ingest([ROW, replace(ROW, time="09:00")], repository)

    assert (report.stored, report.already_stored) == (1, 1)


def test_counts_duplicates_malformed_and_unresolved() -> None:
    rows = [
        ROW,
        ROW,  # logged twice
        replace(ROW, date="2026-02-30"),
        replace(ROW, min_delay="n/a"),
        replace(ROW, station="LEASIDE STATION"),
    ]
    report = ingest(rows, InMemoryRepository())

    assert report.rows_read == 5
    assert report.duplicates == 1
    assert report.malformed == 2
    assert report.unresolved == {"LEASIDE STATION": 1}
    assert report.by_kind[LocationKind.STATION] == 2
    assert report.resolution_rate == 2 / 3


def test_empty_source() -> None:
    report = ingest([], InMemoryRepository())
    assert report.stored == 0
    assert report.resolution_rate == 0.0


def test_blank_minutes_mean_zero() -> None:
    repository = InMemoryRepository()
    ingest([replace(ROW, min_delay="", min_gap="")], repository)
    (delay,) = repository.delays.values()
    assert (delay.minutes, delay.gap_minutes) == (0, 0)


def test_fingerprint_depends_on_every_field() -> None:
    assert ROW.fingerprint == replace(ROW).fingerprint
    assert ROW.fingerprint != replace(ROW, vehicle="5232").fingerprint
