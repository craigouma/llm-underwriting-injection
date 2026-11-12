"""Scorecard: sign-constrained logistic regression (auditable) and a LightGBM robustness check.

The logistic regression is the scorecard used by architectures B and C. Its coefficients are
bounded so that every feature with an agreed credit direction can only push risk that way.
Parameters are stored as plain JSON so inference needs no pickle and no training data.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np
from scipy.optimize import minimize

from src.data import FEATURES

# +1: more of the feature raises default risk, -1: lowers it, 0: left free (no agreed direction).
DIRECTION: dict[str, int] = {
    "utilization": 1,
    "age": -1,
    "late_30_59": 1,
    "debt_ratio": 1,
    "log_income": -1,
    "open_lines": 0,
    "late_90": 1,
    "real_estate_loans": 0,
    "late_60_89": 1,
    "dependents": 1,
}
MODEL_FEATURES = list(DIRECTION)
CAPS = {"utilization": 2.0, "debt_ratio": 5.0, "late_30_59": 6, "late_60_89": 6, "late_90": 6, "open_lines": 25,
        "real_estate_loans": 6, "dependents": 8, "age": 100}


def transform(raw: Mapping[str, float]) -> np.ndarray:
    """Map the ten applicant features to the model design vector (capped, income on log scale)."""
    row = {k: min(max(float(raw[k]), 0.0), CAPS[k]) if k in CAPS else float(raw[k]) for k in FEATURES}
    row["log_income"] = float(np.log1p(max(float(raw["monthly_income"]), 0.0)))
    return np.array([row[f] for f in MODEL_FEATURES])


def design_matrix(df) -> np.ndarray:
    return np.vstack([transform(r) for r in df[FEATURES].to_dict("records")])


@dataclass
class LogisticScorecard:
    mean: np.ndarray
    scale: np.ndarray
    coef: np.ndarray
    intercept: float

    def predict_proba_matrix(self, x: np.ndarray) -> np.ndarray:
        z = ((x - self.mean) / self.scale) @ self.coef + self.intercept
        return 1.0 / (1.0 + np.exp(-z))

    def pd(self, raw: Mapping[str, float]) -> float:
        return float(self.predict_proba_matrix(transform(raw)[None, :])[0])

    def contributions(self, raw: Mapping[str, float]) -> dict[str, float]:
        """Per-feature contribution to the log-odds, relative to the training mean (for audit)."""
        z = (transform(raw) - self.mean) / self.scale * self.coef
        return dict(zip(MODEL_FEATURES, map(float, z)))

    def to_json(self, path: Path) -> None:
        path.write_text(json.dumps({
            "features": MODEL_FEATURES, "mean": self.mean.tolist(), "scale": self.scale.tolist(),
            "coef": self.coef.tolist(), "intercept": self.intercept}, indent=2))

    @classmethod
    def from_json(cls, path: Path) -> "LogisticScorecard":
        d = json.loads(path.read_text())
        assert d["features"] == MODEL_FEATURES
        return cls(np.array(d["mean"]), np.array(d["scale"]), np.array(d["coef"]), float(d["intercept"]))


def fit_logistic(x: np.ndarray, y: np.ndarray, l2: float = 1.0) -> LogisticScorecard:
    """L2-penalised logistic regression with sign bounds on coefficients (L-BFGS-B)."""
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale == 0] = 1.0
    z = (x - mean) / scale
    n, p = z.shape
    bounds = [((0, None) if DIRECTION[f] > 0 else (None, 0) if DIRECTION[f] < 0 else (None, None)) for f in MODEL_FEATURES]
    bounds.append((None, None))

    def objective(w: np.ndarray):
        beta, b0 = w[:p], w[p]
        s = z @ beta + b0
        loss = np.mean(np.logaddexp(0, s) - y * s) + 0.5 * l2 / n * beta @ beta
        prob = 1.0 / (1.0 + np.exp(-s))
        g = np.empty(p + 1)
        g[:p] = z.T @ (prob - y) / n + l2 / n * beta
        g[p] = np.mean(prob - y)
        return loss, g

    w0 = np.zeros(p + 1)
    w0[p] = np.log(y.mean() / (1 - y.mean()))
    res = minimize(objective, w0, jac=True, method="L-BFGS-B", bounds=bounds, options={"maxiter": 500})
    return LogisticScorecard(mean, scale, res.x[:p], float(res.x[p]))


# Outcome mapping --------------------------------------------------------------------------

APPROVE, REFER, DECLINE = "approve", "refer", "decline"


@dataclass(frozen=True)
class Thresholds:
    approve_below: float
    decline_from: float

    def outcome(self, pd_value: float) -> str:
        if pd_value < self.approve_below:
            return APPROVE
        return DECLINE if pd_value >= self.decline_from else REFER

    def to_json(self, path: Path) -> None:
        path.write_text(json.dumps({"approve_below": self.approve_below, "decline_from": self.decline_from}, indent=2))

    @classmethod
    def from_json(cls, path: Path) -> "Thresholds":
        d = json.loads(path.read_text())
        return cls(d["approve_below"], d["decline_from"])


def choose_thresholds(pd_val: np.ndarray, y_val: np.ndarray, loss_to_margin: float = 6.0) -> Thresholds:
    """Decline cut-off maximises expected profit on validation (margin 1 per good loan, loss
    `loss_to_margin` per default). Applicants between half that cut-off and the cut-off are referred."""
    grid = np.unique(np.quantile(pd_val, np.linspace(0.5, 0.999, 500)))

    def profit(cut: float) -> float:
        accepted = pd_val < cut
        return float(((1 - y_val[accepted]).sum() - loss_to_margin * y_val[accepted].sum()))

    decline_from = float(max(grid, key=profit))
    return Thresholds(approve_below=decline_from / 2.0, decline_from=decline_from)
