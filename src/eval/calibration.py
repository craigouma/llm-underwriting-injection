"""Calibration summaries for the scorecard."""
from __future__ import annotations

import numpy as np


def calibration_table(prob: np.ndarray, y: np.ndarray, bins: int = 10) -> list[dict[str, float]]:
    """Equal-count bins of predicted probability with the observed default rate in each."""
    order = np.argsort(prob)
    rows = []
    for chunk in np.array_split(order, bins):
        rows.append({"mean_pred": float(prob[chunk].mean()), "observed": float(y[chunk].mean()), "n": int(len(chunk))})
    return rows


def expected_calibration_error(prob: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    rows = calibration_table(prob, y, bins)
    n = sum(r["n"] for r in rows)
    return float(sum(r["n"] / n * abs(r["mean_pred"] - r["observed"]) for r in rows))
