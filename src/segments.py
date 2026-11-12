"""Applicant segments (age bands) and per-segment value distributions from the training split.

Used twice, with the same definition: the plausibility score of a falsified value (attacks) and the
plausible-band review rule (architecture C).
"""
from __future__ import annotations

import json
from bisect import bisect_left, bisect_right
from pathlib import Path

import numpy as np

AGE_BANDS = [(18, 30), (30, 40), (40, 50), (50, 60), (60, 70), (70, 200)]
SEGMENT_FIELDS = ("monthly_income", "debt_ratio", "utilization", "late_total")
SEGMENTS_PATH = Path("data/segments.json")
QUANTILES = 201


def band_of(age: float) -> int:
    for i, (lo, hi) in enumerate(AGE_BANDS):
        if lo <= age < hi:
            return i
    return len(AGE_BANDS) - 1


class Segments:
    """Empirical CDFs per age band, stored as 201 quantiles so the file stays small."""

    def __init__(self, quantiles: dict[str, dict[str, list[float]]]):
        self.quantiles = quantiles

    @classmethod
    def from_frame(cls, train) -> "Segments":
        df = train.assign(late_total=train["late_30_59"] + train["late_60_89"] + train["late_90"])
        q = np.linspace(0, 1, QUANTILES)
        out: dict[str, dict[str, list[float]]] = {}
        for field_name in SEGMENT_FIELDS:
            out[field_name] = {}
            for i, (lo, hi) in enumerate(AGE_BANDS):
                vals = df.loc[(df["age"] >= lo) & (df["age"] < hi), field_name].to_numpy()
                out[field_name][str(i)] = [float(v) for v in np.quantile(vals, q)]
        return cls(out)

    def cdf(self, field_name: str, age: float, value: float) -> float:
        """Mid-rank CDF of `value` among training applicants in the same age band."""
        qs = self.quantiles[field_name][str(band_of(age))]
        lo, hi = bisect_left(qs, value), bisect_right(qs, value)
        return (lo + hi) / 2 / (len(qs))

    def plausibility(self, field_name: str, age: float, value: float) -> float:
        """1 at the segment median, 0 at or beyond the extremes."""
        return float(1.0 - abs(2.0 * min(max(self.cdf(field_name, age, value), 0.0), 1.0) - 1.0))

    def outside_band(self, field_name: str, age: float, value: float, lower: float = 0.001, upper: float = 0.995) -> bool:
        qs = self.quantiles[field_name][str(band_of(age))]
        return value < qs[int(lower * (len(qs) - 1))] or value > qs[int(upper * (len(qs) - 1))]

    def to_json(self, path: Path = SEGMENTS_PATH) -> None:
        path.write_text(json.dumps(self.quantiles))

    @classmethod
    def from_json(cls, path: Path = SEGMENTS_PATH) -> "Segments":
        return cls(json.loads(path.read_text()))
