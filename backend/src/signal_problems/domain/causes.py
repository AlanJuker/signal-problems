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


def cause_for(code: str, mode: str = "subway") -> DelayCause:
    """Streetcars and buses publish their own code lists, with the same prefixes as the subway."""
    code = code.strip().upper()
    category = _CATEGORY_BY_PREFIX.get(code[:1], CauseCategory.UNKNOWN)
    return DelayCause(code, _published_codes(mode).get(code), category)
