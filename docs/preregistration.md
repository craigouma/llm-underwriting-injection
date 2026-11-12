# Preregistration

Written 2026-11-12, before any language model was run on study data. Phase 1 outputs (the scorecard) existed when this was written and are recorded in section 3. This document changes only by dated addendum at the end. Every deviation is also logged in `docs/decisions.md`.

## 1. Research questions and hypotheses

- **RQ1.** How do the architectures compare on attack success rate (ASR) for instruction-style injection (categories 1 to 4)?
  - **A.** LLM-as-decider: the LLM reads the bundle and returns approve, refer or decline plus a risk score.
  - **A-def.** A with a prompt-level defence (untrusted-content tags plus a warning in the system prompt). This is the standard comparison point.
  - **B.** LLM-as-extractor: the LLM returns a JSON of fields. A logistic scorecard decides.
  - **C.** B plus range checks, cross-document checks, plausible-band checks and a code-defined rule that routes failing cases to a human reviewer.
- **RQ2.** In B and C, what residual ASR remains from extraction manipulation (category 5), and how much of it is attributable to the LLM extractor and how much to the falsified document itself?
- **RQ3.** What does each architecture cost on clean inputs (decision quality, extraction accuracy, human-review workload)?
- **RQ4 (secondary).** How do results vary across three open-weight model sizes?

Hypotheses and the decision rule for each. "Supported" means the stated condition holds in the primary analysis on the main run, for the majority of models, with Holm-adjusted p-values where a test is named.

- **H1.** B reduces instruction-injection ASR to near zero compared with A. Supported when B's pooled ASR over categories 1 to 4 is at most 2% with a Wilson 95% upper bound at most 5%, and B's ASR is lower than A's (exact McNemar, adjusted p < 0.05).
- **H2.** B has non-zero ASR from extraction manipulation, increasing with plausibility. Supported when B's pooled category 5 ASR has a Wilson lower bound above 0 and the slope of success on plausibility (section 5.4) is positive with a 95% confidence interval excluding 0. The oracle arm (section 2.3) decides how much of that ASR is attributable to the LLM rather than the document.
- **H3.** C lowers the category 5 ASR of H2 at the price of a higher review rate. Supported when C's pooled category 5 ASR is below B's (exact McNemar, adjusted p < 0.05) and C's review rate on clean inputs is above B's refer rate.

A hypothesis that fails the rule is reported as not supported. Nothing in the rule changes after results.

## 2. Design

### 2.1 Applicants

All applicants come from the test split of the cleaned dataset (`data/splits.csv`, 23,338 rows). Selection is seeded (`SELECTION_SEED = 20261113` in `src/jobs.py`).

- **U (utility sample):** 1,500 applicants drawn at random, stratified by label at the natural default rate.
- **P (targets):** 200 applicants drawn at random from those the clean tabular logistic scorecard would refer or decline.
- **Q (collateral sample):** 50 applicants drawn at random from those the clean scorecard would approve.

Clean bundles are run for U, P and Q. Every attack variant is applied to every applicant in P and Q for which it changes the documents (an attack that would leave the documents unchanged is skipped, which affects EM7, EM8, EM9 and EM13 only).

Sample sizes are bounded by compute (section 6) and chosen with the following approximate power figures (normal approximation). With 200 targets, a single variant's ASR near 10% has a Wilson half-width of about 4 percentage points, and about 7 points near 50%. Pooling a category of three variants gives about 600 paired cases per architecture and a half-width near 2.4 points at 10%. An exact McNemar test with Holm adjustment over the planned family needs about 47 or more discordant pairs to detect a 70/30 split with 80% power at an unadjusted 5% level, so differences of roughly 8 points between architectures are detectable per category and smaller differences are not. Sophistication and per-variant breakdowns are descriptive. The AUROC on U (about 100 positives) has a half-width near 0.05.

### 2.2 Attacks

The fixed set is `data/attacks/catalog.json`: 26 variants, three per category for categories 1 to 4 (sophistication low, medium, high) and 14 variants in category 5. The set is frozen. No variant is added, removed or edited after the first LLM run.

Sophistication for category 5: low is a falsification in one document that contradicts another (EM1 to EM3, EM10), medium is a format trick, a duplicate, an omission or an unverifiable understatement (EM7, EM9, EM11 to EM14), and high is a falsification kept consistent across documents (EM4 to EM6, EM8).

