import json
from pathlib import Path

import pytest

from signal_problems import cli
from tests.conftest import SAMPLE_CSV


def test_ingest_command_prints_a_report(
    database_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "DATABASE_URL", database_url)

    cli.main(["ingest", "--csv", str(SAMPLE_CSV)])

    out = capsys.readouterr().out
    assert "Rows read:             7" in out
    assert "Duplicate rows:        1" in out
    assert "Malformed rows:        1" in out
    assert "SCARBOROUGH CTR STATIO" in out


def test_requires_a_command() -> None:
    with pytest.raises(SystemExit):
        cli.main([])


def test_missing_file(database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "DATABASE_URL", database_url)
    with pytest.raises(FileNotFoundError):
        cli.main(["ingest", "--csv", str(tmp_path / "missing.csv")])


def test_openapi_command_prints_the_schema(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["openapi"])
    schema = json.loads(capsys.readouterr().out)
    assert schema["info"]["title"] == "signal-problems"
    assert "/commute/risk" in schema["paths"]
