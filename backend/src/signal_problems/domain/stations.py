import re
from dataclasses import dataclass

from signal_problems.domain.lines import Line


@dataclass(frozen=True, slots=True)
class Station:
    id: str
    name: str
    lines: frozenset[Line]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", "")).strip("-")


# Stations in travel order. Line 1 is a U: Vaughan → Union → Finch.
_LINE_ORDER: dict[Line, tuple[str, ...]] = {
    Line.YONGE_UNIVERSITY: (
        "Vaughan Metropolitan Centre",
        "Highway 407",
        "Pioneer Village",
        "York University",
        "Finch West",
        "Downsview Park",
        "Sheppard West",
        "Wilson",
        "Yorkdale",
        "Lawrence West",
        "Glencairn",
        "Cedarvale",
        "St Clair West",
        "Dupont",
        "Spadina",
        "St George",
        "Museum",
        "Queen's Park",
        "St Patrick",
        "Osgoode",
        "St Andrew",
        "Union",
        "King",
        "Queen",
        "TMU",
        "College",
        "Wellesley",
        "Bloor-Yonge",
        "Rosedale",
        "Summerhill",
        "St Clair",
        "Davisville",
        "Eglinton",
        "Lawrence",
        "York Mills",
        "Sheppard-Yonge",
        "North York Centre",
        "Finch",
    ),
    Line.BLOOR_DANFORTH: (
        "Kipling",
        "Islington",
        "Royal York",
        "Old Mill",
        "Jane",
        "Runnymede",
        "High Park",
        "Keele",
        "Dundas West",
        "Lansdowne",
        "Dufferin",
        "Ossington",
        "Christie",
        "Bathurst",
        "Spadina",
        "St George",
        "Bay",
        "Bloor-Yonge",
        "Sherbourne",
        "Castle Frank",
        "Broadview",
        "Chester",
        "Pape",
        "Donlands",
        "Greenwood",
        "Coxwell",
        "Woodbine",
        "Main Street",
        "Victoria Park",
        "Warden",
        "Kennedy",
    ),
    Line.SHEPPARD: ("Sheppard-Yonge", "Bayview", "Bessarion", "Leslie", "Don Mills"),
}

# Extra names operators use, already normalized (see `resolver.normalize`).
ALIASES: dict[str, str] = {
    "VMC": "vaughan-metropolitan-centre",
    "VAUGHAN MC": "vaughan-metropolitan-centre",
    "VAUGHAN METRO CENTRE": "vaughan-metropolitan-centre",
    "HWY 407": "highway-407",
    "EGLINTON WEST": "cedarvale",  # renamed
    "DUNDAS": "tmu",  # renamed
    "BLOOR": "bloor-yonge",  # Line 1 platform
    "YONGE": "bloor-yonge",  # Line 2 platform ("YONGE BD STATION")
    "SHEPPARD": "sheppard-yonge",
    "YONGE SHEP": "sheppard-yonge",
    "YONGE AND BLOOR": "bloor-yonge",
    "NORTH YORK CTR": "north-york-centre",
    "NORTH YORK CENTER": "north-york-centre",
    "MAIN": "main-street",
}


class StationRegistry:
    def __init__(self, line_order: dict[Line, tuple[str, ...]]) -> None:
        lines_by_name: dict[str, set[Line]] = {}
        for line, names in line_order.items():
            for name in names:
                lines_by_name.setdefault(name, set()).add(line)
        self._by_id = {
            _slug(name): Station(_slug(name), name, frozenset(lines))
            for name, lines in lines_by_name.items()
        }
        self._order = {line: tuple(_slug(n) for n in names) for line, names in line_order.items()}

    def get(self, station_id: str) -> Station | None:
        return self._by_id.get(station_id)

    def all(self) -> list[Station]:
        return list(self._by_id.values())

    def on_line(self, line: Line) -> list[Station]:
        return [self._by_id[station_id] for station_id in self._order[line]]

    def between(self, line: Line, origin_id: str, destination_id: str) -> list[Station]:
        """Stations a trip passes through, both ends included, in travel order."""
        order = self._order[line]
        if origin_id not in order or destination_id not in order:
            raise ValueError(f"Both stations must be on {line.display_name}")
        start, end = order.index(origin_id), order.index(destination_id)
        step = 1 if end >= start else -1
        return [self._by_id[station_id] for station_id in order[start : end + step : step]]


TTC_SUBWAY = StationRegistry(_LINE_ORDER)
