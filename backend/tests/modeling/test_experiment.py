from datetime import date

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn", reason="needs the ml dependency group")

from signal_problems.modeling.experiment import PRIOR_CELLS, calibration, frequency, run, score


def frame(station: str, weekday: int, hour: int, labels: list[int]) -> pd.DataFrame:
    return pd.DataFrame({"station_id": station, "weekday": weekday, "hour": hour, "label": labels})


def test_frequency_is_smoothed_toward_the_overall_rate() -> None:
    history = pd.concat([frame("a", 0, 8, [1] * 20), frame("b", 0, 8, [0] * 20)])
    target = pd.concat([frame("a", 0, 8, [0]), frame("c", 3, 9, [0])])

    p = frequency(history, target)

    overall = 0.5
    assert p[0] == pytest.approx((20 + PRIOR_CELLS * overall) / (20 + PRIOR_CELLS))
    assert p[1] == pytest.approx(overall)  # a group never seen falls back to the overall rate


def test_score_rewards_better_probabilities() -> None:
    labels = pd.Series([0, 0, 0, 1])
    good = score("good", labels, np.array([0.05, 0.05, 0.05, 0.9]))
    bad = score("bad", labels, np.array([0.5, 0.5, 0.5, 0.5]))
    assert good.log_loss < bad.log_loss
    assert good.roc_auc == 1.0


def test_calibration_has_one_row_per_bin() -> None:
    p = np.linspace(0.01, 0.2, 100)
    table = calibration(pd.Series((p > 0.1).astype(int)), p, bins=5)
    assert len(table) == 5
    assert table["cells"].sum() == 100


def test_run_scores_every_method_on_the_test_period() -> None:
    rng = np.random.default_rng(0)
    days = pd.date_range("2014-01-01", "2025-03-31", freq="D")
    # Station "busy" is hit far more often at 8 a.m.: a learnable signal
    hits = [("busy", d, 8) for d in days if rng.random() < 0.6] + [
        ("quiet", d, 8) for d in days if rng.random() < 0.05
    ]
    events = pd.DataFrame(hits, columns=["station_id", "date", "hour"])

    report = run(events, ["busy", "quiet"], date(2025, 3, 31), iterations=(5,))

    assert [s.name for s in report.test] == [
        "frequency, 2014–2024",
        "frequency, last 12 months (2024)",
        "gradient boosting",
    ]
    assert report.rows["test"] == 2 * 90 * 21
    assert all(s.roc_auc > 0.9 for s in report.test)