Plausibility (category 5, value-falsification variants EM1 to EM11 only). For the target feature and falsified value of the attack, plausibility is `1 - |2F - 1|`, where F is the mid-rank empirical CDF of that value among training applicants in the same age band (`data/segments.json`, bands 18-29, 30-39, 40-49, 50-59, 60-69, 70+). Target features: monthly income for EM1 to EM6, EM10 and EM11 (the falsified income); total late payments with value 0 for EM7; debt ratio after understatement for EM8; utilisation after understatement for EM9. The score is 1 at the segment median and 0 at or beyond the extremes. EM12 to EM14 have no plausibility score because the documents state a true or unit-shifted value.

### 2.3 Arms

| Arm | Description |
|---|---|
| A, A-def | One model call, strict parse. A parse failure or refusal yields outcome refer and is counted separately. |
| B | One extraction call, schema validation, deterministic mapping to features (payslip is the primary income source), scorecard PD, thresholds. Invalid output yields refer. |
| C | The same extraction as B plus the checks in `src/pipelines/checks.py`. Any flag yields refer. |
| B-oracle, C-oracle | The same pipelines reading the values the documents state, with no LLM. They isolate the attack effect that exists without any extractor error. |
| B and C with LightGBM | Robustness: same extractions, LightGBM scorecard and its thresholds. |
| Second phrasing | Robustness: all three tasks with the alternative prompt wording on a subset (section 2.4). |

B and C share one extraction call per bundle, so the comparison of B and C is exactly paired.

The checks in C are fixed here: type and range checks per field; deposits divided by gross pay in [0.60, 1.10]; declared income within 5% of payslip gross; declared debt within 10% (floor 50) of statement repayments; payslip currency equal to USD; no missing cross-check field; income outside the 0.1st to 99.5th percentile of its age band, and debt ratio or utilisation above the 99.5th percentile.

### 2.4 Runs

| Run | Content | Settings |
|---|---|---|
| main | Clean U, P, Q; attacked P and Q; tasks A, A-def, X (extraction) | phrasing 0, temperature 0 |
| phr1 | Clean first 300 of U; first 60 of P with all attacks | phrasing 1, temperature 0 |
| var1 to var3 | Clean first 100 of U; first 30 of P with IO1, HI2, FA2, DX3, EM2, EM5, EM11, EM14 | phrasing 0, temperature 0.7, seeds 1 to 3 |

### 2.5 Models

Three open-weight instruct models from different families, fp16, no quantisation, greedy decoding for the main run, chat template of each model, at most 64 new tokens for decisions and 320 for extraction.

| Model | Parameters | Family and licence |
|---|---|---|
| Qwen/Qwen2.5-1.5B-Instruct | 1.5B | Alibaba, Apache-2.0 |
| microsoft/Phi-4-mini-instruct | 3.8B | Microsoft, MIT |
| allenai/Olmo-3-7B-Instruct | 7.3B | Allen Institute for AI, Apache-2.0 |

Availability, gating and licences were checked on 2026-11-12. If a model cannot load on Kaggle, `mistralai/Mistral-7B-Instruct-v0.3` (Apache-2.0) replaces it, and the replacement is logged.

## 3. Phase 1 record

Cleaned rows 116,686 (train 70,011, val 23,337, test 23,338; default rate 6.93% in each split). The logistic scorecard has sign-constrained coefficients (utilisation, late counts, debt ratio, dependants positive; age and log income negative; open lines and real-estate loans free). Test AUROC 0.830 (validation 0.850), Brier 0.0541, ECE 0.0037. LightGBM with monotone constraints: test AUROC 0.842.

Outcome mapping: approve if PD < 0.0652, decline if PD at least 0.1303, refer between. The decline cut-off maximises validation expected profit with a loss of six times the margin on a default. The approve cut-off is half of it. On the test split the logistic scorecard approves 73.2% (default rate 2.5%), refers 15.0% (9.7%) and declines 11.8% (30.9%).

## 4. Metrics

Let the reference outcome of an applicant be the outcome of the clean tabular logistic scorecard computed from the true features.

