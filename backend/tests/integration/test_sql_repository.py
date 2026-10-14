import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from signal_problems.application.ingest import to_delay
from signal_problems.domain.delays import Delay
from signal_problems.domain.resolver import StationResolver
from signal_problems.domain.stations import TTC_SUBWAY
from signal_problems.infrastructure.database import (
    DelayRecord,
    SqlDelayRepository,
    _insert_ignoring_duplicates,
)
from signal_problems.infrastructure.toronto_open_data import CsvFileSource
from tests.conftest import SAMPLE_CSV

resolver = StationResolver(TTC_SUBWAY)


def sample_delays() -> list[Delay]:
    delays = []
    for row in CsvFileSource(SAMPLE_CSV).fetch():
        try:
            delays.append(to_delay(row, resolver))
        except ValueError:
            continue
    return list({d.fingerprint: d for d in delays}.values())


def test_add_new_is_idempotent(engine: Engine) -> None:
    delays = sample_delays()
    with Session(engine) as session:
        repository = SqlDelayRepository(session)
        assert repository.add_new(delays) == len(delays)
        assert repository.add_new(delays) == 0
        assert session.scalar(select(func.count()).select_from(DelayRecord)) == len(delays)


def test_maps_domain_fields(engine: Engine) -> None:
    with Session(engine) as session:
        SqlDelayRepository(session).add_new(sample_delays())
        segment = session.scalars(
            select(DelayRecord).where(DelayRecord.location_kind == "segment")
        ).one()
        bloor = session.scalars(
            select(DelayRecord).where(DelayRecord.station_id == "bloor-yonge")
        ).one()

    assert (segment.station_id, segment.segment_end_id) == ("finch", "st-clair")
    assert bloor.line == "2"  # "YONGE BD STATION" is the Line 2 platform


def test_inserts_in_batches(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SqlDelayRepository, "_BATCH", 2)
    delays = sample_delays()
    with Session(engine) as session:
        assert SqlDelayRepository(session).add_new(delays) == len(delays)


def test_rejects_unsupported_databases() -> None:
    with pytest.raises(ValueError, match="mysql"):
        _insert_ignoring_duplicates("mysql", [])
