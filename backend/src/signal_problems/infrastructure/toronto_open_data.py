import csv
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, replace
from datetime import date, datetime, time
from functools import partial
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import httpx
from openpyxl import load_workbook

from signal_problems.application.ports import RawDelayRow
from signal_problems.domain.causes import incident_code
from signal_problems.domain.surface import Mode

CKAN_API = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action"
CURRENT_LOG = "TTC Subway Delay Data since 2025.csv"

# Header names for each RawDelayRow field, in field order. A field can go by several names.
Columns = tuple[tuple[str, ...], ...]
COLUMNS: Columns = tuple(
    (name,)
    for name in (
        "Date",
        "Time",
        "Station",
        "Line",
        "Code",
        "Min Delay",
        "Min Gap",
        "Bound",
        "Vehicle",
    )
)
# 2014–2024 streetcar workbooks renamed columns over the years, and log an incident word
# ("Mechanical") where the current logs have a code.
STREETCAR_HISTORY: Columns = (
    ("Report Date", "Date"),
    ("Time",),
    ("Location",),
    ("Route", "Line"),
    ("Incident",),
    ("Min Delay", "Delay"),
    ("Min Gap", "Gap"),
    ("Direction", "Bound"),
    ("Vehicle",),
)
# Bus workbooks always say Route and Direction. The only bus sheets that say Line and Bound, July
# and August 2021, repeat the streetcar workbook's row for row, so they're skipped.
BUS_HISTORY: Columns = (
    ("Report Date", "Date"),
    ("Time",),
    ("Location",),
    ("Route",),
    ("Incident",),
    ("Min Delay", "Delay"),
    ("Min Gap", "Gap"),
    ("Direction",),
    ("Vehicle",),
)


def parse_csv(lines: Iterable[str]) -> Iterator[RawDelayRow]:
    for row in csv.DictReader(lines):
        yield RawDelayRow(
            date=row["Date"],
            time=row["Time"],
            station=row["Station"],
            line=row["Line"],
            code=row["Code"],
            min_delay=row["Min Delay"],
            min_gap=row["Min Gap"],
            bound=row["Bound"],
            vehicle=row["Vehicle"],
        )


def parse_xlsx(stream: BinaryIO, columns: Columns = COLUMNS) -> Iterator[RawDelayRow]:
    """Every sheet of a yearly workbook (some years have one sheet per month).

    Cells come typed (dates as datetimes, minutes as numbers); they're turned into the same text
    the CSV has, so both formats go through the same parsing and fingerprinting.
    """
    workbook = load_workbook(stream, read_only=True, data_only=True)
    try:
        for sheet in workbook.worksheets:
            rows = sheet.iter_rows(values_only=True)
            header = [str(cell).strip() if cell is not None else "" for cell in next(rows, ())]
            index = [next((header.index(n) for n in names if n in header), -1) for names in columns]
            if -1 in index:
                continue
            for cells in rows:
                if not cells or cells[index[0]] is None:
                    continue
                yield RawDelayRow(*(_text(cells[i]) for i in index))
    finally:
        workbook.close()


def parse_surface_history(stream: BinaryIO, columns: Columns) -> Iterator[RawDelayRow]:
    for row in parse_xlsx(stream, columns):
        yield replace(row, code=incident_code(row.code))


def _text(cell: object) -> str:
    if cell is None:
        return ""
    if isinstance(cell, datetime | date):
        return cell.strftime("%Y-%m-%d")
    if isinstance(cell, time):
        return cell.strftime("%H:%M")
    if isinstance(cell, float) and cell.is_integer():
        return str(int(cell))
    return str(cell).strip()


@dataclass(frozen=True, slots=True)
class Package:
    """A delay log on the portal: a current log that grows monthly, and 2014–2024 workbooks."""

    id: str
    current_log: str
    history: re.Pattern[str]
    parse_history: Callable[[BinaryIO], Iterator[RawDelayRow]] = parse_xlsx


SUBWAY = Package(
    "ttc-subway-delay-data", CURRENT_LOG, re.compile(r"^ttc-subway-delay-(data-)?.*20\d\d$")
)
# The streetcar package also lists 2020 under a name ending in a tab; the pattern skips that copy.
SURFACE = {
    mode: Package(
        f"ttc-{mode}-delay-data",
        f"TTC {mode.title()} Delay Data since 2025.csv",
        re.compile(rf"^ttc-{mode}-delay-data-20\d\d$"),
        partial(parse_surface_history, columns=columns),
    )
    for mode, columns in ((Mode.STREETCAR, STREETCAR_HISTORY), (Mode.BUS, BUS_HISTORY))
}


class TorontoOpenDataSource:
    """Downloads a delay log through the portal's CKAN API."""

    def __init__(
        self, client: httpx.Client, *, include_history: bool = False, package: Package = SUBWAY
    ) -> None:
        self._client = client
        self._include_history = include_history
        self._package = package

    def fetch(self) -> Iterator[RawDelayRow]:
        response = self._client.get(f"{CKAN_API}/package_show", params={"id": self._package.id})
        response.raise_for_status()
        resources = response.json()["result"]["resources"]
        if self._include_history:
            for resource in resources:
                if self._package.history.match(resource["name"]):
                    yield from self._package.parse_history(BytesIO(self._download(resource["url"])))
        url = next(r["url"] for r in resources if r["name"] == self._package.current_log)
        yield from parse_csv(self._download(url).decode("utf-8-sig").splitlines())

    def _download(self, url: str) -> bytes:
        response = self._client.get(url, follow_redirects=True)
        response.raise_for_status()
        return response.content


class CsvFileSource:
    """A delay log saved locally, for offline runs and tests."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def fetch(self) -> Iterator[RawDelayRow]:
        with self._path.open(encoding="utf-8-sig", newline="") as f:
            yield from parse_csv(f)
