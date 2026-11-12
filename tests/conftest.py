import pytest

from src.documents import make_bundle
from src.segments import Segments

ROWS = [
    {"utilization": 0.62, "age": 41, "late_30_59": 1, "debt_ratio": 0.35, "monthly_income": 4250, "open_lines": 7,
     "late_90": 0, "real_estate_loans": 1, "late_60_89": 0, "dependents": 2},
    {"utilization": 0.05, "age": 29, "late_30_59": 0, "debt_ratio": 0.0, "monthly_income": 2100, "open_lines": 3,
     "late_90": 0, "real_estate_loans": 0, "late_60_89": 0, "dependents": 0},
    {"utilization": 1.1, "age": 63, "late_30_59": 2, "debt_ratio": 0.9, "monthly_income": 8900, "open_lines": 12,
     "late_90": 1, "real_estate_loans": 2, "late_60_89": 1, "dependents": 1},
]


@pytest.fixture(scope="session")
def rows():
    return ROWS


@pytest.fixture(scope="session")
def bundles(rows):
    return [make_bundle(r, 1000 + i) for i, r in enumerate(rows)]


@pytest.fixture(scope="session")
def segments():
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(0)
    n = 4000
    df = pd.DataFrame({"age": rng.integers(18, 90, n), "monthly_income": rng.lognormal(8.5, 0.5, n),
                       "debt_ratio": rng.beta(2, 5, n), "utilization": rng.beta(1, 3, n),
                       "late_30_59": rng.poisson(0.2, n), "late_60_89": rng.poisson(0.1, n), "late_90": rng.poisson(0.1, n)})
    return Segments.from_frame(df)
