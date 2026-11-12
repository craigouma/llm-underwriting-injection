# Data

## Source

Give Me Some Credit, Kaggle competition `GiveMeSomeCredit` (2011), file `cs-training.csv`: 150,000 borrowers, 10 features, label `SeriousDlqin2yrs`.

The raw file is not in this repository. The Kaggle community mirror `brycecf/give-me-some-credit-dataset` carries licence "unknown" and the original is competition data under Kaggle's competition rules, so redistribution is not assumed to be allowed. To get it:

```
kaggle datasets download brycecf/give-me-some-credit-dataset -p data/raw --unzip
```

Kernels in this study attach the same Kaggle dataset directly.

## Cleaning (src/data.py)

Minimal and driven by data quality, never by model results. Rules are applied in this order and the counts below come from `results/scorecard/metrics.json`.

| Rule | Rows removed |
|---|---|
| Missing monthly income or number of dependents | 29,731 |
| Sentinel delinquency codes 96 or 98 | 148 |
| Age below 18 | 1 |
| Monthly income below 500 or above 50,000 | 2,981 |
| Revolving utilisation above 2 | 274 |
| Debt ratio above 5 | 179 |

Result: 116,686 of 150,000 rows (77.8%). Complete cases are used because every document states an income. Rows with a missing income are the main population this excludes. Rows with implausible debt ratios nearly all have income below 500, which is why the debt cap removes few rows after the income rule.

## Splits

`data/splits.csv` assigns each cleaned row to train, val or test (60/20/20) with a fixed seed, stratified by label. Base rate is 6.93% in each split.

## Derived files

- `data/segments.json`: 201 quantiles of income, debt ratio, utilisation and total late counts per age band, from the training split. Used for the plausibility score and the plausible-band review rule.
- `data/attacks/catalog.json`: the fixed attack set (26 variants).
- `data/generated/`: document bundles, regenerated on demand and gitignored.
