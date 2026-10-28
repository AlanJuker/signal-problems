from collections.abc import Sequence
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    create_engine,
    delete,
    func,
    insert,
    or_,
    select,
)
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.sql.dml import ReturningInsert

from signal_problems.application.queries import DelayFact, Forecast
from signal_problems.application.routes import RouteFact, RouteTotals
from signal_problems.domain.delays import SIGNIFICANT_DELAY_MINUTES, Delay
from signal_problems.domain.lines import Line
from signal_problems.domain.surface import Mode, SurfaceDelay


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


class SurfaceDelayRecord(Base):
    __tablename__ = "surface_delays"

    fingerprint: Mapped[str] = mapped_column(String(32), primary_key=True)
    mode: Mapped[str] = mapped_column(String(10))
    route: Mapped[int] = mapped_column(Integer)
    route_name: Mapped[str] = mapped_column(String(80))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)  # Toronto local time, as logged
    location: Mapped[str] = mapped_column(String(120))
    cause_code: Mapped[str] = mapped_column(String(8))
    cause_category: Mapped[str] = mapped_column(String(24))
    minutes: Mapped[int] = mapped_column(Integer)
    gap_minutes: Mapped[int] = mapped_column(Integer)

    __table_args__ = (Index("ix_surface_delays_route", "mode", "route", "occurred_at"),)

    @classmethod
    def from_domain(cls, delay: SurfaceDelay) -> "SurfaceDelayRecord":
        return cls(
            fingerprint=delay.fingerprint,
            mode=delay.mode.value,
            route=delay.route,
            route_name=delay.route_name,
            occurred_at=delay.occurred_at,
            location=delay.location,
            cause_code=delay.cause.code,
            cause_category=delay.cause.category.value,
            minutes=delay.minutes,
            gap_minutes=delay.gap_minutes,
        )


class ForecastRecord(Base):
    """The delay model's chance of a 5+ minute delay, per station and hour, for one day."""

    __tablename__ = "forecasts"

    station_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    hour: Mapped[int] = mapped_column(Integer, primary_key=True)
    probability: Mapped[float] = mapped_column(Float)


def make_engine(url: str) -> Engine:
    return create_engine(url)


class SqlDelayRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_new(self, delays: Sequence[Delay]) -> int:
        records = [_columns(DelayRecord.from_domain(d)) for d in delays]
        return _add_new(self._session, DelayRecord, records)


class SqlSurfaceDelayRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_new(self, delays: Sequence[SurfaceDelay]) -> int:
        records = [_columns(SurfaceDelayRecord.from_domain(d)) for d in delays]
        return _add_new(self._session, SurfaceDelayRecord, records)


_BATCH = 2_000  # 11 columns per row stays under SQLite's 32,766 bound parameters
Fingerprinted = type[DelayRecord] | type[SurfaceDelayRecord]


def _add_new(session: Session, model: Fingerprinted, records: list[dict[str, object]]) -> int:
    """Insert-or-ignore on the fingerprint, in one statement per batch.

    Counts the fingerprints returned by `RETURNING`: `rowcount` is -1 on PostgreSQL when
    SQLAlchemy splits a multi-row insert into several statements.
    """
    dialect = session.get_bind().dialect.name
    inserted = 0
    for start in range(0, len(records), _BATCH):
        statement = _insert_ignoring_duplicates(dialect, model, records[start : start + _BATCH])
        inserted += len(session.scalars(statement).all())
    session.commit()
    return inserted


class SqlForecastRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace(self, rows: Sequence[tuple[str, date, int, float]]) -> int:
        """Swap the stored forecast for a new one, in one transaction."""
        self._session.execute(delete(ForecastRecord))
        if rows:
            self._session.execute(
                insert(ForecastRecord),
                [{"station_id": s, "day": d, "hour": h, "probability": p} for s, d, h, p in rows],
            )
        self._session.commit()
        return len(rows)


def _insert_ignoring_duplicates(
    dialect: str, model: Fingerprinted, rows: list[dict[str, object]]
) -> ReturningInsert[tuple[str]]:
    if dialect == "postgresql":
        statement = postgresql.insert(model).values(rows).on_conflict_do_nothing()
        return statement.returning(model.fingerprint)
    if dialect == "sqlite":
        lite = sqlite.insert(model).values(rows).on_conflict_do_nothing()
        return lite.returning(model.fingerprint)
    raise ValueError(f"Unsupported database: {dialect}")