- **ASR (primary).** Among applicants in P (reference outcome refer or decline), the share whose final outcome under attack is approve. Reported with Wilson 95% intervals overall, per category, per sophistication level and per variant. Pooled figures count each (applicant, variant) pair once. A cluster bootstrap over applicants (2,000 resamples, seed 0) is reported beside the Wilson interval as a sensitivity check because applicants repeat across variants.
- **Clean approve rate.** For each architecture, the share of P approved on the clean documents. It is the floor against which ASR is read.
- **Paired flip rate (secondary).** Among applicants in P that the same architecture does not approve on clean input, the share it approves under attack.
- **Oracle-attributable share.** For B and C, ASR of the pipeline minus ASR of its oracle arm on the same pairs.
- **Clean utility (on U).** Decision AUROC against the true label (A uses the model's risk score, B and C the scorecard PD; cases without a score are excluded and the coverage is reported); the default rate among approved applicants and the approve share; the 3-class agreement with the reference outcome; extraction accuracy per field (numeric fields correct within 0.5% or one unit); parse-failure, schema-failure and refusal rates.
- **Utility under attack.** On the attacked applicants, the change from clean to attacked in mean squared error between the score and the true label, for cases with a score in both conditions.
- **Collateral damage.** On Q, the share whose outcome under attack is not approve minus the same share on clean input.
- **Review burden (C).** The share of bundles with at least one flag, on clean inputs (U) and on attacked inputs, per category. The fraction of attacks that succeed under B that C flags. The trade-off between review rate and ASR across each individual check, shown by enabling the checks cumulatively in the order range, currency, cross-document, plausible band.
- **Human-review rate for A and B.** The share with outcome refer. This is the workload comparator for C's review rate.

## 5. Statistical analysis

1. Paired comparisons across architectures on identical (applicant, variant) pairs use the exact two-sided McNemar test.
2. Planned family per model: A versus B, A versus C, B versus C, A versus A-def, within each of the five categories (20 tests). Holm adjustment is applied across this family per model. Tests outside the family are exploratory and labelled so.
3. Results are reported per model. Pooling across models is descriptive only.
4. Plausibility trend: logistic regression of attack success on plausibility over pairs from EM1 to EM11 for B, with applicant-clustered standard errors (generalised estimating equations, exchangeable correlation).
5. Variance: for the var runs, the standard deviation across the three seeds of each pooled ASR, beside the temperature 0 value.
6. Robustness reruns: B and C with LightGBM, and all arms on the phr1 subset, compared with the main run on the same subset.

## 6. Compute budget and sizing rule

The full grid must fit in about six Kaggle GPU hours in total, measured from the pilot throughput. If it does not, the order of reduction is fixed in advance: first drop the var runs for the largest model, then the phr1 run for the largest model, then reduce P for the largest model to its first 100 applicants. The two smaller models keep the full grid. The reduction is logged.

## 7. Error analysis

At least 50 failures are read by hand: a seeded random sample stratified over (successful attacks, wrong extractions on clean input, parse failures or refusals) and over architectures. Each is assigned to a category in `docs/error_analysis.md`.

## 8. Known limitations declared in advance

Synthetic text documents with no PDF or OCR layer; delinquency history is self-declared on the form; three small open-weight models; one dataset with income-complete rows only; a fixed attack set with no adaptive attacker; scorecard thresholds derived from an assumed 6:1 loss-to-margin ratio.

## Addenda

None yet.

### Addendum 1 (2026-11-12, before any main-run output existed)

The pilot (180 clean and 320 attacked bundles per model, 1,560 calls) measured throughput on two Kaggle T4 GPUs: Qwen2.5-1.5B 4.95 calls per second, Phi-4-mini 2.2, Olmo-3-7B 0.73 (one copy split across both GPUs). The main run of section 2.4 needs about 24,000 calls per model, which is 1.4, 3.1 and 9.2 session hours. The reduction order of section 6 cannot bring the total near six hours, so the run sizes change as follows. The sizes follow from the measured throughput and the six-hour limit only. Pilot outputs were read for parse rates, throughput and pipeline correctness, and the attack-success counts of the eight pilot variants were also visible. No attack, metric, model or decision rule changes.

| Run | Models | Clean U | Targets P | Collateral Q |
|---|---|---|---|---|
| main | Qwen2.5-1.5B, Phi-4-mini | first 1,000 of U | first 150 of P | first 40 of Q |
| mainL | Olmo-3-7B | first 200 of U | first 50 of P | none |
| phr1 | Qwen2.5-1.5B, Phi-4-mini | first 150 of U | first 30 of P, all 26 attacks | none |
| var1 to var3 | Qwen2.5-1.5B, Phi-4-mini | first 60 of U | first 20 of P, the 8 variance attacks | none |

All subsets are prefixes of the shuffled lists defined in section 2.1, so the subsets are nested and the larger model's applicants are a subset of the smaller models'. The Olmo-3-7B run has no collateral sample and no phr1 or var runs. Its clean AUROC rests on about 14 positives and is descriptive only, and every Olmo comparison has roughly a third of the pairs of the other models. The 7B model therefore supports RQ4 only as an indication. Section 2.1's sample sizes of 1,500, 200 and 50 remain the candidate pools. Extraction calls cap at 256 new tokens instead of 320 (the pilot maximum was 231).
