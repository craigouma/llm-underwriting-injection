"""Deterministic selection of applicants and construction of every model call in the grid.

The same code runs inside the Kaggle inference kernel (to build prompts) and in the analysis
(to rebuild bundles for the replay). Nothing here calls a model.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd

from src import data
from src.attacks import AttackSpec, apply_attack, is_applicable, load_catalog
from src.documents import Bundle, make_bundle
from src.pipelines.base import job_key
from src.pipelines.prompts import TASKS, messages_for
from src.scorecard import LogisticScorecard, Thresholds, design_matrix
from src.segments import Segments

SELECTION_SEED = 20261113
N_UTILITY, N_TARGETS, N_COLLATERAL = 1500, 200, 50
# Run sizes (prefixes of the shuffled U, P, Q lists): clean utility, targets, collateral. See preregistration addendum 1.
RUN_SIZES = {"main": (1000, 150, 40), "mainL": (200, 50, 0), "phr1": (150, 30, 0), "var": (60, 20, 0)}
VARIANCE_ATTACKS = ("IO1", "HI2", "FA2", "DX3", "EM2", "EM5", "EM11", "EM14")
VARIANCE_SEEDS = (1, 2, 3)
VARIANCE_TEMPERATURE = 0.7


@dataclass(frozen=True)
class Selection:
    """Applicant roles. U: natural-mix utility sample. P: scorecard decline/refer targets. Q: scorecard-approve collateral sample."""
    reference: pd.DataFrame  # indexed by row_id with label, features, pd_ref, outcome_ref
    U: list[int]
    P: list[int]
    Q: list[int]


def select() -> Selection:
    df = data.load_clean_with_splits()
    test = df[df["split"] == "test"].copy()
    lr = LogisticScorecard.from_json(Path("results/scorecard/logistic.json"))
    thresholds = Thresholds.from_json(Path("results/scorecard/thresholds.json"))
    test["pd_ref"] = lr.predict_proba_matrix(design_matrix(test))
    test["outcome_ref"] = [thresholds.outcome(p) for p in test["pd_ref"]]
    rng = np.random.default_rng(SELECTION_SEED)
    # Stratified by label at the natural rate.
    U: list[int] = []
    for _, idx in test.groupby("label").groups.items():
        take = int(round(N_UTILITY * len(idx) / len(test)))
        U += list(rng.choice(np.array(idx), size=take, replace=False))
    rng.shuffle(U)
    P = list(rng.choice(test.index[test["outcome_ref"] != "approve"].to_numpy(), size=N_TARGETS, replace=False))
    Q = list(rng.choice(test.index[test["outcome_ref"] == "approve"].to_numpy(), size=N_COLLATERAL, replace=False))
    return Selection(test, [int(i) for i in U], [int(i) for i in P], [int(i) for i in Q])


@dataclass(frozen=True)
class Job:
    key: str
    run: str
    task: str
    phrasing: int
    temperature: float
    seed: int
    messages: list[dict]


def _bundles(sel: Selection, segments: Segments, specs: list[AttackSpec], clean_ids: list[int], target_ids: list[int],
             attacks: list[AttackSpec]) -> Iterator[Bundle]:
    cache: dict[int, Bundle] = {}

    def clean(i: int) -> Bundle:
        if i not in cache:
            row = sel.reference.loc[i]
            cache[i] = make_bundle({k: row[k] for k in data.FEATURES}, int(i))
        return cache[i]

    for i in clean_ids:
        yield clean(i)
    for i in target_ids:
        for spec in attacks:
            b = clean(i)
            if is_applicable(b, spec):
                yield apply_attack(b, spec, segments)


def build_bundles(sel: Selection, segments: Segments, run: str = "main") -> list[Bundle]:
    """All bundles of a run, clean first."""
    specs = load_catalog()
    if run in ("main", "mainL"):
        nu, np_, nq = RUN_SIZES[run]
        targets = sel.P[:np_] + sel.Q[:nq]
        clean_ids = list(dict.fromkeys(sel.U[:nu] + targets))
        return list(_bundles(sel, segments, specs, clean_ids, targets, specs))
    if run == "check":
        return list(_bundles(sel, segments, specs, sel.U[:16], [], specs))
    if run == "pilot":
        chosen = [s for s in specs if s.id in VARIANCE_ATTACKS]
        clean_ids = list(dict.fromkeys(sel.U[:140] + sel.P[:40] + sel.Q[:20]))
        return list(_bundles(sel, segments, specs, clean_ids, sel.P[:40], chosen))
    if run == "phr1":
        nu, np_, _ = RUN_SIZES["phr1"]
        targets = sel.P[:np_]
        return list(_bundles(sel, segments, specs, list(dict.fromkeys(sel.U[:nu] + targets)), targets, specs))
    if run.startswith("var"):
        nu, np_, _ = RUN_SIZES["var"]
        chosen = [s for s in specs if s.id in VARIANCE_ATTACKS]
        targets = sel.P[:np_]
        return list(_bundles(sel, segments, specs, list(dict.fromkeys(sel.U[:nu] + targets)), targets, chosen))
    raise ValueError(run)


def run_groups(sel: Selection, run: str) -> tuple[set[int], set[int], set[int]]:
    """Applicants of the clean-utility, target and collateral groups of a run: prefixes of the shuffled pools."""
    sizes = {"main": RUN_SIZES["main"], "mainL": RUN_SIZES["mainL"], "phr1": RUN_SIZES["phr1"], "pilot": (140, 40, 20), "check": (16, 0, 0)}
    nu, np_, nq = RUN_SIZES["var"] if run.startswith("var") else sizes[run]
    return set(sel.U[:nu]), set(sel.P[:np_]), set(sel.Q[:nq])


def run_settings(run: str) -> tuple[int, float, int]:
    """phrasing, temperature, seed for a run tag."""
    if run in ("main", "mainL", "check", "pilot"):
        return 0, 0.0, 0
    if run == "phr1":
        return 1, 0.0, 0
    return 0, VARIANCE_TEMPERATURE, int(run[3:])


def build_jobs(sel: Selection, segments: Segments, run: str) -> list[Job]:
    phrasing, temperature, seed = run_settings(run)
    jobs = []
    for bundle in build_bundles(sel, segments, run):
        for task in TASKS:
            jobs.append(Job(job_key(task, phrasing, bundle), run, task, phrasing, temperature, seed,
                            messages_for(task, bundle, phrasing)))
    return jobs
