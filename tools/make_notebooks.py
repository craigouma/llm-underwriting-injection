"""Write notebooks/pilot.ipynb and notebooks/analysis.ipynb. Standard library only.

Both notebooks are executed on Kaggle (see README): the pilot needs a GPU session with internet and the
Give Me Some Credit dataset attached, and the analysis reads only cached tables.
"""
from __future__ import annotations

import json
from pathlib import Path


def cell(kind: str, text: str) -> dict:
    src = text.strip("\n").splitlines(keepends=True)
    base = {"cell_type": kind, "metadata": {}, "source": src}
    return {**base, "outputs": [], "execution_count": None} if kind == "code" else base


def notebook(cells: list[dict]) -> dict:
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                         "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


SETUP = '''
import os, subprocess, sys
from pathlib import Path

REPO_URL = "https://github.com/craigouma/llm-underwriting-injection"
REPO = Path(os.environ.get("UW_REPO_DIR", "/kaggle/working/repo"))
if not REPO.exists():
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO)], check=True)
os.chdir(REPO)
sys.path.insert(0, str(REPO))
RAW = next(Path("/kaggle/input").rglob("cs-training.csv"))
(REPO / "data/raw").mkdir(parents=True, exist_ok=True)
if not (REPO / "data/raw/cs-training.csv").exists():
    (REPO / "data/raw/cs-training.csv").symlink_to(RAW)
print("repo", REPO, "data", RAW)
'''

pilot = notebook([
    cell("markdown", """
# Pilot: where should the LLM sit in an automated underwriting pipeline?

This notebook reproduces the pilot end to end on Kaggle: it cleans the Give Me Some Credit data, trains the scorecard,
builds synthetic document bundles for 200 applicants and a subset of 8 attacks, runs one small open-weight model on
architectures A, A with a prompt defense, and the extractor used by B and C, and prints the main metrics.

Requirements: a GPU session (T4 x2) with internet on, and the dataset `brycecf/give-me-some-credit-dataset` attached.
Expected runtime: about 15 minutes. All data and payloads are synthetic.
"""),
    cell("code", SETUP),
    cell("markdown", "## 1. Clean the data, write the splits and train the scorecards"),
    cell("code", "!python -m src.train_scorecard | tail -n 12"),
    cell("markdown", "## 2. Run the model on the pilot applicants (raw outputs are cached to `results/raw/pilot`)"),
    cell("code", "!python kaggle/infer/infer.py --model Qwen/Qwen2.5-1.5B-Instruct --run pilot"),
    cell("markdown", "## 3. Replay the cached outputs through every architecture and summarise"),
    cell("code", "!python -m src.evaluate --run pilot --models Qwen/Qwen2.5-1.5B-Instruct --oracle"),
    cell("code", """
import pandas as pd
from src import analysis as an
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
df = an.with_oracle(an.load("pilot"))
display(an.clean_utility(df).round(3))
display(an.asr(df, ["category"])[["model", "arm", "category", "k", "n", "rate", "lo", "hi"]].round(3))
"""),
])

analysis = notebook([
    cell("markdown", """
# Analysis

Reads only the cached decision tables in `results/tables` (produced by `python -m src.evaluate` from the cached raw model
outputs) and produces every figure and table in the paper, plus the macros the paper includes.
"""),
    cell("code", SETUP.replace("RAW = next(Path(\"/kaggle/input\").rglob(\"cs-training.csv\"))\n", "").replace(
        '(REPO / "data/raw").mkdir(parents=True, exist_ok=True)\nif not (REPO / "data/raw/cs-training.csv").exists():\n    (REPO / "data/raw/cs-training.csv").symlink_to(RAW)\nprint("repo", REPO, "data", RAW)', 'print("repo", REPO)')),
    cell("code", """
import pandas as pd
from src import analysis as an, figures, report
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
RUNS = tuple(os.environ.get("UW_RUNS", "main,mainL").split(","))
df = an.load_runs(list(RUNS))
len(df)
"""),
    cell("markdown", "## Clean utility and extraction accuracy (RQ3)"),
    cell("code", "display(an.clean_utility(df).round(3)); display(an.extraction_accuracy(df).pivot(index='field', columns='model', values='accuracy').round(3))"),
    cell("markdown", "## Attack success rate by architecture and category (RQ1, RQ2)"),
    cell("code", "display(report.pooled_asr(df)[['model','arm','category','k','n','rate','lo','hi']].round(3))\ndisplay(an.clean_approve_rate(df).round(3))"),
    cell("markdown", "## Planned paired tests, Holm-adjusted per model"),
    cell("code", "display(an.family_tests(df).round(4))"),
    cell("markdown", "## Oracle attribution, review burden and plausibility trend (RQ2, RQ3, H2, H3)"),
    cell("code", "display(an.oracle_attribution(df).round(3)); display(an.review_burden(df).round(3)); display(an.caught_by_c(df).round(3)); display(an.plausibility_trend(df).round(3))"),
    cell("markdown", "## Preregistered decision rules (H1 to H3), paired flips, collateral damage and utility under attack"),
    cell("code", "display(an.hypotheses(df).round(4)); display(an.paired_flip(df, ['category']).round(3)); display(an.collateral(df).round(3)); display(an.utility_under_attack(df).round(4))"),
    cell("markdown", "## Figures and paper tables"),
    cell("code", """
from IPython.display import display
paths = figures.make_all(df)
report.main(RUNS)
print([str(p) for p in paths])
"""),
])

if __name__ == "__main__":
    out = Path("notebooks")
    out.mkdir(exist_ok=True)
    (out / "pilot.ipynb").write_text(json.dumps(pilot, indent=1) + "\n")
    (out / "analysis.ipynb").write_text(json.dumps(analysis, indent=1) + "\n")
    print("wrote", out / "pilot.ipynb", out / "analysis.ipynb")
