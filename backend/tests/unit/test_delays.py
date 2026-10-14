from datetime import datetime

import pytest

from signal_problems.domain.causes import cause_for
from signal_problems.domain.delays import Delay, infer_line
from signal_problems.domain.lines import Line
from signal_problems.domain.resolver import StationResolver
from signal_problems.domain.stations import TTC_SUBWAY

resolver = StationResolver(TTC_SUBWAY)


@pytest.mark.parametrize(
    ("raw_station", "raw_line", "line"),
    [
        ("KEELE STATION", "", Line.BLOOR_DANFORTH),  # only one line serves it
        ("BLOOR STATION", "YU", Line.YONGE_UNIVERSITY),
        ("ST GEORGE BD STATION", "", Line.BLOOR_DANFORTH),  # line written in the name
        ("SPADINA STATION", "", None),  # interchange, no hint
        ("SPADINA STATION", "YU/BD", None),
        ("LINE 2 BLOOR DANFORTH", "", Line.BLOOR_DANFORTH),
        ("GREENWOOD YARD", "BD", Line.BLOOR_DANFORTH),
        ("GREENWOOD YARD", "", None),
    ],
)
def test_infer_line(raw_station: str, raw_line: str, line: Line | None) -> None:
    assert infer_line(resolver.resolve(raw_station, raw_line)) == line


@pytest.mark.parametrize(("minutes", "significant"), [(0, False), (4, False), (5, True)])
def test_significant_delay(minutes: int, significant: bool) -> None:
    delay = Delay(
        source_id=1,
        occurred_at=datetime(2026, 8, 31, 8, 12),
        location=resolver.resolve("UNION STATION"),
        line=Line.YONGE_UNIVERSITY,
        cause=cause_for("MUIS"),
        minutes=minutes,
        gap_minutes=0,
    )
    assert delay.is_significant is significant
