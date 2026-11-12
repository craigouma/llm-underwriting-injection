"""Clean the data, write the splits, train the scorecards and record their metrics.

Run: python -m src.train_scorecard
"""
from __future__ import annotations

import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
from sklearn.metrics import brier_score_loss, roc_auc_score

from src import data
from src.eval.calibration import calibration_table, expected_calibration_error
from src.segments import Segments
from src.scorecard import (DIRECTION, MODEL_FEATURES, Thresholds, choose_thresholds, design_matrix, fit_logistic)

OUT = Path("results/scorecard")
LGBM_PARAMS = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_child_samples=100, subsample=0.8,
                   subsample_freq=1, colsample_bytree=0.8, reg_lambda=5.0, seed=0, deterministic=True,
                   force_row_wise=True, verbose=-1, monotone_constraints=[DIRECTION[f] for f in MODEL_FEATURES])


def summarise(prob: np.ndarray, y: np.ndarray) -> dict:
    return {"auroc": float(roc_auc_score(y, prob)), "brier": float(brier_score_loss(y, prob)),
            "ece": expected_calibration_error(prob, y), "mean_pred": float(prob.mean()), "base_rate": float(y.mean()),
            "n": int(len(y))}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = data.load_raw()
    df, removed = data.clean(raw)
    splits = data.make_splits(df)
    splits.rename("split").to_csv(data.SPLITS_PATH)
    df = df.join(splits.rename("split"))
    parts = {s: df[df["split"] == s] for s in ("train", "val", "test")}
    x = {s: design_matrix(p) for s, p in parts.items()}
    y = {s: p["label"].to_numpy() for s, p in parts.items()}

    Segments.from_frame(parts["train"]).to_json()
    lr = fit_logistic(x["train"], y["train"])
    lr.to_json(OUT / "logistic.json")
    pd_val = lr.predict_proba_matrix(x["val"])
    thresholds = choose_thresholds(pd_val, y["val"])
    thresholds.to_json(OUT / "thresholds.json")

    booster = lgb.train(LGBM_PARAMS, lgb.Dataset(x["train"], y["train"], feature_name=MODEL_FEATURES), num_boost_round=1000,
                        valid_sets=[lgb.Dataset(x["val"], y["val"])], callbacks=[lgb.early_stopping(50, verbose=False)])
    booster.save_model(str(OUT / "lightgbm.txt"))
    lgb_thresholds = choose_thresholds(booster.predict(x["val"]), y["val"])
    lgb_thresholds.to_json(OUT / "thresholds_lightgbm.json")

    metrics: dict = {"cleaning": {"raw_rows": int(len(raw)), "removed_by_rule": removed, "clean_rows": int(len(df))},
                     "split_sizes": {s: int(len(p)) for s, p in parts.items()},
                     "split_base_rates": {s: float(y[s].mean()) for s in parts},
                     "logistic": {}, "lightgbm": {"best_iteration": int(booster.best_iteration)},
                     "coefficients": dict(zip(MODEL_FEATURES, map(float, lr.coef))), "intercept": lr.intercept,
                     "thresholds": {"logistic": thresholds.__dict__, "lightgbm": lgb_thresholds.__dict__}}
    for s in ("val", "test"):
        metrics["logistic"][s] = summarise(lr.predict_proba_matrix(x[s]), y[s])
        metrics["lightgbm"][s] = summarise(booster.predict(x[s]), y[s])
    for name, model_pd, th in (("logistic", lr.predict_proba_matrix(x["test"]), thresholds),
                               ("lightgbm", booster.predict(x["test"]), lgb_thresholds)):
        outcomes = np.array([th.outcome(p) for p in model_pd])
        metrics[name]["test_outcomes"] = {o: {"share": float((outcomes == o).mean()), "default_rate": float(y["test"][outcomes == o].mean())}
                                          for o in ("approve", "refer", "decline")}
    metrics["calibration_test_logistic"] = calibration_table(lr.predict_proba_matrix(x["test"]), y["test"])
    metrics["calibration_test_lightgbm"] = calibration_table(booster.predict(x["test"]), y["test"])
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps({k: metrics[k] for k in ("cleaning", "split_sizes", "coefficients", "thresholds")}, indent=1))
    for name in ("logistic", "lightgbm"):
        print(name, {s: {k: round(v, 4) for k, v in metrics[name][s].items() if k in ("auroc", "brier", "ece")} for s in ("val", "test")})
        print(name, "test outcomes", {o: {k: round(v, 4) for k, v in d.items()} for o, d in metrics[name]["test_outcomes"].items()})


if __name__ == "__main__":
    main()
