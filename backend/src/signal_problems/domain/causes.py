import csv
import re
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from importlib.resources import files


class CauseCategory(StrEnum):
    EQUIPMENT = "equipment"  # E: trains (doors, brakes, propulsion…)
    PASSENGERS_AND_OTHER = "passengers_and_other"  # M: ill customers, alarms, fires, misc.
    INFRASTRUCTURE = "infrastructure"  # P: signals, track, power, escalators
    SECURITY = "security"  # S: assaults, threats, people at track level
    OPERATIONS = "operations"  # T: crew, transit control
    UNKNOWN = "unknown"


_CATEGORY_BY_PREFIX = {
    "E": CauseCategory.EQUIPMENT,
    "M": CauseCategory.PASSENGERS_AND_OTHER,
    "P": CauseCategory.INFRASTRUCTURE,
    "S": CauseCategory.SECURITY,
    "T": CauseCategory.OPERATIONS,
}
_SIGNAL_WORDS = re.compile(r"\bsignal|\bATC\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class DelayCause:
    code: str
    description: str | None  # None when the code isn't in the TTC's published code list
    category: CauseCategory

    @property
    def is_signal_problem(self) -> bool:
        """An actual signalling failure, the excuse every Toronto commuter knows.

        Only infrastructure codes count: "Operator Violated Signal" is a crew issue, not a
        signal problem.
        """
        return (
            self.category is CauseCategory.INFRASTRUCTURE
            and self.description is not None
            and bool(_SIGNAL_WORDS.search(self.description))
        )


@cache
def _published_codes(mode: str) -> dict[str, str]:
    table = files("signal_problems.domain.data").joinpath(f"{mode}_codes.csv")
    with table.open(encoding="utf-8") as f:
        return {row["code"]: row["description"] for row in csv.DictReader(f)}


# The 2014–2024 streetcar and bus logs name an incident instead of giving a code (#28). A word gets
# the category of the code with the same meaning in that mode's current list (ADR 0005); words with
# no such code stay unknown rather than guessed.
_INCIDENTS = {
    "MECHANICAL": CauseCategory.EQUIPMENT,
    "LATE LEAVING GARAGE - MECHANICAL": CauseCategory.EQUIPMENT,
    "LATE ENTERING SERVICE - MECHANICAL": CauseCategory.EQUIPMENT,
    "OPERATIONS": CauseCategory.OPERATIONS,
    "OPERATIONS - OPERATOR": CauseCategory.OPERATIONS,
    "LATE": CauseCategory.OPERATIONS,
    "LATE ENTERING SERVICE": CauseCategory.OPERATIONS,
    "LATE LEAVING GARAGE": CauseCategory.OPERATIONS,
    "LATE LEAVING GARAGE - OPERATOR": CauseCategory.OPERATIONS,
    "LATE LEAVING GARAGE - OPERATIONS": CauseCategory.OPERATIONS,
    "COLLISION - TTC": CauseCategory.OPERATIONS,
    "COLLISION - TTC INVOLVED": CauseCategory.OPERATIONS,
    "SECURITY": CauseCategory.SECURITY,
    "SECURITTY": CauseCategory.SECURITY,
    "GENERAL DELAY": CauseCategory.PASSENGERS_AND_OTHER,
    "DIVERSION": CauseCategory.PASSENGERS_AND_OTHER,
    "CLEANING": CauseCategory.PASSENGERS_AND_OTHER,
    "CLEANING - UNSANITARY": CauseCategory.PASSENGERS_AND_OTHER,
    "CLEANING - DISINFECTION": CauseCategory.PASSENGERS_AND_OTHER,
    "VISION": CauseCategory.PASSENGERS_AND_OTHER,
    "LATE LEAVING GARAGE - VISION": CauseCategory.PASSENGERS_AND_OTHER,
    "ROAD BLOCKED - NON-TTC COLLISION": CauseCategory.PASSENGERS_AND_OTHER,
    "ROAD BLOCK - NON-TTC COLLISION": CauseCategory.PASSENGERS_AND_OTHER,
    "ROADBLOCK BY COLLISION - NON-TTC": CauseCategory.PASSENGERS_AND_OTHER,
    "OVERHEAD": CauseCategory.INFRASTRUCTURE,
    "RAIL/SWITCHES": CauseCategory.INFRASTRUCTURE,
    "HELD BY": CauseCategory.UNKNOWN,
    "EMERGENCY SERVICES": CauseCategory.UNKNOWN,
    "UTILIZED OFF ROUTE": CauseCategory.UNKNOWN,
    "UTILIZING OFF ROUTE": CauseCategory.UNKNOWN,
    "MANAGEMENT": CauseCategory.UNKNOWN,
    "LATE LEAVING GARAGE - MANAGEMENT": CauseCategory.UNKNOWN,
    "OVERHEAD - PANTOGRAPH": CauseCategory.UNKNOWN,
}
# Police investigations: a passenger code for streetcars (MTPOL), a security one for buses (SFPOL)
_INVESTIGATION = {"streetcar": CauseCategory.PASSENGERS_AND_OTHER, "bus": CauseCategory.SECURITY}


def incident_code(incident: str) -> str:
    """How a 2014–2024 incident word is stored: tidied, or empty when it isn't one the TTC used
    (a stray "e"), so it can't pass for a code."""
    word = " ".join(incident.split()).upper()
    return word if word in _INCIDENTS or word == "INVESTIGATION" else ""


def cause_for(code: str, mode: str = "subway") -> DelayCause:
    """Streetcars and buses publish their own code lists, with the same prefixes as the subway."""
    code = code.strip().upper()
    if mode in _INVESTIGATION:  # streetcar or bus: their history logged incident words
        if code == "INVESTIGATION":
            return DelayCause(code, code, _INVESTIGATION[mode])
        if code in _INCIDENTS:
            return DelayCause(code, code, _INCIDENTS[code])
    category = _CATEGORY_BY_PREFIX.get(code[:1], CauseCategory.UNKNOWN)
    return DelayCause(code, _published_codes(mode).get(code), category)
