# Where should the LLM sit in an automated credit underwriting pipeline?

This repository holds the code, synthetic data generator, cached model outputs and paper for a study of document-borne prompt injection against automated credit underwriting. Three architectures are compared on synthetic application bundles (payslip, bank statement, application form) built from rows of the Give Me Some Credit dataset:

- **A.** The LLM reads the bundle and decides (approve, refer, decline). **A-def** adds a prompt-level defense.
- **B.** The LLM only extracts fields into a JSON schema. A sign-constrained logistic scorecard decides.
- **C.** B plus range checks, cross-document checks and plausible-band checks. Any flag sends the case to a human.

The attack set has 26 variants in five categories (instruction override, hidden instruction, fake authority, delimiter and format, extraction manipulation). Three open-weight models are evaluated: Qwen2.5-1.5B-Instruct, Phi-4-mini-instruct and Olmo-3-7B-Instruct. The plan, hypotheses and decision rules are in `docs/preregistration.md` and were fixed before any model ran on study data. Every later change is dated in `docs/decisions.md`.

All documents, applicants and attack payloads are synthetic. No real applicant data, company documents or live systems are involved. See `docs/ethics.md`.

## Layout

| Path | Content |
|---|---|
| `src/data.py`, `src/scorecard.py`, `src/train_scorecard.py` | Cleaning, splits, scorecards and outcome thresholds |
| `src/documents.py`, `src/attacks.py`, `data/attacks/catalog.json` | Document generator and the frozen attack catalog |
| `src/pipelines/` | Architectures A, A-def, B and C, prompts, schema and checks |
| `src/jobs.py`, `kaggle/infer/infer.py` | Applicant selection, run definitions and the GPU inference script |
| `src/evaluate.py`, `src/analysis.py`, `src/figures.py`, `src/report.py` | Replay of cached outputs, statistics, figures and paper tables |
| `results/raw/` | Raw model outputs, one JSON line per call |
| `results/scorecard/` | Trained scorecards, thresholds and their metrics |
| `results/tables/` | Per-decision tables written by `src.evaluate` |
| `paper/` | LaTeX source, generated tables and numbers, figures, verified references |
| `notebooks/` | `pilot.ipynb` (end-to-end pilot) and `analysis.ipynb` (tables and figures from cached outputs) |
| `docs/` | Preregistration, decision log, environment notes, novelty check, ethics, error analysis |

## Reproducing the results

Model outputs are cached in `results/raw`, so every table and figure in the paper regenerates without a GPU.

1. Download Give Me Some Credit (`cs-training.csv`) from Kaggle (`brycecf/give-me-some-credit-dataset`) to `data/raw/`. The data is not redistributed here (see `LICENSE-DATA`).
2. `python -m src.train_scorecard` rebuilds the cleaned data, the splits, the scorecards and the thresholds.
3. `python -m src.evaluate --run main --models Qwen/Qwen2.5-1.5B-Instruct microsoft/Phi-4-mini-instruct --oracle` replays the cached outputs through every architecture and writes `results/tables/decisions_main_*.csv.gz`. Repeat for the other runs listed in `docs/preregistration.md`.
4. `notebooks/analysis.ipynb` (or `python -c "from src import analysis as an, figures, report; df = an.load_runs(['main','mainL']); figures.make_all(df); report.main(('main','mainL'))"`) writes `paper/figures/*.pdf` and `paper/generated/*`.
5. Compile `paper/main.tex` with a standard LaTeX toolchain (`pdflatex`, `bibtex`, `pdflatex` twice). The compiled paper is `paper/where_should_the_llm_sit.pdf`.
6. `python3 tools/make_landing.py` rebuilds the landing page `index.html` from `site/landing.json` and the numbers in `paper/generated/numbers.tex`, so the page shows the same figures as the paper. It uses the standard library only.

`pytest` runs the unit tests (documents, attacks, metrics, pipelines).

### Regenerating the model outputs

`notebooks/pilot.ipynb` reruns a small pilot (200 applicants, 8 attacks, one model) end to end. It needs a Kaggle GPU session (T4 x2) with internet on and the Give Me Some Credit dataset attached. The full grid is `kaggle/infer/infer.py` once per model and run:

```
python kaggle/infer/infer.py --model Qwen/Qwen2.5-1.5B-Instruct --run main
python kaggle/infer/infer.py --model allenai/Olmo-3-7B-Instruct --run mainL --split --batch-tokens 10000 --max-batch 24
```

Decoding is greedy except for the three variance runs (temperature 0.7, seeds 1 to 3). Run sizes and the reasons for them are in the preregistration addendum.

## Licences

Code is MIT (`LICENSE`). Generated data, outputs and the paper are CC BY 4.0 (`LICENSE-DATA`). The Give Me Some Credit data and the model weights keep their own licences and are not redistributed.

## Citation

See `CITATION.cff`.
