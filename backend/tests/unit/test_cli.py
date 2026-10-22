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


def test_history_flag_is_passed_to_the_source(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    created: list[bool] = []

    class FakeSource:
        def __init__(self, _client: object, *, include_history: bool) -> None:
            created.append(include_history)

        def fetch(self) -> list[object]:
            return []

    monkeypatch.setattr(cli, "DATABASE_URL", database_url)
    monkeypatch.setattr(cli, "TorontoOpenDataSource", FakeSource)
    cli.main(["ingest", "--history"])
    assert created == [True]


def test_model_eval_prints_a_table(
    database_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pytest.importorskip("sklearn", reason="needs the ml dependency group")
    from signal_problems.modeling import experiment  # noqa: PLC0415

    report = experiment.Report(
        rows={"train": 10, "validation": 2, "test": 3},
        positive_rate={"train": 0.1, "validation": 0.1, "test": 0.2},
        chosen_iterations=50,
        test=[experiment.Scores("gradient boosting", 0.05, 0.008, 0.66, 0.02)],
        calibration=experiment.pd.DataFrame({"predicted": [0.1], "observed": [0.1], "cells": [3]}),
    )
    monkeypatch.setattr(cli, "DATABASE_URL", database_url)
    monkeypatch.setattr(experiment, "run", lambda *_: report)
    cli.main(["ingest", "--csv", str(SAMPLE_CSV)])
    capsys.readouterr()

    cli.main(["model-eval"])

    out = capsys.readouterr().out
    assert "| gradient boosting | 0.05000 | 0.008000 | 0.660 | 0.0200 |" in out
    assert "Boosting rounds chosen on 2024: 50" in out


def test_train_model_stores_a_forecast(
    database_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pytest.importorskip("sklearn", reason="needs the ml dependency group")
    from signal_problems.modeling import forecast  # noqa: PLC0415

    week = forecast.pd.DataFrame(
        {
            "station_id": ["union", "union"],
            "date": forecast.pd.to_datetime(["2026-09-01", "2026-09-02"]),
            "hour": [8, 8],
            "probability": [0.1, 0.2],
        }
    )
    monkeypatch.setattr(cli, "DATABASE_URL", database_url)
    monkeypatch.setattr(forecast, "forecast_week", lambda *_: week)
    cli.main(["train-model"])
    assert "No delays stored yet" in capsys.readouterr().out

    cli.main(["ingest", "--csv", str(SAMPLE_CSV)])
    capsys.readouterr()
    cli.main(["train-model"])

    assert "Stored 2 forecasts for 2026-09-01 – 2026-09-02" in capsys.readouterr().out
