import pytest

from signal_problems.domain.lines import Line, parse_lines


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("YU", {Line.YONGE_UNIVERSITY}),
        ("YUS", {Line.YONGE_UNIVERSITY}),
        ("bd", {Line.BLOOR_DANFORTH}),
        ("YU/BD", {Line.YONGE_UNIVERSITY, Line.BLOOR_DANFORTH}),
        ("YU/ BD", {Line.YONGE_UNIVERSITY, Line.BLOOR_DANFORTH}),
        ("YU/BD/SHP", set(Line)),
        ("SRT", set()),
        ("", set()),
    ],
)
def test_parse_lines(raw: str, expected: set[Line]) -> None:
    assert parse_lines(raw) == expected


def test_display_name() -> None:
    assert Line.SHEPPARD.display_name == "Line 4 Sheppard"