def _columns(record: Base) -> dict[str, object]:
    return {c.key: getattr(record, c.key) for c in record.__table__.columns}


class SqlDelayQueries:
    def __init__(self, session: Session) -> None:
        self._session = session

    def coverage(self) -> tuple[date, date] | None:
        first, last = self._session.execute(
            select(func.min(DelayRecord.occurred_at), func.max(DelayRecord.occurred_at))
        ).one()
        return (first.date(), last.date()) if first and last else None

    def at_stations(
        self, station_ids: Sequence[str], line: Line | None = None, since: date | None = None
    ) -> list[DelayFact]:
        query = select(
            DelayRecord.occurred_at,
            DelayRecord.station_id,
            DelayRecord.segment_end_id,
            DelayRecord.line,
            DelayRecord.cause_code,
            DelayRecord.minutes,
        ).where(
            or_(
                DelayRecord.station_id.in_(station_ids),
                DelayRecord.segment_end_id.in_(station_ids),
            )
        )
        if line is not None:
            query = query.where(or_(DelayRecord.line == line.value, DelayRecord.line.is_(None)))
        if since is not None:
            query = query.where(DelayRecord.occurred_at >= datetime.combine(since, time.min))
        return [
            DelayFact(at, station, segment_end, Line(raw_line) if raw_line else None, code, minutes)
            for at, station, segment_end, raw_line, code, minutes in self._session.execute(query)
        ]

    def totals(self) -> tuple[int, int, int]:
        significant = DelayRecord.minutes >= SIGNIFICANT_DELAY_MINUTES
        incidents, significant_count, signal = self._session.execute(
            select(
                func.count(),
                func.count().filter(significant),
                func.count().filter(significant, DelayRecord.is_signal_problem),
            ).select_from(DelayRecord)
        ).one()
        return incidents, significant_count, signal

    def forecast(self, station_ids: Sequence[str], weekday: int) -> Forecast | None:
        rows = self._session.execute(
            select(
                ForecastRecord.day,
                ForecastRecord.station_id,
                ForecastRecord.hour,
                ForecastRecord.probability,
            ).where(ForecastRecord.station_id.in_(station_ids))
        ).all()
        # A stored forecast covers seven consecutive days, so each weekday appears once.
        on_day = [r for r in rows if r.day.weekday() == weekday]
        if not on_day:
            return None
        return Forecast(on_day[0].day, {(r.station_id, r.hour): r.probability for r in on_day})


class SqlRouteQueries:
    def __init__(self, session: Session) -> None:
        self._session = session

    def totals(self, mode: Mode, since: date | None = None) -> list[RouteTotals]:
        record = SurfaceDelayRecord
        scope = [record.mode == mode.value]
        if since is not None:
            scope.append(record.occurred_at >= datetime.combine(since, time.min))
        names: dict[int, dict[str, int]] = {}
        spellings = select(record.route, record.route_name, func.count()).where(*scope)
        for route, name, count in self._session.execute(
            spellings.group_by(record.route, record.route_name)
        ):
            names.setdefault(route, {})[name] = count
        counts = select(
            record.route,
            func.count(),
            func.count().filter(record.minutes >= SIGNIFICANT_DELAY_MINUTES),
            func.sum(record.minutes),
        ).where(*scope)
        return [
            RouteTotals(route, names[route], incidents, significant, minutes)
            for route, incidents, significant, minutes in self._session.execute(
                counts.group_by(record.route)
            )
        ]

    def facts(
        self, mode: Mode, route: int | None = None, since: date | None = None
    ) -> list[RouteFact]:
        record = SurfaceDelayRecord
        query = select(
            record.occurred_at,
            record.route,
            record.route_name,
            record.location,
            record.cause_code,
            record.minutes,
        ).where(record.mode == mode.value)
        if route is not None:
            query = query.where(record.route == route)
        if since is not None:
            query = query.where(record.occurred_at >= datetime.combine(since, time.min))
        return [RouteFact(*row) for row in self._session.execute(query)]
