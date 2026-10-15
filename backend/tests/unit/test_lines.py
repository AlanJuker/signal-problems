import pytest

from signal_problems.domain.lines import Line, is_scarborough_rt_only, parse_lines


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("YU", {Line.YONGE_UNIVERSITY}),
        ("YUS", {Line.YONGE_UNIVERSITY}),
        ("bd", {Line.BLOOR_DANFORTH}),
        ("YU/BD", {Line.YONGE_UNIVERSITY, Line.BLOOR_DANFORTH}),
        ("YU/ BD", {Line.YONGE_UNIVERSITY, Line.BLOOR_DANFORTH}),
        ("YU/BD/SHP", set(Line)),
        ("B/D", {Line.BLOOR_DANFORTH}),
        ("YU & BD", {Line.YONGE_UNIVERSITY, Line.BLOOR_DANFORTH}),
        ("YU\\BD", {Line.YONGE_UNIVERSITY, Line.BLOOR_DANFORTH}),
        ("BD LINE 2", {Line.BLOOR_DANFORTH}),
        ("BLOOR - DANFORTH", {Line.BLOOR_DANFORTH}),
        ("LINE 1", {Line.YONGE_UNIVERSITY}),
        ("SHEP", {Line.SHEPPARD}),
        ("SRT", set()),
        ("29 DUFFERIN", set()),  # a bus route typed into the line column
        ("999", set()),
        ("", set()),
    ],
)
def test_parse_lines(raw: str, expected: set[Line]) -> None:
    assert parse_lines(raw) == expected


def test_display_name() -> None:
    assert Line.SHEPPARD.display_name == "Line 4 Sheppard"


@pytest.mark.parametrize(
    ("raw", "only_line_3"),
    [("SRT", True), ("RT", True), ("YU/SRT", False), ("BD", False), ("", False), ("SHEP", False)],
)
def test_is_scarborough_rt_only(raw: str, only_line_3: bool) -> None:
    assert is_scarborough_rt_only(raw) is only_line_3
