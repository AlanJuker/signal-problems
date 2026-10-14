from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from sqlalchemy import Boolean, DateTime, Index, Integer, String, create_engine
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import CursorResult, Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.sql.expression import Executable

from signal_problems.domain.delays import Delay


class Base(DeclarativeBase):
    pass


class DelayRecord(Base):
    __tablename__ = "delays"

    fingerprint: Mapped[str] = mapped_column(String(32), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime)  # Toronto local time, as logged
    location_kind: Mapped[str] = mapped_column(String(16))
    station_id: Mapped[str | None] = mapped_column(String(40))
    segment_end_id: Mapped[str | None] = mapped_column(String(40))
    line: Mapped[str | None] = mapped_column(String(1))
    cause_code: Mapped[str] = mapped_column(String(8))
    cause_category: Mapped[str] = mapped_column(String(24))
    is_signal_problem: Mapped[bool] = mapped_column(Boolean)
    minutes: Mapped[int] = mapped_column(Integer)
    gap_minutes: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        Index("ix_delays_station_occurred_at", "station_id", "occurred_at"),
        Index("ix_delays_line_occurred_at", "line", "occurred_at"),
    )

    @classmethod
    def from_domain(cls, delay: Delay) -> "DelayRecord":
        stations = delay.location.stations
        return cls(
            fingerprint=delay.fingerprint,
            occurred_at=delay.occurred_at,
            location_kind=delay.location.kind.value,
            station_id=stations[0].id if stations else None,
            segment_end_id=stations[1].id if len(stations) > 1 else None,
            line=delay.line.value if delay.line else None,
            cause_code=delay.cause.code,
            cause_category=delay.cause.category.value,
            is_signal_problem=delay.cause.is_signal_problem,
            minutes=delay.minutes,
            gap_minutes=delay.gap_minutes,
        )


def make_engine(url: str) -> Engine:
    return create_engine(url)


class SqlDelayRepository:
    _BATCH = 2_000  # 11 columns per row stays under SQLite's 32,766 bound parameters

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_new(self, delays: Sequence[Delay]) -> int:
        """Insert-or-ignore on the fingerprint, in one statement per batch."""
        dialect = self._session.get_bind().dialect.name
        inserted = 0
        for start in range(0, len(delays), self._BATCH):
            rows = [
                _columns(DelayRecord.from_domain(d)) for d in delays[start : start + self._BATCH]
            ]
            result = self._session.execute(_insert_ignoring_duplicates(dialect, rows))
            inserted += cast("CursorResult[Any]", result).rowcount
        self._session.commit()
        return inserted


def _insert_ignoring_duplicates(dialect: str, rows: list[dict[str, object]]) -> Executable:
    if dialect == "postgresql":
        return postgresql.insert(DelayRecord).values(rows).on_conflict_do_nothing()
    if dialect == "sqlite":
        return sqlite.insert(DelayRecord).values(rows).on_conflict_do_nothing()
    raise ValueError(f"Unsupported database: {dialect}")


def _columns(record: DelayRecord) -> dict[str, object]:
    return {c.key: getattr(record, c.key) for c in DelayRecord.__table__.columns}
