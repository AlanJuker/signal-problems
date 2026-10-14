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

# Codes operators type in the `Line` column, including the older "YUS" (Yonge–University–Spadina).
_LINE_CODES = {
    "YU": Line.YONGE_UNIVERSITY,
    "YUS": Line.YONGE_UNIVERSITY,
    "BD": Line.BLOOR_DANFORTH,
    "SHP": Line.SHEPPARD,
}


def parse_lines(raw: str) -> frozenset[Line]:
    """Parse the free-text `Line` column ("YU", "YU/BD", "BD/ YUS", …) into lines.

    Unknown tokens (e.g. "SRT", the Line 3 that closed in 2023) are ignored.
    """
    tokens = raw.upper().replace(" ", "").replace("-", "/").split("/")
    return frozenset(_LINE_CODES[token] for token in tokens if token in _LINE_CODES)
