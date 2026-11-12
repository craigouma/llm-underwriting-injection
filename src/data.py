"""Give Me Some Credit loading, cleaning and splitting.

Cleaning is deliberately minimal and driven only by data-quality facts, never by model results.
Every rule is documented in data/README.md.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAW_PATH = Path("data/raw/cs-training.csv")
SPLITS_PATH = Path("data/splits.csv")
SPLIT_SEED = 20261112
SPLIT_FRACTIONS = {"train": 0.6, "val": 0.2, "test": 0.2}

RENAME = {
    "SeriousDlqin2yrs": "label",
    "RevolvingUtilizationOfUnsecuredLines": "utilization",
    "age": "age",
    "NumberOfTime30-59DaysPastDueNotWorse": "late_30_59",
    "DebtRatio": "debt_ratio",
    "MonthlyIncome": "monthly_income",
    "NumberOfOpenCreditLinesAndLoans": "open_lines",
    "NumberOfTimes90DaysLate": "late_90",
    "NumberRealEstateLoansOrLines": "real_estate_loans",
    "NumberOfTime60-89DaysPastDueNotWorse": "late_60_89",
    "NumberOfDependents": "dependents",
}
FEATURES = [c for c in RENAME.values() if c != "label"]
SENTINEL_COLUMNS = ["late_30_59", "late_60_89", "late_90"]
SENTINEL_VALUES = (96, 98)

# Upper bounds that remove obvious entry errors (see data/README.md for the evidence).
MAX_UTILIZATION = 2.0
MAX_DEBT_RATIO = 5.0
MIN_AGE = 18
MIN_INCOME = 500.0
MAX_INCOME = 50_000.0


def load_raw(path: Path = RAW_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0).rename(columns=RENAME)
    df.index.name = "row_id"
    return df


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Return the cleaned frame and the number of rows removed by each rule, in order."""
    removed: dict[str, int] = {}
    out = df

    def drop(name: str, mask: pd.Series) -> None:
        nonlocal out
        removed[name] = int(mask.sum())
        out = out[~mask]

    drop("missing_income_or_dependents", out["monthly_income"].isna() | out["dependents"].isna())
    drop("sentinel_delinquency_codes", out[SENTINEL_COLUMNS].isin(SENTINEL_VALUES).any(axis=1))
    drop("age_below_minimum", out["age"] < MIN_AGE)
    drop("income_out_of_range", (out["monthly_income"] < MIN_INCOME) | (out["monthly_income"] > MAX_INCOME))
    drop("utilization_above_cap", out["utilization"] > MAX_UTILIZATION)
    drop("debt_ratio_above_cap", out["debt_ratio"] > MAX_DEBT_RATIO)
    out = out.copy()
    for col in ("dependents", "open_lines", "real_estate_loans", *SENTINEL_COLUMNS):
        out[col] = out[col].astype(int)
    out["monthly_income"] = out["monthly_income"].round().astype(int)
    return out, removed


def make_splits(df: pd.DataFrame, seed: int = SPLIT_SEED) -> pd.Series:
    """Stratified train/val/test assignment indexed by row_id."""
    rng = np.random.default_rng(seed)
    split = pd.Series(index=df.index, dtype="object")
    for _, idx in df.groupby("label").groups.items():
        ids = np.array(idx)
        rng.shuffle(ids)
        n_train = int(round(len(ids) * SPLIT_FRACTIONS["train"]))
        n_val = int(round(len(ids) * SPLIT_FRACTIONS["val"]))
        split.loc[ids[:n_train]] = "train"
        split.loc[ids[n_train : n_train + n_val]] = "val"
        split.loc[ids[n_train + n_val :]] = "test"
    return split


def load_clean_with_splits() -> pd.DataFrame:
    """Cleaned data with a `split` column read from the committed split file."""
    df, _ = clean(load_raw())
    splits = pd.read_csv(SPLITS_PATH, index_col="row_id")["split"]
    df = df.join(splits, how="inner")
    return df
