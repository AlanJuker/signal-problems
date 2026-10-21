"""Does a model beat the historical frequency at predicting delays? (issue #21)

Temporal split: train 2014–2023, validate 2024, test 2025 onward. Never shuffled.
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

from signal_problems.modeling.dataset import FEATURES, build_cells

Probabilities = NDArray[np.float64]

TRAIN = (date(2014, 1, 1), date(2023, 12, 31))
VALIDATION = (date(2024, 1, 1), date(2024, 12, 31))
TEST_START = date(2025, 1, 1)
GROUP = ["station_id", "weekday", "hour"]
PRIOR_CELLS = 20  # smoothing: a group with no history falls back to the overall rate


@dataclass(frozen=True)
class Scores:
    name: str
    log_loss: float
    brier: float
    roc_auc: float
    pr_auc: float


def frequency(history: pd.DataFrame, target: pd.DataFrame) -> Probabilities:
    """Share of past cells with a delay, per station, weekday and hour, smoothed toward the mean."""
    overall = history["label"].mean()
    stats = history.groupby(GROUP)["label"].agg(["sum", "count"])
    rate = (stats["sum"] + PRIOR_CELLS * overall) / (stats["count"] + PRIOR_CELLS)
    looked_up = target.join(rate.rename("p"), on=GROUP)["p"].fillna(overall)
    probabilities: Probabilities = looked_up.to_numpy(dtype=np.float64)
    return probabilities


def fit_model(train: pd.DataFrame, max_iter: int) -> HistGradientBoostingClassifier:
    model = HistGradientBoostingClassifier(
        max_iter=max_iter,
        learning_rate=0.1,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        categorical_features=[FEATURES.index("station")],
        early_stopping=False,
        random_state=0,
    )
    return model.fit(train[FEATURES], train["label"])


def score(name: str, labels: pd.Series, p: Probabilities) -> Scores:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return Scores(
        name,
        log_loss(labels, p),
        brier_score_loss(labels, p),
        roc_auc_score(labels, p),
        average_precision_score(labels, p),
    )


def calibration(labels: pd.Series, p: Probabilities, bins: int = 10) -> pd.DataFrame:
    """Predicted vs observed rate by decile of predicted probability."""
    frame = pd.DataFrame({"p": p, "y": labels.to_numpy()})
    frame["bin"] = pd.qcut(frame["p"].rank(method="first"), bins, labels=False)
    return frame.groupby("bin").agg(
        predicted=("p", "mean"), observed=("y", "mean"), cells=("y", "size")
    )


@dataclass(frozen=True)
class Report:
    rows: dict[str, int]
    positive_rate: dict[str, float]
    chosen_iterations: int
    test: list[Scores]
    calibration: pd.DataFrame


def run(
    events: pd.DataFrame,
    stations: list[str],
    last: date,
    iterations: tuple[int, ...] = (50, 100, 300),
) -> Report:
    cells = build_cells(events, stations, TRAIN[0], last)

    def between(start: date, end: date) -> pd.DataFrame:
        return cells[(cells["date"] >= pd.Timestamp(start)) & (cells["date"] <= pd.Timestamp(end))]

    train, validation = between(*TRAIN), between(*VALIDATION)
    test = cells[cells["date"] >= pd.Timestamp(TEST_START)]

    # Pick the number of boosting rounds on 2024, then refit on everything before the test period
    losses = {
        n: log_loss(
            validation["label"], fit_model(train, n).predict_proba(validation[FEATURES])[:, 1]
        )
        for n in iterations
    }
    chosen = min(losses, key=lambda n: losses[n])
    before_test = pd.concat([train, validation])
    model_p = fit_model(before_test, chosen).predict_proba(test[FEATURES])[:, 1]

    results = [
        score("frequency, 2014–2024", test["label"], frequency(before_test, test)),
        score("frequency, last 12 months (2024)", test["label"], frequency(validation, test)),
        score("gradient boosting", test["label"], model_p),
    ]
    return Report(
        rows={"train": len(train), "validation": len(validation), "test": len(test)},
        positive_rate={
            "train": float(train["label"].mean()),
            "validation": float(validation["label"].mean()),
            "test": float(test["label"].mean()),
        },
        chosen_iterations=chosen,
        test=results,
        calibration=calibration(test["label"], model_p),
    )
