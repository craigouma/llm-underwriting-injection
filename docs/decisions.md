# Decisions log

Every choice the brief left open, and every departure from it, with the date and the reason. Numbers quoted here are read from files in this repository.

## 2026-11-12

**Run to completion without stopping at each phase.** Craig asked for this after the Phase 0 report. The brief's hard limits still apply: no paid resources and no public publishing without approval.

**Defaults taken for the open questions in `docs/novelty_check.md`.** Craig did not answer them individually, so the recommended option in each case is used. Craig can overrule any of them.
- Narrowed novelty framing: no use of "first" or "novel".
- Oracle-extractor reference arm added to B and C.
- Primary ASR is the raw definition from the brief. The paired flip rate and the clean approve rate are reported beside it.
- The attack set contains both single-document and consistent falsification, labelled separately.
- The MCP works are dropped from related work.
- Author name on the paper is "Craig Ouma", as in the brief. The earlier papers use "Craig Carlos Ouma". One line to change in `paper/main.tex` and `CITATION.cff`.

**All computation runs on Kaggle.** Craig expected nothing heavy to run on the local machine. Code is written locally as text and executed in Kaggle kernels through the API. No local Python environment exists. The Give Me Some Credit file (14 MB) was downloaded to the gitignored `data/raw/` before this decision and is not used by any local run.

**Inference stack.** The smoke kernel (2 x T4, transformers 5.20.2) measured Hugging Face batched generation at about 3.3 calls per second for a 1.5B model with 1,142-token prompts. vLLM 0.33.0 installed but ran at 2.6 calls per second on the same test and broke other preinstalled packages. The study uses Hugging Face generation.

## 2026-11-12, pipeline debugging before any attacked prompt was run

**Decider prompt now states the lender policy and the base rate.** The model check on 16 clean applicants showed Phi-4-mini and Olmo-3-7B approving none of them (stated risk of 25% to 92% where the scorecard PD is 2% to 4%) and Qwen2.5-1.5B approving 15 of 16 with risk scores of 0 to 20. A decider with no policy has no way to place its answer on the lender's scale, and a real deployment would give it one. Both prompt phrasings now carry the same thresholds the scorecard enforces (approve below 6.5%, decline from 13%) and the 7% average default rate. The change used only clean inputs. No attacked prompt had been run, so it cannot have been tuned to attack results. The extraction prompt is unchanged.

**Model check, 2026-11-12.** All three models load in fp16 on Kaggle T4s and return parseable JSON. Observed on 16 clean applicants: Qwen2.5-1.5B flagged 5 of 16 by the declared-versus-payslip income check, Olmo-3-7B left the bank deposits field null in 3 of 16, Phi-4-mini wrapped output in a code fence (accepted by the strict parser) and failed to parse once. These are extraction errors by small models and belong in the RQ3 results.
