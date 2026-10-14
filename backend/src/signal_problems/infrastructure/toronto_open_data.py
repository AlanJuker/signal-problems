import csv
from collections.abc import Iterable, Iterator
from pathlib import Path

import httpx

from signal_problems.application.ports import RawDelayRow

CKAN_API = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action"
PACKAGE = "ttc-subway-delay-data"
# Older years are published as separate XLSX files; the current log is one CSV that grows monthly.
CURRENT_LOG = "TTC Subway Delay Data since 2025.csv"


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


class TorontoOpenDataSource:
    """Downloads the current delay log through the portal's CKAN API."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def fetch(self) -> Iterator[RawDelayRow]:
        package = self._client.get(f"{CKAN_API}/package_show", params={"id": PACKAGE})
        package.raise_for_status()
        resources = package.json()["result"]["resources"]
        url = next(r["url"] for r in resources if r["name"] == CURRENT_LOG)
        response = self._client.get(url, follow_redirects=True)
        response.raise_for_status()
        return parse_csv(response.text.splitlines())


class CsvFileSource:
    """A delay log saved locally, for offline runs and tests."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def fetch(self) -> Iterator[RawDelayRow]:
        with self._path.open(encoding="utf-8-sig", newline="") as f:
            yield from parse_csv(f)
