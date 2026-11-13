"""Draw the failures that are read by hand for the error analysis (preregistration section 7).

Run: python -m src.error_sample --runs main mainL
Writes results/error_sample.md: a seeded random sample stratified over failure type and model, each with the
document lines the attack changed (or the wrongly extracted fields), the raw model output and the decision.
"""
from __future__ import annotations

import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd

from src import analysis as an
from src.evaluate import RAW, slug
from src.jobs import build_bundles, select
from src.pipelines.base import ReplayBackend, job_key
from src.segments import Segments

TASK = {"A": "A", "A_def": "A_def", "B": "X", "C": "X"}
PER_CELL = 4
STRATA = {
    "successful attack, decider (A or A + defense)": lambda d: d["arm"].isin(["A", "A_def"]) & d["in_P"] & (d["attack_id"] != "clean") & d["success"],
    "successful attack, B": lambda d: (d["arm"] == "B") & d["in_P"] & (d["attack_id"] != "clean") & d["success"],
    "successful attack, C": lambda d: (d["arm"] == "C") & d["in_P"] & (d["attack_id"] != "clean") & d["success"],
    "wrong extraction on a clean bundle (B)": lambda d: (d["arm"] == "B") & d["in_U"] & (d["attack_id"] == "clean") & ~d["parse_failure"] & d.filter(like="fc_").eq(False).any(axis=1),
    "format failure (parse, schema or refusal)": lambda d: d["arm"].isin(["A", "B"]) & (d["parse_failure"] | d["schema_invalid"] | d["refusal"]),
    "C flag on a clean bundle": lambda d: (d["arm"] == "C") & d["in_U"] & (d["attack_id"] == "clean") & d["review"],
}


def changed_lines(clean_text: str, attacked_text: str) -> str:
    before, after = set(clean_text.split("\n")), attacked_text.split("\n")
    new = [line for line in after if line not in before]
    return "\n".join(new) if new else "(no changed line)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", default=["main", "mainL"])
    a = ap.parse_args()
    df = an.load_runs(a.runs)
    df = df[df["model"] != "oracle"]
    sel, segments = select(), Segments.from_json()
    rng = np.random.default_rng(0)
    out = ["# Error analysis sample\n", f"Seeded sample, up to {PER_CELL} cases per failure type and model. Runs: {', '.join(a.runs)}.\n"]
    n = 0
    for run in a.runs:
        bundles = {(b.applicant_id, b.attack_id or "clean"): b for b in build_bundles(sel, segments, run)}
        for model in sorted(df[df["run"] == run]["model"].unique()):
            paths = [Path(p) for p in sorted(glob.glob(str(RAW / run / f"{slug(model)}.shard*.jsonl")))]
            backend = ReplayBackend.from_jsonl(paths, model, run)
            sub = df[(df["run"] == run) & (df["model"] == model)]
            for name, mask in STRATA.items():
                cases = sub[mask(sub)]
                if cases.empty:
                    continue
                pick = cases.iloc[rng.permutation(len(cases))[:PER_CELL]]
                for _, r in pick.iterrows():
                    n += 1
                    b = bundles[(r["applicant_id"], r["attack_id"])]
                    clean = bundles[(r["applicant_id"], "clean")]
                    raw = backend.complete(job_key(TASK[r["arm"]], 0, b))
                    diff = changed_lines(clean.text(), b.text()) if r["attack_id"] != "clean" else "(clean bundle)"
                    truth = b.stated.as_dict()
                    wrong = [f"{c[3:]} (stated {truth[c[3:]]})" for c in r.index if c.startswith("fc_") and pd.notna(r[c]) and not r[c]]
                    out.append(f"\n## Case {n}: {name}\n- model {model}, arm {r['arm']}, applicant {r['applicant_id']}, attack {r['attack_id']}, "
                               f"reference outcome {r['outcome_ref']}, outcome {r['outcome']}, flags `{r['flags'] if isinstance(r['flags'], str) else ''}`\n"
                               + (f"- wrongly extracted fields: {', '.join(wrong)}\n" if wrong else "")
                               + f"\nChanged or relevant document lines:\n```\n{diff}\n```\nRaw model output:\n```\n{raw[:700]}\n```\n")
    Path("results/error_sample.md").write_text("\n".join(out))
    print("wrote", n, "cases")


if __name__ == "__main__":
    main()
