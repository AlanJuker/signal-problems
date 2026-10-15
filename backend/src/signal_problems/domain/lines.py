import re
from enum import StrEnum


class Line(StrEnum):
    """TTC subway lines covered by the delay dataset."""

    YONGE_UNIVERSITY = "1"
    BLOOR_DANFORTH = "2"
    SHEPPARD = "4"

    @property
    def display_name(self) -> str:
        return _DISPLAY_NAMES[self]


_DISPLAY_NAMES = {
    Line.YONGE_UNIVERSITY: "Line 1 Yonge–University",
    Line.BLOOR_DANFORTH: "Line 2 Bloor–Danforth",
    Line.SHEPPARD: "Line 4 Sheppard",
}

# How operators write each line in the free-text `Line` column: "YU", "YUS" (the older
# Yonge–University–Spadina), "B/D", "BD LINE 2", "SHEP", "YU & BD", "YU\BD"…
_LINE_COLUMN = {
    Line.YONGE_UNIVERSITY: re.compile(r"\bYUS?\b|YONGE[- ]*UNIVERSITY|\bLINE ?1\b"),
    Line.BLOOR_DANFORTH: re.compile(r"\bB/?D\b|BLOOR[- ]*DANFORTH|\bLINE ?2\b"),
    Line.SHEPPARD: re.compile(r"\bSHP\b|\bSHEP\b|\bLINE ?4\b"),
}
# Line 3 Scarborough, closed in 2023 and out of scope.
_SCARBOROUGH_RT = re.compile(r"\bS?RT\b")

# Line codes operators append to station names ("KENNEDY BD STATION", "ST GEORGE YUS STATION").
# Stricter than the column: "SHEP" in "YONGE SHEP STATION" is part of the name.
_NAME_CODES = {
    "YU": Line.YONGE_UNIVERSITY,
    "YUS": Line.YONGE_UNIVERSITY,
    "BD": Line.BLOOR_DANFORTH,
    "SHP": Line.SHEPPARD,
}


def parse_lines(raw: str) -> frozenset[Line]:
    """Lines named in the free-text `Line` column. Bus routes and unknown values give none."""
    text = raw.upper()
    return frozenset(line for line, pattern in _LINE_COLUMN.items() if pattern.search(text))


def is_scarborough_rt_only(raw: str) -> bool:
    """The `Line` column names Line 3 and none of the lines covered here."""
    return bool(_SCARBOROUGH_RT.search(raw.upper())) and not parse_lines(raw)


def line_code(token: str) -> Line | None:
    """The line a station-name token like "BD" or "YUS" stands for."""
    return _NAME_CODES.get(token)
