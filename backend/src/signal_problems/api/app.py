import os
from collections.abc import Callable, Iterator
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from signal_problems.api.schemas import (
    CauseOut,
    CommuteOut,
    CommuteRequest,
    LineOut,
    LocationCountOut,
    RouteOut,
    RouteProfileOut,
    StationCountOut,
    StationHeatOut,
    StationOut,
    StationProfileOut,
    SummaryOut,
)
from signal_problems.application import queries, routes
from signal_problems.domain.lines import Line
from signal_problems.domain.stations import TTC_SUBWAY
from signal_problems.domain.surface import Mode
from signal_problems.infrastructure.database import SqlDelayQueries, SqlRouteQueries, make_engine
from signal_problems.infrastructure.settings import DATABASE_URL


def create_app(session_factory: Callable[[], Session]) -> FastAPI:
    app = FastAPI(
        title="signal-problems",
        summary="Toronto subway delays, decoded.",
        version="0.1.0",
    )
    origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"])

    def get_queries() -> Iterator[queries.DelayQueries]:
        with session_factory() as session:
            yield SqlDelayQueries(session)

    Queries = Annotated[queries.DelayQueries, Depends(get_queries)]

    def get_route_queries() -> Iterator[routes.RouteQueries]:
        with session_factory() as session:
            yield SqlRouteQueries(session)

    RouteQueries = Annotated[routes.RouteQueries, Depends(get_route_queries)]
    Since = Annotated[date | None, Query(description="Only count delays from this day on")]

    @app.get("/health", include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/summary")
    def get_summary(q: Queries) -> SummaryOut:
        s = queries.summary(q)
        return SummaryOut(
            first_day=s.first_day,
            last_day=s.last_day,
            incidents=s.incidents,
            significant=s.significant,
            signal_problems=s.signal_problems,
        )

    @app.get("/lines")
    def get_lines() -> list[LineOut]:
        return [
            LineOut(
                id=line,
                name=line.display_name,
                stations=[StationOut.of(s) for s in TTC_SUBWAY.on_line(line)],
            )
            for line in Line
        ]

    @app.get("/lines/{line}/heat")
    def get_line_heat(line: Line, q: Queries, since: Since = None) -> list[StationHeatOut]:
        return [
            StationHeatOut(
                station=StationOut.of(h.station),
                incidents=h.incidents,
                significant=h.significant,
                minutes_lost=h.minutes_lost,
            )
            for h in queries.line_heat(q, TTC_SUBWAY, line, since)
        ]

    @app.get("/stations/{station_id}", responses={404: {"description": "Unknown station"}})
    def get_station(station_id: str, q: Queries, since: Since = None) -> StationProfileOut:
        try:
            p = queries.station_profile(q, TTC_SUBWAY, station_id, since)
        except queries.StationNotFoundError:
            raise HTTPException(404, f"Unknown station: {station_id}") from None
        return StationProfileOut(
            station=StationOut.of(p.station),
            incidents=p.incidents,
            significant=p.significant,
            minutes_lost=p.minutes_lost,
            categories=p.categories,
            top_causes=[CauseOut.of(c) for c in p.top_causes],
            by_weekday_hour=p.by_weekday_hour,
        )

    @app.get("/routes")
    def get_routes(mode: Mode, q: RouteQueries, since: Since = None) -> list[RouteOut]:
        """Streetcar or bus routes, the most 5+ minute delays first."""
        return [RouteOut.of(mode, h) for h in routes.route_ranking(q, mode, since)]

    @app.get("/routes/{mode}/{route}", responses={404: {"description": "No delays on that route"}})
    def get_route(mode: Mode, route: int, q: RouteQueries, since: Since = None) -> RouteProfileOut:
        try:
            p = routes.route_profile(q, mode, route, since)
        except routes.RouteNotFoundError:
            raise HTTPException(404, f"No delays logged on {mode} route {route}") from None
        return RouteProfileOut(
            route=RouteOut.of(mode, p.heat),
            categories=p.categories,
            top_causes=[CauseOut.of(c) for c in p.top_causes],
            top_locations=[LocationCountOut(location=loc, delays=n) for loc, n in p.top_locations],
            by_weekday_hour=p.by_weekday_hour,
        )

    @app.post("/commute/risk", responses={422: {"description": "Stations not on that line"}})
    def post_commute_risk(body: CommuteRequest, q: Queries) -> CommuteOut:
        try:
            query = queries.CommuteQuery(
                body.line, body.origin, body.destination, body.weekday, body.departure, body.since
            )
            a = queries.assess_commute(q, TTC_SUBWAY, query)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        return CommuteOut(
            stations=[StationOut.of(s) for s in a.trip.stations],
            window_start=a.window[0],
            window_end=a.window[1],
            days_observed=a.risk.days_observed,
            days_hit=a.risk.days_hit,
            risk=a.risk.share,
            worst_stations=[
                StationCountOut(station=StationOut.of(s), delays=n) for s, n in a.worst_stations
            ],
            top_causes=[CauseOut.of(c) for c in a.top_causes],
            model_chance=a.forecast.chance if a.forecast else None,
            model_day=a.forecast.day if a.forecast else None,
        )

    return app


def _default_sessions() -> Callable[[], Session]:
    engine = make_engine(DATABASE_URL)
    return lambda: Session(engine)


app = create_app(_default_sessions())
