"""Builds `domain/data/run_times.csv` from the TTC's GTFS schedule.

Download "Complete GTFS" from https://open.toronto.ca/dataset/merged-gtfs-ttc-routes-and-schedules/,
unzip it and run, from `backend/`:

    uv run python scripts/run_times.py path/to/gtfs > src/signal_problems/domain/data/run_times.csv

Each row is the median scheduled time from leaving one station to arriving at the next, over trips
in both directions.
"""

import csv
import re
import statistics
import sys
from collections import defaultdict
from itertools import pairwise
from pathlib import Path

from signal_problems.domain.lines import Line
from signal_problems.domain.stations import TTC_SUBWAY

# GTFS names platforms ("Bloor Station - Northbound Platform"); the delay log's names are stations.
_PLATFORM = re.compile(r"( Station)?( - .*)?$")
_STATION_IDS = {s.name: s.id for s in TTC_SUBWAY.all()} | {
    "Bloor": "bloor-yonge",
    "Yonge": "bloor-yonge",
}


def _seconds(clock: str) -> int:
    hours, minutes, seconds = map(int, clock.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def _rows(gtfs: Path, name: str) -> csv.DictReader[str]:
    return csv.DictReader((gtfs / name).open(encoding="utf-8-sig"))


def main(gtfs: Path) -> None:
    lines = {
        r["route_id"]: Line(r["route_short_name"])
        for r in _rows(gtfs, "routes.txt")
        if r["route_type"] == "1"
    }
    trip_line = {
        r["trip_id"]: lines[r["route_id"]]
        for r in _rows(gtfs, "trips.txt")
        if r["route_id"] in lines
    }
    station = {
        r["stop_id"]: _STATION_IDS.get(_PLATFORM.sub("", r["stop_name"]))
        for r in _rows(gtfs, "stops.txt")
    }

    stops: dict[str, list[tuple[int, int, int, str | None]]] = defaultdict(list)
    for r in _rows(gtfs, "stop_times.txt"):
        if r["trip_id"] in trip_line:
            stops[r["trip_id"]].append(
                (
                    int(r["stop_sequence"]),
                    _seconds(r["arrival_time"]),
                    _seconds(r["departure_time"]),
                    station[r["stop_id"]],
                )
            )

    hops: dict[tuple[Line, frozenset[str | None]], list[int]] = defaultdict(list)
    for trip_id, visits in stops.items():
        visits.sort()
        for (_, _, left, here), (_, arrived, _, there) in pairwise(visits):
            hops[trip_line[trip_id], frozenset((here, there))].append(arrived - left)

    out = csv.writer(sys.stdout, lineterminator="\n")
    out.writerow(["line", "from", "to", "seconds"])
    for line in Line:
        order = [s.id for s in TTC_SUBWAY.on_line(line)]
        for a, b in pairwise(order):
            times = hops[line, frozenset((a, b))]
            if not times:
                raise SystemExit(f"No scheduled trips between {a} and {b} on line {line}")
            out.writerow([line.value, a, b, round(statistics.median(times))])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
