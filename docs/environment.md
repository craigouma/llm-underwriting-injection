# Environment report

Recorded 2026-11-12. Values marked "measured" came from commands run on this machine. Values marked "reported" or "estimate" did not.

## Local machine (measured)

| Item | Value |
|---|---|
| CPU | Intel Core i5-5287U, 2.9 GHz, 2 physical cores, 4 threads, x86_64 |
| RAM | 8 GB |
| Disk | 466 GB volume, 251 GB free |
| GPU | Intel Iris Graphics 6100, 1.5 GB shared memory, no CUDA |
| OS | macOS 14.8.9 (Darwin 23.6.0) |
| Python | 3.14.7 (system). `uv` is installed with managed Python 3.13. 3.12 is downloadable. |
| LaTeX | `tectonic` is installed. `pdflatex` and `latexmk` are not. |
| Kaggle CLI | 2.2.5, authenticated (`kaggle kernels list --mine` returned results) |

## What the machine can and cannot do

Cannot run the model grid. An 8B model at 4-bit needs roughly 5 GB for weights alone, which leaves little of the 8 GB for the operating system and the KV cache. CPU-only inference on two cores would be far too slow for the grid. A rough count is 1,000 applicants, about 30 attacked variants plus the clean input, and four to five pipeline variants, which gives on the order of 10^5 model calls per model (estimate, to be replaced by the Phase 4 count). I did not benchmark local inference, and I do not expect a benchmark to change the conclusion.

The machine could run light work (data cleaning, scorecard training, tests), but the study runs all computation on Kaggle by choice, see `docs/decisions.md`.

## Plan that follows

1. Every run executes on Kaggle through the API: scorecard training, document generation, tests, LLM inference and the analysis notebook. Nothing is installed locally and no notebook or model runs on this machine.
2. Code is written locally as text files. A private Kaggle dataset carries the code to each kernel, and kernels are pushed with `kaggle kernels push`.
3. Only small outputs are pulled back with `kaggle kernels output` into `results/`. They are the only input to the analysis.

## Kaggle compute

- `kaggle kernels push --accelerator NvidiaTeslaT4` selects a T4 x2 session (measured from the CLI help). The same help text says the P100 accelerator is retired and sessions requesting it run on a replacement.
- Weekly GPU quota: about 30 hours is the figure secondary sources report, with 12-hour sessions. I could not confirm either number from Kaggle's own documentation. Check the quota shown in the Kaggle account page before sizing the full grid in Phase 4.
- Model weights have to reach the kernel. Options are Hugging Face downloads with kernel internet enabled, or Kaggle Models and datasets attached to the kernel. Decide in Phase 3 when the model list is fixed.

## Dataset access

The Give Me Some Credit competition is visible to the CLI, and a community mirror exists on Kaggle Datasets. Licence and redistribution terms are checked in Phase 1 before any data file is committed. `data/raw/` is gitignored in the meantime.

## Python environment

Kaggle images provide Python 3.13, torch 2.11 and transformers 5.20 (measured by the smoke kernel). Additional pins are recorded in `requirements.txt` once the code settles.
