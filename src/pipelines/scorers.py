"""Score functions for the B and C pipelines: the logistic scorecard and the LightGBM robustness check."""
from __future__ import annotations

from pathlib import Path

from src.pipelines.extractor import ScoreFn
from src.scorecard import LogisticScorecard, Thresholds, transform

SCORECARD_DIR = Path("results/scorecard")


def logistic() -> tuple[ScoreFn, Thresholds]:
    return LogisticScorecard.from_json(SCORECARD_DIR / "logistic.json").pd, Thresholds.from_json(SCORECARD_DIR / "thresholds.json")


def lightgbm() -> tuple[ScoreFn, Thresholds]:
    import lightgbm as lgb

    booster = lgb.Booster(model_file=str(SCORECARD_DIR / "lightgbm.txt"))
    return (lambda raw: float(booster.predict(transform(raw)[None, :])[0])), Thresholds.from_json(SCORECARD_DIR / "thresholds_lightgbm.json")
