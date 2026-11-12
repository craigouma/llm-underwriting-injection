"""Replay cached raw model outputs through every architecture arm and write tidy decision tables.

Run: python -m src.evaluate --run main --models Qwen/Qwen2.5-1.5B-Instruct ...
Nothing here calls a model: the raw outputs in results/raw are the only model-dependent input.
"""
from __future__ import annotations

import argparse
import glob
from pathlib import Path

import pandas as pd

from src.eval.metrics import field_correct
from src.jobs import Selection, build_bundles, select
from src.pipelines import scorers
from src.pipelines.base import REFER, Backend, Decision, ReplayBackend
from src.pipelines.decider import DeciderPipeline
from src.pipelines.extractor import ExtractorPipeline, to_features
from src.pipelines.schema import FIELDS
from src.segments import Segments

TABLES = Path("results/tables")
RAW = Path("results/raw")
LLM_ARMS = ("A", "A_def", "B", "C", "B_lgbm", "C_lgbm")
ORACLE_ARMS = ("B_oracle", "C_oracle", "B_oracle_lgbm", "C_oracle_lgbm")


def slug(model: str) -> str:
    return model.replace("/", "__")


def build_arms(backend: Backend | None, segments: Segments, phrasing: int) -> dict:
    lr_fn, lr_th = scorers.logistic()
    lg_fn, lg_th = scorers.lightgbm()
    if backend is not None:
        return {
            "A": DeciderPipeline(backend, False, phrasing), "A_def": DeciderPipeline(backend, True, phrasing),
            "B": ExtractorPipeline(lr_fn, lr_th, backend, False, phrasing=phrasing),
            "C": ExtractorPipeline(lr_fn, lr_th, backend, True, segments, phrasing),
            "B_lgbm": ExtractorPipeline(lg_fn, lg_th, backend, False, phrasing=phrasing),
            "C_lgbm": ExtractorPipeline(lg_fn, lg_th, backend, True, segments, phrasing),
        }
    return {
        "B_oracle": ExtractorPipeline(lr_fn, lr_th, None, False, oracle=True),
        "C_oracle": ExtractorPipeline(lr_fn, lr_th, None, True, segments, oracle=True),
        "B_oracle_lgbm": ExtractorPipeline(lg_fn, lg_th, None, False, oracle=True),
        "C_oracle_lgbm": ExtractorPipeline(lg_fn, lg_th, None, True, segments, oracle=True),
    }


def decision_row(d: Decision) -> dict:
    flags = d.flags
    failure = {"parse_failure", "refusal", "schema_invalid", "incomplete_extraction"}
    return {"outcome": d.outcome, "score": d.score, "flags": "|".join(flags),
            "parse_failure": "parse_failure" in flags, "refusal": "refusal" in flags,
            "schema_invalid": "schema_invalid" in flags, "incomplete": "incomplete_extraction" in flags,
            "n_check_flags": len([f for f in flags if f not in failure]), "review": bool(flags) and not (set(flags) & failure)}


def extraction_extras(d: Decision, bundle) -> dict:
    out: dict = {}
    if d.extracted_fields is None:
        return out
    truth = bundle.stated.as_dict()
    for k in FIELDS:
        out[f"fc_{k}"] = field_correct(d.extracted_fields.get(k), truth[k])
    feats, _ = to_features(d.extracted_fields)
    if feats is not None:
        out["x_income"] = feats["monthly_income"]
        out["x_debt_ratio"] = feats["debt_ratio"]
        out["x_utilization"] = feats["utilization"]
    return out


def table_for(run: str, model: str | None, sel: Selection, segments: Segments, allow_missing: bool) -> pd.DataFrame:
    bundles = build_bundles(sel, segments, run)
    phrasing = 1 if run == "phr1" else 0
    backend = None
    if model is not None:
        paths = [Path(p) for p in sorted(glob.glob(str(RAW / run / f"{slug(model)}.shard*.jsonl")))]
        backend = ReplayBackend.from_jsonl(paths, model, run)
    arms = build_arms(backend, segments, phrasing)
    U, P, Q = set(sel.U), set(sel.P), set(sel.Q)
    rows = []
    for bundle in bundles:
        row_id = int(bundle.applicant_id[2:])
        ref = sel.reference.loc[row_id]
        attack = bundle.extras.get("attack", {})
        base = {"model": model or "oracle", "run": run, "applicant_id": bundle.applicant_id, "row_id": row_id,
                "attack_id": bundle.attack_id or "clean", "category": attack.get("category", "clean"),
                "sophistication": attack.get("sophistication"), "plausibility": attack.get("plausibility"),
                "in_U": row_id in U, "in_P": row_id in P, "in_Q": row_id in Q, "label": int(ref["label"]),
                "pd_ref": float(ref["pd_ref"]), "outcome_ref": ref["outcome_ref"]}
        for name, pipeline in arms.items():
            try:
                decision = pipeline.run(bundle)
            except KeyError:
                if allow_missing:
                    continue
                raise
            rows.append({**base, "arm": name, **decision_row(decision), **extraction_extras(decision, bundle)})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--models", nargs="*", default=[])
    ap.add_argument("--oracle", action="store_true", help="also write the model-free oracle arms")
    ap.add_argument("--allow-missing", action="store_true")
    a = ap.parse_args()
    TABLES.mkdir(parents=True, exist_ok=True)
    sel, segments = select(), Segments.from_json()
    targets = [(m, m) for m in a.models] + ([("oracle", None)] if a.oracle else [])
    for name, model in targets:
        df = table_for(a.run, model, sel, segments, a.allow_missing)
        path = TABLES / f"decisions_{a.run}_{slug(name)}.csv.gz"
        df.to_csv(path, index=False)
        print(path, len(df), "rows", flush=True)


if __name__ == "__main__":
    main()
