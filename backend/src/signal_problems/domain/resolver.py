"""Turns the free-text `Station` column into a known location.

Operators type station names by hand into a field that truncates at 22 characters, so the same place
shows up dozens of ways. Resolution is deliberately conservative: when a value can't be matched with
confidence it stays `UNRESOLVED` instead of being guessed.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum

from signal_problems.domain.lines import Line, line_code, parse_lines
from signal_problems.domain.stations import ALIASES, Station, StationRegistry


class LocationKind(StrEnum):
    STATION = "station"
    SEGMENT = "segment"  # between two stations ("FINCH TO ST CLAIR")
    FACILITY = "facility"  # yards, carhouses, emergency exits: no passengers
    LINE_WIDE = "line_wide"  # "LINE 1 YONGE UNIVERSITY", "BLOOR DANFORTH SUBWAY"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class ResolvedLocation:
    kind: LocationKind
    stations: tuple[Station, ...] = ()
    line_hints: frozenset[Line] = frozenset()


_STATION_WORDS = {"STATION", "STATIONS", "STATIO", "STATI", "STAT", "STA", "STN"}
_FACILITY_WORDS = {
    "YARD",
    "CARHOUSE",
    "HOUSE",
    "WYE",
    "PORTAL",
    "SUBSTATION",
    "EMERGENCY",
    "EMER",
    "EE",
    "TAIL",
    "POCKET",
    "INTERLOCKING",
    "SHOP",
    "HOSTLER",
    "COMMIS",
    "TRANSIT",
    "BUILDING",
    "BUILD",
    "DIVISION",
    "TRACK",
    "TERMINAL",
    "STRUC",
    "SHOPS",
    "COMPLEX",
    "GARAGE",
    "BUILDUP",
    "MIGRATION",  # points where trains cross between lines
    "LOWER",  # Lower Bay, the unused platform under Bay station
}
_LINE_WIDE_WORDS = {
    "LINE",
    "LINE1",
    "LINE2",
    "LINE4",
    "SUBWAY",
    "SUBWA",
    "SUB",
    "SYSTEM",
    "SYSTEMWIDE",
    "VARIOUS",
}
_LINES_NAMED = {
    Line.YONGE_UNIVERSITY: re.compile(r"\bLINE ?1\b|YONGE UNIVERSITY"),
    # "YONGE-UNIVERSITY AND B…" is "…and Bloor–Danforth", cut off at 22 characters
    Line.BLOOR_DANFORTH: re.compile(r"\bLINE ?2\b|BLOOR DANFORTH|YONGE UNIVERSITY AND B"),
    Line.SHEPPARD: re.compile(r"\bLINE ?4\b|SHEPPARD (LINE|SUBWAY)"),
}
_MIN_PREFIX = 5
_FUZZY_CUTOFF = 0.85


def _clean(raw: str) -> str:
    text = raw.upper().replace("'", "").replace("’", "").replace(".", "")
    text = re.sub(r"\(.*", "", text)  # "(PLATFORM)", or a parenthesis cut off by the 22-char limit
    return re.sub(r"[-/,]", " ", text)


def normalize(raw: str) -> tuple[str, frozenset[Line]]:
    """Reduce a raw value to a comparable station name plus any line written into it.

    "KENNEDY BD STATION - PLATFORM" → ("KENNEDY", {Line 2})
    "ST. GEORGE YUS STATION" → ("ST GEORGE", {Line 1})
    """
    tokens = _clean(raw).split()
    for i, token in enumerate(tokens):
        if token in _STATION_WORDS:
            tokens = tokens[:i]
            break
    hints = frozenset(line for t in tokens if (line := line_code(t)))
    name = " ".join(t for t in tokens if not line_code(t))
    return name, hints


class StationResolver:
    def __init__(self, registry: StationRegistry) -> None:
        self._registry = registry
        self._names: dict[str, str] = {normalize(s.name)[0]: s.id for s in registry.all()}
        self._names.update(ALIASES)

    def resolve(self, raw_station: str, raw_line: str = "") -> ResolvedLocation:
        line_hints = parse_lines(raw_line)
        cleaned = _clean(raw_station)
        words = set(cleaned.split())

        if " TO " in f" {cleaned} ":
            return self._resolve_segment(raw_station, line_hints)
        if words & _FACILITY_WORDS:
            return ResolvedLocation(LocationKind.FACILITY, line_hints=line_hints)

        name, name_hints = normalize(raw_station)
        if station := self._match(name):
            return ResolvedLocation(LocationKind.STATION, (station,), line_hints | name_hints)
        if words & _LINE_WIDE_WORDS or self._is_line_name(name) or (not name and name_hints):
            named = {line for line, pattern in _LINES_NAMED.items() if pattern.search(cleaned)}
            return ResolvedLocation(
                LocationKind.LINE_WIDE, line_hints=line_hints | name_hints | named
            )
        return ResolvedLocation(LocationKind.UNRESOLVED, line_hints=line_hints)

    def _resolve_segment(self, raw: str, line_hints: frozenset[Line]) -> ResolvedLocation:
        left, _, right = f" {_clean(raw)} ".partition(" TO ")
        ends = [self._match(normalize(part)[0]) for part in (left, right)]
        if ends[0] and ends[1] and ends[0] != ends[1]:
            return ResolvedLocation(LocationKind.SEGMENT, (ends[0], ends[1]), line_hints)
        return ResolvedLocation(LocationKind.UNRESOLVED, line_hints=line_hints)

    def _match(self, name: str) -> Station | None:
        if not name:
            return None
        if name in self._names:
            return self._registry.get(self._names[name])
        # Truncated by the 22-character limit: "PIONEER VILLAGE STATIO", "UNION STATION TO ST AN"
        if len(name) >= _MIN_PREFIX:
            by_prefix = {sid for key, sid in self._names.items() if key.startswith(name)}
            if len(by_prefix) == 1:
                return self._registry.get(by_prefix.pop())
        return self._fuzzy(name)

    def _fuzzy(self, name: str) -> Station | None:
        """Typos ("SCARBOUROUGH", "LANSDOWN"). Only accept a clear, unambiguous winner."""
        scored = sorted(
            ((SequenceMatcher(None, name, key).ratio(), sid) for key, sid in self._names.items()),
            reverse=True,
        )
        best_score, best_id = scored[0]
        runner_up = next((score for score, sid in scored[1:] if sid != best_id), 0.0)
        if best_score >= _FUZZY_CUTOFF and best_score - runner_up > 0.05:
            return self._registry.get(best_id)
        return None

    @staticmethod
    def _is_line_name(name: str) -> bool:
        """ "YONGE UNIVERSITY AND B…" ("…and Bloor–Danforth lines"), "YONGE UNIVERSITY SPADI…" """
        return name.startswith(("YONGE UNIVERSITY", "BLOOR DANFORTH"))
