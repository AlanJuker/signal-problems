import pytest

from signal_problems.domain.causes import CauseCategory, cause_for
from signal_problems.domain.surface import route_number


@pytest.mark.parametrize(
    ("line", "route"),
    [
        ("504 KING", 504),
        ("504A KING", 504),  # a branch counts as its route
        ("7 BATHURST", 7),
        ("939 FINCH EXPRESS", 939),
        (" 52 LAWRENCE WEST", 52),
        ("LINE 1 SHUTTLE", None),  # subway replacement buses
        ("RAD", None),
        ("", None),
        ("1234 NOT A ROUTE", None),
    ],
)
def test_route_number(line: str, route: int | None) -> None:
    assert route_number(line) == route


def test_each_mode_has_its_own_code_list() -> None:
    assert cause_for("MTSAN", "streetcar").category is CauseCategory.PASSENGERS_AND_OTHER
    assert cause_for("EFD", "bus").description == "DOORS"
    assert cause_for("EFD").description is None  # not a subway code
