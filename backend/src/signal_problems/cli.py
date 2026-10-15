import argparse
import json
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from signal_problems.application.ingest import IngestDelays, IngestReport
from signal_problems.application.ports import DelaySource
from signal_problems.domain.resolver import StationResolver
from signal_problems.domain.stations import TTC_SUBWAY
from signal_problems.infrastructure.database import SqlDelayRepository, make_engine
from signal_problems.infrastructure.settings import DATABASE_URL
from signal_problems.infrastructure.toronto_open_data import CsvFileSource, TorontoOpenDataSource


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="signal-problems")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="import the TTC subway delay log")
    ingest.add_argument("--csv", type=Path, help="read a saved CSV instead of downloading it")
    ingest.add_argument(
        "--history", action="store_true", help="also import 2014–2024 (about 222,000 rows)"
    )
    commands.add_parser("openapi", help="print the API's OpenAPI schema (the frontend contract)")
    args = parser.parse_args(argv)

    if args.command == "openapi":
        from signal_problems.api.app import create_app  # noqa: PLC0415 (only this command needs FastAPI)

        schema = create_app(lambda: Session(make_engine(DATABASE_URL))).openapi()
        print(json.dumps(schema, indent=2, ensure_ascii=False))
        return

    engine = make_engine(DATABASE_URL)
    try:
        with httpx.Client(timeout=60) as client, Session(engine) as session:
            source: DelaySource = (
                CsvFileSource(args.csv)
                if args.csv
                else TorontoOpenDataSource(client, include_history=args.history)
            )
            resolver = StationResolver(TTC_SUBWAY)
            report = IngestDelays(source, SqlDelayRepository(session), resolver)()
    finally:
        engine.dispose()  # close pooled connections instead of leaving them to the GC
    print(format_report(report))


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
