import argparse
import json
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from signal_problems.application.ingest import (
    IngestDelays,
    IngestReport,
    IngestSurfaceDelays,
    SurfaceIngestReport,
)
from signal_problems.application.ports import DelaySource
from signal_problems.domain.resolver import StationResolver
from signal_problems.domain.stations import TTC_SUBWAY
from signal_problems.domain.surface import Mode
from signal_problems.infrastructure.database import (
    SqlDelayRepository,
    SqlForecastRepository,
    SqlSurfaceDelayRepository,
    make_engine,
)
from signal_problems.infrastructure.settings import DATABASE_URL
from signal_problems.infrastructure.toronto_open_data import (
    SURFACE,
    CsvFileSource,
    TorontoOpenDataSource,
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="signal-problems")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="import a TTC delay log")
    ingest.add_argument("--csv", type=Path, help="read a saved CSV instead of downloading it")
    ingest.add_argument(
        "--mode",
        choices=["subway", *Mode],
        default="subway",
        help="which delay log (default: subway)",
    )
    ingest.add_argument(
        "--history", action="store_true", help="also import 2014–2024 (about 222,000 rows)"
    )
    commands.add_parser("openapi", help="print the API's OpenAPI schema (the frontend contract)")
    commands.add_parser(
        "model-eval", help="compare a delay model with the historical frequency (needs --group ml)"
    )
    commands.add_parser(
        "train-model",
        help="store next week's delay forecasts for the commute check (needs --group ml)",
    )
    args = parser.parse_args(argv)

    if args.command == "model-eval":
        print(run_model_eval())
        return

    if args.command == "train-model":
        print(run_train_model())
        return

    if args.command == "openapi":
        from signal_problems.api.app import create_app  # noqa: PLC0415 (only this command needs FastAPI)

        schema = create_app(lambda: Session(make_engine(DATABASE_URL))).openapi()
        print(json.dumps(schema, indent=2, ensure_ascii=False))
        return

    if args.history and args.mode != "subway":
        parser.error("--history is only available for the subway so far (#28)")

    engine = make_engine(DATABASE_URL)
    try:
        with httpx.Client(timeout=60) as client, Session(engine) as session:
            if args.mode == "subway":
                source: DelaySource = (
                    CsvFileSource(args.csv)
                    if args.csv
                    else TorontoOpenDataSource(client, include_history=args.history)
                )
                resolver = StationResolver(TTC_SUBWAY)
                text = format_report(IngestDelays(source, SqlDelayRepository(session), resolver)())
            else:
                mode = Mode(args.mode)
                package, current_log = SURFACE[mode]
                source = (
                    CsvFileSource(args.csv)
                    if args.csv
                    else TorontoOpenDataSource(client, package=package, current_log=current_log)
                )
                repository = SqlSurfaceDelayRepository(session)
                text = format_surface_report(IngestSurfaceDelays(source, repository, mode)())
    finally:
        engine.dispose()  # close pooled connections instead of leaving them to the GC
    print(text)


def format_report(report: IngestReport) -> str:
    lines = [
        f"Rows read:       {report.rows_read:>7,}",
        f"Line 3 (skipped):{report.scarborough_rt:>8,}",
        f"Stored:          {report.stored:>7,}",
        f"Already stored:  {report.already_stored:>7,}",
        f"Duplicate rows:  {report.duplicates:>7,}",
        f"Malformed rows:  {report.malformed:>7,}",
        f"Resolution rate: {report.resolution_rate:>8.1%}",
        "By location kind:",
        *(f"  {kind:<11} {count:>7,}" for kind, count in report.by_kind.most_common()),
    ]
    if report.unresolved:
        lines.append("Most common unresolved values:")
        lines += [f"  {count:>4}  {raw}" for raw, count in report.unresolved.most_common(10)]
    return "\n".join(lines)


def format_surface_report(report: SurfaceIngestReport) -> str:
    lines = [
        f"Rows read:       {report.rows_read:>7,}",
        f"No route number: {report.no_route.total():>7,}",
        f"Stored:          {report.stored:>7,}",
        f"Already stored:  {report.already_stored:>7,}",
        f"Duplicate rows:  {report.duplicates:>7,}",
        f"Malformed rows:  {report.malformed:>7,}",
    ]
    if report.no_route:
        lines.append("Most common lines without a route number (skipped):")
        lines += [
            f"  {count:>4}  {line or '(empty)'}" for line, count in report.no_route.most_common(10)
        ]
    return "\n".join(lines)


def run_model_eval() -> str:
    from signal_problems.domain.stations import TTC_SUBWAY  # noqa: PLC0415
    from signal_problems.modeling.dataset import significant_delays  # noqa: PLC0415
    from signal_problems.modeling.experiment import run  # noqa: PLC0415

    engine = make_engine(DATABASE_URL)
    try:
        with engine.connect() as connection:
            events = significant_delays(connection)
    finally:
        engine.dispose()
    last = events["date"].max().date()
    report = run(events, sorted(s.id for s in TTC_SUBWAY.all()), last)
    lines = [
        f"Cells: {report.rows['train']:,} train, {report.rows['validation']:,} validation, "
        f"{report.rows['test']:,} test (through {last})",
        f"Share with a 5+ minute delay: {report.positive_rate['test']:.2%} in the test period",
        f"Boosting rounds chosen on 2024: {report.chosen_iterations}",
        "",
        "| Method | Log loss | Brier | ROC AUC | PR AUC |",
        "|---|---|---|---|---|",
        *(
            f"| {s.name} | {s.log_loss:.5f} | {s.brier:.6f} | {s.roc_auc:.3f} | {s.pr_auc:.4f} |"
            for s in report.test
        ),
        "",
        "Calibration of the model on the test period (deciles of predicted probability):",
        report.calibration.to_string(float_format=lambda x: f"{x:.4f}"),
    ]
    return "\n".join(lines)


def run_train_model() -> str:
    from signal_problems.modeling.dataset import significant_delays  # noqa: PLC0415
    from signal_problems.modeling.forecast import forecast_week  # noqa: PLC0415

    engine = make_engine(DATABASE_URL)
    try:
        with engine.connect() as connection:
            events = significant_delays(connection)
        if events.empty:
            return "No delays stored yet: run ingest first."
        last = events["date"].max().date()
        week = forecast_week(events, sorted(s.id for s in TTC_SUBWAY.all()), last)
        rows = [
            (r.station_id, r.date.date(), int(r.hour), float(r.probability))
            for r in week.itertuples()
        ]
        with Session(engine) as session:
            stored = SqlForecastRepository(session).replace(rows)
    finally:
        engine.dispose()
    days = week["date"].dt.date
    return f"Stored {stored:,} forecasts for {days.min()} – {days.max()} (data through {last})"
