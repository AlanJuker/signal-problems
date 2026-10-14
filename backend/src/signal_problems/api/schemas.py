"""HTTP contract. The frontend's TypeScript types are generated from the OpenAPI schema."""

from datetime import date, time

from pydantic import BaseModel, Field

from signal_problems.application import queries
from signal_problems.domain.causes import CauseCategory
from signal_problems.domain.lines import Line
from signal_problems.domain.stations import Station


class StationOut(BaseModel):
    id: str
    name: str
    lines: list[Line]

    @classmethod
    def of(cls, station: Station) -> "StationOut":
        return cls(id=station.id, name=station.name, lines=sorted(station.lines))


class LineOut(BaseModel):
    id: Line
    name: str
    stations: list[StationOut]


class SummaryOut(BaseModel):
    first_day: date | None
    last_day: date | None
    incidents: int
    significant: int = Field(description="Delays of 5 minutes or more")
    signal_problems: int = Field(description="5+ minute delays caused by signal failures")


class StationHeatOut(BaseModel):
    station: StationOut
    incidents: int
    significant: int
    minutes_lost: int


class CauseOut(BaseModel):
    code: str
    description: str | None
    category: CauseCategory
    is_signal_problem: bool
    count: int

    @classmethod
    def of(cls, item: queries.CauseCount) -> "CauseOut":
        cause = item.cause
        return cls(
            code=cause.code,
            description=cause.description,
            category=cause.category,
            is_signal_problem=cause.is_signal_problem,
            count=item.count,
        )


class StationProfileOut(BaseModel):
    station: StationOut
    incidents: int
    significant: int
    minutes_lost: int
    categories: dict[CauseCategory, int]
    top_causes: list[CauseOut]
    by_weekday_hour: list[list[int]] = Field(
        description="5+ minute delays per [weekday][hour], Monday = 0"
    )


class CommuteRequest(BaseModel):
    line: Line
    origin: str
    destination: str
    weekday: int = Field(ge=0, le=6, description="Monday = 0")
    departure: time


class StationCountOut(BaseModel):
    station: StationOut
    delays: int


class CommuteOut(BaseModel):
    stations: list[StationOut]
    window_start: time
    window_end: time
    days_observed: int
    days_hit: int = Field(description="Days with at least one 5+ minute delay on the trip")
    risk: float = Field(ge=0, le=1)
    worst_stations: list[StationCountOut]
    top_causes: list[CauseOut]
